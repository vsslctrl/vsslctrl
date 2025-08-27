#!/usr/bin/env python
# -*- coding: utf-8 -*-
# v0.3
# Tested on A.3x on p15305.016.3701

import re
import json
import logging
import asyncio
import ipaddress
from typing import Union

from . import core
from .api_alpha import APIAlpha
from .api_bravo import APIBravo
from .event_bus import event_bus
from .utils import is_ipv4, RepeatTimer, clamp_volume
from .data_structure import VsslIntEnum, ZoneIDs
from .track import TrackMetadata
from .io import AnalogOutput, InputRouter
from .settings import ZoneSettings
from .transport import ZoneTransport
from .group import ZoneGroup
from .exceptions import ZoneError
from .decorators import logging_helpers


@logging_helpers()
class Zone:
    #
    # Zone Events
    #
    class Events:
        PREFIX = "zone."
        INITIALISED = PREFIX + "initialised"
        ID_RECEIVED = PREFIX + "id_received"
        MODEL_ID_RECEIVED = PREFIX + "model_id_received"
        MODEL_NAME_RECEIVED = PREFIX + "model_name_received"
        SERIAL_RECEIVED = PREFIX + "serial_received"
        MAC_ADDR_CHANGE = PREFIX + "mac_addr_change"
        VOLUME_CHANGE = PREFIX + "volume_change"
        MUTE_CHANGE = PREFIX + "mute_change"

    def __init__(self, vsslctrl_core: "core.Vssl", host: str):
        self.event_bus = event_bus()

        self.vssl = vsslctrl_core
        self.initialisation = asyncio.Event()

        # check and set the host
        self._host = None
        self.host = host

        # ID
        self._id = None

        self._mac_addr = None
        self._serial = None
        self._model_id = None
        self._volume = 0
        self._mute = False

        self.transport = ZoneTransport(self)
        self.track = TrackMetadata(self)
        self.group = ZoneGroup(self)
        self.analog_output = AnalogOutput(self)
        self.input = InputRouter(self)
        self.settings = ZoneSettings(self)

        # Communication interfaces
        self.api_alpha = APIAlpha(self.vssl, self)
        self.api_bravo = APIBravo(self.vssl, self)

        # Requests to poll
        self._poller = ZonePoller(
            self,
            [
                self._request_status,  # First
                self._request_mac_addr,
                self._request_status_bus,
                self._request_output_status,
                self._request_eq_status,
                self._request_status_extended,
            ],
        )

    ##########################################################
    #
    # Logging Prefix
    #
    ##########################################################
    @property
    def _log_prefix(self):
        zone = self.zone.id if self.zone.id != None else self.host
        return f"Zone {zone}:"

    ##########################################################
    #
    # Initialise
    #
    ##########################################################
    async def initialise(self, timeout: int = 20):
        # Data we require from the device
        future_id = self.event_bus.future(self.Events.ID_RECEIVED, self.host)
        future_serial = self.event_bus.future(self.Events.SERIAL_RECEIVED, self.host)
        future_name = self.event_bus.future(ZoneSettings.Events.NAME_CHANGE, self.host)

        # Connect the APIs
        await self.api_alpha.connect()
        await self.api_bravo.connect()

        # Start polling zone
        self._poller.start()

        try:
            # wait and set the ID
            self.id = await self.event_bus.wait_future(future_id, timeout)
            # wait and set the serial
            self.serial = await self.event_bus.wait_future(future_serial, timeout)
            # wait for the zone name
            self._request_name()
            await self.event_bus.wait_future(future_name, timeout)

        except asyncio.TimeoutError:
            message = f"host {self.host} connection timeout."
            self._log_critical(message)
            await self.shutdown()
            raise ZoneError(message)

        # Subscribe to events
        self.event_bus.subscribe(
            ZoneTransport.Events.STATE_CHANGE,
            self._event_transport_state_change,
            self.host,
        )

        # Initialised
        self.initialisation.set()
        self._event_publish(self.Events.INITIALISED, self)
        self._log_info(f"Zone {self.id} initialised")

        # Request the track info
        self._request_track()

        return self

    @property
    def initialised(self):
        """Initialised Event"""
        return self.initialisation.is_set()

    @property
    def connected(self):
        """Check that the zone is connected to both APIs"""
        return self.api_alpha.connected and self.api_bravo.connected

    async def shutdown(self):
        self._poller.cancel()

        await self.api_alpha.shutdown()
        await self.api_bravo.shutdown()

    def _event_publish(self, event_type, data=None):
        """Event Publish Wrapper"""
        self.event_bus.publish(event_type, self.host, data)

    """Request track info on transport state change unless stopped


    VSSL doens't clear some variables on stopping of the stream, so we will do it.

    Doing this will fire the change events on the bus. Instead of conditionally
    using the getter functions since we want the changes to be propogated

    VSSL has a habit of caching the last songs metadata

    """

    async def _event_transport_state_change(self, *args):
        if not self.transport.is_stopped:
            self._request_track()
        else:
            self.track.set_defaults()
            self.transport.set_defaults()

    #
    # """TODO, use the ZoneDataClass here too? Needs some reconfig"""
    #
    def _set_property(self, property_name: str, new_value):
        log = False
        direct_setter = f"_set_{property_name}"

        if hasattr(self, direct_setter):
            log = getattr(self, direct_setter)(new_value)
        else:
            current_value = getattr(self, property_name)
            if current_value != new_value:
                setattr(self, f"_{property_name}", new_value)
                log = True

        if log:
            self._log_debug(f"Set {property_name}: {getattr(self, property_name)}")
            self._event_publish(
                getattr(self.Events, property_name.upper() + "_CHANGE"),
                getattr(self, property_name),
            )

    #
    # Host
    #
    @property
    def host(self):
        return self._host

    @host.setter
    def host(self, host: str):
        host = host.strip()
        if not is_ipv4(host):
            raise ZoneError(f"{host} is not a valid IPv4 address")
        self._host = host

    #
    # Zone ID
    #
    @property
    def id(self):
        return self._id

    @id.setter
    def id(self, zone_id: int):
        if not self.initialised:
            if ZoneIDs.is_not_valid(zone_id):
                raise ZoneError(f"ZoneID {zone_id} does not exist")

            self._id = zone_id

    #
    # Serial Number
    #
    @property
    def serial(self):
        return self._serial

    @serial.setter
    def serial(self, serial: str):
        if not self.initialised:
            if self.vssl.serial and self.vssl.serial != serial:
                raise ZoneError(
                    f"vssl serial {self.vssl.serial} and zone serial {serial} do not match"
                )

            self._serial = serial

    #
    # MAC Address
    #
    @property
    def mac_addr(self):
        return self._mac_addr

    @mac_addr.setter
    def mac_addr(self, mac: str):
        if not self.initialised:
            mac = mac.strip()
            if mac != self.mac_addr:
                # Strip Wlan0: from beginging of string
                # Original A series amps had this prefix
                if mac.startswith("Wlan0:"):
                    mac = mac[len("Wlan0:") :]

                # Define the regular expression pattern for a MAC address
                mac_pattern = re.compile(r"^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$")

                if mac_pattern.match(mac):
                    self._mac_addr = mac
                    self._poller.remove(self._request_mac_addr)
                    return True
                else:
                    self._log_error(f"Invalid MAC address {mac}")

    #
    # Transport Helper Commands
    #
    def play(self):
        """Play"""
        self.transport.play()

    def stop(self):
        """Stop"""
        self.transport.stop()

    def pause(self):
        """Pause"""
        self.transport.pause()

    def next(self):
        """Next Track"""
        self.transport.next()

    def prev(self):
        """Previous track"""
        self.transport.prev()

    def back(self):
        """Back"""
        self.transport.back()

    #
    # Volume
    #
    @property
    def volume(self):
        """
        return 0 if self._mute else self._volume

        Dont do this, as when the zone is unmuted, the volume is returned first
        (before the mute status) so the events fire with a volume of zero.
        This will need to be handled on the front end, to display, 0 when muted

        Note; Some input sources i.e Spotify, will set the volume to 0 when muted, others dont
        """
        return self._volume

    @volume.setter
    def volume(self, vol: int):
        self.api_alpha.request_action_05(vol)

    def _set_volume(self, vol: int):
        vol = clamp_volume(vol)
        if self.volume != vol:
            self._volume = vol
            return True

    def volume_raise(self, step: int = 1):
        """Volume Up"""
        step = max(min(step, 100), 1)
        if step > 1:
            self.volume = self.volume + step
        else:
            self.api_alpha.request_action_05_raise()

    def volume_lower(self, step: int = 1):
        """Volume Down"""
        step = max(min(step, 100), 1)
        if step > 1:
            self.volume = self.volume - step
        else:
            self.api_alpha.request_action_05_lower()

    #
    # Mute
    #
    # Note: Mute will still return true if volume is at 0
    # so always use _mute when comparing
    #
    @property
    def mute(self):
        return True if not self._volume else self._mute

    @mute.setter
    def mute(self, muted: Union[bool, int]):
        self.api_alpha.request_action_11(not not muted)

    def mute_toggle(self):
        self.mute = False if self._mute else True

    # Use self._mute since we are chcking volume in mute property
    def _set_mute(self, state: bool):
        if self._mute != state:
            self._mute = state
            return True

    #
    # Play a URL
    #
    def play_url(self, url: str, all_zones: bool = False, volume: int = None):
        self.api_alpha.request_action_55(url, all_zones, volume)
        return self

    #
    # Reboot this zone
    #
    def reboot(self):
        self.api_alpha.request_action_33()
        return self

    #
    # Requests
    #
    def _request_name(self):
        self.api_bravo.request_action_5A()
        return self

    def _request_mac_addr(self):
        self.api_bravo.request_action_5B()
        return self

    def _request_status_bus(self):
        self.api_alpha.request_action_00_00()
        return self

    def _request_status(self):
        self.api_alpha.request_action_00_08()
        return self

    def _request_eq_status(self):
        self.api_alpha.request_action_00_09()
        return self

    def _request_output_status(self):
        self.api_alpha.request_action_00_0A()
        return self

    def _request_status_extended(self):
        self.api_alpha.request_action_00_0B()
        return self

    def _request_track(self):
        self.api_bravo.request_action_2A()
        return self


class ZonePoller:
    def __init__(self, zone, requests=[], interval=60):
        self.zone = zone
        self._requests = requests
        self._interval = interval
        self._timer = RepeatTimer(self._interval, self._poll_state)

    def _poll_state(self):
        if self.zone.connected:
            self.zone._log_debug("Polling state")
            for request in self._requests:
                request()

    def start(self):
        self._timer.start()

    def cancel(self):
        self._timer.cancel()

    def remove(self, request):
        if request in self._requests:
            self._requests.remove(request)

    def append(self, request):
        if request not in self._requests:
            self._requests.append(request)

    def contains(self, request):
        return request in self._requests
