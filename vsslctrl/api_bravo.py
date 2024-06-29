#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json
import struct
import logging

from .api_base import APIBase
from .utils import hex_to_int, hex_to_bytearray_string
from .decorators import logging_helpers
from .data_structure import TrackMetadataExtKeys


@logging_helpers()
class APIBravo(APIBase):
    TCP_PORT = 7777
    HEADER_LENGTH = 10

    def __init__(self, vssl_host: "vssl.VSSL", zone: "zone.Zone"):
        super().__init__(host=zone.host, port=self.TCP_PORT)

        self._log_prefix = f"Zone {zone.id}: Bravo API:"

        self.vssl = vssl_host
        self.zone = zone

    #
    # Send keep alive
    #
    def _send_keepalive(self):
        self.request_action_03()

    #
    #
    #
    # Requests
    #
    #
    #
    def _build_request(self, command: int, get=True):
        setget = 1 if get else 2
        return bytearray([170, 170, setget, command, 0, 0, 0, 0])

    #
    # Request with data
    #
    def _build_request_with_data(self, cmd: int, data: str):
        command = self._build_request(cmd, False)
        command.extend(struct.pack(">B", len(data)))
        command.extend([0])
        command.extend(data.encode("utf-8"))
        return command

    #
    # 03 [3]
    # Keep alive
    #
    def request_action_03(self):
        self._log_debug("Sending keep alive with IP")
        self.send(self._build_request_with_data(3, self.zone.host))

    #
    # 5A [90]
    # Zone Name - Request
    #
    def request_action_5A(self):
        self._log_debug("Requesting name")
        command = self._build_request(90)
        command.extend([0, 0])
        self.send(command)

    #
    # 5A [90]
    # Zone Name - Rename
    #
    def request_action_5A_set(self, name: str):
        self._log_debug(f"Requesting to set name: {name}")
        self.send(self._build_request_with_data(90, name))

    #
    # 5B [91]
    # MAC Address
    #
    def request_action_5B(self):
        self._log_debug("Requesting MAC address")
        command = self._build_request(91)
        command.extend([0, 0])
        self.send(command)

    #
    # 2A [42]
    # Track Metadata
    #
    def request_action_2A(self):
        self._log_debug("Requesting track metadata")
        command = self._build_request(42)
        command.extend([0, 0])
        self.send(command)

    #
    # 28 [40]
    # Track Next
    #
    # b'\xaa\xaa\x01(\x00\x00\x00\x00\x04\x00NEXT'
    # aaaa01280000000004004e455854
    #
    def request_action_40_next(self):
        self._log_debug("Requesting next track")
        command = self._build_request(40, False)
        command.extend([4, 0, 78, 69, 88, 84])
        self.send(command)

    #
    # 28 [40]
    # Track Previous
    #
    # b'\xaa\xaa\x01(\x00\x00\x00\x00\x08\x00PREV'
    # aaaa012800000000080050524556
    #
    def request_action_40_prev(self):
        self._log_debug("Requesting previous track")
        command = self._build_request(40, False)
        command.extend([8, 0, 80, 82, 69, 86])
        self.send(command)

    #
    # 40 [64]
    # Zone Volume
    #
    def request_action_64(self):
        self._log_debug("Requesting volume")
        command = self._build_request(64)
        command.extend([0, 0])
        self.send(command)

    #
    #
    #
    # Respsonses
    #
    #
    #

    #
    # Handle Response
    #

    async def _read_byte_stream(self, reader, data):
        data += await reader.readexactly(self.HEADER_LENGTH - APIBase.FRIST_BYTE)

        length = int.from_bytes(data[8:10], "big")

        data += await reader.readexactly(length)

        self._log_debug(f"Response: {data}")

        await self._handle_response(data)

    async def _handle_response(self, response: bytes):
        try:
            # Convert to HEX and split into a array
            hexl = response.hex("-").split("-")
            action = f"response_action_{hexl[4].upper()}"
            length = hexl[2]

            self._log_debug(f"Response action: {action}")

        except Exception as error:
            self._log_error(f"Couldnt handle response: {error} | {hexl} | {response}")
            return None

        if hasattr(self, action):
            method = getattr(self, action)
            if callable(method):
                return method(hexl, response)
        # Default
        return self.response_action_default(hexl, response)

    #
    # Extract Data
    #
    def _extract_response_data(self, response: bytes, length_index: int = 9):
        try:
            header = response[:9]
            length_field = response[8:10]
            length = int.from_bytes(length_field, "big")
            return response[10 : 10 + length].decode("ascii")
        except Exception as e:
            self._log_error(
                f"Unable to extract response data. Exception: {e} | Response: {hexl}"
            )

    #
    # 03 [3]
    # Keep Alive
    #
    def response_action_03(self, hexl: list, response: bytes):
        if hex_to_int(hexl[5]) != 1:
            self._log_debug(f"Couldnt register, trying again", "critical")
            self.request_action_03()

        self._log_debug(f"Received keep alive")

    #
    # 5A [90]
    # Zone Name
    #
    def response_action_5A(self, hexl: list, response: bytes):
        name = self._extract_response_data(response)
        self._log_debug(f"Received zone name: {name}")
        self.zone.settings._set_property("name", name.strip())

    #
    # 31 [49]
    # Progress
    #
    def response_action_31(self, hexl: list, response: bytes):
        self.zone.track.progress = int(self._extract_response_data(response))

    #
    # 2A [42]
    # Track Metadata
    #
    def response_action_2A(self, hexl: list, response: bytes):
        """

        Example PlayView Response:

        {'Album': 'International Skankers', 'Artist': 'Ashkabad', 'BitDepth': 16,
        'BitRate': '320000', 'CoverArtUrl': 'https://i.scdn.co/image/ab67616d0000b2730cbb03a339c6ffd18d10eab2',
        'Current Source': 4, 'Current_time': -1, 'DSDType': '', 'Fav': False, 'FileSize': 0, 'Genre': '',
        'Index': 0, 'Mime': 'Ogg', 'Next': False, 'PlayState': 0, 'PlayUrl': 'spotify:track:0IHTiLO5qBYhf7Hmn0UDBN',
        'Prev': False, 'Repeat': 0, 'SampleRate': '44100', 'Seek': False, 'Shuffle': 0, 'SinglePlay': False,
        'TotalTime': 203087, 'TrackName': 'Beijing'}
        """
        try:
            jsonr = response[10:]
            metadata = json.loads(jsonr)
            # CMD ID = 1 BrowseView - VSSL File Browser
            # CMD ID = 3 PlayView (Track Info)
            if (
                TrackMetadataExtKeys.COMMAND_ID in metadata
                and metadata[TrackMetadataExtKeys.COMMAND_ID] == 3
            ):
                track_data = metadata[TrackMetadataExtKeys.WINDOW_CONTENTS]
                self.zone.track._map_response_dict(track_data)
                self.zone.transport._map_response_dict(track_data)
            else:
                self._log_debug(
                    f"{metadata[TrackMetadataExtKeys.WINDOW_TITLE]} is currently unsupported: {metadata}"
                )

        except Exception as e:
            self._log_error(f"Unable to parse JSON. Exception: {e} | Response: {hexl}")

    #
    # 2D [45]
    # Track Metadata from Track Next and Track Previous responses
    #
    def response_action_2D(self, hexl: list, response: bytes):
        self.response_action_2A(hexl, response)

    #
    # 32 [50]
    # Track Source Update
    #
    def response_action_32(self, hexl: list, response: bytes):
        self.zone.track.source = int(self._extract_response_data(response))
        self._log_debug(f"Received stream source: {self.zone.track.source}")

    #
    # 33 [51]
    # Transport State
    #
    # Note: This state is different from the Alpha API
    #
    # Returns:
    # Play = 0
    # Stop = 1
    # Pause = 2
    #
    def response_action_33(self, hexl: list, response: bytes):
        """
        Alpha API will handle transport state

        self._log_debug(f"Received transport state 33: {hexl}")
        state = int(self._extract_response_data(response))

        if state == 0:
            self.zone.transport._set_state(ZoneTransport.States.PLAY)
        elif state == 1:
            self.zone.transport._set_state(ZoneTransport.States.STOP)
        else:
            self.zone.transport._set_state(state)

        """
        return

    #
    # 36 [54]
    # Errors and Success
    #
    # e.g When we play a URL directy, we get "success" on play then "error_nonextsong"
    #
    # success
    # error_playfail
    # error_nonextsong
    #
    def response_action_36(self, hexl: list, response: bytes):
        feedback = self._extract_response_data(response).split("_")
        if len(feedback) > 1:
            self._log_debug(f"Received feedback {feedback[0]}: {feedback[1]}")
        else:
            self._log_debug(f"Received feedback: {feedback[0]}")

    #
    # 3F [63]
    # Mute Status
    #
    def response_action_3F(self, hexl: list, response: bytes):
        """
        Alpha API will handle the mute feedback

        state = self._extract_response_data(response)
        self._log_debug(f"Received mute status: {state}")
        if state == "MUTE":
            self.zone._set_property('mute', True)
        elif state == "UNMUTE":
            self.zone._set_property('mute', False)

        """
        return

    #
    # 40 [64]
    # Zone Volume Feedback
    #
    def response_action_40(self, hexl: list, response: bytes):
        """
        Alpha API will handle the volume, there is some strange behavior
        that the Bravo API gets a 0 vol when the zone is muted, but then
        the device status responses with the actual volume level, even
        though the zone is muted.

        vol = int(self._extract_response_data(response))
        self._log_debug(f"Received volume: {vol}%")
        self.zone._set_property('volume', int(vol))

        """
        return

    #
    # 46 [70]
    # Unknown | Speaker active / inactive
    #
    def response_action_46(self, hexl: list, response: bytes):
        self._log_debug(f"Received Unknown 46: {self._extract_response_data(response)}")

        """
            This looks to be a stream update, Speaker active and stream input. 
            SPEAKER_INACTIVE or SPEAKER_ACTIVE plus the source input e,g 24. example:

            b'\x00\x00\x02\x00F\x00\xa4\xce\x00\x12SPEAKER_INACTIVE,4\x00\x00\x02\x002\x00P*\x00\x0224'
            b'\x00\x00\x02\x00F\x00\xd2\xac\x00\x13SPEAKER_INACTIVE,24\x00\x00\x02\x001\x00yc\x00\x05-1000'
            ex: SPEAKER_INACTIVE,24
            ex: SPEAKER_INACTIVE,4

        """

    #
    # 4E [78]
    # Unknown | Looks to be like a comfirmation feedback
    #
    def response_action_4E(self, hexl: list, response: bytes):
        self._log_debug(f"Received Unknown 4E: {self._extract_response_data(response)}")

        """

            self._log_debug(f"Looks to be the play & volume feedback, possibly end of stream / stop feedback?")
            Feecback when rebooting zone

        """

    #
    # 4F [79]
    # Unknown | Status Change?!
    #
    def response_action_4F(self, hexl: list, response: bytes):
        self._log_debug(f"Received Unknown 4F {self._extract_response_data(response)}")

    #
    # 5B [91]
    # MAC Address
    #
    def response_action_5B(self, hexl: list, response: bytes):
        mac = self._extract_response_data(response)
        self._log_debug(f"Received MAC address: {mac}")
        self.zone._set_property("mac_addr", mac)

    #
    # 70 [112]
    # System Status
    #
    # This is the confirmation that the device actually received the commands.
    # This is a great way to discover the VSSL API
    #
    # NOTE: This will be a feedback for ALL zones not just this zone
    #
    def response_action_70(self, hexl: list, response: bytes):
        length = 4 if hexl[0] == 16 else 10
        cmd = response[length:].hex()
        self._log_debug(
            f"Received command confimation: {hex_to_bytearray_string(cmd)} Hex: {cmd}"
        )

    #
    # Default
    # Default Action
    #
    def response_action_default(self, hexl: list, response: bytes):
        string = self._extract_response_data(response)
        self._log_debug(f"Unknown command {hexl[1].upper()}: {string}")
