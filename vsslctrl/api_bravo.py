#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json
import struct
import logging

from . import LOG_DIVIDER
from .api_base import APIBase
from .decorators import logging_helpers
from .data_structure import TrackMetadataExtKeys


@logging_helpers()
class APIBravo(APIBase):
    """

    TCP Frame Structure:
    ---------------------------------------------------------------------------------------
    | 170 | 170 | [get: 1 / set: 2] | command | 0 | 0 | 0 | 0 | Length of Data | 0 | Data |
    ---------------------------------------------------------------------------------------

    Port Info:

    Zone discovery occurs over multicast UDP on ports 1800 and 1900.
    The VSSL app communicates with the VSSL amplifier over all zones on ports 7777 and 50002.

    """

    HEADER_LENGTH = 10

    # Protocol frame byte positions (zero indexed)
    FRAME_CMD_HI = 4
    FRAME_DATA_LENGTH = slice(8, 10)
    # Protocol frame header length (first 10 bytes are the header)
    FRAME_HEADER_LENGTH = 10
    # Port Number
    TCP_PORT = 7777

    # JSON Structure
    WINDOW_CONTENTS = "Window CONTENTS"

    #
    # API Events
    #
    class Events:
        PREFIX = "zone.api.bravo."
        CONNECTING = PREFIX + "connecting"
        CONNECTED = PREFIX + "connected"
        DISCONNECTING = PREFIX + "disconnecting"
        DISCONNECTED = PREFIX + "disconnected"
        RECONNECTING = PREFIX + "reconnecting"

    def __init__(self, vssl_host: "vssl.VSSL", zone: "zone.Zone"):
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
        return f"Zone {zone}: bravo api:"

    ##########################################################
    #
    # Publish Event
    #
    ##########################################################
    def _event_publish(self, event_type, data=None):
        self.zone._event_publish(event_type, data)

    #
    # Send keep alive
    #
    def _send_keepalive(self):
        self.request_action_03()

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
        command.extend(self._encode_frame_data(data))
        return command

    ##########################################################
    #
    # Read Byte Stream
    #
    ##########################################################

    async def _read_byte_stream(self, reader, first_byte: bytes):
        frame_header = first_byte + await reader.readexactly(
            self.FRAME_HEADER_LENGTH - APIBase.FIRST_BYTE  # already have the first byte
        )

        # Index 8 & 9 make up the data length
        length = int.from_bytes(frame_header[self.FRAME_DATA_LENGTH], "big")

        # Read the frame data
        frame_data = await reader.readexactly(length)

        self._log_debug(LOG_DIVIDER)
        self._log_debug(f"↓ rec: header: {frame_header.hex(' ')}")
        self._log_debug(f"↓ rec: data hex: {frame_data.hex(' ')}")
        self._log_debug(f"↓ rec: data ascii: {self._decode_frame_data(frame_data)}")
        self._log_debug(LOG_DIVIDER)

        try:
            await self._handle_response(frame_header, frame_data)

        except Exception as error:
            self._log_error(
                f"error handling response: {error} | {frame_header + frame_data}"
            )

    ##########################################################
    #
    # Handle Response
    #
    ##########################################################

    async def _handle_response(self, frame_header: bytes, frame_data: bytes):
        cmd = (
            bytes([frame_header[self.FRAME_CMD_HI]]).hex().upper()
        )  # byte array to padded hex string

        self._log_debug(f"↓ rec: command: {cmd}")

        # Handle Command Response
        try:
            action_fn = f"response_action_{cmd}"

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
    # Command confirmation - system status?
    #
    # CMD: 70 [112]
    #
    ##########################################################

    def response_action_70(self, frame_header: bytes, frame_data: bytes):
        """

        The action is called when the device receives a command. When we send a command from the
        alpha api, we can also see a response here.

        This is a good way to figure out the api of the vssl, but dont think it will be used.

        NOTE: This will be a feedback for ALL zones not just this zone

        """
        self._log_debug(LOG_DIVIDER)
        self._log_debug(
            f"↓ rec: command confimation - header: {frame_header.hex(' ')} | data: {frame_data.hex(' ')} | ascii: {self._decode_frame_data(frame_data)}"
        )
        self._log_debug(LOG_DIVIDER)

    ##########################################################
    #
    # Default action when no receive command is defined
    #
    ##########################################################

    def response_action_default(self, frame_header: bytes, frame_data: bytes):
        cmd = bytes(
            [frame_header[self.FRAME_CMD_HI]]
        ).hex()  # byte array to padded hex string

        string = self._decode_frame_data(frame_data)
        self._log_debug(f"↓ rec: unknown command {cmd.upper()}: {string}")

    ##########################################################
    #
    # Keep alive - Register?
    #
    # CMD: 03 [3]
    #
    # Includes the IP address
    #
    ##########################################################

    #
    # Request
    #
    def request_action_03(self):
        self._log_debug("↑ req: keep alive")
        self.send(self._build_request_with_data(3, self.zone.host))

    #
    # Response
    #
    def response_action_03(self, frame_header: bytes, frame_data: bytes):
        if frame_header[5] != 1:
            self._log_error(f"failed to register")
            self.request_action_03()

        self._log_debug(f"↓ rec: regisitered OK")

    ##########################################################
    #
    # Unknown
    #
    # CMD: 67 [103]
    #
    ##########################################################

    #
    # Request
    #
    def request_action_67(self):
        self._log_debug("↑ req: unknown")
        command = self._build_request(103)
        command.extend([0, 0])
        self.send(command)

    #
    # Response
    #
    def response_action_67(self, frame_header: bytes, frame_data: bytes):
        self.response_action_default(frame_header, frame_data)

    ##########################################################
    #
    # Unknown
    #
    # CMD: 07 [7]
    #
    ##########################################################

    #
    # Request
    #
    def request_action_07(self):
        self._log_debug("↑ req: unknown")
        command = self._build_request(7)
        command.extend([0, 0])
        self.send(command)

    #
    # Response
    #
    def response_action_07(self, frame_header: bytes, frame_data: bytes):
        self.response_action_default(frame_header, frame_data)

    ##########################################################
    #
    # Provisioning Info
    #
    # CMD: EA [234]
    #
    ##########################################################

    #
    # Request
    #
    def request_action_EA(self):
        self._log_debug("↑ req: provisioning info")
        command = self._build_request(234)
        command.extend([0, 0])
        self.send(command)

    #
    # Response
    #
    def response_action_EA(self, frame_header: bytes, frame_data: bytes):
        try:
            json_data = json.loads(frame_data)

            if self.WINDOW_CONTENTS in json_data:
                provisioning_info = json_data[self.WINDOW_CONTENTS]
                self._log_error(provisioning_info)

        except Exception as error:
            self._log_error(
                f"Unable to parse JSON - exception: {error} | frame data: {frame_data}"
            )

    ##########################################################
    #
    # Zone Name
    #
    # CMD: 5A [90]
    #
    ##########################################################

    #
    # Request - Set
    #
    def request_action_5A_set(self, name: str):
        self._log_debug(f"↑ req: to set zone name: {name}")
        self.send(self._build_request_with_data(90, name))

    #
    # Request - Get
    #
    def request_action_5A(self):
        self._log_debug("↑ req: zone name")
        command = self._build_request(90)
        command.extend([0, 0])
        self.send(command)

    #
    # Response
    #
    def response_action_5A(self, frame_header: bytes, frame_data: bytes):
        name = self._decode_frame_data(frame_data)
        self._log_debug(f"↓ rec: zone name: {name}")
        self.zone.settings._set_property("name", name)

    ##########################################################
    #
    # MAC Address
    #
    # CMD: 5B [91]
    #
    # Note: On a factory A.1x this returns the IP address with padded zeros.
    # e.g 010.010.030.013 - Once setup a MAC will be returned
    #
    ##########################################################

    #
    # Request
    #
    def request_action_5B(self):
        self._log_debug("↑ req: MAC address")
        command = self._build_request(91)
        command.extend([0, 0])
        self.send(command)

    #
    # Response
    #
    def response_action_5B(self, frame_header: bytes, frame_data: bytes):
        mac = self._decode_frame_data(frame_data)
        self._log_debug(f"↓ rec: MAC address {mac}")
        self.zone._set_property("mac_addr", mac)

    ##########################################################
    #
    # Transport Commands
    #
    # CMD: 28 [40]
    #
    ##########################################################

    #
    # Transport - Next
    #
    def request_action_28_next(self):
        self._log_debug("↑ req: next track")
        self.send(self._build_request_with_data(40, "NEXT"))

    #
    # Transport - Previous
    #
    def request_action_28_prev(self):
        self._log_debug("↑ req: previous track")
        self.send(self._build_request_with_data(40, "PREV"))

    #
    # Transport - Pause
    #
    def request_action_28_pause(self):
        self._log_debug("↑ req: previous track")
        self.send(self._build_request_with_data(40, "PAUSE"))

    #
    # Transport - Play
    #
    def request_action_28_play(self):
        self._log_debug("↑ req: previous track")
        self.send(self._build_request_with_data(40, "PLAY"))

    #
    # Transport - Stop
    #
    def request_action_28_stop(self):
        self._log_debug("↑ req: previous track")
        self.send(self._build_request_with_data(40, "STOP"))

    ##########################################################
    #
    # Track Metadata
    #
    # CMD: 2A [42]
    #
    ##########################################################

    #
    # Request
    #
    def request_action_2A(self):
        self._log_debug("↑ req: track metadata")
        command = self._build_request(42)
        command.extend([0, 0])
        self.send(command)

    #
    # Response
    #
    def response_action_2A(self, frame_header: bytes, frame_data: bytes):
        """
        Example PlayView Response:

        {"CMD ID":3,"Title":"PlayView","Window CONTENTS":{"Album":"So Tonight That I Might See","Artist":"Mazzy Star",
        "BitDepth":16,"BitRate":"320000","CoverArtUrl":"https://i.scdn.co/image/ab67616d0000b27389a392107ebd79818022b3ea",
        "Current Source":4,"Current_time":-1,"DSDType":"","Fav":false,"FileSize":0,"Genre":"","Index":0,"Mime":"Ogg","Next":true,
        "PlayState":0,"PlayUrl":"spotify:track:3BdHMOIA9B0bN53jbE5nWe","Prev":true,"Repeat":0,"SampleRate":"44100","Seek":true,
        "Shuffle":0,"SinglePlay":false,"TotalTime":310733,"TrackName":"Blue Light"}}
        """
        try:
            metadata = json.loads(frame_data)

            # CMD ID = 1 BrowseView - VSSL File Browser
            # CMD ID = 3 PlayView (Track Info)
            if (
                TrackMetadataExtKeys.COMMAND_ID in metadata
                and metadata[TrackMetadataExtKeys.COMMAND_ID] == 3
            ):
                track_data = metadata[self.WINDOW_CONTENTS]
                self.zone.track._map_response_dict(track_data)
                self.zone.transport._map_response_dict(track_data)
            else:
                self._log_debug(
                    f"{metadata[TrackMetadataExtKeys.WINDOW_TITLE]} is currently unsupported: {metadata}"
                )

        except Exception as error:
            self._log_error(
                f"Unable to parse JSON - exception: {error} | frame data: {frame_data}"
            )

    ##########################################################
    #
    # Track - Metadata
    #
    # CMD: 2D [45]
    #
    # Track Metadata from Track Next and Track Previous responses
    #
    ##########################################################

    def response_action_2D(self, frame_header: bytes, frame_data: bytes):
        self.response_action_2A(frame_header, frame_data)

    ##########################################################
    #
    # Zone Volume
    #
    # CMD: 40 [64]
    #
    ##########################################################

    #
    # Request
    #
    def request_action_64(self):
        self._log_debug("↑ req: volume")
        command = self._build_request(64)
        command.extend([0, 0])
        self.send(command)

    ##########################################################
    #
    # Track - Progress
    #
    # CMD: 31 [49]
    #
    ##########################################################

    def response_action_31(self, frame_header: bytes, frame_data: bytes):
        self.zone.track.progress = int(self._decode_frame_data(frame_data))

    ##########################################################
    #
    # Track - Source
    #
    # CMD: 32 [50]
    #
    ##########################################################

    def response_action_32(self, frame_header: bytes, frame_data: bytes):
        self.zone.track.source = int(self._decode_frame_data(frame_data))
        self._log_debug(f"↓ rec: stream source: {self.zone.track.source}")

    ##########################################################
    #
    # Track - State
    #
    # CMD: 33 [51]
    #
    # Play = 0
    # Stop = 1
    # Pause = 2
    #
    # note: state is different from the alpha api
    #
    ##########################################################

    def response_action_33(self, frame_header: bytes, frame_data: bytes):
        # Alpha API will handle transport states
        pass

    ##########################################################
    #
    # Mute Status ?
    #
    # CMD: 3F [63]
    #
    ##########################################################

    def response_action_3F(self, frame_header: bytes, frame_data: bytes):
        """
        Alpha API will handle the mute feedback

        state = self._decode_frame_data(frame_data)
        self._log_debug(f"↓ rec: mute status: {state}")
        if state == "MUTE":
            self.zone._set_property('mute', True)
        elif state == "UNMUTE":
            self.zone._set_property('mute', False)

        """
        self._log_debug(f"↓ rec: mute feedback")

    ##########################################################
    #
    # Unknown - Errors and Success Text Status
    #
    # CMD: 36 [54]
    #
    # e.g When we play a URL directy, we get "success" on play then "error_nonextsong"
    #
    # success
    # error_playfail
    # error_nonextsong
    #
    #
    ##########################################################

    def response_action_36(self, frame_header: bytes, frame_data: bytes):
        feedback = self._decode_frame_data(frame_data).split("_")
        self._log_debug(LOG_DIVIDER)
        if len(feedback) > 1:
            self._log_debug(f"↓ rec: feedback {feedback[0]}: {feedback[1]}")
        else:
            self._log_debug(f"↓ rec: feedback: {feedback[0]}")
        self._log_debug(LOG_DIVIDER)

    ##########################################################
    #
    # Unknown - Speaker active / inactive
    #
    # CMD: 46 [70]
    #
    ##########################################################

    def response_action_46(self, frame_header: bytes, frame_data: bytes):
        """
        This looks to be a stream update, Speaker active and stream input.
        SPEAKER_INACTIVE or SPEAKER_ACTIVE plus the source input e,g 24. example:

        b'\x00\x00\x02\x00F\x00\xa4\xce\x00\x12SPEAKER_INACTIVE,4\x00\x00\x02\x002\x00P*\x00\x0224'
        b'\x00\x00\x02\x00F\x00\xd2\xac\x00\x13SPEAKER_INACTIVE,24\x00\x00\x02\x001\x00yc\x00\x05-1000'
        ex: SPEAKER_INACTIVE,24
        ex: SPEAKER_INACTIVE,4

        """
        self._log_debug(f"↓ rec: unknown 46")

    ##########################################################
    #
    # Unknown - Looks to be like a comfirmation feedback
    #
    # CMD: 4E [78]
    #
    ##########################################################

    def response_action_4E(self, frame_header: bytes, frame_data: bytes):
        """

        self._log_debug(f"Looks to be the play & volume feedback, possibly end of stream / stop feedback?")
        Feecback when rebooting zone

        """
        self._log_debug(f"↓ rec: unknown 4E")

    ##########################################################
    #
    # Unknown - Status Change?!
    #
    # CMD: 4F [79]
    #
    ##########################################################

    def response_action_4F(self, frame_header: bytes, frame_data: bytes):
        self._log_debug(f"↓ rec: unknown 4F")

    ##########################################################
    #
    # Zone Volume Feedback
    #
    # CMD: 40 [64]
    #
    ##########################################################

    def response_action_40(self, frame_header: bytes, frame_data: bytes):
        """
        Alpha API will handle the volume, there is some strange behavior
        that the Bravo API gets a 0 vol when the zone is muted, but then
        the device status responses with the actual volume level, even
        though the zone is muted.

        vol = int(self._decode_frame_data(frame_data))
        self._log_debug(f"↓ rec: volume: {vol}%")
        self.zone._set_property('volume', int(vol))

        """
        self._log_debug(f"↓ rec: unknown 40 - volume?")
