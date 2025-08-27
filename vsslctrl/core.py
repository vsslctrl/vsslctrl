#!/usr/bin/env python
# -*- coding: utf-8 -*-

import asyncio
from typing import Dict, Union, List

from . import VSSL_VERSION, LOG_DIVIDER
from .zone import Zone
from .exceptions import VsslCtrlException, ZoneError, ZeroConfNotInstalled
from .event_bus import event_bus
from .settings import VsslSettings
from .decorators import logging_helpers
from .discovery import check_zeroconf_availability
from .device import Models
from .utils import is_ipv4
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

    def __init__(self, model: Models = None):
        self.event_bus = event_bus()
        self.initialisation = asyncio.Event()

        self.zones = {}

        self._sw_version = None
        self._serial = None
        self._model = None

        if model:
            self.model = model

        self.settings = VsslSettings(self)

        self._log_info(f"vsslctrl version: {VSSL_VERSION}")

    @property
    def initialised(self):
        """Initialised Event"""
        return self.initialisation.is_set()

    #
    # Initialise the zones
    #
    async def initialise(self, timeout: int = 20):
        if len(self.zones) < 1:
            raise VsslCtrlException("one or more zones is required before initializing")

        # Get a list of zone keys which need to be initialised
        zone_hosts_to_init = list(self.zones.keys())
        first_zone = self.zones[zone_hosts_to_init.pop(0)]

        try:
            # wildcard* listening futures
            future_serial = self.event_bus.future(Zone.Events.SERIAL_RECEIVED)
            future_sw_version = self.event_bus.future(self.Events.SW_VERSION_CHANGE)
            future_name = self.event_bus.future(VsslSettings.Events.NAME_CHANGE)
            future_model_id = self.event_bus.future(Zone.Events.MODEL_ID_RECEIVED)

            # Init the fist zone to get some device info
            await first_zone.initialise(timeout)

            # Wait until we have some basic infomation
            self._serial = await self.event_bus.wait_future(future_serial, timeout)
            await self.event_bus.wait_future(future_sw_version, timeout)
            await self.event_bus.wait_future(future_name, timeout)

            # wait for the device model
            model_id = await self.event_bus.wait_future(future_model_id, timeout)
            # setting model will have error checking
            self.model = Models.find(model_id)

            # Request the device model for logging purpose
            self._request_model_name()

            # wait for initialise of remaining zones
            initialisations = []
            for host in zone_hosts_to_init:
                initialisations.append(self._initialise_secondry_zone(self.zones[host]))
            await asyncio.gather(*initialisations)

        except ZoneError as e:
            message = f"zone initializing error: {e}"
            self._log_critical(message)
            await self.shutdown()
            raise

        except asyncio.TimeoutError:
            message = f"timeout during vsslctrl core initialization. Is {first_zone.host} online?"
            self._log_critical(message)
            await first_zone.shutdown()
            raise VsslCtrlException(message)

        # Initialised
        self.initialisation.set()
        self.event_bus.publish(self.Events.INITIALISED, self.ENTITY_ID, self)

        # Output a bit of helpful info
        self._log_info(LOG_DIVIDER)
        self._log_info(f"device serial: {self.serial}")
        self._log_info(f"device software version: {self.sw_version}")
        self._log_info(f"device model: {self.model.name}")
        self._log_info(LOG_DIVIDER)

        return self

    #
    # Initialise a secondry zone and check for errors
    #
    async def _initialise_secondry_zone(self, zone: "Zone", timeout: int = 10):
        # init the zone
        await zone.initialise(timeout)

        # Check zone_id is unique
        zone_to_compare = self.get_zone_by_id(zone.id)
        if zone_to_compare != None and zone_to_compare.host != zone.host:
            raise ZoneError(
                f"zone ID conflict. {zone.host} and {zone_to_compare.host} both have ID {zone.id}"
            )

        # Check the ZoneID is valid for the model
        if zone.id not in self.model.zones:
            raise ZoneError(f"{self.model.name} does not support ZoneID {zone.id}")

    #
    # Shutdown
    #
    async def shutdown(self):
        for zone in self.zones.values():
            await zone.shutdown()

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
    def model(self, model_obj):
        model = Models.find(model_obj)

        if Models.is_valid(model):
            # check we haven't added too many zones
            if len(self.zones) > model.zone_count:
                raise VsslCtrlException(
                    f"{model.name} only has {model.zone_count} zones not {len(self.zones)}"
                )

            self._set_property("model", model)
        else:
            message = f"VSSL model {model} does not exist"
            raise VsslCtrlException(message)

    #
    # Add a Zone
    #
    def add_zone(self, host: str):
        host = host.strip()

        # Check if VSSL is already initialised
        if self.initialised:
            error = f"Zones can not be added after VSSL is initialised. Error trying to add zone {host}"
            self._log_critical(error)
            raise ZoneError(error)

        # Check host is valid
        if not is_ipv4(host):
            message = f"{host} is not a valid IPv4 address"
            self._log_critical(message)
            raise ZoneError(message)

        # Check IPs are unique
        if any(zone.host == host for zone in self.zones.values()):
            error = f"Zone with host {host} already exists"
            self._log_critical(error)
            raise ZoneError(error)

        self.zones[host] = Zone(self, host)

        return self.zones[host]

    #
    # Get a Zone
    #
    def get_zone(self, host: str):
        if host in self.zones:
            return self.zones[host]

    #
    # Get zone by ID
    #
    def get_zone_by_id(self, zone_id: ZoneIDs):
        if self.zones:
            for host in self.zones:
                zone = self.zones[host]
                if zone.id == zone_id:
                    return zone

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
    # Get the model name
    #
    def _request_model_name(self):
        zone = self.get_connected_zone()
        if zone:
            zone.api_alpha.request_action_01()

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
