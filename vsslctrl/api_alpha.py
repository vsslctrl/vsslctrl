#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json
import time
import struct
import logging

from .api_base import APIBase
from .transport import ZoneTransport
from .settings import EQSettings

from .utils import hex_to_int, clamp_volume, hex_to_bytearray_string
from .decorators import logging_helpers
from .data_structure import (
    ZoneStatusExtKeys,
    ZoneEQStatusExtKeys,
    ZoneRouterStatusExtKeys,
    DeviceStatusExtKeys,
    DeviceStatusExtendedExtKeys,
)


@logging_helpers()
class APIAlpha(APIBase):
    TCP_PORT = 50002
    HEADER_LENGTH = 3
    JSON_HEADER_LENGTH = HEADER_LENGTH + 1  # action is 1 byte

    def __init__(self, vssl_host: "core.Vssl", zone: "zone.Zone"):
        super().__init__(host=zone.host, port=self.TCP_PORT)

        self._log_prefix = f"Zone {zone.id}: Alpha API:"

        self.vssl = vssl_host
        self.zone = zone

    #
    # Send keep alive
    #
    def _send_keepalive(self):
        self.request_action_17()

    #
    #
    #
    # Requests
    #
    #
    #
    def _add_zone_id_to_request(self, command: bytearray, index: int = 3):
        command[index] = self.zone.id
        return command

    #
    # 17 [23]
    # Keep Alive
    #
    def request_action_17(self):
        self._log_debug("Requesting keep alive")
        self.send(bytearray([16, 23, 1, 7]))

    #
    # 00 [0] - 00 [0]
    # Status Bus
    #
    def request_action_00_00(self):
        self._log_debug("Requesting device status")
        self.send(bytearray([16, 0, 1, 0]))  # HEX: 10000100

    #
    # 00 [0] - 08 [8]
    # Status General
    #
    ZONE_STATUS = bytearray([16, 0, 1, 8])

    def request_action_00_08(self):
        self._log_debug("Requesting zone status")
        self.send(self.ZONE_STATUS)  # HEX: 10000108

    #
    # 00 [0] - 09 [9]
    # Status EQ
    #
    def request_action_00_09(self):
        self._log_debug("Requesting EQ status")
        self.send(bytearray([16, 0, 1, 9]))  # HEX: 10000109

    #
    # 00 [0] - 0A [10]
    # Status Output
    #
    def request_action_00_0A(self):
        self._log_debug("Requesting output status")
        self.send(bytearray([16, 0, 1, 10]))  # HEX: 1000010A

    #
    # 00 [0] - 0B [11]
    # Status device extended
    #
    def request_action_00_0B(self):
        self._log_debug("Requesting device status extended")
        self.send(bytearray([16, 0, 1, 11]))  # HEX: 1000010B

    #
    # 03 [3]
    # Input Source Set
    #
    def request_action_03(self, src: int):
        self._log_debug(f"Requesting to change input source to {src}")
        command = self._add_zone_id_to_request(bytearray([16, 3, 2, 0, src]))
        self.send(command)

    #
    # 04 [4]
    # Input Source Get
    #
    def request_action_04(self):
        self._log_debug("Requesting input source")
        command = self._add_zone_id_to_request(bytearray([16, 4, 1, 0]))
        self.send(command)

    #
    # 05 [5]
    # Set Volume
    #
    def request_action_05(self, vol: int):
        vol = clamp_volume(vol)
        self._log_debug(f"Requesting to set volume level: {vol}")
        command = self._add_zone_id_to_request(bytearray([16, 5, 3, 0, vol, 3]))
        self.send(command)

    #
    # 05 [5]
    # Volume Raise
    #
    def request_action_05_raise(self):
        self._log_debug("Requesting raise volume")
        command = self._add_zone_id_to_request(bytearray([16, 5, 3, 0, 255, 3]))
        self.send(command)

    #
    # 05 [5]
    # Volume Lower
    #
    def request_action_05_lower(self):
        self._log_debug("Requesting lower volume")
        command = self._add_zone_id_to_request(bytearray([16, 5, 3, 0, 254, 3]))
        self.send(command)

    #
    # 05 [5]
    # Set Default On Volume
    #
    def request_action_05_08(self, vol: int):
        vol = clamp_volume(vol)
        self._log_debug(f"Requesting to set default on volume level: {vol}")
        command = self._add_zone_id_to_request(bytearray([16, 5, 3, 0, vol, 8]))
        self.send(command)

    #
    # 05 [5]
    # Set Analog Input Fixed Gain
    #
    def request_action_05_00(self, gain: int):
        gain = clamp_volume(gain)
        self._log_debug(f"Requesting to set fix analog input gain: {gain}")
        command = self._add_zone_id_to_request(bytearray([16, 5, 3, 0, gain, 0]))
        self.send(command)

    #
    # 05 [5]
    # Set Max Left Volume
    #
    def request_action_05_01(self, vol: int):
        vol = clamp_volume(vol)
        self._log_debug(f"Requesting to set left max volume: {vol}")
        command = self._add_zone_id_to_request(bytearray([16, 5, 3, 0, vol, 1]))
        self.send(command)

    #
    # 05 [5]
    # Set Max Right Volume
    #
    def request_action_05_02(self, vol: int):
        vol = clamp_volume(vol)
        self._log_debug(f"Requesting to set right max volume: {vol}")
        command = self._add_zone_id_to_request(bytearray([16, 5, 3, 0, vol, 2]))
        self.send(command)

    #
    # 07 [7]
    # Status Transport State
    #
    def request_action_07(self):
        self._log_debug("Requesting status transport state")
        self.send(bytearray([16, 7, 1, 0]))

    #
    # 0D [13]
    # EQ
    #
    def request_action_0D(self, freq: "EQSettings.Freqs", value: int = 0):
        clamped = max(EQSettings.MIN_VALUE, min(value, EQSettings.MAX_VALUE))
        self._log_debug(
            f"Requesting to set EQ: {freq.name[1:]} ({freq.value}) to {clamped}"
        )
        command = self._add_zone_id_to_request(
            bytearray([16, 13, 3, 0, freq.value, clamped])
        )
        self.send(command)

    #
    # 0F [15]
    # Output Set Mono
    #
    def request_action_mono_set(self, state: int):
        self._log_debug(f"Requesting to set output to mono: {state}")
        command = self._add_zone_id_to_request(
            bytearray([16, 15, 2, 0, int(not not state)])
        )
        self.send(command)

    #
    # 11 [17]
    # Mute
    #
    def request_action_11(self, state: int):
        self._log_debug(f"Requesting to mute volume: {state}")
        command = self._add_zone_id_to_request(
            bytearray([16, 17, 2, 0, int(not not state)])
        )
        self.send(command)

    #
    # 12 [18]
    # Status Mute
    #
    def request_action_12(self):
        self._log_debug(f"Requesting status mute")
        command = self._add_zone_id_to_request(bytearray([16, 18, 1, 0]))
        self.send(command)

    #
    # 25 [37]
    # Enable or Disable Zone
    #
    # 1 = Disable
    # 0 = Enable
    #
    def request_action_25(self, disable: bool = True):
        self._log_debug(f"Requesting disable zone: {disable}")
        command = self._add_zone_id_to_request(
            bytearray([16, 37, 2, 0, int(not not disable)])
        )
        self.send(command)

    #
    # 15 [21]
    # Set Analog Input Name / Rename Analog Input
    #
    def request_action_15(self, name: str):
        name = name.strip()
        self._log_debug(f"Requesting to change analog input name: {name}")
        command = bytearray([16, 21])
        command.extend(struct.pack(">B", len(name) + 1))
        command.extend([0])  # zone id placeholder
        command = self._add_zone_id_to_request(command)
        command.extend(name.encode("utf-8"))
        self.send(command)

    #
    # 15 [21]
    # Set Optical Input Name / Rename Optical Input
    #
    def request_action_15_12(self, name: str):
        name = name.strip()
        self._log_debug(f"Requesting to change optical input name: {name}")
        command = bytearray([16, 21])
        command.extend(struct.pack(">B", len(name) + 1))
        command.extend([12])
        command.extend(name.encode("utf-8"))
        self.send(command)

    #
    # 18 [24]
    # Set Device Name / Rename Device
    #
    def request_action_18(self, name: str):
        name = name.strip()
        self._log_debug(f"Requesting to change device name: {name}")
        command = bytearray([16, 24])
        command.extend(struct.pack(">B", len(name) + 1))
        command.extend([7])
        command.extend(name.encode("utf-8"))
        self.send(command)

    #
    # 19 [25]
    # Get Device name
    #
    def request_action_19(self):
        self._log_debug(f"Requesting device name")
        command = self._add_zone_id_to_request(bytearray([16, 25, 1, 0]))
        self.send(command)

    #
    # 1D [29]
    # Analog Output Set Src
    #
    def request_action_1D(self, src: int):
        self._log_debug(f"Requesting to change analog ouput source to {src}")
        command = self._add_zone_id_to_request(bytearray([16, 29, 2, 0, src]))
        self.send(command)

    def request_action_1D_router(self, ao_id: int, src: int):
        self._log_debug(f"Requesting to change analog ouput {ao_id} source to {src}")
        self.send(bytearray([16, 29, 2, ao_id, src]))

    #
    # 49 [73]
    # Analog Output Fix Output Vol
    #
    def request_action_49(self, fix: bool):
        self._log_debug(f"Requesting to fix analog ouput volume {fix}")
        command = self._add_zone_id_to_request(
            bytearray([16, 73, 2, 0, int(not not fix)])
        )
        self.send(command)

    def request_action_49_router(self, ao_id: int, fix: bool):
        self._log_debug(f"Requesting to fix analog ouput {ao_id} volume {fix}")
        self.send(bytearray([16, 73, 2, ao_id, int(not not fix)]))

    #
    # 3D [61]
    # Transport State
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

        self._log_debug(f"Requesting transports state {state.name}, {state.value}")
        command = self._add_zone_id_to_request(bytearray([16, 61, 2, 0, cmd]))
        self.send(command)

    #
    # 2A [42]
    # Status Stream Source
    #
    def request_action_2A(self):
        self._log_debug(f"Requesting stream source")
        command = self._add_zone_id_to_request(bytearray([16, 42, 1, 0]))
        self.send(command)

    #
    # 2D [45]
    # Disable / Enable EQ
    #
    def request_action_2D(self, state: int):
        self._log_debug(f"Requesting EQ Enable: {state}")
        command = self._add_zone_id_to_request(
            bytearray([16, 45, 2, 0, int(not not state)])
        )
        self.send(command)

    #
    # 33 [51]
    # Reboot
    #
    def request_action_33(self):
        self._log_debug(f"Requesting to reboot single zone")
        command = self._add_zone_id_to_request(bytearray([16, 51, 2, 0, 1]))
        self.send(command)

    #
    # 33 [51]
    # Reboot All Zones
    #
    def request_action_33_device(self):
        self._log_debug(f"Requesting to reboot device")
        self.send(bytearray([16, 51, 2, 0, 1]))

    #
    # 47 [71]
    # Set Input Priority
    #
    def request_action_47(self, priority: int):
        self._log_debug(f"Requesting to set input priority {priority}")
        command = self._add_zone_id_to_request(bytearray([16, 71, 2, 0, priority]))
        self.send(command)

    #
    # 4B [75]
    # Group Add Member
    #
    # In other words: set the zones (zone_index) parent to this zone
    #
    def request_action_4B_add(self, zone_index: int):
        self._log_debug(f"Requesting to add child zone {zone_index} to group")
        command = self._add_zone_id_to_request(bytearray([16, 75, 2, 0, zone_index]))
        self.send(command)

    #
    # 4B [75]
    # Group Remove Member
    #
    # In other words: set the zones parent to 255
    #
    def request_action_4B_remove(self, zone_index: int):
        self._log_debug(f"Requesting to remove child zone {zone_index} from group")
        # Doesnt need a zone id
        self.send(bytearray([16, 75, 2, 255, zone_index]))

    #
    # 4B [75]
    # Group Dissolve
    #
    # In other words: set this zones childen to 255
    #
    def request_action_4B_dissolve(self):
        self._log_debug(f"Requesting to Dissolve group")
        command = self._add_zone_id_to_request(bytearray([16, 75, 2, 0, 255]))
        self.send(command)

    #
    # 55 [85]
    # Play URL
    #
    # Unexpected behaviour on A3.x - feedback is inconsistent
    #
    # There is a bug in the vssl that if we send the volume, it will continually send
    # back volume updates while the url is being played. So for now, we send the current
    # volume and it them seems to behave ok
    #
    #
    """ note: the call will return immediately with either a failure message or an indication that the 
    playback has been requested. It is possible for the playback to fail (e.g. the network can't retrieve the file, 
    the file format is invalid, ...). Further status will be provided in the coming VSSL FW iterations.

    note2: if this is the first time a playback has been requested then we will send a command to wake up the unit 
    and wait a few seconds before playing the file. Otherwise, if the last playback was less then 15 minutes ago 
    then we will play the clip immediately.
    
    note3: this call allows you to play a file on 1 or all of the zones. If you want to play to a subset 
    (e.g. zone 1,2) then you will need to make two calls, one for each zone you want to play the file on.

    ref: https://vssl.gitbook.io/vssl-rest-api/announcements/play-audio-file

    """

    def request_action_55(self, url: str, all_zones: bool = False):
        string = "PLAYITEM:DIRECT:" + f"{url}"

        command = bytearray([16, 85])
        command.extend(struct.pack(">B", len(string) + 2))

        # Zone 0 will play on all zones
        command.extend([0, self.zone.volume])

        if not all_zones:
            command = self._add_zone_id_to_request(command)

        command.extend(string.encode("utf-8"))

        self._log_debug(f"Requesting to play file {url} cmd: {command}")
        self.send(command)

    #
    # 4F [79]
    # Adaptive Power - Device level Command
    #
    def request_action_4F(self, state=True):
        self._log_debug(f"Requesting to set adaptive power state: {state}")
        # Device level command (dont need zone)
        command = bytearray([16, 79, 2, 8, int(state)])
        self.send(command)

    #
    #
    #
    # Respsonses
    #
    #
    #

    async def _read_byte_stream(self, reader, data):
        data += await reader.readexactly(self.HEADER_LENGTH - APIBase.FRIST_BYTE)
        length = data[2]

        data += await reader.readexactly(length)

        self._log_debug(f"Response data: {data}")

        if length == 1:
            return self.response_action_confimation(data)

        await self._handle_response(data)

    async def _handle_response(self, response: bytes):
        try:
            # Convert to HEX and split into a array
            hexl = response.hex("-").split("-")
            action = f"response_action_{hexl[1].upper()}"

            self._log_debug(f"Response action: {action}")

        except Exception as error:
            self._log_error(f"couldnt handle response: {error} | {hexl}")
            return None

        if hasattr(self, action):
            method = getattr(self, action)
            if callable(method):
                return method(hexl, response)

        # Default
        return self.response_action_default(hexl, response)

    #
    # 00 [0]
    # Received JSON Status Data
    #
    def response_action_00(self, hexl: list, response: bytes):
        try:
            packet_length = hexl[2]

            length = hex_to_int(packet_length) - 1
            string = response[
                self.JSON_HEADER_LENGTH : self.JSON_HEADER_LENGTH + length
            ].decode("ascii")
            metadata = json.loads(string)

            # Call a sub action
            sub_action = f"response_action_00_{hexl[3].upper()}"

            if hasattr(self, sub_action):
                method = getattr(self, sub_action)
                if callable(method):
                    self._log_debug(f"Calling status sub action: {sub_action}")
                    return method(metadata)

            self._log_debug(f"Unknown status sub action {sub_action}")

        except Exception as error:
            self._log_error(f"Couldnt parse JSON: {error} | {hexl}")

    #
    # 00_00
    # Device Status 00
    #
    # {'B1Src': '3', 'B2Src': '4', 'B3Src': '5', 'B1Nm': '', 'B2Nm': 'Optical In', 'dev': 'Device Name', 'ver': 'p15305.016.3701'}
    #
    def response_action_00_00(self, metadata: list):
        self._log_debug(f"Received 00 Status: {metadata}")

        # Guess device model
        self.vssl._infer_device_model(metadata)

        # Analog output source
        key = DeviceStatusExtKeys.add_zone_to_bus_key(self.zone.id)
        if key in metadata:
            self.zone.analog_output._set_property("source", int(metadata[key]))

        # B1Nm - Bus1 Name
        # Not used?

        # B2Nm - Bus2 Name - For A3.X this is the optical input name
        if DeviceStatusExtKeys.OPTICAL_INPUT_NAME in metadata:
            self.vssl.settings._set_property(
                "optical_input_name",
                metadata[DeviceStatusExtKeys.OPTICAL_INPUT_NAME].strip(),
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

    #
    # 00_08
    # Zone Status 08
    #
    # {'id': '1', 'ac': '0', 'mc': 'XXXXXXXXXXXX', 'vol': '20', 'mt': '0', 'pa': '0', 'rm': '0', 'ts': '14',
    #  'alex': '14', 'nmd': '0', 'ird': '14', 'lb': '24', 'tp': '13', 'wr': '0', 'as': '0', 'rg': '0'}
    #
    def response_action_00_08(self, metadata: list):
        self._log_debug(f"Received 08 Status: {metadata}")

        # If the zone is not initialised, then we just return the ID and serial
        if not self.zone.initialised:
            # Zone Index
            if ZoneStatusExtKeys.ID in metadata:
                self.zone.id = int(metadata[ZoneStatusExtKeys.ID])

            # Serial number and MAC address of ZONE 1
            if ZoneStatusExtKeys.SERIAL_NUMBER in metadata:
                # Always set VSSL first before zone
                if self.vssl.serial == None:
                    self.vssl._set_property(
                        "serial", metadata[ZoneStatusExtKeys.SERIAL_NUMBER]
                    )

                if self.zone.serial == None:
                    self.zone._set_property(
                        "serial", metadata[ZoneStatusExtKeys.SERIAL_NUMBER]
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
        # Not supported by X series?
        if ZoneStatusExtKeys.PARTY_MODE in metadata:
            pass

        # Group Index see below
        if ZoneStatusExtKeys.GROUP_INDEX in metadata:
            self.zone.group._set_property(
                "index", int(metadata[ZoneStatusExtKeys.GROUP_INDEX])
            )

        # Set Stream Source
        if ZoneStatusExtKeys.TRACK_SOURCE in metadata:
            self.zone.track.source = int(metadata[ZoneStatusExtKeys.TRACK_SOURCE])

        # Zone Enabled (0) or Disabled (1)
        if ZoneStatusExtKeys.DISABLED in metadata:
            self.zone.settings._set_property(
                "disabled", bool(int(metadata[ZoneStatusExtKeys.DISABLED]))
            )

    #
    # 00_09
    # EQ Status
    #
    # {'mono': '0', 'AiNm': 'Analog In 1', 'eq1': '100', 'eq2': '100', 'eq3': '100', 'eq4': '100',
    #  'eq5': '100', 'eq6': '100', 'eq7': '100', 'voll': '75', 'volr': '75', 'vold': '0'}
    #
    def response_action_00_09(self, metadata: list):
        self._log_debug(f"Received 09 Status: {metadata}")

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

    #
    # 00_0A
    # System Status 0A (Output / Amp)
    #
    # {'ECO': '0', 'eqsw': '1', 'inSrc': '0', 'SP': '0', 'BF1': '0', 'BF2': '0', 'BF3': '0',
    #  'GRM': '0', 'GRS': '255', 'Pwr': '0', 'Bvr': '1', 'fxv': '24', 'AtPwr': '1'}
    #
    def response_action_00_0A(self, metadata: list):
        self._log_debug(f"Received 0A Status: {metadata}")

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
        #  e.g BF1
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
                "is_master", int(metadata[ZoneRouterStatusExtKeys.GROUP_MASTER])
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

    #
    # 00_0B
    # Device Status Extended 0B
    #
    # {'IRMskL': '241', 'IRMskH': '255', 'BTSta': '0', 'Crs': '0', 'Fes': '0', 'Drk': '0'}
    #
    def response_action_00_0B(self, metadata: list):
        self._log_debug(f"Received 0B Status: {metadata}")

        # Bluetooth
        if DeviceStatusExtendedExtKeys.BLUETOOTH_STATUS in metadata:
            self.vssl.settings._set_property(
                "bluetooth", int(metadata[DeviceStatusExtendedExtKeys.BLUETOOTH_STATUS])
            )

        # Subwoofer Crossover
        if DeviceStatusExtendedExtKeys.SUBWOOFER_CROSSOVER in metadata:
            self.zone.settings.subwoofer._set_property(
                "crossover",
                int(metadata[DeviceStatusExtendedExtKeys.SUBWOOFER_CROSSOVER]),
            )

    #
    # 2A [42]
    # Stream Source
    #
    def response_action_2A(self, hexl: list, response: bytes):
        if hex_to_int(hexl[2]) == 2:
            source = hex_to_int(hexl[4])
            self._log_debug(f"Received stream source: {source}")
            self.zone.track.source = source

    #
    # 1E [30]
    # Received Analog Output Source Change
    #
    # Note: This is received on the zone which is the same as the output ID
    #
    def response_action_1E(self, hexl: list, response: bytes):
        if hex_to_int(hexl[2]) == 2:
            output = hex_to_int(hexl[3])
            source = hex_to_int(hexl[4])
            self._log_debug(f"Received analog output {output} source change: {source}")
            self.zone.analog_output._set_property("source", source)

    #
    # 4A [74]
    # Analog Output Fix Output Vol
    #
    # Note: This is received on the zone which is the same as the output ID
    #
    def response_action_4A(self, hexl: list, response: bytes):
        if hex_to_int(hexl[2]) == 2:
            output = hex_to_int(hexl[3])
            state = hex_to_int(hexl[4])
            self._log_debug(f"Received analog output {output} volume fixed: {state}")
            self.zone.analog_output._set_property("is_fixed_volume", bool(state))

    #
    # 04 [4]
    # Received Input Source
    #
    def response_action_04(self, hexl: list, response: bytes):
        if hex_to_int(hexl[2]) == 2:
            source = hex_to_int(hexl[4])
            self._log_debug(f"Received input source: {source}")
            self.zone.input._set_property("source", source)

    #
    # 06 [6]
    # Received Volume Data
    #
    def response_action_06(self, hexl: list, response: bytes):
        if hex_to_int(hexl[2]) == 3:
            vol = hex_to_int(hexl[4])
            vol_cmd = hex_to_int(hexl[5])

            self._log_debug(f"Received volume cmd: {vol_cmd} vol: {vol}")
            self._log_debug(f"Received volume {response.hex()}")

            # Analog input fixed gain
            if vol_cmd == 0:
                self.zone.settings.analog_input._set_property("fixed_gain", vol)

            # Max Left
            elif vol_cmd == 1:
                self.zone.settings.volume._set_property("max_left", vol)

            # Max Right
            elif vol_cmd == 2:
                self.zone.settings.volume._set_property("max_right", vol)

            # Normal Volume Change
            elif vol_cmd == 3:
                self.zone._set_property("volume", vol)

            # Defaul On Volume Change
            elif vol_cmd == 8:
                self.zone.settings.volume._set_property("default_on", vol)
        else:
            self._log_debug(f"Volume Error")

    #
    # 07 [7]
    # Transport State
    #
    # 0 = stop
    # 1 = play
    # 2 = pause
    #
    def response_action_07(self, hexl: list, response: bytes):
        if hex_to_int(hexl[2]) == 2:
            state = hex_to_int(hexl[4])
            self._log_debug(f"Received transport state: {state}")
            self.zone.transport._set_property("state", state)

    #
    # 0B [11]
    # Party Mode not supported on X series (I think. TODO)
    #
    def response_action_0B(self, hexl: list, response: bytes):
        pass

    #
    # 0E [14]
    # EQ
    #
    def response_action_0E(self, hexl: list, response: bytes):
        if hex_to_int(hexl[2]) == 3:
            freq = hex_to_int(hexl[4])
            value = hex_to_int(hexl[5])
            self._log_debug(f"Received EQ requency:{freq} value: {value}")
            self.zone.settings.eq._set_eq_freq(freq, value)

    #
    # 10 [16]
    # Mono output
    #
    def response_action_10(self, hexl: list, response: bytes):
        if hex_to_int(hexl[2]) == 2:
            state = hex_to_int(hexl[4])
            self._log_debug(f"Received mono ouput: {state}")
            self.zone.settings._set_property("mono", state)

    #
    # 12 [18]
    # Mute status
    #
    def response_action_12(self, hexl: list, response: bytes):
        if hex_to_int(hexl[2]) == 2:
            is_muted = bool(hex_to_int(hexl[4]))
            self._log_debug(f"Received mute status 12: {is_muted}")
            self.zone._set_property("mute", is_muted)

    #
    # 16 [22]
    # Received Analog Input Name
    #
    # TODO, maybe this should be global with the analog outputs
    #
    def response_action_16(self, hexl: list, response: bytes):
        self._log_debug(f"Received analog input name: {hexl}")

        input_id = hex_to_int(hexl[3])
        name = response[4:].decode("ascii")

        if input_id == self.zone.id:
            self._log_debug(f"Received analog input {input_id} name: {name}")
            self.zone.settings.analog_input._set_property("name", name.strip())

        # Optical Input
        elif input_id == 12:
            self._log_debug(f"Received optical input name: {name}")
            self.vssl.settings._set_property("optical_input_name", name.strip())

    #
    # 17 [23]
    # Keep Alive
    #
    def response_action_17(self, hexl: list, response: bytes):
        self._log_debug(f"Z{self.zone.id} Alpha - Received keep alive: {response}")
        # TODO
        pass

    #
    # 19 [25]
    # Received Device Name
    #
    def response_action_19(self, hexl: list, response: bytes):
        try:
            length = hex_to_int(hexl[2]) - 1
            name = response[
                self.JSON_HEADER_LENGTH : self.JSON_HEADER_LENGTH + length
            ].decode("ascii")

            self._log_debug(f"Received device name: {name}")

            self.vssl.settings._set_property("name", name.strip())

        except Exception as error:
            self._log_error(f"Exception occurred receiving device name: {error}")

    #
    # 26 [38]
    # Zone Enabled / Disabled Feedback
    #
    def response_action_26(self, hexl: list, response: bytes):
        if hex_to_int(hexl[2]) == 3:
            # hexl[4] is the zone id
            disabled = hex_to_int(hexl[5])
            self._log_debug(f"Received zone disable: {disabled}")
            self.zone.settings._set_property("disabled", bool(disabled))

    #
    # 2E [46]
    # EQ Switch
    #
    def response_action_2E(self, hexl: list, response: bytes):
        if hex_to_int(hexl[2]) == 2:
            enabled = hex_to_int(hexl[4])
            self._log_debug(f"Received EQ Switch: {enabled}")
            self.zone.settings.eq._set_property("enabled", bool(enabled))

    #
    # 32 [50]
    # = 'rm' key in the status object.
    #
    # A int is assigned to the zone when it starts playing.
    # When a zone joins a group it will allocated the same 'rm' number.
    #
    # When a stream is started, a 'rm' is allocated to the zone.
    # RM feedback is 0 when not playing and removed from a group
    def response_action_32(self, hexl: list, response: bytes):
        if hex_to_int(hexl[2]) == 2:
            index = hex_to_int(hexl[4])
            self._log_debug(f"Received group index: {index}")
            self.zone.group._set_property("index", int(index))

    #
    # 4C [76]
    # Group Response
    #
    def response_action_4C(self, hexl: list, response: bytes):
        self._log_debug(f"Received group info: {hexl}")

        if hex_to_int(hexl[2]) == 3:
            if hex_to_int(hexl[3]) != self.zone.id:
                self._log_warning(
                    f"Z{self.zone.id} Alpha - incorrect zone id in group response"
                )
                return

            self.zone.group._set_property("source", hex_to_int(hexl[5]))
            self.zone.group._set_property("is_master", hex_to_int(hexl[4]))

    #
    # 48 [72]
    # Input Priority Feedback
    #
    def response_action_48(self, hexl: list, response: bytes):
        if hex_to_int(hexl[2]) == 2:
            priority = hex_to_int(hexl[4])
            self._log_debug(f"Received input priority: {priority}")
            self.zone.input._set_property("priority", priority)

    #
    # 50 [80]
    # Adaptive Power Feedback
    #
    def response_action_50(self, hexl: list, response: bytes):
        if hex_to_int(hexl[2]) == 2:
            enabled = hex_to_int(hexl[4])
            self._log_debug(f"Received adaptive power setting: {enabled}")
            self.vssl.settings.power._set_property("adaptive", bool(int(enabled)))

    #
    # Command confimation
    #
    def response_action_confimation(self, response: bytes):
        cmd = response.hex()
        self._log_debug(
            f"Received command confimation: {hex_to_bytearray_string(cmd)} Hex: {cmd}"
        )

    #
    # Default
    # Default Action
    #
    def response_action_default(self, hexl: list, response: bytes):
        cmd = response.hex()
        self._log_debug(
            f"Received unknown command: {hex_to_bytearray_string(cmd)} Hex: {cmd}"
        )
