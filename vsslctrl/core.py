#!/usr/bin/env python
# -*- coding: utf-8 -*-

import asyncio
from typing import Dict, Union, List

from . import VSSL_VERSION
from .zone import Zone
from .exceptions import VsslCtrlException, ZoneError, ZeroConfNotInstalled
from .event_bus import EventBus
from .settings import VsslSettings
from .decorators import logging_helpers
from .discovery import check_zeroconf_availability, fetch_zone_id_serial
from .device import Models
from .data_structure import ZoneIDs


@logging_helpers("VSSL:")
class Vssl:
    ENTITY_ID = 0

    #
    # VSSL Events
    #
    class Events:
        PREFIX = "vssl."
        INITIALISED = PREFIX + "initialised"
        MODEL_CHANGE = PREFIX + "model_changed"
        SW_VERSION_CHANGE = PREFIX + "sw_version_changed"
        SERIAL_CHANGE = PREFIX + "serial_changed"

    def __init__(self, model: Models):
        self.event_bus = EventBus()
        self.initialisation = asyncio.Event()
        self.zones = {}
        self._sw_version = None
        self._serial = None
        self._model = None
        self.model = model
        self.settings = VsslSettings(self)

    @property
    def initialised(self):
        """Initialised Event"""
        return self.initialisation.is_set()

    #
    # Initialize the zones
    #
    async def initialise(self, init_timeout: int = 10):
        if len(self.zones) < 1:
            raise VsslCtrlException("Add minimum one zone before initializing")

        zones_to_init = self.zones.copy()

        try:
            key, first_zone = zones_to_init.popitem()

            future_serial = self.event_bus.future(Zone.Events.SERIAL_RECEIVED)
            future_sw_version = self.event_bus.future(self.Events.SW_VERSION_CHANGE)
            future_name = self.event_bus.future(VsslSettings.Events.NAME_CHANGE)

            await first_zone.initialise()

            # Wait until we have some basic infomation
            await self.event_bus.wait_future(future_serial, init_timeout)
            await self.event_bus.wait_future(future_sw_version, init_timeout)
            await self.event_bus.wait_future(future_name, init_timeout)

            # Check we haven't added too many zones
            if len(self.zones) > self.model.zone_count:
                message = f"Device model {self.model.name} only has {self.model.zone_count} zones not {len(self.zones)}."
                self._log_critical(message)
                await first_zone.disconnect()
                raise VsslCtrlException(message)

            # Output a bit of helpful info
            self._log_info(f"vsslctrl Version: {VSSL_VERSION}")
            self._log_info(f"Device Serial: {self.serial}")
            self._log_info(f"Device SW Version: {self.sw_version}")
            self._log_info(f"Device Model: {self.model.name}")

            # Initialise remaining zones
            initialisations = [zone.initialise() for zone in zones_to_init.values()]
            await asyncio.gather(*initialisations)

        except ZoneError as e:
            message = f"Zone initializing error: {e}"
            self._log_critical(message)
            await self.disconnect()
            raise

        except asyncio.TimeoutError:
            message = f"Timeout during VSSL initialization. Are any zones available?"
            self._log_critical(message)
            await first_zone.disconnect()
            raise VsslCtrlException(message)

        # Initialised
        self.initialisation.set()
        self.event_bus.publish(self.Events.INITIALISED, self.ENTITY_ID, self)
        self._log_info(f"Core initialization complete")

        return self

    #
    # Shutdown
    #
    async def shutdown(self):
        await self.disconnect()
        self.event_bus.stop()

    #
    # Discover host on the network using zero_conf package
    #
    @staticmethod
    async def discover(*args):
        check_zeroconf_availability()

        from .discovery import VsslDiscovery

        service = VsslDiscovery(*args)
        return await service.discover()

    #
    # Update a property and fire an event
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
    # Model of the device
    #
    @property
    def model(self):
        return self._model

    @model.setter
    def model(self, model):
        if Models.is_valid(model):
            self._set_property("model", Models(model).value)
        elif isinstance(model, str):
            model = model.upper()
            if hasattr(Models, model):
                self._set_property("model", getattr(Models, model).value)
        else:
            message = f"VSSL model {model} doesnt exist"
            self._log_error(message)
            raise VsslCtrlException(message)

    #
    # Disconnect / Shutdown
    #
    async def disconnect(self):
        for zone in self.zones.values():
            await zone.disconnect()

    #
    # Add a Zone
    #
    def add_zone(self, host: str, zone_index: ZoneIDs = ZoneIDs.A1):
        # Check if VSSL is already initialised
        if self.initialised:
            error = f"Zones can not be added after VSSL is initialised. Error trying to add Zone {zone_index}"
            self._log_error(error)
            raise ZoneError(error)

        # Check the ZoneID is valid for the model
        if zone_index not in self.model.zones:
            error = f"ZoneIDs {zone_index} is not supported on device model {self.model.name}. Did you select the correct model?"
            self._log_error(error)
            raise ZoneError(error)

        # Double check ZoneID is valid
        if ZoneIDs.is_not_valid(zone_index):
            error = f"ZoneIDs {zone_index} doesnt exist"
            self._log_error(error)
            raise ZoneError(error)

        # Check ZoneID is unique
        if zone_index in self.zones:
            error = f"Zone {zone_index} already exists on this instance"
            self._log_error(error)
            raise ZoneError(error)

        # Check IPs are unique
        if any(zone.host == host for zone in self.zones.values()):
            error = f"Zone with IP {host} already exists"
            self._log_error(error)
            raise ZoneError(error)

        self.zones[zone_index] = Zone(self, zone_index, host)

        return self.zones[zone_index]

    #
    # Add a Zones using a list.
    #
    async def add_zones(self, zones=Union[str, List[str]]):
        zones_list = [zones] if isinstance(zones, str) else zones

        # A.1(x)
        if not self.model.is_multizone:
            return self.add_zone(zones_list[0], ZoneIDs.A1)
        else:
            # Fetch the ZoneID from the device
            for host in zones_list:
                zone_id, serial = await fetch_zone_id_serial(host)
                self.add_zone(host, ZoneIDs(int(zone_id)))

        return self.zones

    #
    # Get a Zone by ID
    #
    def get_zone(self, zone_index: ZoneIDs):
        if zone_index in self.zones:
            return self.zones[zone_index]
        else:
            return None

    #
    # Get a zone that is connected
    #
    def get_connected_zone(self):
        if self.zones:
            for zone_id in self.zones:
                zone = self.zones[zone_id]
                if zone.connected:
                    return zone
        self._log_error("There are no connected zones.")

    #
    # Has a connected zone
    #
    @property
    def connected(self):
        return True if self.get_connected_zone() else False

    #
    # Get the device name
    #
    def _request_name(self):
        zone = self.get_connected_zone()
        if zone:
            zone.api_alpha.request_action_19()

    #
    # Reboot Device (All Zones)
    #
    def reboot(self):
        zone = self.get_connected_zone()
        if zone:
            zone.api_alpha.request_action_33_device()

    #
    # Factory Reset Device
    #
    def factory_reset(self):
        zone = self.get_connected_zone()
        if zone:
            zone.api_alpha.request_action_2B()

    #
    # Get a Zone by group index
    #
    def get_zones_by_group_index(self, group_index: int):
        zones = {}
        if self.zones:
            for zone_id in self.zones:
                zone = self.zones[zone_id]
                if zone.group.index == group_index:
                    zones[zone_id] = zone
        return zones

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
