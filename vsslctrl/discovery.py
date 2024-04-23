import time

# mDNS Discovery
class Discovery:
    def __init__(self):
        self.hosts = {}
        self.zeroconf_available = self.check_zeroconf_availability()

        if self.zeroconf_available:
            self.discover_services()

    def check_zeroconf_availability(self):
        try:
            import zeroconf
            return True
        except ImportError:
            print("Error: 'zeroconf' package is not installed. Please install it using 'pip install zeroconf'.")
            return False

    def discover_services(self, service_string="_googlecast._tcp.local."):
        if not self.zeroconf_available:
            return

        from zeroconf import Zeroconf, ServiceBrowser

        class MyListener:
            def __init__(self, parent):
                self.parent = parent

            def remove_service(self, zeroconf, type, name):
                pass

            def add_service(self, zeroconf, type, name):
                info = zeroconf.get_service_info(type, name)
                if info and info.name.startswith('VSSL'):

                    mac_address = info.decoded_properties.get('bs', None)

                    self.parent.hosts[name] = {
                        "host": info.parsed_addresses()[0],
                        "name": info.decoded_properties.get('fn', None),
                        "model": info.decoded_properties.get('md', None), 
                        "mac_addr": ":".join([mac_address[i:i+2] for i in range(0, len(mac_address), 2)]) if mac_address else None
                    }

            def update_service(self, zeroconf, type, name):
                pass

        zeroconf_instance = Zeroconf()
        listener = MyListener(self)
        browser = ServiceBrowser(zeroconf_instance, service_string, listener)

        # Wait for a few seconds to allow time for discovery
        time.sleep(5)

        # Print the discovered hosts
        print("Discovered hosts:")
        for host in self.hosts.items():
            print(f"{host}")

        # Close the Zeroconf instance
        zeroconf_instance.close()

# Usage
mdns_service_discovery = MDNSServiceDiscovery()
