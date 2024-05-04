import time
import json
import socket
from .api_alpha import APIAlpha
from .utils import group_list_by_property
from .exceptions import ZeroConfNotInstalled


# mDNS Zone Discovery
class VsslDiscovery:
    SERVICE_STRING = "_airplay._tcp.local."

    def __init__(self, discovery_time: int = 5):
        self.discovery_time = discovery_time
        self.hosts = []
        self.zeroconf_available = self.check_zeroconf_availability()

    def check_zeroconf_availability(self):
        try:
            import zeroconf

            return True
        except ImportError:
            raise ZeroConfNotInstalled(
                "Error: 'zeroconf' package is not installed. Please install it using 'pip install zeroconf'."
            )
            return False

    async def discover(self):
        if not self.zeroconf_available:
            return

        from zeroconf import Zeroconf, ServiceBrowser

        class Listener:
            def __init__(self, parent):
                self.parent = parent

            def add_service(self, zeroconf, type, name):
                info = zeroconf.get_service_info(type, name)

                if info:
                    properties = info.properties
                    manufacturer = properties.get(b"manufacturer", None)

                    if manufacturer and manufacturer.startswith(b"VSSL"):
                        self.parent.hosts.append(
                            {
                                # Convert byte representation of IP address to string
                                "host": socket.inet_ntop(
                                    socket.AF_INET, info.addresses[0]
                                ),
                                "name": name.rstrip(f".{ZoneDiscovery.SERVICE_STRING}"),
                                "model": properties.get(b"model", b"")
                                .decode("utf-8")
                                .lstrip(f"VSSL")
                                .strip(),
                                "mac_addr": properties.get(b"deviceid", b"").decode(
                                    "utf-8"
                                ),
                            }
                        )

            def update_service(self, zeroconf, type, name):
                pass

        zeroconf_instance = Zeroconf()
        listener = Listener(self)
        browser = ServiceBrowser(
            zeroconf_instance, ZoneDiscovery.SERVICE_STRING, listener
        )

        # Wait for a few seconds to allow time for discovery
        time.sleep(self.discovery_time)

        hosts = []
        for zone in self.hosts:
            zone_id, serial = self.fetch_zone_properties(zone["host"])
            zone["zone_id"] = zone_id
            zone["serial"] = serial
            hosts.append(zone)

        # Close the Zeroconf instance
        zeroconf_instance.close()

        return group_list_by_property(hosts, "serial")

    def fetch_zone_properties(self, host):
        # Create a socket object
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                # Connect to the server
                s.connect((host, APIAlpha.TCP_PORT))

                # Send data
                s.sendall(bytes.fromhex("10000108"))

                # Receive response
                response = s.recv(1024)
                string = response[4:].decode("ascii")
                metadata = json.loads(string)

            except Exception as e:
                return (None, None)

        # Return the response received from the server
        return (metadata["id"], metadata["mc"])
