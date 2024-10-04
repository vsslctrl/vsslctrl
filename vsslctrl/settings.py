import logging
from typing import Dict, Union
from .utils import clamp_volume
from .io import AnalogInput
from .device import Features as DeviceFeatures
from .data_structure import (
    VsslIntEnum,
    VsslDataClass,
    ZoneDataClass,
    ZoneEQStatusExtKeys,
)

VSSL_SETTINGS_EVENT_PREFIX = "vssl.settings."


class VsslSettings(VsslDataClass):
    class Keys:
        NAME = "name"
        OPTICAL_INPUT_NAME = "optical_input_name"
        BLUETOOTH = "bluetooth"

    #
    # VSSL Events
    #
    class Events:
        PREFIX = VSSL_SETTINGS_EVENT_PREFIX
        NAME_CHANGE = PREFIX + "name_changed"
        OPTICAL_INPUT_NAME_CHANGE = PREFIX + "optical_input_name_changed"
        BLUETOOTH_CHANGE = PREFIX + "bluetooth_changed"

    #
    # Defaults
    #
    DEFAULTS = {
        Keys.NAME: None,
        Keys.OPTICAL_INPUT_NAME: "Optical In",
        Keys.BLUETOOTH: 0,
    }

    def __init__(self, vssl: "vsslctrl.Vssl"):
        self._vssl = vssl

        self._name = None  # device name
        self._optical_input_name = self.DEFAULTS[self.Keys.OPTICAL_INPUT_NAME]
        self._bluetooth = self.DEFAULTS[self.Keys.BLUETOOTH]
        self.power = VsslPowerSettings(vssl)

    #
    # Name
    #
    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, name: str):
        zone = self._vssl.get_connected_zone()
        if zone and name:
            zone.api_alpha.request_action_18(name)

    #
    # Optical Input Name
    #
    @property
    def optical_input_name(self):
        return self._optical_input_name

    @optical_input_name.setter
    def optical_input_name(self, name: str):
        zone = self._vssl.get_connected_zone()
        if zone:
            zone.api_alpha.request_action_15_12(name)

    #
    # Bluetooth
    #
    @property
    def bluetooth(self):
        return bool(self._bluetooth)

    @bluetooth.setter
    def bluetooth(self, enabled: bool):
        if not self._vssl.model.supports_feature(DeviceFeatures.BLUETOOTH):
            self._vssl._log_error(
                f"VSSL {self._vssl.model.name} does not support Bluetooth"
            )
            return

        zone = self._vssl.get_connected_zone()
        if zone:
            # TODO
            # zone.api_alpha.request_action_bluetooth(not not enabled)
            pass

    def bluetooth_toggle(self):
        self.bluetooth = False if self.bluetooth else True


class VsslPowerSettings(VsslDataClass):
    #
    # Transport States
    #
    # DO NOT CHANGE - VSSL Defined
    #
    class States(VsslIntEnum):
        ON = 0
        STANDBY = 1
        SLEEP = 2

    #
    # Volume Setting Events
    #
    class Events:
        PREFIX = VSSL_SETTINGS_EVENT_PREFIX + "power."
        STATE_CHANGE = PREFIX + "state_changed"
        ADAPTIVE_CHANGE = PREFIX + "adaptive_changed"

    #
    # Defaults
    #
    DEFAULTS = {"state": States.ON, "adaptive": False}

    def __init__(self, vssl: "vsslctrl.Vssl"):
        self._vssl = vssl

        self._state = self.States.ON
        self._adaptive = True  # 1 = auto, 0 = always on

    #
    # Power State
    #
    @property
    def state(self):
        return self._state

    @state.setter
    def state(self, state: int):
        # read-only
        pass

    def _set_state(self, state: int):
        if self.state != state:
            if self.States.is_valid(state):
                self._state = self.States(state)
                return True
            else:
                self._vssl._log_warning(
                    f"VsslPowerSettings.States {state} doesnt exist"
                )

    #
    # Adaptive Power (always on or auto)
    #
    # 1 = Auto / Adaptive Power On
    # 0 = Always On
    #
    @property
    def adaptive(self):
        return bool(self._adaptive)

    @adaptive.setter
    def adaptive(self, enabled: bool):
        zone = self._vssl.get_connected_zone()
        if zone:
            zone.api_alpha.request_action_4F(not not enabled)

    def adaptive_toggle(self):
        self.adaptive = False if self.adaptive else True


