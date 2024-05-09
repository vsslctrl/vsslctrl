#!/usr/bin/env python
# -*- coding: utf-8 -*-

import asyncio
from typing import Dict, Union, List

from .zone import Zone
from .exceptions import VsslCtrlException, ZoneError, ZeroConfNotInstalled
from .event_bus import EventBus
from .settings import VsslSettings
from .decorators import logging_helpers
from .discovery import check_zeroconf_availability, fetch_zone_id_serial


@logging_helpers("VSSL:")
class Vssl:
    ENTITY_ID = 0

    #
    # VSSL Events
    #
    class Events:
        PREFIX = "vssl."
        MODEL_ZONE_QTY_CHANGE = PREFIX + "model_zone_qty_changed"
        SW_VERSION_CHANGE = PREFIX + "sw_version_changed"
        SERIAL_CHANGE = PREFIX + "serial_changed"
        ALL = EventBus.WILDCARD

    def __init__(self, zones: Union[str, List[str]] = None):
        self.event_bus = EventBus()
        self._zones = {}
        self._sw_version = None  # e.g p15305.016.3701
        self._serial = (
            None  # We use this to check the zones belong to the same hardware
        )
        self._model_zone_qty = 0
        self.settings = VsslSettings(self)

        # Add zones if any are passed
        if zones:
            self.add_zones(zones)

    #
    # Initialise the zones
    #
    # We init all the zones sequentially, so we can do some error checking
    # and failed the init of all the zones if any of them fail.
    #
    async def initialise(self, init_timeout: int = 10):
        if len(self._zones) < 1:
            raise VsslCtrlException("No zones were added to VSSL before calling run()")

        zones_to_init = self._zones.copy()

        try:
            key, first_zone = zones_to_init.popitem()

            # We will get the devices supported zone count in the future
            future_model_zone_qty = self.event_bus.future(
                self.Events.MODEL_ZONE_QTY_CHANGE, self.ENTITY_ID
            )

            # Lets make sure the zone is initialised, otherwsie we fail all
            await first_zone.initialise()

            # Only continue after we now how many zones the device supports
            try:
                model_zone_qty = await asyncio.wait_for(
                    future_model_zone_qty, timeout=init_timeout
                )

                if len(self._zones) > model_zone_qty:
                    raise VsslCtrlException("")

            except asyncio.TimeoutError:
                message = f"Timed out waiting for model infomation from zone {first_zone.id}, exiting!"
                self._log_critical(message)
                await first_zone.disconnect()
                raise VsslCtrlException(message)

            except VsslCtrlException:
                message = f"Device only has {model_zone_qty} zones instead of the {len(self._zones)} given"
                self._log_critical(message)
                await first_zone.disconnect()
                raise VsslCtrlException(message)

            # Now we can init the rest of the zones
            initialisations = [zone.initialise() for zone in zones_to_init.values()]
            await asyncio.gather(*initialisations)

        except ZoneError as e:
            message = f"Error occured while initialising zones {e}"
            self._log_critical(e)
            await self.disconnect()
            raise

        return True

    #
    # Shutdown
    #
    async def shutdown(self):
        await self.disconnect()
        self.event_bus.stop()

    #
    # Discover host on the network using zero_conf package
    #
    async def discover(self, *args):
        try:
            check_zeroconf_availability()

            from .discovery import VsslDiscovery

            service = VsslDiscovery(*args)
            return await service.discover()
        except ZeroConfNotInstalled as e:
            self._log_error(e)
            raise

    #
    # Update a property and fire the event
    #

    #
    # TODO, use the ZoneDataClass here too? Needs some reconfig
    #

    def _set_property(self, property_name: str, new_value):
        current_value = getattr(self, property_name)
        if current_value != new_value:
            setattr(self, f"_{property_name}", new_value)
            self.event_bus.publish(
                getattr(self.Events, property_name.upper() + "_CHANGE"),
                self.ENTITY_ID,
                getattr(self, property_name),
            )
            self._log_debug(f"Set {property_name}: {getattr(self, property_name)}")

    #
    # Zones
    #
    @property
    def zones(self):
        return self._zones

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
                1 for key in data if key.startswith("B") and key.endswith("Src")
            )
            self.event_bus.publish(
                self.Events.MODEL_ZONE_QTY_CHANGE, self.ENTITY_ID, self.model_zone_qty
            )

    #
    # Disconnect / Shutdown
    #
    async def disconnect(self):
        for zone in self._zones.values():
            await zone.disconnect()

    #
    # Add a Zones using a List, index emplys the zone ID
    #
    def add_zones(self, zones=Union[str, List[str]]):
        zones_list = [zones] if isinstance(zones, str) else zones

        for index, ip in enumerate(zones_list):
            self.add_zone(index + 1, ip)

    #
    # Add a Zone
    #
    def add_zone(self, zone_index: "Zone.IDs", host: str):
        if Zone.IDs.is_not_valid(zone_index):
            error = f"Zone.IDs {zone_index} doesnt exist"
            self._log_error(error)
            raise ZoneError(error)
            return None

        if zone_index in self._zones:
            error = f"Zone {zone_index} already exists"
            self._log_error(error)
            raise ZoneError(error)
            return None

        # Check if any object in the dictionary has the specified value for the
        # property
        if any(zone.host == host for zone in self._zones.values()):
            error = f"Zone with IP {host} already exists"
            self._log_error(error)
            raise ZoneError(error)
            return None

        self._zones[zone_index] = Zone(self, zone_index, host)

        return self._zones[zone_index]

    #
    # Get a Zone by ID
    #
    def get_zone(self, zone_index: "Zone.IDs"):
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

    #
    # Zones Groups. Build a dict of zone according to group membership
    #
    @property
    def zone_groups(self):
        MASTER = "master"
        MEMBERS = "members"

        groups = []
        for zone in self.zones.values():
            if zone.group.is_master:
                groups.append({MASTER: zone, MEMBERS: zone.group.members})

        return groups
