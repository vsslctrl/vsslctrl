import re
from enum import Enum, IntEnum
from abc import ABC, abstractmethod
from .decorators import sterilizable


class VsslEnum(Enum):
    @classmethod
    def is_valid(cls, value):
        try:
            cls(value)
            return True
        except ValueError:
            return False

    @classmethod
    def is_not_valid(cls, value):
        return not cls.is_valid(value)

    @classmethod
    def get(cls, value, default=None):
        try:
            return cls(value)
        except ValueError:
            return default


class VsslIntEnum(VsslEnum, IntEnum):
    """IntEnum"""


#
# Zones IDs
#
# Moved here to help with circular imports
#
class ZoneIDs(VsslIntEnum):
    ZONE_1 = 1
    ZONE_2 = 2
    ZONE_3 = 3
    ZONE_4 = 4
    ZONE_5 = 5
    ZONE_6 = 6


"""
JSON Structure

DO NOT CHANGE - VSSL Defined

A3.x
{
    "B1Src": "3",
    "B2Src": "4",
    "B3Src": "5",
    "B1Nm": "",
    "B2Nm": "Optical In",
    "dev": "Device Name",
    "ver": "p15305.016.3701"
}

A6.x
{
    "B1Src": "3",
    "B2Src": "4",
    "B3Src": "5",
    "B4Src": "6",
    "B5Src": "7",
    "B6Src": "8",
    "B1Nm": "",
    "B2Nm": "",
    "dev": "VSSL A.6x",
    "ver": "p15305.017.3701"
}
"""


class DeviceStatusExtKeys:
    ANALOG_OUTPUT_1_SOURCE = "B1Src"
    ANALOG_OUTPUT_2_SOURCE = "B2Src"
    ANALOG_OUTPUT_3_SOURCE = "B3Src"
    ANALOG_OUTPUT_4_SOURCE = "B4Src"
    ANALOG_OUTPUT_5_SOURCE = "B5Src"
    ANALOG_OUTPUT_6_SOURCE = "B6Src"
    UNKNOWN = "B1Nm"  # Party mode bus?
    OPTICAL_INPUT_NAME = "B2Nm"  # For A.3x this is the optical input name
    DEVICE_NAME = "dev"
    SW_VERSION = "ver"

    @staticmethod
    def add_zone_to_bus_key(zone_id: int):
        return f"B{zone_id}Src"


"""
JSON Structure

DO NOT CHANGE - VSSL Defined


 IRMskL / IRMskH:
 These could potentially be related to Infrared (IR) remote control signals. "IRMskL" and "IRMskH" might represent the low and high values of the modulation frequency or pulse width for an infrared signal.

 BTSta:
 This might represent the Bluetooth status, with "0" indicating that Bluetooth is currently not active or disconnected.

 Crs:
 It could stand for "Crossfade" and may represent a setting related to crossfading between audio tracks.

 Fes:
 This might stand for "Frequency" or "Filter Effect Setting," representing a parameter related to frequency or filtering effects.

 Drk: ?


A3.x
{
    'IRMskL': '241', 
    'IRMskH': '255', 
    'BTSta': '0', 
    'Crs': '0', 
    'Fes': '0', 
    'Drk': '0'
}

A6.x
{
    "IRMskL":"255",
    "IRMskH":"255",
    "BTSta":"0",
    "Crs":"0",
    "Fes":"0",
    "Drk":"0"
'

"""


class DeviceStatusExtendedExtKeys:
    IR_HIGH = "IRMskH"  # Guess - To Confirm
    IR_LOW = "IRMskL"  # Guess - To Confirm
    BLUETOOTH_STATUS = "BTSta"  # Guess - To Confirm
    SUBWOOFER_CROSSOVER = "Crs"  # Guess - To Confirm


"""
JSON Structure

DO NOT CHANGE - VSSL Defined

A3.x
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

A6.x
{
    "id": "1",
    "ac": "0",
    "mc": "XXXXXXXXXXXX",
    "vol": "50",
    "mt": "0",
    "pa": "0",
    "rm": "0",
    "ts": "0",
    "alex": "126",
    "nmd": "0",
    "ird": "255",
    "lb": "17",
    "tp": "16",
    "wr": "0",
    "as": "0",
    "rg": "0"
}
"""


class ZoneStatusExtKeys:
    ID = "id"
    TRANSPORT_STATE = "ac"
    SERIAL_NUMBER = "mc"
    VOLUME = "vol"
    MUTE = "mt"
    PARTY_MODE = "pa"
    GROUP_INDEX = "rm"
    TRACK_SOURCE = "lb"
    DISABLED = "wr"


"""
JSON Structure

DO NOT CHANGE - VSSL Defined

A3.x
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

A6.x
{
    "mono": "0",
    "AiNm": "",
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


class ZoneEQStatusExtKeys:
    MONO = "mono"
    ANALOG_INPUT_NAME = "AiNm"
    HZ60 = "eq1"
    HZ200 = "eq2"
    HZ500 = "eq3"
    KHZ1 = "eq4"
    KHZ4 = "eq5"
    KHZ8 = "eq6"
    KHZ15 = "eq7"
    VOL_MAX_LEFT = "voll"
    VOL_MAX_RIGHT = "volr"
    VOL_DEFAULT_ON = "vold"


"""
JSON Structure