class ZoneSettings(ZoneDataClass):
    class StereoMono(VsslIntEnum):
        """StereoMono

        0: Stereo
        1: Mono

        DO NOT CHANGE - VSSL Defined
        """

        Stereo = 0
        Mono = 1

    class Events:
        """Setting Events"""

        PREFIX = "zone.settings."
        DISABLED_CHANGE = PREFIX + "disabled_changed"
        NAME_CHANGE = PREFIX + "name_changed"
        MONO_CHANGE = PREFIX + "mono_changed"

    def __init__(self, zone: "zone.Zone"):
        self.zone = zone

        self._disabled = False
        self._name = f"Zone {zone.id}"
        self._mono = self.StereoMono.Stereo

        self.eq = EQSettings(zone)
        self.subwoofer = SubwooferSettings(zone)
        self.volume = VolumeSettings(zone)
        self.analog_input = AnalogInput(zone)

    #
    # Disable the zone
    #
    @property
    def disabled(self):
        return self._disabled

    @disabled.setter
    def disabled(self, disabled: Union[bool, int]):
        self.zone.api_alpha.request_action_25(not not disabled)

    def disabled_toggle(self):
        self.disabled = False if self.disabled else True

    #
    # Name
    #
    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, name: str):
        self.zone.api_bravo.request_action_5A_set(str(name))
        # Incase for some network reason _request_name arrives before the change
        # the setter will remove the request once set
        self.zone._poller.append(self.zone._request_name)
        self.zone._request_name()

    def _set_name(self, name: str):
        if name != self._name:
            self._name = name
            self.zone._poller.remove(self.zone._request_name)
            return True

    #
    # Mono
    # Set the output to mono
    #
    @property
    def mono(self):
        return self._mono

    @mono.setter
    def mono(self, mono: "ZoneSettings.StereoMono"):
        if self.StereoMono.is_valid(mono):
            self.zone.api_alpha.request_action_mono_set(mono)
        else:
            self.zone._log_error(f"ZoneSettings.StereoMono {mono} doesnt exist")

    def _set_mono(self, mono: int):
        if self.mono != mono:
            if self.StereoMono.is_valid(mono):
                self._mono = self.StereoMono(mono)
                return True
            else:
                self.zone._log_error(f"ZoneSettings.StereoMono {mono} doesnt exist")

    def mono_toggle(self):
        self.mono = (
            self.StereoMono.Stereo
            if self.mono == self.StereoMono.Mono
            else self.StereoMono.Mono
        )


