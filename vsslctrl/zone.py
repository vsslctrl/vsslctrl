#!/usr/bin/env python
# -*- coding: utf-8 -*-
# v0.3
# Tested on A.3x on p15305.016.3701

import re
import json
import logging
import asyncio
from typing import Union

from . import core
from .api_alpha import APIAlpha
from .api_bravo import APIBravo
from .utils import RepeatTimer, clamp_volume
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
        ALL = "*"
        PREFIX = "zone."
        INITIALISED = PREFIX + "initialised"
        ID_RECEIVED = PREFIX + "id_received"
        SERIAL_RECEIVED = PREFIX + "serial_received"
        MAC_ADDR_CHANGE = PREFIX + "mac_addr_change"
        VOLUME_CHANGE = PREFIX + "volume_change"
        MUTE_CHANGE = PREFIX + "mute_change"

    def __init__(self, vssl_host: "core.Vssl", zone_id: ZoneIDs, host: str):
        self._log_prefix = f"Zone {zone_id}:"

        self.vssl = vssl_host
        self.initialisation = asyncio.Event()

        # Data / Cache
        self._host = host
        self._id = ZoneIDs(zone_id)
        self._mac_addr = None
        self._serial = None
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
                self._request_track,
                self._request_name,
                self._request_status_extended,
            ],
        )

    # Initialise
    async def initialise(self):
        # ID and serial number futures
        future_id = self.vssl.event_bus.future(self.Events.ID_RECEIVED, self.id)
        future_serial = self.vssl.event_bus.future(self.Events.SERIAL_RECEIVED, self.id)
        future_name = self.vssl.event_bus.future(
            ZoneSettings.Events.NAME_CHANGE, self.id
        )

        # Subscribe to events
        self.vssl.event_bus.subscribe(
            ZoneTransport.Events.STATE_CHANGE,
            self._event_transport_state_change,
            self.id,
        )
        self.vssl.event_bus.subscribe(
            ZoneGroup.Events.SOURCE_CHANGE, self._event_group_source_change, self.id
        )

        # Connect the APIs
        # Wait until the zone is connected then continue
        await self.api_alpha.connect()
        await self.api_bravo.connect()

        # Start polling zone
        self._poller.start()

        # Wait for the ID, serial and name to be returned from the device
        received_id = await future_id
        received_serial = await future_serial
        await future_name

        # Confirm the zone id is matches returned ID
        if received_id != self.id:
            message = f"Zone ID mismatch. {self.host} returned zone ID {received_id} instead of {self.id}"
            self._log_critical(message)
            await self.disconnect()
            raise ZoneError(message)

        # Confirm the zone and VSSL serial numbers match
        if self.vssl.serial != received_serial:
            message = f"Zone ({received_serial}) and VSSL ({self.vssl.serial}) serial numbers do not match. Does this zone belong to this VSSL?"
            self._log_critical(message)
            await self.disconnect()
            raise ZoneError(message)

        # Initialised
        self.initialisation.set()
        self.vssl.event_bus.publish(self.Events.INITIALISED, self.id, self)

        self._log_info(f"Zone {self.id} initialised")

        return self

    @property
    def initialised(self):
        """Initialised Event"""
        return self.initialisation.is_set()

    @property
    def connected(self):
        """Check that the zone is connected to both APIs"""
        return self.api_alpha.connected and self.api_bravo.connected

    async def disconnect(self):
        """Disconnect / Shutdown"""
        self._poller.cancel()

        await self.api_alpha.disconnect()
        await self.api_bravo.disconnect()

    def _event_publish(self, event_type, data=None):
        """Event Publish Wrapper"""
        self.vssl.event_bus.publish(event_type, self.id, data)

    async def _event_transport_state_change(self, *args):
        """Request track info on transport state change unless stopped


        VSSL doenst clear some vars on stopping of the stream, so we will do it

        Doing this will fire the change events on the bus. Instead of conditionally
        using the getter functions since we want the changes to be propogated

        VSSL has a happit of caching the last songs metadata

        """
        if not self.transport.is_stopped:
            self._request_track()
        else:
            self.track.set_defaults()
            self.transport.set_defaults()

    async def _event_group_source_change(self, source: int, *args):
        """Propgate the track metadata from a group master to its members"""
        if source == None:
            self._log_debug(f"unsubscribe to group master {source} track updates")
            self.vssl.event_bus.unsubscribe(
                TrackMetadata.Events.CHANGE,
                self.track._update_property_from_group_master,
            )
        else:
            self._log_debug(f"subscribe to group master {source} track updates")
            self.vssl.event_bus.subscribe(
                TrackMetadata.Events.CHANGE,
                self.track._update_property_from_group_master,
                source,
            )

            # Populate group member from master
            self.track._pull_from_zone(source)

    def _set_property(self, property_name: str, new_value):
        """TODO, use the ZoneDataClass here too? Needs some reconfig"""
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
        pass  # Immutable

    #
    # Zone ID
    #
    @property
    def id(self):
        return self._id

    @id.setter
    def id(self, zone_id: int):
        if not self.initialised:
            # We wait for this in the initialise function
            self._event_publish(self.Events.ID_RECEIVED, zone_id)

    #
    # Serial Number
    #
    @property
    def serial(self):
        return self._serial

    @serial.setter
    def serial(self, serial: str):
        pass  # Immutable

    def _set_serial(self, serial: str):
        if not self.initialised:
            self._serial = serial
            # We wait for this in the initialise function
            self._event_publish(self.Events.SERIAL_RECEIVED, serial)

    @property
    def mac_addr(self):
        """MAC Address

        Note: This command wont work if there is another VSSL agent running on the network

        Known issue: zone 1 sometimes stops repsonding to the _request_mac_addr request.
        rebooting all zones seems to fix it.
        """
        return self._mac_addr

    @mac_addr.setter
    def mac_addr(self, mac: str):
        pass  # Immutable

    def _set_mac_addr(self, mac: str):
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
    @property
    def mute(self):
        return True if not self._volume else self._mute

    @mute.setter
    def mute(self, muted: Union[bool, int]):
        self.api_alpha.request_action_11(not not muted)

    def mute_toggle(self):
        self.mute = False if self.mute else True

    #
    # Play a URL
    #
    def play_url(self, url: str, all_zones: bool = False):
        self.api_alpha.request_action_55(url, all_zones)
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
    def __init__(self, zone, requests=[], interval=30):
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