DO NOT CHANGE - VSSL Defined

A3.x
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

A6.x
{
    "ECO": "0",
    "eqsw": "1",
    "inSrc": "0",
    "SP": "0",
    "BF1": "0",
    "BF2": "0",
    "BF3": "0",
    "BF4": "0",
    "BF5": "0",
    "BF6": "0",
    "GRM": "0",
    "GRS": "255",
    "Pwr": "0",
    "Bvr": "2",
    "fxv": "25",
    "AtPwr": "1"
}
"""


class ZoneRouterStatusExtKeys:
    EQ_ENABLED = "eqsw"
    INPUT_SOURCE = "inSrc"
    SOURCE_PRIORITY = "SP"
    ANALOG_OUTPUT_1_FIXED_VOLUME = "BF1"
    ANALOG_OUTPUT_2_FIXED_VOLUME = "BF2"
    ANALOG_OUTPUT_3_FIXED_VOLUME = "BF3"
    ANALOG_OUTPUT_4_FIXED_VOLUME = "BF4"
    ANALOG_OUTPUT_5_FIXED_VOLUME = "BF5"
    ANALOG_OUTPUT_6_FIXED_VOLUME = "BF6"
    GROUP_SOURCE = "GRS"
    GROUP_MASTER = "GRM"
    POWER_STATE = "Pwr"
    ANALOG_INPUT_FIXED_GAIN = "fxv"
    ADAPTIVE_POWER = "AtPwr"

    @staticmethod
    def add_zone_to_ao_fixed_volume_key(zone_id: int):
        return f"BF{zone_id}"


"""
JSON Structure

DO NOT CHANGE - VSSL Defined

{
    "Album": "International Skankers",
    "Artist": "Ashkabad",
    "BitDepth": 16,
    "BitRate": "320000",
    "CoverArtUrl": "https://i.scdn.co/image/ab67616d0000b2730cbb03a339c6ffd18d10eab2",
    "Current Source": 4,
    "Current_time": -1,
    "DSDType": "",
    "Fav": False,
    "FileSize": 0,
    "Genre": "",
    "Index": 0,
    "Mime": "Ogg",
    "Next": False,
    "PlayState": 0,
    "PlayUrl": "spotify:track:0IHTiLO5qBYhf7Hmn0UDBN",
    "Prev": False,
    "Repeat": 0,
    "SampleRate": "44100",
    "Seek": False,
    "Shuffle": 0,
    "SinglePlay": False,
    "TotalTime": 203087,
    "TrackName": "Beijing"
}
"""


class TrackMetadataExtKeys:
    COMMAND_ID = "CMD ID"
    WINDOW_CONTENTS = "Window CONTENTS"
    WINDOW_TITLE = "Title"
    DURATION = "TotalTime"
    TITLE = "TrackName"
    ALBUM = "Album"
    ARTIST = "Artist"
    COVER_ART_URL = "CoverArtUrl"
    SOURCE = "Current Source"
    GENRE = "Genre"
    URL = "PlayUrl"


@sterilizable
class VsslDataClass(ABC):
    def _set_property(self, property_name: str, new_value):
        log = False
        direct_setter = f"_set_{property_name}"

        if hasattr(self, direct_setter):
            log = getattr(self, direct_setter)(new_value)
        else:
            current_value = getattr(self, property_name)
            if current_value != new_value:
                setattr(self, f"_{property_name}", new_value)
                log = True

        if log:
            updated_value = getattr(self, property_name)

            message = ""
            if isinstance(updated_value, IntEnum):
                message = f"{self.__class__.__name__} set {property_name}: {updated_value.name} ({updated_value.value})"
            else:
                message = (
                    f"{self.__class__.__name__} set {property_name}: {updated_value}"
                )

            self._vssl._log_debug(message)

            self._vssl.event_bus.publish(
                getattr(self.Events, property_name.upper() + "_CHANGE"),
                self._vssl.ENTITY_ID,
                updated_value,
            )


@sterilizable
class ZoneDataClass(ABC):
    def _set_property(self, property_name: str, new_value):
        log = False
        direct_setter = f"_set_{property_name}"

        if hasattr(self, direct_setter):
            log = getattr(self, direct_setter)(new_value)
        else:
            current_value = getattr(self, property_name)
            if current_value != new_value:
                setattr(self, f"_{property_name}", new_value)
                log = True

        if log:
            updated_value = getattr(self, property_name)

            message = ""
            if isinstance(updated_value, IntEnum):
                message = f"{self.__class__.__name__} set {property_name}: {updated_value.name} ({updated_value.value})"
            else:
                message = (
                    f"{self.__class__.__name__} set {property_name}: {updated_value}"
                )

            self.zone._log_debug(message)

            self.zone._event_publish(
                getattr(self.Events, property_name.upper() + "_CHANGE"), updated_value
            )
