#!/usr/bin/env python
# -*- coding: utf-8 -*-
#v0.3
# Tested on A.3x on p15305.016.3701

import re
import json
import logging
import asyncio
from typing import Union

from . import core

from .api_alpha import APIAlpha
from .api_bravo import APIBravo

from .utils import VsslIntEnum, add_logging_helpers, RepeatTimer, clamp_volume

from .track import TrackMetadata
from .io import AnalogOutput, InputRouter
from .settings import ZoneSettings
from .transport import ZoneTransport
from .group import ZoneGroup

from .exceptions import ZoneError, ZoneInitialisationError


class Zone:

    #
    # Zones IDs
    #
    class IDs(VsslIntEnum):
        ZONE_1 = 1,
        ZONE_2 = 2,
        ZONE_3 = 3,
        ZONE_4 = 4,
        ZONE_5 = 5,
        ZONE_6 = 6

    #
    # Zone Events
    #
    class Events():
        PREFIX              = 'zone.'
        INITIALISED         = PREFIX+'initialised'
        ID_RECEIVED         = PREFIX+'id_received'
        SERIAL_RECEIVED     = PREFIX+'serial_received'
        MAC_ADDR_CHANGE     = PREFIX+'mac_addr_change'
        VOLUME_CHANGE       = PREFIX+'volume_change'
        MUTE_CHANGE         = PREFIX+'mute_change'


    def __init__(self, vssl_host: 'core.Vssl', zone_id: 'Zone.IDs', host: str):

        add_logging_helpers(self, f'Zone {zone_id}:')

        self.vssl = vssl_host
        self.initialisation = asyncio.Event()
        
        # Data / Cache
        self._host = host
        self._id = Zone.IDs(zone_id)
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
        self._api_alpha = APIAlpha(self.vssl, self)
        self._api_bravo = APIBravo(self.vssl, self)

        # Requests to poll
        self._poller = ZonePoller(self, [
            self._request_status, # First
            self._request_mac_addr,
            self._request_status_bus,
            self._request_output_status,
            self._request_eq_status,
            self._request_track,
            self._request_name,
            #self._request_bt_status
        ])
        

    # Initialise
    async def initialise(self):

        # ID and serial number futures
        future_id = self.vssl.event_bus.future(Zone.Events.ID_RECEIVED, self.id)
        future_serial = self.vssl.event_bus.future(Zone.Events.SERIAL_RECEIVED, self.id)

        # Subscribe to events
        self.vssl.event_bus.subscribe(ZoneTransport.Events.STATE_CHANGE, self._event_transport_state_change, self.id)
        self.vssl.event_bus.subscribe(ZoneTransport.Events.STATE_CHANGE_STOP, self._event_transport_state_stop, self.id)
        self.vssl.event_bus.subscribe(ZoneGroup.Events.SOURCE_CHANGE, self._event_group_source_change, self.id)

        # Connect the APIs
        self._api_alpha.connect()
        self._api_bravo.connect()

        # Wait until the zone is connected then continue
        await self._api_alpha.connection_event.wait()
        await self._api_bravo.connection_event.wait()

        # Start polling zone
        self._poller.start()

        # Wait for the zone ID and serial to be returned from the device
        received_id = await future_id
        received_serial = await future_serial

        # Confirm the zone id is correct
        if received_id != self.id:
            message = f"Zone ID mismatch. {self.host} returned zone ID {received_id} instead of {self.id}"
            self._log_critical(message)
            await self.disconnect()
            raise ZoneInitialisationError(message)

        # Confirm the zone and VSSL serial numbers match
        if self.vssl.serial != received_serial:
            message = f"Zone ({received_serial}) and VSSL ({self.vssl.serial}) serial numbers do not match. Does this zone belong to this VSSL?"
            self._log_critical(message)
            await self.disconnect()
            raise ZoneInitialisationError(message)

        # Initialised
        self.initialisation.set()
        self.vssl.event_bus.publish(Zone.Events.INITIALISED, self.id, self)

        return self

    # 
    # Initialised Event
    #
    @property
    def initialised(self):
        return self.initialisation.is_set()

    #
    # Is the zone connected to both APIs?
    #
    @property
    def connected(self):
        return self._api_alpha.connected and self._api_bravo.connected

    #
    # Disconnect / Shutdown
    #
    async def disconnect(self):
        self._poller.cancel()

        await self._api_alpha.disconnect()
        await self._api_bravo.disconnect()

    # 
    # Wait until the zone is connected helper
    #
    async def await_initialisation(self, timeout: int = 0):
        try:
            if timeout > 0:
                return await asyncio.wait_for(self.initialisation.wait(), timeout)
            else:
                return await self.initialisation.wait()
        except asyncio.TimeoutError:
            message = f"Zone {self.id} initialisation timeout"
            self._log_error(message)
            raise ZoneError(message)

    # 
    # Event Publish Wrapper
    #
    def _event_publish(self, event_type, data=None):
        self.vssl.event_bus.publish(event_type, self.id, data)

    #
    # VSSL doenst clear some vars on stopping of the stream, so we will do it
    #
    # Doing this will fire the change events on the bus. Instead of conditionally
    # using the getter functions since we want the changes to be propogated
    #
    # VSSL has a happit of caching the last songs metadata
    #
    async def _event_transport_state_stop(self, *args, **kwargs):
        self.track.set_defaults()
        self.transport.set_defaults()

    #
    # Request track info on transport state change unless stopped
    #
    async def _event_transport_state_change(self, *args, **kwargs):
        if not self.transport.is_stopped:
            self._request_track()

    #
    # Propgate the track metadata from a group master to its members
    #
    async def _event_group_source_change(self, source: int, *args, **kwargs):
        if source == None:
            self._log_debug(f'unsubscribe to group master {source} track updates')
            self.vssl.event_bus.unsubscribe(
                TrackMetadata.Events.CHANGE, 
                self.track._update_property_from_group_master
            )
        else:
            self._log_debug(f'subscribe to group master {source} track updates')
            self.vssl.event_bus.subscribe(
                TrackMetadata.Events.CHANGE, 
                self.track._update_property_from_group_master, 
                source
            )

            # Populate group member from master
            self.track._pull_from_zone(source)


    def _set_property(self, property_name: str, new_value):
        
        log = False
        direct_setter = f'_set_{property_name}'

        if hasattr(self, direct_setter):
            log = getattr(self, direct_setter)(new_value)
        else:
            current_value = getattr(self, property_name)
            if current_value != new_value:
                setattr(self, f'_{property_name}', new_value)
                log = True
                
        if log:
            self._log_debug(f'Set {property_name}: {getattr(self, property_name)}')
            self._event_publish(
                getattr(Zone.Events, property_name.upper() + '_CHANGE'), 
                getattr(self, property_name)
            )
            
    #
    # Host
    #
    @property
    def host(self):
        return self._host

    @host.setter
    def host(self, host: str):
        pass #Immutable

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
            self._event_publish(Zone.Events.ID_RECEIVED, zone_id)

    #
    # Serial Number
    #
    @property
    def serial(self):
        return self._serial

    @serial.setter
    def serial(self, serial: str):
        pass #Immutable

    def _set_serial(self, serial: str):
        if not self.initialised:
            self._serial = serial
            # We wait for this in the initialise function
            self._event_publish(Zone.Events.SERIAL_RECEIVED, serial)

    #
    # MAC Address
    #
    # Note: This command wont work if there is a VSSL agent running on the network
    #
    # Known issue: zone 1 sometimes stops repsonding to the _request_mac_addr request.
    # rebooting all zones seems to fix it.
    #
    @property
    def mac_addr(self):
        return self._mac_addr

    @mac_addr.setter
    def mac_addr(self, mac: str):
        pass #Immutable

    def _set_mac_addr(self, mac: str):
        mac = mac.strip()
        if mac != self.mac_addr:
            # Define the regular expression pattern for a MAC address
            mac_pattern = re.compile(r'^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$')

            if mac_pattern.match(mac):
                self._mac_addr = mac
                self._poller.remove(self._request_mac_addr)
                return True
            else:
                self._log_error(f'Invalid MAC address {mac}')

    #
    # Transport Helper Commands
    #
    def play(self):
        self.transport.play()

    def stop(self):
        self.transport.stop()

    def pause(self):
        self.transport.pause()

    def next(self):
        self._api_bravo.request_action_40_next()

    def prev(self):
        self._api_bravo.request_action_40_prev()

    def back(self):
        self.track_prev()
        self.track_prev()
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
        self._api_alpha.request_action_05(vol)

    def _set_volume(self, vol: int):
        vol = clamp_volume(vol)
        if self.volume != vol:
            self._volume = vol
            return True

    #
    # Volume Commands
    #
    def volume_raise(self, step: int = 1):
        if step > 1:
            self.volume = self.volume + step
        else:
            self._api_alpha.request_action_05_raise()

    def volume_lower(self, step: int = 1):
        if step > 1:
            self.volume = self.volume - step
        else:
            self._api_alpha.request_action_05_lower()

    #
    # Mute
    #
    @property
    def mute(self):
        return True if not self._volume else self._mute

    @mute.setter
    def mute(self, muted: Union[bool, int]):
        self._api_alpha.request_action_11(not not muted)

    def mute_toggle(self):
        self.mute = False if self.mute else True

    #
    # Play a URL
    #
    def announce(self, url: str, all_zones: bool = False):
        self._api_alpha.request_action_55(url, all_zones)
        return self

    #
    # Reboot this zone
    #
    def reboot(self):
        self._api_alpha.request_action_33()
        return self

    #
    # Requests 
    #
    def _request_name(self):
        self._api_bravo.request_action_5A()
        return self

    def _request_mac_addr(self):
        self._api_bravo.request_action_5B()
        return self

    def _request_status_bus(self):
        self._api_alpha.request_action_00_00()
        return self

    def _request_status(self):
        self._api_alpha.request_action_00_08()
        return self

    def _request_eq_status(self):
        self._api_alpha.request_action_00_09()
        return self

    def _request_output_status(self):
        self._api_alpha.request_action_00_0A()
        return self

    def _request_bt_status(self):
        self._api_alpha.request_action_00_0B()
        return self

    def _request_track(self):
        self._api_bravo.request_action_2A()
        return self

    # Return the current state
    @property
    def state(self):
        return {
            'id': self.id,
            'initialised': self.initialised,
            'connected': self.connected,
            'transport': self.transport.as_dict(),
            'volume': self.volume,
            'mute': self.mute,
            'group': self.group.as_dict(),
            'track': self.track.as_dict(),
            'input': self.input.as_dict(),
            'analog_output': self.analog_output.as_dict(),
        }

    # Return the current settings
    @property
    def settingsP(self):
        return {
            'id': self.id,
            'name': self.settings.name,
            'host': self.host,
            'mac_addr': self.mac_addr,
            'disabled': self.settings.disabled,
            'mono': self.settings.mono,
            'eq': self.settings.eq.as_dict(),
            'volume': self.settings.volume.as_dict(),
            'analog_input': self.settings.analog_input.as_dict()
            
        }

    # Return the current settings
    @property
    def state_settings(self):
        json = self.state
        json['settings'] = self.settingsP
        return json



class ZonePoller:

    def __init__(self, zone, requests = [], interval = 30):
        self._zone = zone
        self._requests = requests
        self._interval = interval
        self._timer = RepeatTimer(self._interval, self._poll_state)

    def _poll_state(self):
        if self._zone.connected:
            self._zone._log_debug('Polling state')
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
