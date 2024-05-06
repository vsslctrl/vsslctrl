#!/usr/bin/env python3

""" Scan for apple devices. """

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

from .utils import group_list_by_property
from .api_alpha import APIAlpha
from .decorators import logging_helpers
from .exceptions import ZeroConfNotInstalled


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
                zone_id, serial = await self._fetch_zone_info(zone["host"])
                if zone_id and serial:
                    zone["zone_id"] = zone_id
                    zone["serial"] = serial
                    hosts.append(zone)

            except Exception:
                self._log_error(
                    f'Error fetching zone info for discovered host {zone["host"]}'
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
                        .decode("utf-8")
                        .lstrip(f"VSSL")
                        .strip(),
                        "mac_addr": info.properties.get(b"deviceid", b"").decode(
                            "utf-8"
                        ),
                    }
                )

    #
    # Get zone info
    #
    async def _fetch_zone_info(self, host):
        try:
            # Open a connection to the server
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(host, APIAlpha.TCP_PORT), APIAlpha.TIMEOUT
            )

            # Request zones status
            writer.write(APIAlpha.ZONE_STATUS)

            # Wait until the data is flushed
            await writer.drain()

            # Receive response
            response = await reader.read(1024)
            string = response[4:].decode("ascii")
            metadata = json.loads(string)

        finally:
            # Close the connection
            writer.close()
            await writer.wait_closed()

        # Return the response received from the server
        return (metadata["id"], metadata["mc"])