class VolumeSettings(ZoneDataClass):
    class Keys:
        DEFAULT_ON = "default_on"
        MAX_LEFT = "max_left"
        MAX_RIGHT = "max_right"

    class Events:
        """Volume Setting Events"""

        PREFIX = "zone.settings.volume."
        DEFAULT_ON_CHANGE = PREFIX + "default_on_changed"
        MAX_LEFT_CHANGE = PREFIX + "max_left_changed"
        MAX_RIGHT_CHANGE = PREFIX + "max_right_changed"

    #
    # Defaults
    #
    DEFAULTS = {
        Keys.DEFAULT_ON: 0,
        Keys.MAX_LEFT: 75,
        Keys.MAX_RIGHT: 75,
    }

    #
    # Key Map for the reponse JSON to our internal structure
    #
    KEY_MAP = {
        ZoneEQStatusExtKeys.VOL_DEFAULT_ON: Keys.DEFAULT_ON,
        ZoneEQStatusExtKeys.VOL_MAX_LEFT: Keys.MAX_LEFT,
        ZoneEQStatusExtKeys.VOL_MAX_RIGHT: Keys.MAX_RIGHT,
    }

    def __init__(self, zone: "zone.Zone"):
        self.zone = zone

        self._default_on = self.DEFAULTS[self.Keys.DEFAULT_ON]
        self._max_left = self.DEFAULTS[self.Keys.MAX_LEFT]
        self._max_right = self.DEFAULTS[self.Keys.MAX_RIGHT]

    #
    # Update from a JSON dict passed
    #
    def _map_response_dict(self, volume_data: Dict[str, int]) -> None:
        for volume_data_key, settings_prop in self.KEY_MAP.items():
            if volume_data_key in volume_data:
                set_func = f"_set_{settings_prop}"
                if hasattr(self, set_func):
                    getattr(self, set_func)(volume_data[volume_data_key])

    #
    # Default On Volume
    #
    # When enabled, volume automatically reverts to the determined volume level
    # when initiating a new audio session
    #
    # 0 is off (no default on vol)
    #
    @property
    def default_on(self):
        return self._default_on

    @default_on.setter
    def default_on(self, vol: int):
        self.zone.api_alpha.request_action_05_08(vol)

    def _set_default_on(self, vol: int):
        vol = clamp_volume(vol)
        if self.default_on != vol:
            self._default_on = vol
            return True

    #
    # Max Left Volume
    #
    @property
    def max_left(self):
        return self._max_left

    @max_left.setter
    def max_left(self, vol: int):
        self.zone.api_alpha.request_action_05_01(vol)

    def _set_max_left(self, vol: int):
        vol = clamp_volume(vol)
        if self.max_left != vol:
            self._max_left = vol
            return True

    #
    # Max Right Volume
    #
    @property
    def max_right(self):
        return self._max_right

    @max_right.setter
    def max_right(self, vol: int):
        self.zone.api_alpha.request_action_05_02(vol)

    def _set_max_right(self, vol: int):
        vol = clamp_volume(vol)
        if self.max_right != vol:
            self._max_right = vol
            return True


