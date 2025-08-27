#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json
import time
import struct
import logging

from .api_base import APIBase
from .transport import ZoneTransport
from .settings import EQSettings, VolumeSettings
from .group import ZoneGroup

from . import LOG_DIVIDER
from .utils import clamp_volume
from .decorators import (
    logging_helpers,
    validate_response_length,
    validate_response_zone_id,
)
from .data_structure import (
    ZoneIDs,
    ZoneStatusExtKeys,
    ZoneEQStatusExtKeys,
    ZoneRouterStatusExtKeys,
    DeviceStatusExtKeys,
    DeviceStatusExtendedExtKeys,
)


@logging_helpers()
class APIAlpha(APIBase):
    """

    TCP Frame Structure:
    ------------------------------------------------------------
    | CMD Hi | CMD Lo | Length of Data | Data 1 | ... | Data n |
    ------------------------------------------------------------

    Port Info:

    Zone discovery occurs over multicast UDP on ports 1800 and 1900.
    The VSSL app communicates with the VSSL amplifier over all zones on ports 7777 and 50002.

    """

    # Protocol frame byte positions (zero indexed)
    FRAME_CMD_HI = 0
    FRAME_CMD_LO = 1
    FRAME_DATA_LENGTH = 2
    # Protocol frame header length (first 3 bytes are the header)
    FRAME_HEADER_LENGTH = 3
    # Port Number
    TCP_PORT = 50002

    #
    # API Events
    #
    class Events:
        PREFIX = "zone.api.alpha."
        CONNECTING = PREFIX + "connecting"
        CONNECTED = PREFIX + "connected"
        DISCONNECTING = PREFIX + "disconnecting"
        DISCONNECTED = PREFIX + "disconnected"
        RECONNECTING = PREFIX + "reconnecting"

    def __init__(self, vssl_host: "core.Vssl", zone: "zone.Zone"):
        super().__init__(host=zone.host, port=self.TCP_PORT)

        self.vssl = vssl_host
        self.zone = zone

    ##########################################################
    #
    # Logging Prefix
    #
    ##########################################################
    @property
    def _log_prefix(self):
        zone = self.zone.id if self.zone.id != None else self.host
        return f"Zone {zone}: alpha api:"

    ##########################################################
    #
    # Publish Event
    #
    ##########################################################
    def _event_publish(self, event_type, data=None):
        self.zone._event_publish(event_type, data)

    ##########################################################
    #
    # Keep Alive
    #
    ##########################################################
    def _send_keepalive(self):
        pass

    ##########################################################
    #
    # Read the byte stream
    #
    ##########################################################
    async def _read_byte_stream(self, reader, first_byte: bytes):
        frame_header = first_byte + await reader.readexactly(
            self.FRAME_HEADER_LENGTH - APIBase.FIRST_BYTE  # already have the first byte
        )

        # Read the frame data
        frame_data = await reader.readexactly(frame_header[self.FRAME_DATA_LENGTH])

        # self._log_debug(f"↓ rec: raw frame: {(frame_header + frame_data).hex(' ')}")

        try:
            await self._handle_response(frame_header, frame_data)
        except Exception as error:
            self._log_error(
                f"error handling response: {error} | {frame_header + frame_data}"
            )

    ##########################################################
    #
    # Handle Respsone Frame
    #
    ##########################################################
    async def _handle_response(self, frame_header: bytes, frame_data: bytes):
        cmd_hi = frame_header[self.FRAME_CMD_HI]
        cmd_lo = frame_header[self.FRAME_CMD_LO]

        # Length of 1 means a command was received a command confirmation pass / fail
        if frame_header[self.FRAME_DATA_LENGTH] == 1:
            return self.response_action_confimation(frame_header, frame_data)

        # Handle JSON Data
        if cmd_hi == 0x10 and cmd_lo == 0x00:
            return self.response_handle_json(frame_header, frame_data)

        # Handle Command Response
        try:
            cmd = bytes([cmd_lo]).hex()  # byte array to padded hex string
            action_fn = f"response_action_{cmd.upper()}"

            self._log_debug(f"response action: {action_fn}")

            if hasattr(self, action_fn):
                action_fn = getattr(self, action_fn)
                if callable(action_fn):
                    return action_fn(frame_header, frame_data)

        except Exception as error:
            self._log_error(f"error handling response: {error}")
            return None

        # Default
        return self.response_action_default(frame_header, frame_data)

    ##########################################################
    #
    # Decode JSON received data
    #
    ##########################################################

    def response_handle_json(self, frame_header: bytes, frame_data: bytes):
        try:
            # First byte is the JSON cmd
            json_cmd = bytes([frame_data[0]]).hex()  # byte array to padded hex string
            json_data = json.loads(self._decode_frame_data(frame_data[1:]))
            # Call a sub action
            json_action = f"response_action_00_{json_cmd.upper()}"

            # Call JSON sub action
            if hasattr(self, json_action):
                method = getattr(self, json_action)
                if callable(method):
                    self._log_debug(f"calling JSON action: {json_action}")
                    return method(json_data)

            self._log_debug(f"unknown JSON action {json_action}")

        except Exception as error:
            self._log_error(
                f"error handling JSON: {error} | {frame_header + frame_data}"
            )

    ##########################################################
    #
    # Command Confirmation
    #
    # Device will send back a OK or FAIL when we set a value
    #
    ##########################################################

    def response_action_confimation(self, frame_header: bytes, frame_data: bytes):
        result = "OK" if frame_data[0] else "FAIL"
        cmd = bytes([frame_header[self.FRAME_CMD_LO]]).hex()
        cmd_decimal = frame_header[self.FRAME_CMD_LO]

        if not frame_data[0]:
            self._log_debug(LOG_DIVIDER)

        self._log_debug(
            f"↓ rec: command confirmation - hex: {cmd} [{cmd_decimal}] | result: {result}"
        )

        if not frame_data[0]:
            self._log_debug(LOG_DIVIDER)

    ##########################################################
    #
    # Default action when no receive command is defined
    #
    ##########################################################

    def response_action_default(self, frame_header: bytes, frame_data: bytes):
        self._log_debug(LOG_DIVIDER)
        self._log_debug(
            f"↓ rec: unknown response. header: {frame_header.hex(' ')} | data: {frame_data.hex(' ')}"
        )
        self._log_debug(LOG_DIVIDER)

    ##########################################################
    #
    # Device Status JSON
    #
    # CMD: 00 [0]
    #
    # Sub-commands:
    #
    # 00 [0]: device status
    # 08 [8]: zone status
    # 09 [9]: EQ status
    # 0A [10]: output status
    # 0B [11]: device status extended
    #
    #
    ##########################################################

    ##########################################################
    #
    # Request - Device status
    #
    # Sub CMD: 00 [0]
    #
    ##########################################################

    #
    # Request
    #
    def request_action_00_00(self):
        self._log_debug("↑ req: device status")
        self.send(bytearray([16, 0, 1, 0]))

    #
    # Response
    #
    def response_action_00_00(self, metadata: list):
        """
        A.3x:
        {
            "B1Src": "3",
            "B2Src": "4",
            "B3Src": "5",
            "B1Nm": "",
            "B2Nm": "Optical In",
            "dev": "Device Name",
            "ver": "p15305.016.3701"
        }
        """
        self._log_debug(f"↓ rec: 00 Status: {metadata}")

        # Analog output source
        key = DeviceStatusExtKeys.add_zone_to_bus_key(self.zone.id)
        if key in metadata:
            self.zone.analog_output._set_property("source", int(metadata[key]))

        # Bus 1 Name
        if DeviceStatusExtKeys.BUS_1_NAME in metadata:
            self.vssl.settings._set_property(
                "bus_1_name",
                metadata[DeviceStatusExtKeys.BUS_1_NAME].strip(),
            )

        # Bus 2 Name
        if DeviceStatusExtKeys.BUS_2_NAME in metadata:
            self.vssl.settings._set_property(
                "bus_2_name",
                metadata[DeviceStatusExtKeys.BUS_2_NAME].strip(),
            )

        # Set the device name
        if DeviceStatusExtKeys.DEVICE_NAME in metadata:
            self.vssl.settings._set_property(
                "name", metadata[DeviceStatusExtKeys.DEVICE_NAME].strip()
            )

        # Set the software version
        if DeviceStatusExtKeys.SW_VERSION in metadata and self.vssl.sw_version == None:
            self.vssl._set_property(
                "sw_version", metadata[DeviceStatusExtKeys.SW_VERSION].strip()
            )

    ##########################################################
    #
    # Request - zone status
    #
    # Sub CMD: 08 [8]
    #
    ##########################################################

    #
    # Request
    #
    ZONE_STATUS = bytearray([16, 0, 1, 8])

    def request_action_00_08(self):
        self._log_debug("↑ req: zone status")
        self.send(self.ZONE_STATUS)

    #
    # Response
    #
    def response_action_00_08(self, metadata: list):
        """
        A.3x:
        {
            "id": "1",
            "ac": "0",
            "mc": "XXXXXXXXXXXX",
            "vol": "20",
            "mt": "0",
            "pa": "0",
            "rm": "0",
            "ts": "14",
            "alex": "14",
            "nmd": "0",
            "ird": "14",
            "lb": "24",
            "tp": "13",
            "wr": "0",
            "as": "0",
            "rg": "0"
        }
        """
        self._log_debug(f"↓ rec: 08 Status: {metadata}")

        #
        # We publish events for the vssl and zone required data.
        #
        # This data is readonly so we only need to do this before
        # init.
        #
        if not self.vssl.initialised or not self.zone.initialised:
            # Serial number
            if ZoneStatusExtKeys.SERIAL_NUMBER in metadata:
                self._event_publish(
                    self.zone.Events.SERIAL_RECEIVED,
                    metadata[ZoneStatusExtKeys.SERIAL_NUMBER],
                )

            # Model_ID
            if ZoneStatusExtKeys.MODEL_ID in metadata:
                self._event_publish(
                    self.zone.Events.MODEL_ID_RECEIVED,
                    int(metadata[ZoneStatusExtKeys.MODEL_ID]),
                )

            # Zone ID
            if ZoneStatusExtKeys.ID in metadata:
                self._event_publish(
                    self.zone.Events.ID_RECEIVED, int(metadata[ZoneStatusExtKeys.ID])
                )

        # Transport state
        if ZoneStatusExtKeys.TRANSPORT_STATE in metadata:
            self.zone.transport._set_property(
                "state", int(metadata[ZoneStatusExtKeys.TRANSPORT_STATE])
            )

        # Volume
        if ZoneStatusExtKeys.VOLUME in metadata:
            self.zone._set_property("volume", int(metadata[ZoneStatusExtKeys.VOLUME]))

        # Mute
        if ZoneStatusExtKeys.MUTE in metadata:
            self.zone._set_property("mute", bool(int(metadata[ZoneStatusExtKeys.MUTE])))

        # Party Mode
        if ZoneStatusExtKeys.PARTY_ZONE in metadata:
            self.zone.group._set_property(
                "is_party_zone_member", int(metadata[ZoneStatusExtKeys.PARTY_ZONE])
            )

        # Set Stream Source
        if ZoneStatusExtKeys.TRACK_SOURCE in metadata:
            self.zone.track.source = int(metadata[ZoneStatusExtKeys.TRACK_SOURCE])

        # Zone Enabled (0) or Disabled (1)
        if ZoneStatusExtKeys.DISABLED in metadata:
            self.zone.settings._set_property(
                "disabled", bool(int(metadata[ZoneStatusExtKeys.DISABLED]))
            )

    ##########################################################
    #
    # Request - EQ status
    #
    # Sub CMD: 09 [9]
    #
    ##########################################################

    #
    # Request
    #
    def request_action_00_09(self):
        self._log_debug("↑ req: EQ status")
        self.send(bytearray([16, 0, 1, 9]))

    #
    # Response
    #
    def response_action_00_09(self, metadata: list):
        """
        A.3x:
        {
            "mono": "0",
            "AiNm": "Analog In 1",
            "eq1": "100",
            "eq2": "100",
            "eq3": "100",
            "eq4": "100",
            "eq5": "100",
            "eq6": "100",
            "eq7": "100",
            "voll": "75",
            "volr": "75",
            "vold": "0"
        }
        """
        self._log_debug(f"↓ rec: 09 Status: {metadata}")

        # Mono output
        if ZoneEQStatusExtKeys.MONO in metadata:
            self.zone.settings._set_property(
                "mono", int(metadata[ZoneEQStatusExtKeys.MONO])
            )

        # Analog Input Name
        if ZoneEQStatusExtKeys.ANALOG_INPUT_NAME in metadata:
            self.zone.settings.analog_input._set_property(
                "name", metadata[ZoneEQStatusExtKeys.ANALOG_INPUT_NAME].strip()
            )

        self.zone.settings.eq._map_response_dict(metadata)
        self.zone.settings.volume._map_response_dict(metadata)

    ##########################################################
    #
    # Request - output status
    #
    # Sub CMD: 0A [10]
    #
    ##########################################################

    #
    # Request
    #
    def request_action_00_0A(self):
        self._log_debug("↑ req: output status")
        self.send(bytearray([16, 0, 1, 10]))

    #
    # Response
    #
    def response_action_00_0A(self, metadata: list):
        """
        A.3x:
        {
            "ECO": "0",
            "eqsw": "1",
            "inSrc": "0",
            "SP": "0",
            "BF1": "0",
            "BF2": "0",
            "BF3": "0",
            "GRM": "0",
            "GRS": "255",
            "Pwr": "0",
            "Bvr": "1",
            "fxv": "24",
            "AtPwr": "1"
        }
        """
        self._log_debug(f"↓ rec: 0A Status: {metadata}")

        # EQ Switch
        if ZoneRouterStatusExtKeys.EQ_ENABLED in metadata:
            self.zone.settings.eq._set_property(
                "enabled", bool(int(metadata[ZoneRouterStatusExtKeys.EQ_ENABLED]))
            )

        # Input Source
        if ZoneRouterStatusExtKeys.INPUT_SOURCE in metadata:
            self.zone.input._set_property(
                "source", int(metadata[ZoneRouterStatusExtKeys.INPUT_SOURCE])
            )

        # Source Priority
        if ZoneRouterStatusExtKeys.SOURCE_PRIORITY in metadata:
            self.zone.input._set_property(
                "priority", int(metadata[ZoneRouterStatusExtKeys.SOURCE_PRIORITY])
            )

        # Analog Output Fix Volume
        # e.g BF1
        if self.zone.id:
            key = ZoneRouterStatusExtKeys.add_zone_to_ao_fixed_volume_key(self.zone.id)
            if key in metadata:
                self.zone.analog_output._set_property(
                    "is_fixed_volume", bool(int(metadata[key]))
                )

        # Handle groups
        if (
            ZoneRouterStatusExtKeys.GROUP_MASTER in metadata
            and ZoneRouterStatusExtKeys.GROUP_SOURCE in metadata
        ):
            self.zone.group._set_property(
                "source", int(metadata[ZoneRouterStatusExtKeys.GROUP_SOURCE])
            )
            self.zone.group._set_property(
                "is_master",
                int(metadata[ZoneRouterStatusExtKeys.GROUP_MASTER]) != 0,
            )

        # Power State
        if ZoneRouterStatusExtKeys.POWER_STATE in metadata:
            self.vssl.settings.power._set_property(
                "state", int(metadata[ZoneRouterStatusExtKeys.POWER_STATE])
            )

        # Analog input fixed gain
        if ZoneRouterStatusExtKeys.ANALOG_INPUT_FIXED_GAIN in metadata:
            self.zone.settings.analog_input._set_property(
                "fixed_gain",
                int(metadata[ZoneRouterStatusExtKeys.ANALOG_INPUT_FIXED_GAIN]),
            )

        # Alway On power state = 0 else 1 = auto
        if ZoneRouterStatusExtKeys.ADAPTIVE_POWER in metadata:
            self.vssl.settings.power._set_property(
                "adaptive", bool(int(metadata[ZoneRouterStatusExtKeys.ADAPTIVE_POWER]))
            )

    ##########################################################
    #
    # Request - device status extended
    #
    # Sub CMD: 0B [11]
    #
    ##########################################################

    #
    # Request
    #
    def request_action_00_0B(self):
        self._log_debug("↑ req: device status extended")
        self.send(bytearray([16, 0, 1, 11]))

    #
    # Response
    #
    def response_action_00_0B(self, metadata: list):
        """
        A.3x:
        {
            'IRMskL': '241',
            'IRMskH': '255',
            'BTSta': '0',
            'Crs': '0',
            'Fes': '0',
            'Drk': '0'
        }
        """
        self._log_debug(f"↓ rec: 0B Status: {metadata}")

        # Bluetooth
        if DeviceStatusExtendedExtKeys.BLUETOOTH_STATUS in metadata:
            self.vssl.settings.bluetooth._set_property(
                "state", int(metadata[DeviceStatusExtendedExtKeys.BLUETOOTH_STATUS])
            )

        # Subwoofer Crossover
        if DeviceStatusExtendedExtKeys.SUBWOOFER_CROSSOVER in metadata:
            self.zone.settings.subwoofer._set_property(
                "crossover",
                int(metadata[DeviceStatusExtendedExtKeys.SUBWOOFER_CROSSOVER]),
            )

    ##########################################################
    #
    # Device Model Name
    #
    # CMD: 01 (1)
    #
    ##########################################################

    #
    # Request
    #
    def request_action_01(self):
        self._log_debug(f"↑ req: get device model name")
        self.send(bytearray([16, 1, 0]))

    #
    # Response
    #
    def response_action_01(self, frame_header: bytes, frame_data: bytes):
        try:
            name = self._decode_frame_data(frame_data)
            self._log_info(f"↓ rec: device model name: {name}")
            self._event_publish(self.zone.Events.MODEL_NAME_RECEIVED, name)

        except Exception as error:
            self._log_error(f"error decoding device model name: {error}")

    ##########################################################
    #
    # Set Device Name
    #
    # CMD: 18 [24]
    #
    ##########################################################

    def request_action_18(self, name: str):
        name = name.strip()
        self._log_debug(f"↑ req: set device name: {name}")
        self._request_action_rename(name, 24, 7)

    ##########################################################
    #
    # Device Name
    #
    # CMD: 19 (25)
    #
    ##########################################################

    #
    # Request
    #
    def request_action_19(self):
        self._log_debug(f"↑ req: get device name")
        self.send(bytearray([16, 25, 1, 0]))

    #
    # Response
    #
    def response_action_19(self, frame_header: bytes, frame_data: bytes):
        try:
            # First byte is the ID
            name = self._decode_frame_data(frame_data[1:])
            self._log_debug(f"↓ rec: device name: {name}")
            self.vssl.settings._set_property("name", name)

        except Exception as error:
            self._log_error(f"error decoding device name: {error}")

    ##########################################################
    #
    # Set Bluetooth
    #
    # CMD: 65 (101)
    #
    # 13: Clear All
    # 14: On
    # 15: Off
    # 16: Enter Pairing
    # 17: Exit Pairing
    #
    ##########################################################

    #
    # Request
    #
    def request_action_65(self, cmd: int):
        self._log_debug(f"↑ req: set bluetooth: {cmd}")
        self.send(bytearray([16, 101, 2, 1, cmd]))

    ##########################################################
    #
    # Get Bluetooth
    #
    # CMD: 66 (102)
    #
    # 0: Off
    # 1: Disconnected
    # 2: Pairing
    # 3: Connected
    #
    ##########################################################

    #
    # Request
    #
    def request_action_66(self):
        self._log_debug(f"↑ req: get bluetooth state")
        self.send(bytearray([16, 102, 1, self.zone.id]))

    #
    # Response
    #
    @validate_response_length()
    def response_action_66(self, frame_header: bytes, frame_data: bytes):
        state = frame_data[1]
        self._log_debug(f"↓ rec: bluetooth state: {state}")
        self.vssl.settings.bluetooth._set_property("state", state)

    ##########################################################
    #
    # Reboot
    #
    # CMD: 33 (51)
    #
    # Zone: [zone_id]
    # Device: 0
    #
    ##########################################################

    #
    # Reboot Device
    #
    def request_action_33_device(self):
        self._log_debug("↑ req: reboot device")
        self.send(bytearray([16, 51, 2, 0, 1]))

    #
    # Reboot Zone
    #
    def request_action_33(self):
        self._log_debug(f"↑ req: reboot single zone")
        self.send(bytearray([16, 51, 2, self.zone.id, 1]))

    ##########################################################
    #
    # Factory Reset
    #
    # CMD: 2B (43)
    #
    ##########################################################

    #
    # Request
    #
    def request_action_2B(self):
        self._log_debug("↑ req: factory reset device")
        self.send(bytearray([16, 43, 2, 8, 0]))

    ##########################################################
    #
    # Rename Commands
    #
    # CMD: 15 (21)
    #
    # A.1x - Renaming functions do not work
    #
    ##########################################################

    #
    # Request Base
    #
    def _request_action_rename(self, name: str, command_byte: int, id_byte: int = 0):
        """
        General method to send a request to change a name.
        :param name: The new name to set.
        :param command_byte: The subcommand byte (e.g., 21 or 24).
        :param id_byte: The ID byte to specify the target (default is 0).
        """
        name = name.strip()
        command = bytearray([16, command_byte])
        command.extend(struct.pack(">B", len(name) + 1))  # +1 for the channel_id
        command.extend([id_byte])
        command.extend(self._encode_frame_data(name))
        self.send(command)

    #
    # Set Analog Input Name / Rename Analog Input
    #
    # A.1x: 1 or 7 both work as channels
    #
    def request_action_15(self, name: str):
        self._log_debug(f"↑ req: change analog input name: {name}")
        self._request_action_rename(name, 21, self.zone.id)

    #
    # Set Bus 1 Name
    #
    def request_action_15_10(self, name: str):
        self._log_debug(f"↑ req: change bus 1 name: {name}")
        self._request_action_rename(name, 21, 10)

    #
    # Set Bus 2 Name
    #
    def request_action_15_12(self, name: str):
        name = name.strip()
        self._log_debug(f"↑ req: change bus 2 name: {name}")
        self._request_action_rename(name, 21, 12)

    ##########################################################
    #
    # Get Input Names
    #
    # CMD: 16 (22)
    #
    # Channel:
    #
    # 1-6: Analog Input [n] Name - A.1x uses 1
    # 10: Bus 1 Name
    # 11: ???
    # 12: Bus 2 Name
    #
    ##########################################################

    #
    # 16 [22]
    # Get Local Input Name
    #
    def request_action_16(self, channel: int = None):
        self._log_debug("↑ req: local input name")
        channel = self.zone.id if channel == None else channel
        self.send(bytearray([16, 22, 1, channel]))

    #
    # 16 [22]
    # Received Local Input Name
    #
    def response_action_16(self, frame_header: bytes, frame_data: bytes):
        # First byte is the sub cmd
        channel = frame_data[0]
        name = self._decode_frame_data(frame_data[1:])

        self._log_debug(f"↓ rec: input name for channel {channel}: {name}")

        if ZoneIDs.is_valid(channel):
            self._log_debug(f"↓ rec: analog input {channel} name: {name}")
            self.zone.settings.analog_input._set_property("name", name)

        # Bus 1 Name
        elif channel == 10:
            self._log_debug(f"↓ rec: bus 1 name: {name}")
            self.vssl.settings._set_property("bus_1_name", name)

        # Bus 2 Name
        elif channel == 12:
            self._log_debug(f"↓ rec: bus 2 name: {name}")
            self.vssl.settings._set_property("bus_2_name", name)

    ##########################################################
    #
    # Power State
    #
    # CMD: 4E (78)
    #
    ##########################################################

    #
    # Get Power State
    #
    def request_action_4E(self):
        self._log_debug(f"↑ req: power state")
        # Device level command (dont need zone)
        command = bytearray([16, 78, 1, 8])
        self.send(command)

    #
    # 4E [78]
    # Power State
    #
    @validate_response_length()
    def response_action_4E(self, frame_header: bytes, frame_data: bytes):
        state = frame_data[1]
        self._log_debug(f"↓ rec: power state: {state}")

    ##########################################################
    #
    # Set Adaptive Power
    #
    # CMD: 4F (79)
    #
    # 0: Always On
    # 1: Adaptive
    #
    ##########################################################

    #
    # 4F [79]
    # Set Adaptive Power
    #
    def request_action_4F(self, state: bool = True):
        self._log_debug(f"↑ req: set adaptive power state: {state}")
        # Device level command (dont need zone)
        # A.1x needs to be channel 7 while other needs 8.
        # Not sure this works on all models
        channel = ZoneIDs.A1 if self.zone.id == ZoneIDs.A1 else 8
        command = bytearray([16, 79, 2, channel, int(state)])
        self.send(command)

    ##########################################################
    #
    # Get Adaptive Power
    #
    # CMD: 50 [80]
    #
    # 0: Always On
    # 1: Adaptive
    #
    # Note: direct feedback is only received on the main zone (1)
    #
    ##########################################################

    #
    # Request
    #
    def request_action_50(self):
        self._log_debug(f"↑ req: adaptive power setting")
        # A.1x needs to be channel 7 while other needs 8.
        channel = ZoneIDs.A1 if self.zone.id == ZoneIDs.A1 else 8
        command = bytearray([16, 80, 1, 7])
        self.send(command)

    #
    # Response
    #
    @validate_response_length()
    # @validate_response_zone_id()
    def response_action_50(self, frame_header: bytes, frame_data: bytes):
        enabled = frame_data[1]
        self._log_debug(f"↓ rec: adaptive power setting: {enabled}")
        self.vssl.settings.power._set_property("adaptive", bool(int(enabled)))

    ##########################################################
    #
    # Set Subwoofer Crossover
    #
    # CMD: 57 [87]
    #
    ##########################################################

    #
    # Request
    #
    def request_action_57(self, freq: int):
        self._log_debug(f"↑ req: set subwoofer crossover: {freq}")
        # We hard code the zone ID to be 7 since this has to be a A.1(x)
        command = bytearray([16, 87, 3, ZoneIDs.A1, 0, freq])
        self.send(command)

    ##########################################################
    #
    # Get Subwoofer Crossover
    #
    # CMD: 58 [88]
    #
    ##########################################################

    #
    # Request
    #
    def request_action_58(self):
        self._log_debug(f"↑ req: subwoofer crossover frequency")
        # We hard code the zone ID to be 7 since this has to be a A.1(x)
        command = bytearray([16, 88, 2, ZoneIDs.A1, 0])
        self.send(command)

    #
    # Response
    #
    @validate_response_length(3)
    @validate_response_zone_id()
    def response_action_58(self, frame_header: bytes, frame_data: bytes):
        freq = frame_data[2]
        self._log_debug(f"↓ rec: subwoofer crossover frequency: {freq}")
        self.zone.settings.subwoofer._set_property("crossover", freq)

    ##########################################################
    #
    # Set Status Lights Dark Mode
    #
    # CMD: 59 [89]
    #
    # Note: not persistent across reboots
    #
    ##########################################################

    #
    # Request
    #
    def request_action_59(self, state: int):
        self._log_debug(f"↑ req: set status lights dark mode: {bool(state)}")
        command = bytearray([16, 89, 2, self.zone.id, int(state)])
        self.send(command)

    ##########################################################
    #
    # Get Status Lights Dark Mode
    #
    # CMD: 5A [90]
    #
    ##########################################################

    #
    # Request
    #
    def request_action_5A(self):
        self._log_debug(f"↑ req: status lights dark mode")
        command = bytearray([16, 90, 1, self.zone.id])
        self.send(command)

    #
    # Response
    #
    @validate_response_length()
    @validate_response_zone_id()
    def response_action_5A(self, frame_header: bytes, frame_data: bytes):
        enabled = frame_data[1]
        self._log_debug(f"↓ rec: status lights dark mode: {enabled}")
        self.vssl.settings._set_property("status_light_mode", bool(int(enabled)))

    ##########################################################
    #
    # Set Input Source / Router
    #
    # CMD: 03 [3]
    #
    # @see InputRouter.Sources
    #
    ##########################################################

    #
    # Request
    #
    def request_action_03(self, src: int):
        self._log_debug(f"↑ req: change input source to {src}")
        self.send(bytearray([16, 3, 2, self.zone.id, src]))

    ##########################################################
    #
    # Get Input Source / Router
    #
    # CMD: 04 [4]
    #
    ##########################################################

    #
    # Request
    #
    def request_action_04(self):
        self._log_debug("↑ req: input source")
        self.send(bytearray([16, 4, 1, self.zone.id]))

    #
    # Response
    #
    @validate_response_length()
    @validate_response_zone_id()
    def response_action_04(self, frame_header: bytes, frame_data: bytes):
        source = frame_data[1]
        self._log_debug(f"↓ rec: input source: {source}")
        self.zone.input._set_property("source", source)

    ##########################################################
    #
    # Set Volume Commands
    #
    # CMD: 05 [5]
    #
    # @see VolumeSettings.Commands
    #
    ##########################################################

    #
    # Set Request Base
    #
    def _set_volume_base(self, vol: int, cmd_byte: int, clamp=True):
        vol = clamp_volume(vol) if clamp else vol
        return bytearray([16, 5, 3, self.zone.id, vol, cmd_byte])

    #
    # Set Analog Input Fixed Gain
    #
    def request_action_05_00(self, gain: int):
        self._log_debug(f"↑ req: set fix analog input gain: {gain}")
        self.send(
            self._set_volume_base(gain, VolumeSettings.Commands.ANALOG_INPUT_GAIN)
        )

    #
    # Set Max Volume - Left Channel
    #
    def request_action_05_01(self, vol: int):
        self._log_debug(f"↑ req: set left max volume: {vol}")
        self.send(self._set_volume_base(vol, VolumeSettings.Commands.MAX_VOL_LEFT))

    #
    # Set Max Volume - Right Channel
    #
    def request_action_05_02(self, vol: int):
        self._log_debug(f"↑ req: set right max volume: {vol}")
        self.send(self._set_volume_base(vol, VolumeSettings.Commands.MAX_VOL_RIGHT))

    #
    # Set Volume
    #
    def request_action_05(self, vol: int):
        self._log_debug(f"↑ req: set volume level: {vol}")
        self.send(self._set_volume_base(vol, VolumeSettings.Commands.VOLUME))

    #
    # Raise Volume
    #
    def request_action_05_raise(self):
        self._log_debug("↑ Req: raise volume")
        self.send(self._set_volume_base(255, VolumeSettings.Commands.VOLUME, False))

    #
    # Lower Volume
    #
    def request_action_05_lower(self):
        self._log_debug("↑ Req: lower volume")
        self.send(self._set_volume_base(254, VolumeSettings.Commands.VOLUME, False))

    #
    # Set Default On Volume
    #
    def request_action_05_08(self, vol: int):
        self._log_debug(f"↑ req: set default on volume level: {vol}")
        self.send(self._set_volume_base(vol, VolumeSettings.Commands.DEFAULT_ON))

    ##########################################################
    #
    # Get Volume Commands
    #
    # CMD: 06 [6]
    #
    ##########################################################

    #
    # Get Request Base
    #
    def _get_volume_base(self, cmd_byte: int):
        return bytearray([16, 6, 2, self.zone.id, cmd_byte])

    #
    # Get Analog Input Fixed Gain
    #
    def request_action_06_00(self):
        self._log_debug(f"↑ req: analog input fixed gain")
        self.send(self._get_volume_base(VolumeSettings.Commands.ANALOG_INPUT_GAIN))

    #
    # Get Max Volume - Left Channel
    #
    def request_action_06_01(self):
        self._log_debug(f"↑ req: left max volume")
        self.send(self._get_volume_base(VolumeSettings.Commands.MAX_VOL_LEFT))

    #
    # Get Max Volume - Right Channel
    #
    def request_action_06_02(self):
        self._log_debug(f"↑ req: right max volume")
        self.send(self._get_volume_base(VolumeSettings.Commands.MAX_VOL_RIGHT))

    #
    # Get Volume
    #
    def request_action_06(self):
        self._log_debug(f"↑ req: volume")
        self.send(self._get_volume_base(VolumeSettings.Commands.VOLUME))

    #
    # Get Default On Volume
    #
    def request_action_06_08(self):
        self._log_debug(f"↑ req: default on volume")
        self.send(self._get_volume_base(VolumeSettings.Commands.DEFAULT_ON))

    #
    # 06 [6]
    # Received Volume Data
    #
    @validate_response_length(3)
    @validate_response_zone_id()
    def response_action_06(self, frame_header: bytes, frame_data: bytes):
        # First byte is the zone ID checked in decorator
        vol = frame_data[1]
        vol_cmd = frame_data[2]

        self._log_debug(f"↓ rec: volume - cmd: {vol_cmd} vol: {vol}")

        # Analog input fixed gain
        if vol_cmd == VolumeSettings.Commands.ANALOG_INPUT_GAIN:
            self.zone.settings.analog_input._set_property("fixed_gain", vol)

        # Max Left
        elif vol_cmd == VolumeSettings.Commands.MAX_VOL_LEFT:
            self.zone.settings.volume._set_property("max_left", vol)

        # Max Right
        elif vol_cmd == VolumeSettings.Commands.MAX_VOL_RIGHT:
            self.zone.settings.volume._set_property("max_right", vol)

        # Normal Volume Change
        elif vol_cmd == VolumeSettings.Commands.VOLUME:
            self.zone._set_property("volume", vol)

        # Defaul On Volume Change
        elif vol_cmd == VolumeSettings.Commands.DEFAULT_ON:
            self.zone.settings.volume._set_property("default_on", vol)

    ##########################################################
    #
    # Set Transport Control
    #
    # 3D [61]
    #
    # @see ZoneTransport.States
    #
    ##########################################################

    #
    # Request
    #
    def request_action_3D(self, state: ZoneTransport.States):
        if state == ZoneTransport.States.STOP:
            cmd = 1
        elif state == ZoneTransport.States.PLAY:
            cmd = 0
        elif state == ZoneTransport.States.PAUSE:
            cmd = 2
        else:
            return

        self._log_debug(f"↑ req: set transport control {state.name} ({state.value})")
        self.send(bytearray([16, 61, 2, self.zone.id, cmd]))

    ##########################################################
    #
    # Get Transport State
    #
    # CMD: 07 [7]
    #
    # 0 = Stopped
    # 1 = Playing
    # 2 = Paused
    #
    ##########################################################

    #
    # Request
    #
    def request_action_07(self):
        self._log_debug("↑ req: status transport state")
        self.send(bytearray([16, 7, 1, self.zone.id]))

    #
    # Response
    #
    @validate_response_length()
    @validate_response_zone_id()
    def response_action_07(self, frame_header: bytes, frame_data: bytes):
        state = frame_data[1]
        self._log_debug(f"↓ rec: transport state: {state}")
        self.zone.transport._set_property("state", state)

    ##########################################################
    #
    # Set Party Mode
    #
    # CMD: 0C [12]
    #
    ##########################################################

    #
    # Request
    #
    def request_action_0C(self, state: int):
        self._log_debug(f"↑ req: set party memeber: {state}")
        self.send(bytearray([16, 11, 2, self.zone.id, int(not not state)]))

    #
    # Response
    #
    @validate_response_length()
    @validate_response_zone_id()
    def response_action_0C(self, frame_header: bytes, frame_data: bytes):
        state = frame_data[1]
        self._log_debug(f"↓ rec: party member state: {state}")
        self.zone.group._set_property("is_party_zone_member", state)

    ##########################################################
    #
    # Set Enable / Disable EQ
    #
    # CMD: 2D [45]
    #
    ##########################################################

    #
    # Request
    #
    def request_action_2D(self, state: int):
        self._log_debug(f"↑ req: EQ enable: {state}")
        self.send(bytearray([16, 45, 2, self.zone.id, int(not not state)]))

    ##########################################################
    #
    # Get Enable / Disable EQ
    #
    # CMD: 2E [46]
    #
    ##########################################################

    #
    # Request
    #
    def request_action_2E(self):
        self._log_debug(f"↑ req: EQ enable status")
        self.send(bytearray([16, 46, 1, self.zone.id]))

    #
    # Response
    #
    @validate_response_length()
    @validate_response_zone_id()
    def response_action_2E(self, frame_header: bytes, frame_data: bytes):
        enabled = frame_data[1]
        self._log_debug(f"↓ rec: EQ enabled: {enabled}")
        self.zone.settings.eq._set_property("enabled", bool(enabled))

    ##########################################################
    #
    # Set EQ
    #
    # CMD: 0D [13]
    #
    # @see EQSettings.Freqs
    #
    ##########################################################

    #
    # Request
    #
    def request_action_0D(self, freq: "EQSettings.Freqs", value: int = 0):
        clamped = max(EQSettings.MIN_VALUE, min(value, EQSettings.MAX_VALUE))
        self._log_debug(f"↑ req: set EQ: {freq.name[1:]} ({freq.value}) to {clamped}")
        self.send(bytearray([16, 13, 3, self.zone.id, freq.value, clamped]))

    ##########################################################
    #
    # Get EQ
    #
    # CMD: 0E [14]
    #
    # @see EQSettings.Freqs
    #
    ##########################################################

    #
    # Request
    #
    def request_action_0E(self, freq: "EQSettings.Freqs"):
        self._log_debug(f"↑ req: EQ for frequency: {freq}")
        self.send(bytearray([16, 14, 2, self.zone.id, freq]))

    #
    # Response
    #
    @validate_response_length(3)
    @validate_response_zone_id()
    def response_action_0E(self, frame_header: bytes, frame_data: bytes):
        freq = frame_data[1]
        value = frame_data[2]
        self._log_debug(f"↓ rec: EQ frequency:{freq}:{value}")
        self.zone.settings.eq._set_eq_freq(freq, value)

    ##########################################################
    #
    # Set Mono
    #
    # CMD: 0F [15]
    #
    # 0: Stereo
    # 1: Mono
    #
    # @see ZoneSettings.StereoMono
    #
    ##########################################################

    #
    # Request
    #
    def request_action_0F(self, state: int):
        self._log_debug(f"↑ req: set output to mono: {state}")
        self.send(bytearray([16, 15, 2, self.zone.id, int(not not state)]))

    ##########################################################
    #
    # Get Mono
    #
    # CMD: 10 [16]
    #
    ##########################################################

    #
    # Request
    #
    def request_action_10(self):
        self._log_debug(f"↑ req: mono state")
        self.send(bytearray([16, 16, 1, self.zone.id]))

    #
    # Response
    #
    @validate_response_length()
    @validate_response_zone_id()
    def response_action_10(self, frame_header: bytes, frame_data: bytes):
        state = frame_data[1]
        self._log_debug(f"↓ rec: mono state: {state}")
        self.zone.settings._set_property("mono", state)

    ##########################################################
    #
    # Set Mute
    #
    # CMD: 11 [17]
    #
    ##########################################################

    #
    # Request
    #
    def request_action_11(self, state: int):
        self._log_debug(f"↑ req: mute volume: {state}")
        self.send(bytearray([16, 17, 2, self.zone.id, int(not not state)]))

    ##########################################################
    #
    # Get Mute
    #
    # CMD: 12 [18]
    #
    ##########################################################

    #
    # Request
    #
    def request_action_12(self):
        self._log_debug(f"↑ req: mute status")
        self.send(bytearray([16, 18, 1, self.zone.id]))

    #
    # Response
    #
    @validate_response_length()
    @validate_response_zone_id()
    def response_action_12(self, frame_header: bytes, frame_data: bytes):
        is_muted = frame_data[1]
        self._log_debug(f"↓ rec: mute: {is_muted}")
        self.zone._set_property("mute", is_muted)

    ##########################################################
    #
    # Set Zone Disable (Disable / Enable)
    #
    # CMD: 25 [37]
    #
    # 1 = Disable
    # 0 = Enable
    #
    ##########################################################

    #
    # Request
    #
    def request_action_25(self, disable: bool = True):
        self._log_debug(f"↑ req: disable state: {disable}")
        self.send(bytearray([16, 37, 2, self.zone.id, int(not not disable)]))

    ##########################################################
    #
    # Get Zone Disable (Disable / Enable)
    #
    # CMD: 26 [38]
    #
    # 1 = Disable
    # 0 = Enable
    #
    ##########################################################

    #
    # Request
    #
    def request_action_26(self):
        self._log_debug(f"↑ req: disable state")
        self.send(bytearray([16, 38, 1, self.zone.id]))

    #
    # Response
    #
    @validate_response_length(3)
    @validate_response_zone_id()
    def response_action_26(self, frame_header: bytes, frame_data: bytes):
        disabled = frame_data[2]
        self._log_debug(f"↓ rec: disable state: {disabled}")
        self.zone.settings._set_property("disabled", bool(disabled))

    ##########################################################
    #
    # Set Analog Output Source
    #
    # CMD: 1D [29]
    #
    # @see AnalogOutput.IDs
    # @see AnalogOutput.Sources
    #
    ##########################################################

    #
    # Request
    #
    def request_action_1D(self, ao_id: int, src: int):
        self._log_debug(
            f"↑ req: change analog ouput id: {ao_id} to analog ouput source: {src}"
        )
        self.send(bytearray([16, 29, 2, ao_id, src]))

    ##########################################################
    #
    # Get Analog Output Source
    #
    # CMD: 1E [30]
    #
    # @see AnalogOutput.IDs
    #
    ##########################################################

    #
    # Request
    #
    def request_action_1E(self, ao_id: int):
        self._log_debug(f"↑ req: analog ouput {ao_id} source")
        self.send(bytearray([16, 30, 1, ao_id]))

    #
    # Response
    #
    @validate_response_length()
    def response_action_1E(self, frame_header: bytes, frame_data: bytes):
        # First byte is the output ID
        output = frame_data[0]
        source = frame_data[1]
        self._log_debug(f"↓ rec: analog output {output} source: {source}")
        self.zone.analog_output._set_property("source", source)

    ##########################################################
    #
    # Set Analog Output Fixed Volume
    #
    # CMD: 49 [73]
    #
    # @see AnalogOutput.Sources
    #
    ##########################################################

    #
    # Request
    #
    def request_action_49(self, ao_id: int, fix: bool):
        self._log_debug(f"↑ req: fix the volume of analog ouput {ao_id}")
        self.send(bytearray([16, 73, 2, ao_id, int(not not fix)]))

    ##########################################################
    #
    # Get Analog Output Fixed Volume
    #
    # CMD: 4A [74]
    #
    # @see AnalogOutput.Sources
    #
    ##########################################################

    #
    # Request
    #
    def request_action_4A(self, ao_id: int):
        self._log_debug(f"↑ req: analog ouput {ao_id} fixed volume")
        self.send(bytearray([16, 74, 1, ao_id]))

    #
    # Response
    #
    @validate_response_length()
    # @validate_response_zone_id()
    def response_action_4A(self, frame_header: bytes, frame_data: bytes):
        output = frame_data[0]
        state = frame_data[1]
        self._log_debug(f"↓ rec: analog output {output} volume fixed: {state}")
        self.zone.analog_output._set_property("is_fixed_volume", bool(state))

    ##########################################################
    #
    # Get Stream Source
    #
    # CMD: 2A [42]
    #
    ##########################################################

    #
    # Request
    #
    def request_action_2A(self):
        self._log_debug(f"↑ req: stream source")
        self.send(bytearray([16, 42, 1, self.zone.id]))

    #
    # Response
    #
    @validate_response_length()
    @validate_response_zone_id()
    def response_action_2A(self, frame_header: bytes, frame_data: bytes):
        # First byte is the zone ID checked in decorator
        source = frame_data[1]
        self._log_debug(f"↓ rec: stream source: {source}")
        self.zone.track.source = source

    ##########################################################
    #
    # Set Input Priority
    #
    # CMD: 47 [71]
    #
    ##########################################################

    #
    # Request
    #
    def request_action_47(self, priority: int):
        self._log_debug(f"↑ req: set input priority {priority}")
        self.send(bytearray([16, 71, 2, self.zone.id, priority]))

    ##########################################################
    #
    # Get Input Priority
    #
    # CMD: 48 [72]
    #
    ##########################################################

    #
    # Request
    #
    def request_action_48(self):
        self._log_debug(f"↑ req: input priority")
        self.send(bytearray([16, 72, 1, self.zone.id]))

    #
    # Response
    #
    @validate_response_length()
    @validate_response_zone_id()
    def response_action_48(self, frame_header: bytes, frame_data: bytes):
        priority = frame_data[1]
        self._log_debug(f"↓ rec: input priority: {priority}")
        self.zone.input._set_property("priority", priority)

    ##########################################################
    #
    # Set Group Membership
    #
    # CMD: 4B [75]
    #
    ##########################################################

    #
    # 4B [75]
    # Group Add Member
    #
    # In other words: Make this zone the master and add zone_index as child
    def request_action_4B_add(self, zone_index: int):
        self._log_debug(f"↑ req: add child zone {zone_index} to group")
        self.send(bytearray([16, 75, 2, self.zone.id, zone_index]))

    #
    # 4B [75]
    # Group Dissolve
    #
    # In other words: set this zones childen to 255 (remove all children)
    #
    def request_action_4B_dissolve(self):
        self._log_debug(f"↑ req: dissolve group")
        self.send(bytearray([16, 75, 2, self.zone.id, ZoneGroup.SLAVE_CLEAR_BYTE]))

    #
    # 4B [75]
    # Group - Remove zone_index from any group
    #
    # In other words: set the zones parent to 255
    #
    def request_action_4B_remove(self, zone_index: int):
        self._log_debug(f"↑ req: remove child zone {zone_index} from group")
        # Doesnt need a zone id
        self.send(bytearray([16, 75, 2, ZoneGroup.SLAVE_CLEAR_BYTE, zone_index]))

    ##########################################################
    #
    # Get Group Membership
    #
    # CMD: 4C [76]
    #
    ##########################################################

    #
    # Request
    #
    def request_action_4C(self):
        self._log_debug(f"↑ req: group membership")
        self.send(bytearray([16, 76, 1, self.zone.id]))

    #
    # Response
    #
    @validate_response_length(3)
    @validate_response_zone_id()
    def response_action_4C(self, frame_header: bytes, frame_data: bytes):
        # First byte is the zone ID checked in decorator
        is_master = frame_data[1] != 0  # Any value other than 0 is a master
        slave_source = frame_data[2]

        self._log_debug(
            f"↓ rec: group info - master: {is_master} ({frame_data[1]}) | slave source: {slave_source}"
        )

        self.zone.group._set_property("is_master", is_master)
        self.zone.group._set_property("source", slave_source)

    ##########################################################
    #
    # Play URL
    #
    # CMD: 55 [85]
    #
    ##########################################################

    def request_action_55(self, url: str, all_zones: bool = False, volume: int = None):
        """
        From VSSL:

        note: the call will return immediately with either a failure message or an indication that the
        playback has been requested. It is possible for the playback to fail (e.g. the network can't retrieve the file,
        the file format is invalid, ...). Further status will be provided in the coming VSSL FW iterations.

        note2: if this is the first time a playback has been requested then we will send a command to wake up the unit
        and wait a few seconds before playing the file. Otherwise, if the last playback was less then 15 minutes ago
        then we will play the clip immediately.

        note3: this call allows you to play a file on 1 or all of the zones. If you want to play to a subset
        (e.g. zone 1,2) then you will need to make two calls, one for each zone you want to play the file on.

        ref: https://vssl.gitbook.io/vssl-rest-api/announcements/play-audio-file

        """
        string = "PLAYITEM:DIRECT:" + f"{url}"

        command = bytearray([16, 85])
        command.extend(struct.pack(">B", len(string) + 2))

        # Zone 0 will play on all zones
        channel = 0 if all_zones else self.zone.id
        command.extend([channel])

        # Volume
        vol = self.zone.volume if volume == None else clamp_volume(volume)
        command.extend([self.zone.volume])

        # Add URL to request
        command.extend(self._encode_frame_data(string))

        self._log_debug(f"↑ req: play file {url}")
        self.send(command)

    ##########################################################
    #
    # Unknown Command
    #
    # CMD: 32 [50]
    #
    ##########################################################

    @validate_response_length()
    @validate_response_zone_id()
    def response_action_32(self, frame_header: bytes, frame_data: bytes):
        """
        This gets assigned when the zone is playing something.
        Has something to do with the input source?

        Not Playing: 0
        Zone 1: 9
        Zone 2: 10
        Zone 3: 11


        'rm' key in the status object.

        """
        self._log_debug(f"↓ rec: unknown cmd 32 index: {frame_data[1]}")
