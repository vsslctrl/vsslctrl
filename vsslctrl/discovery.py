#!/usr/bin/env python3

""" UNTESTED AND IN DEV """

import json
import asyncio
from typing import Any, Optional, cast

from zeroconf import IPVersion, ServiceStateChange, Zeroconf
from zeroconf.asyncio import (
    AsyncServiceBrowser,
    AsyncServiceInfo,
    AsyncZeroconf,
    InterfaceChoice,
)

from .device import Models as VSSLModels
from .utils import group_list_by_property, is_ipv4
from .api_alpha import APIAlpha
from .api_base import APIBase
from .decorators import logging_helpers
from .exceptions import ZeroConfNotInstalled, ZoneConnectionError, ZoneError

from .data_structure import ZoneStatusExtKeys, ZoneIDs


#
# Check to see if Zeroconf is available on the system
#
def check_zeroconf_availability():
    try:
        import zeroconf
        import zeroconf.asyncio

        return True
    except ImportError:
        raise ZeroConfNotInstalled(
            "Error: 'zeroconf' package is not installed. Install using 'pip install zeroconf'."
        )
        return False


#
# Attempt to connect to zone and fetch the status JSON
#
async def fetch_zone_info(host: str):
    # Check host is valid
    if not is_ipv4(host):
        raise ZoneError(f"{host} is not a valid IPv4 address")

    try:
        # Open a connection to the server
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, APIAlpha.TCP_PORT), APIAlpha.TIMEOUT
        )

        # Request zones status
        writer.write(APIAlpha.ZONE_STATUS)

        # Wait until the data is flushed
        await writer.drain()

        # Read the header
        frame_header = await reader.readexactly(APIAlpha.FRAME_HEADER_LENGTH)
        # Read the frame data
        frame_data = await reader.readexactly(frame_header[APIAlpha.FRAME_DATA_LENGTH])
        # First byte is the JSON cmd
        metadata = json.loads(
            frame_data[1:].decode(APIAlpha.ENCODING, errors="replace")
        )

        writer.close()
        await writer.wait_closed()

        required_keys = {
            ZoneStatusExtKeys.ID,
            ZoneStatusExtKeys.SERIAL_NUMBER,
            ZoneStatusExtKeys.MODEL_ID,
        }

        missing = required_keys - metadata.keys()
        if missing:
            raise ZoneError(
                f"Host {host}:{APIAlpha.TCP_PORT} didn't return correct JSON, missing: {', '.join(missing)}"
            )

    except (asyncio.TimeoutError, asyncio.CancelledError):
        raise ZoneConnectionError(f"Connection to {host}:{APIAlpha.TCP_PORT} timed out")

    # convert to vsslctrl data
    return {
        "host": host,
        "zone_id": ZoneIDs(int(metadata[ZoneStatusExtKeys.ID])),
        "serial": metadata[ZoneStatusExtKeys.SERIAL_NUMBER],
        "model": VSSLModels.find(int(metadata[ZoneStatusExtKeys.MODEL_ID])),
    }


@logging_helpers()
class VsslDiscovery:
    SERVICE_STRING: str = "_airplay._tcp.local."

    def __init__(self, aiozc: AsyncZeroconf = None, discovery_time: int = 5):
        self.discovery_time = discovery_time
        self.discovered_zones = []
        self.zeroconf_available = check_zeroconf_availability()

        self.aiozc = aiozc
        self.aiobrowser = None

    #
    # Discover
    #
    async def discover(self):
        if not self.zeroconf_available:
            return

        self.discovered_zones = []

        if not isinstance(self.aiozc, AsyncZeroconf):
            self.aiozc = AsyncZeroconf(
                ip_version=IPVersion.V4Only, interfaces=InterfaceChoice.All
            )

        task = asyncio.create_task(self._run())

        await asyncio.sleep(self.discovery_time)
        await self._close()
        task.cancel()

        hosts = []
        for zone in self.discovered_zones:
            try:
                info = await fetch_zone_info(zone["host"])
                zone["zone_id"] = info["zone_id"]
                zone["serial"] = info["serial"]
                hosts.append(zone)

            except Exception as e:
                self._log_error(
                    f'Error fetching zone info for discovered host {zone["host"]}, {e}'
                )

        return group_list_by_property(hosts, "serial")

    #
    # Run
    #
    async def _run(self) -> None:
        await self.aiozc.zeroconf.async_wait_for_start()
        self._log_debug(f"Browsing for {self.SERVICE_STRING} services")

        self.aiobrowser = AsyncServiceBrowser(
            self.aiozc.zeroconf,
            self.SERVICE_STRING,
            handlers=[self._on_service_state_change],
        )

        while True:
            await asyncio.sleep(1)

    #
    # Close
    #
    async def _close(self) -> None:
        assert self.aiozc is not None
        assert self.aiobrowser is not None
        await self.aiobrowser.async_cancel()
        await self.aiozc.async_close()

    #
    # on_service_state_change
    #
    def _on_service_state_change(
        self,
        zeroconf: Zeroconf,
        service_type: str,
        name: str,
        state_change: ServiceStateChange,
    ) -> None:
        asyncio.ensure_future(self._fetch_service_info(zeroconf, service_type, name))

    #
    # show_service_info
    #
    async def _fetch_service_info(
        self, zeroconf: Zeroconf, service_type: str, name: str
    ) -> None:
        info = AsyncServiceInfo(service_type, name)
        await info.async_request(zeroconf, 3000)

        if info:
            manufacturer = info.properties.get(b"manufacturer", None)
            if manufacturer and manufacturer.startswith(b"VSSL"):
                self.discovered_zones.append(
                    {
                        # Convert byte representation of IP address to string
                        "host": info.parsed_addresses()[0],
                        "name": name.rstrip(f".{self.SERVICE_STRING}"),
                        "model": info.properties.get(b"model", b"")
                        .decode(APIBase.ENCODING, errors="replace")
                        .lstrip(f"VSSL")
                        .strip(),
                        "mac_addr": info.properties.get(b"deviceid", b"").decode(
                            APIBase.ENCODING, errors="replace"
                        ),
                    }
                )