class EQSettings(ZoneDataClass):
    MIN_VALUE = 90
    MAX_VALUE = 110
    MIN_VALUE_DB = -10
    MAX_VALUE_DB = 10

    class Keys:
        ENABLED = "enabled"
        HZ60 = "hz60"  # 60Hz
        HZ200 = "hz200"  # 200Hz
        HZ500 = "hz500"  # 500Hz
        KHZ1 = "khz1"  # 1kHz
        KHZ4 = "khz4"  # 4kHz
        KHZ8 = "khz8"  # 8kHz
        KHZ15 = "khz15"  # 15kHz

    #
    # EQ Frequencies
    #
    # DO NOT CHANGE - VSSL Defined
    #
    class Freqs(VsslIntEnum):
        HZ60 = 1  # 60Hz
        HZ200 = 2  # 200Hz
        HZ500 = 3  # 500Hz
        KHZ1 = 4  # 1kHz
        KHZ4 = 5  # 4kHz
        KHZ8 = 6  # 8kHz
        KHZ15 = 7  # 15kHz

    #
    # Volume Setting Events
    #
    class Events:
        PREFIX = "zone.settings.eq."
        ENABLED_CHANGE = PREFIX + "enabled_change"
        HZ60_CHANGE = PREFIX + "hz60_change"
        HZ200_CHANGE = PREFIX + "hz200_change"
        HZ500_CHANGE = PREFIX + "hz500_change"
        KHZ1_CHANGE = PREFIX + "khz1_change"
        KHZ4_CHANGE = PREFIX + "khz4_change"
        KHZ8_CHANGE = PREFIX + "khz8_change"
        KHZ15_CHANGE = PREFIX + "khz15_change"

    #
    # Defaults
    #
    DEFAULTS = {
        Keys.ENABLED: False,
        Keys.HZ60: 100,
        Keys.HZ200: 100,
        Keys.HZ500: 100,
        Keys.KHZ1: 100,
        Keys.KHZ4: 100,
        Keys.KHZ8: 100,
        Keys.KHZ15: 100,
    }

    #
    # Key Map
    #
    KEY_MAP = {
        ZoneEQStatusExtKeys.HZ60: Keys.HZ60,
        ZoneEQStatusExtKeys.HZ200: Keys.HZ200,
        ZoneEQStatusExtKeys.HZ500: Keys.HZ500,
        ZoneEQStatusExtKeys.KHZ1: Keys.KHZ1,
        ZoneEQStatusExtKeys.KHZ4: Keys.KHZ4,
        ZoneEQStatusExtKeys.KHZ8: Keys.KHZ8,
        ZoneEQStatusExtKeys.KHZ15: Keys.KHZ15,
    }

    def __init__(self, zone: "zone.Zone"):
        self.zone = zone

        self._enabled = self.DEFAULTS[self.Keys.ENABLED]
        self._hz60 = self.DEFAULTS[self.Keys.HZ60]
        self._hz200 = self.DEFAULTS[self.Keys.HZ200]
        self._hz500 = self.DEFAULTS[self.Keys.HZ500]
        self._khz1 = self.DEFAULTS[self.Keys.KHZ1]
        self._khz4 = self.DEFAULTS[self.Keys.KHZ4]
        self._khz8 = self.DEFAULTS[self.Keys.KHZ8]
        self._khz15 = self.DEFAULTS[self.Keys.KHZ15]

    def as_dict(self, with_db=True):
        settings = dict(self)

        if with_db:
            for json_data_key, setting_key in self.KEY_MAP.items():
                key = setting_key + "_db"
                settings[key] = getattr(self, key)

        return settings

    #
    # Clamp betwwen 90 and 110
    #
    def _clamp(self, value: int = 100):
        return int(max(self.MIN_VALUE, min(value, self.MAX_VALUE)))

    #
    # Map between -10 and +10
    #
    # 90 = -10db
    # 100 = 0db
    # 110 = +10db
    #
    def _map_clamp(self, input_value: int = 0, to_db: bool = True):
        """Convert / Map values between 90 & 110 to their -10db & +10db equilivents"""

        if to_db:
            # Ensure the mapped value is clamped between 90 and 110
            clamped_value = self._clamp(input_value)

            # Map the clamped value to the range -10 to 10
            return int(
                ((clamped_value - self.MIN_VALUE) / (self.MAX_VALUE - self.MIN_VALUE))
                * 20
                - self.MAX_VALUE_DB
            )
        else:
            # Map the input value from the range -10 to 10 to the range 90 to 110
            mapped_value = ((input_value + self.MAX_VALUE_DB) / 20) * (
                self.MAX_VALUE - self.MIN_VALUE
            ) + self.MIN_VALUE

            # Ensure the result is clamped between 90 and 110
            return self._clamp(mapped_value)

    #
    # Set EQ Value
    #
    # Expects a value between: 90 to 110
    #
    def _set_frequency_on_device(self, freq: "EQSettings.Freqs", value: int):
        if self.Freqs.is_valid(freq):
            self.zone.api_alpha.request_action_0D(freq, self._clamp(value))
        else:
            self.zone._log_error(f"EQSettings.Freqs {freq} doesnt exist")

    #
    # Set EQ Value, using dB as an input
    #
    # Expects: -10 to +10
    #
    def _set_frequency_on_device_db(self, freq: int, value: int):
        self._set_frequency_on_device(freq, self._map_clamp(value, False))

    #
    # Updade a property and emit and event if changed
    #
    def _set_eq_freq(self, freq: int, new_value: int):
        if self.Freqs.is_valid(freq):
            freq = self.Freqs(freq)
            self._set_property(getattr(self.Keys, freq.name), self._clamp(new_value))
        else:
            self.zone._log_error(f"EQSettings.Freqs {freq} doesnt exist")

    #
    # Update from a JSON dict passed
    #
    def _map_response_dict(self, json_data: Dict[str, int]) -> None:
        for json_data_key, setting_key in self.KEY_MAP.items():
            if json_data_key in json_data:
                self._set_property(
                    setting_key, self._clamp(int(json_data[json_data_key]))
                )

    #
    # EQ Enabled
    #
    @property
    def enabled(self):
        return self._enabled

    @enabled.setter
    def enabled(self, enabled: Union[bool, int]):
        self.zone.api_alpha.request_action_2D(enabled)

    def enabled_toggle(self):
        self.enabled = False if self.enabled else True

    #
    # EQ 60Hz
    #
    @property
    def hz60(self):
        return self._hz60

    @hz60.setter
    def hz60(self, val: int):
        self._set_frequency_on_device(self.Freqs.HZ60, val)

    @property
    def hz60_db(self):
        return self._map_clamp(self.hz60)

    @hz60_db.setter
    def hz60_db(self, val: int):
        self._set_frequency_on_device_db(self.Freqs.HZ60, val)

    #
    # EQ 200Hz
    #
    @property
    def hz200(self):
        return self._hz200

    @hz200.setter
    def hz200(self, val: int):
        self._set_frequency_on_device(self.Freqs.HZ200, val)

    @property
    def hz200_db(self):
        return self._map_clamp(self.hz200)

    @hz200_db.setter
    def hz200_db(self, val: int):
        self._set_frequency_on_device_db(self.Freqs.HZ200, val)

    #
    # EQ 500Hz
    #
    @property
    def hz500(self):
        return self._hz500

    @hz500.setter
    def hz500(self, val: int):
        self._set_frequency_on_device(self.Freqs.HZ500, val)

    @property
    def hz500_db(self):
        return self._map_clamp(self.hz500)

    @hz500_db.setter
    def hz500_db(self, val: int):
        self._set_frequency_on_device_db(self.Freqs.HZ500, val)

    #
    # EQ 1kHz
    #
    @property
    def khz1(self):
        return self._khz1

    @khz1.setter
    def khz1(self, val: int):
        self._set_frequency_on_device(self.Freqs.KHZ1, val)

    @property
    def khz1_db(self):
        return self._map_clamp(self.khz1)

    @khz1_db.setter
    def khz1_db(self, val: int):
        self._set_frequency_on_device_db(self.Freqs.KHZ1, val)

    #
    # EQ 4kHz
    #
    @property
    def khz4(self):
        return self._khz4

    @khz4.setter
    def khz4(self, val: int):
        self._set_frequency_on_device(self.Freqs.KHZ4, val)

    @property
    def khz4_db(self):
        return self._map_clamp(self.khz4)

    @khz4_db.setter
    def khz4_db(self, val: int):
        self._set_frequency_on_device_db(self.Freqs.KHZ4, val)

    #
    # EQ 8kHz
    #
    @property
    def khz8(self):
        return self._khz8

    @khz8.setter
    def khz8(self, val: int):
        self._set_frequency_on_device(self.Freqs.KHZ8, val)

    @property
    def khz8_db(self):
        return self._map_clamp(self.khz8)

    @khz8_db.setter
    def khz8_db(self, val: int):
        self._set_frequency_on_device_db(self.Freqs.KHZ8, val)

    #
    # EQ 15kHz
    #
    @property
    def khz15(self):
        return self._khz15

    @khz15.setter
    def khz15(self, val: int):
        self._set_frequency_on_device(self.Freqs.KHZ15, val)

    @property
    def khz15_db(self):
        return self._map_clamp(self.khz15)

    @khz15_db.setter
    def khz15_db(self, val: int):
        self._set_frequency_on_device_db(self.Freqs.KHZ15, val)


