#!/usr/bin/env python3

""" Scan for apple devices. """

import argparse
import asyncio
import logging
from typing import Any, Optional, cast

from zeroconf import DNSQuestionType, IPVersion, ServiceStateChange, Zeroconf
from zeroconf.asyncio import AsyncServiceBrowser, AsyncServiceInfo, AsyncZeroconf

HOMESHARING_SERVICE: str = "_appletv-v2._tcp.local."
DEVICE_SERVICE: str = "_touch-able._tcp.local."
MEDIAREMOTE_SERVICE: str = "_mediaremotetv._tcp.local."
AIRPLAY_SERVICE: str = "_airplay._tcp.local."
COMPANION_SERVICE: str = "_companion-link._tcp.local."
RAOP_SERVICE: str = "_raop._tcp.local."
AIRPORT_ADMIN_SERVICE: str = "_airport._tcp.local."
DEVICE_INFO_SERVICE: str = "_device-info._tcp.local."

ALL_SERVICES = [AIRPLAY_SERVICE]

log = logging.getLogger(__name__)


def async_on_service_state_change(
    zeroconf: Zeroconf, service_type: str, name: str, state_change: ServiceStateChange
) -> None:
    print(f"Service {name} of type {service_type} state changed: {state_change}")
    if state_change is not ServiceStateChange.Added:
        return
    base_name = name[: -len(service_type) - 1]
    device_name = f"{base_name}.{DEVICE_INFO_SERVICE}"
    asyncio.ensure_future(_async_show_service_info(zeroconf, service_type, name))
    # Also probe for device info
    asyncio.ensure_future(
        _async_show_service_info(zeroconf, DEVICE_INFO_SERVICE, device_name)
    )


async def _async_show_service_info(
    zeroconf: Zeroconf, service_type: str, name: str
) -> None:
    info = AsyncServiceInfo(service_type, name)
    await info.async_request(zeroconf, 3000, question_type=DNSQuestionType.QU)
    print("Info from zeroconf.get_service_info: %r" % (info))
    if info:
        addresses = [
            "%s:%d" % (addr, cast(int, info.port)) for addr in info.parsed_addresses()
        ]
        print("  Name: %s" % name)
        print("  Addresses: %s" % ", ".join(addresses))
        print("  Weight: %d, priority: %d" % (info.weight, info.priority))
        print(f"  Server: {info.server}")
        if info.properties:
            print("  Properties are:")
            for key, value in info.properties.items():
                print(f"    {key!r}: {value!r}")
        else:
            print("  No properties")
    else:
        print("  No info")
    print("\n")


class AsyncAppleScanner:
    def __init__(self, args: Any) -> None:
        self.args = args
        self.aiobrowser: Optional[AsyncServiceBrowser] = None
        self.aiozc: Optional[AsyncZeroconf] = None

    async def async_run(self) -> None:
        self.aiozc = AsyncZeroconf(ip_version=ip_version)
        await self.aiozc.zeroconf.async_wait_for_start()
        print("\nBrowsing %s service(s), press Ctrl-C to exit...\n" % ALL_SERVICES)
        kwargs = {
            "handlers": [async_on_service_state_change],
            "question_type": DNSQuestionType.QU,
        }
        if self.args.target:
            kwargs["addr"] = self.args.target
        self.aiobrowser = AsyncServiceBrowser(self.aiozc.zeroconf, ALL_SERVICES, **kwargs)  # type: ignore
        while True:
            await asyncio.sleep(1)

    async def async_close(self) -> None:
        assert self.aiozc is not None
        assert self.aiobrowser is not None
        await self.aiobrowser.async_cancel()
        await self.aiozc.async_close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)

    parser = argparse.ArgumentParser()
    parser.add_argument("--debug", action="store_true")
    version_group = parser.add_mutually_exclusive_group()
    version_group.add_argument("--target", help="Unicast target")
    version_group.add_argument("--v6", action="store_true")
    version_group.add_argument("--v6-only", action="store_true")
    args = parser.parse_args()

    if args.debug:
        logging.getLogger("zeroconf").setLevel(logging.DEBUG)
    if args.v6:
        ip_version = IPVersion.All
    elif args.v6_only:
        ip_version = IPVersion.V6Only
    else:
        ip_version = IPVersion.V4Only

    loop = asyncio.get_event_loop()
    runner = AsyncAppleScanner(args)
    try:
        loop.run_until_complete(runner.async_run())
    except KeyboardInterrupt:
        loop.run_until_complete(runner.async_close())


# import time
# import json
# import socket
# from .api_alpha import APIAlpha
# from .utils import group_list_by_property
# from .exceptions import ZeroConfNotInstalled


# # mDNS Zone Discovery
# class VsslDiscovery:
#     SERVICE_STRING = "_airplay._tcp.local."

#     def __init__(self, discovery_time: int = 5):
#         self.discovery_time = discovery_time
#         self.hosts = []
#         self.zeroconf_available = self.check_zeroconf_availability()

#     def check_zeroconf_availability(self):
#         try:
#             import zeroconf

#             return True
#         except ImportError:
#             raise ZeroConfNotInstalled(
#                 "Error: 'zeroconf' package is not installed. Please install it using 'pip install zeroconf'."
#             )
#             return False

#     async def discover(self):
#         if not self.zeroconf_available:
#             return

#         from zeroconf import Zeroconf, ServiceBrowser

#         class Listener:
#             def __init__(self, parent):
#                 self.parent = parent

#             def add_service(self, zeroconf, type, name):
#                 info = zeroconf.get_service_info(type, name)

#                 if info:
#                     properties = info.properties
#                     manufacturer = properties.get(b"manufacturer", None)

#                     if manufacturer and manufacturer.startswith(b"VSSL"):
#                         self.parent.hosts.append(
#                             {
#                                 # Convert byte representation of IP address to string
#                                 "host": socket.inet_ntop(
#                                     socket.AF_INET, info.addresses[0]
#                                 ),
#                                 "name": name.rstrip(f".{ZoneDiscovery.SERVICE_STRING}"),
#                                 "model": properties.get(b"model", b"")
#                                 .decode("utf-8")
#                                 .lstrip(f"VSSL")
#                                 .strip(),
#                                 "mac_addr": properties.get(b"deviceid", b"").decode(
#                                     "utf-8"
#                                 ),
#                             }
#                         )

#             def update_service(self, zeroconf, type, name):
#                 pass

#         zeroconf_instance = Zeroconf()
#         listener = Listener(self)
#         browser = ServiceBrowser(
#             zeroconf_instance, ZoneDiscovery.SERVICE_STRING, listener
#         )

#         # Wait for a few seconds to allow time for discovery
#         time.sleep(self.discovery_time)

#         hosts = []
#         for zone in self.hosts:
#             zone_id, serial = self.fetch_zone_properties(zone["host"])
#             zone["zone_id"] = zone_id
#             zone["serial"] = serial
#             hosts.append(zone)

#         # Close the Zeroconf instance
#         zeroconf_instance.close()

#         return group_list_by_property(hosts, "serial")

#     def fetch_zone_properties(self, host):
#         # Create a socket object
#         with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
#             try:
#                 # Connect to the server
#                 s.connect((host, APIAlpha.TCP_PORT))

#                 # Send data
#                 s.sendall(bytes.fromhex("10000108"))

#                 # Receive response
#                 response = s.recv(1024)
#                 string = response[4:].decode("ascii")
#                 metadata = json.loads(string)

#             except Exception as e:
#                 return (None, None)

#         # Return the response received from the server
#         return (metadata["id"], metadata["mc"])
