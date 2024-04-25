#!/usr/bin/env python
# -*- coding: utf-8 -*-

import time
import logging
import asyncio
from typing import Dict, Union, List

from .zone import Zone
from .exceptions import VsslException, ZoneError
from .utils import add_logging_helpers
from .event_bus import EventBus
from .settings import VsslPowerSettings


class Vssl:

    #
    # VSSL Events
    #
    class Events():
        PREFIX                      = 'vssl.'
        NAME_CHANGE                 = PREFIX + 'name_changed'
        MODEL_ZONE_QTY_CHANGE       = PREFIX + 'model_zone_qty_changed'
        SW_VERSION_CHANGE           = PREFIX + 'sw_version_changed'
        SERIAL_CHANGE               = PREFIX + 'serial_changed'
        OPTICAL_INPUT_NAME_CHANGE   = PREFIX + 'optical_input_name_changed'


    def __init__(self, zones: Union[str, List[str]] = None):

        add_logging_helpers(self, 'VSSL:')

        self.event_bus = None
        self._zones = {}

        self._name = None  # device name
        self._sw_version = None  # e.g p15305.016.3701
        self._serial = None  # We use this to check the zones belong to the same hardware
        self._model_zone_qty = 0
        self._optical_input_name = 'Optical In'
        self.power = VsslPowerSettings(self)

        # Add zones if any are passed
        if zones:
            self.add_zones(zones)

    #
    # Run the program
    #

    async def run(self, init_timeout: int = 0):
        self.event_bus = EventBus()  # Needs an event loop

        if len(self._zones) < 1:
            raise VsslException(f'Add atleast one zone before calling run()')

        future_model_zone_qty = self.event_bus.future(
            Vssl.Events.MODEL_ZONE_QTY_CHANGE, 0
        )

        # Initialize the first zone, then we can wait for some infomation
        # about the device itself. i.e the amount of zones its has
        first_zone = next(iter(self._zones.values()), None)
        if first_zone:
            first_zone_task = asyncio.create_task(first_zone.initialise())

        #
        # Check that the device can support the amount of zones requested
        #
        try:
            if init_timeout > 0:
                model_zone_qty = await asyncio.wait_for(future_model_zone_qty, timeout=init_timeout)
            else:
                model_zone_qty = await future_model_zone_qty

            if len(self._zones) > model_zone_qty:
                message = f'Device only has {model_zone_qty} zones, but requested tried to add {len(self._zones)}'
                self._log_critical(message)
                await first_zone.disconnect()
                first_zone_task.cancel()
                raise VsslException(message)

        except asyncio.TimeoutError:
            message = f'Timed out waiting for model infomation from zone {first_zone.id}, exiting!'
            self._log_critical(message)
            await first_zone.disconnect()
            first_zone_task.cancel()
            raise VsslException(message)

        # Init the rest of the zones
        for zone in list(self._zones.values())[1:]:
            asyncio.create_task(zone.initialise())

    #
    # Update a property and fire the event
    #

    def _set_property(self, property_name: str, new_value):
        current_value = getattr(self, property_name)
        if current_value != new_value:
            setattr(self, f'_{property_name}', new_value)
            self.event_bus.publish(
                getattr(Vssl.Events, property_name.upper() +
                        '_CHANGE'), 0, getattr(self, property_name)
            )
            self._log_debug(
                f'Set {property_name}: {getattr(self, property_name)}')

    #
    # Zones
    #
    @property
    def zones(self):
        return self._zones

    #
    # Name
    #
    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, name: str):
        zone = self.get_connected_zone()
        if zone and name:
            zone._api_alpha.request_action_18(name)

    #
    # Software Version
    #
    @property
    def sw_version(self):
        return self._sw_version

    @sw_version.setter
    def sw_version(self, sw: str):
        pass  # read-only

    #
    # Serial Number
    #
    @property
    def serial(self):
        return self._serial

    @serial.setter
    def serial(self, serial: str):
        pass  # read-only

    #
    # The amount of zones this VSSL has. This is not how many zones have been initialised
    # but how many zones the model has in total. We can have 1, 3 or 6 zones.
    #
    @property
    def model_zone_qty(self):
        return self._model_zone_qty

    @model_zone_qty.setter
    def model_zone_qty(self, model_zone_qty: str):
        pass  # read-only

    #
    # Work out the model_zone_qty given device info
    #
    def _infer_model_zone_qty(self, data: Dict[str, int]):
        if not self.model_zone_qty:
            self._model_zone_qty = sum(
                1 for key in data if key.startswith('B') and key.endswith('Src'))
            self.event_bus.publish(
                Vssl.Events.MODEL_ZONE_QTY_CHANGE, 0, self.model_zone_qty)

    #
    # Optical Input Name
    #
    @property
    def optical_input_name(self):
        return self._optical_input_name

    @optical_input_name.setter
    def optical_input_name(self, name: str):
        zone = self.get_connected_zone()
        if zone:
            zone._api_alpha.request_action_15_12(name)

    #
    # Disconnect / Shutdown
    #
    async def disconnect(self):
        for zone in self._zones.values():
            await zone.disconnect()

    #
    # Add a Zones using a List, index emplys the zone ID
    #
    def add_zones(self, zones = Union[str, List[str]]):
        zones_list = [zones] if isinstance(zones, str) else zones

        for index, ip in enumerate(zones_list):
            self.add_zone(index+1, ip)

    #
    # Add a Zone
    #
    def add_zone(self, zone_index: 'Zone.IDs', host: str):

        if Zone.IDs.is_not_valid(zone_index):
            error = f'Zone.IDs {zone_index} doesnt exist'
            self._log_error(error)
            raise ZoneError(error)
            return None

        if zone_index in self._zones:
            error = f'Zone {zone_index} already exists'
            self._log_error(error)
            raise ZoneError(error)
            return None

        # Check if any object in the dictionary has the specified value for the
        # property
        if any(zone.host == host for zone in self._zones.values()):
            error = f'Zone with IP {host} already exists'
            self._log_error(error)
            raise ZoneError(error)
            return None

        zone = Zone(self, zone_index, host)

        self._zones[zone_index] = zone

        return zone

    #
    # Get a Zone by ID
    #
    def get_zone(self, zone_index: 'Zone.IDs'):
        if zone_index in self._zones:
            return self._zones[zone_index]
        else:
            return None

    #
    # Get a Zone by group index
    #
    def get_zones_by_group_index(self, group_index: int):
        zones = {}
        if self._zones:
            for zone_id in self._zones:
                zone = self._zones[zone_id]
                if zone.group.index == group_index:
                    zones[zone_id] = zone
        return zones

    #
    # Get a Zone that is connected to its APIs
    #
    def get_connected_zone(self):
        if self._zones:
            for zone_id in self._zones:
                zone = self._zones[zone_id]
                if zone.connected:
                    return zone

    #
    # Get the status of all zones
    #
    def get_zones_state(self):
        states = {}
        for zone in self._zones.values():
            states[zone.id] = zone.state_settings
        return states

    #
    # Get the device name
    #
    def _request_name(self):
        zone = self.get_connected_zone()
        if zone:
            zone._api_alpha.request_action_19()

    #
    # Reboot Device (All Zones)
    #
    def reboot(self):
        zone = self.get_connected_zone()
        if zone:
            zone._api_alpha.request_action_33_device()

    # Return the current state
    @property
    def state(self):
        return {
            'name': self.name,
            'sw_version': self.sw_version,
            'serial': self.serial,
            'model_zone_qty': self.model_zone_qty,
            'optical_input_name': self.optical_input_name,
            'power': self.power.as_dict(),
            'zones': self.get_zones_state()
        }