# Not in io.py to prevent circ import in device.py
class SubwooferSettings(ZoneDataClass):
    MIN_VALUE = 0
    MAX_VALUE = 1000

    #
    # Subwoofer events
    #
    class Events:
        PREFIX = "zone.subwoofer."
        CROSSOVER_CHANGE = PREFIX + "crossover_change"

    #
    # Defaults
    #
    DEFAULTS = {"crossover": 0}

    def __init__(self, zone: "zone.Zone"):
        self.zone = zone

        self._crossover = self.DEFAULTS["crossover"]

    #
    # Clamp between min and max
    #
    def _clamp_crossover(self, value: int = 100):
        return int(max(self.MIN_VALUE, min(value, self.MAX_VALUE)))

    #
    # Crossover freq
    #
    @property
    def crossover(self):
        return self._crossover

    @crossover.setter
    def crossover(self, freq: int):
        if not self.zone.vssl.model.supports_feature(
            DeviceFeatures.SUBWOOFER_CROSSOVER
        ):
            self.zone._log_error(
                f"VSSL {self.zone.vssl.model.name} does not have a subwoofer output"
            )
            return
        #
        # TODO
        #
        # self.zone.api_alpha.request_action_crossover(freq)

    def _set_crossover(self, freq: int):
        freq = self._clamp_crossover(freq)
        if self.crossover != freq:
            self._crossover = freq
            return True
