import logging
from typing import Dict, Union
from .utils import VsslIntEnum, clamp_volume
from .io import AnalogInput
from .decorators import zone_data_class


class VsslPowerSettings:

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
    class Events():
        PREFIX            = 'vssl.power.'
        STATE_CHANGE      = PREFIX+'state_changed'
        ADAPTIVE_CHANGE   = PREFIX+'adaptive_changed'

    #
    # Defaults
    #
    DEFAULTS = {
        'state': States.ON,
        'adaptive': False
    }

    def __init__(self, vssl: 'vsslctrl.Vssl'):
        self._vssl = vssl

        self._state = VsslPowerSettings.States.ON
        self._adaptive = True #1 = auto, 0 = always on

    def __iter__(self):
        for key in VsslPowerSettings.DEFAULTS:
            yield key, getattr(self, key)

    def as_dict(self):
        return dict(self)

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
            if VsslPowerSettings.States.is_valid(state):
                self._state = VsslPowerSettings.States(state)
                self._vssl.event_bus.publish(VsslPowerSettings.Events.STATE_CHANGE, 0, self.state)
            else:
                self._vssl._log_warning(f"VsslPowerSettings.States {state} doesnt exist")


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
            zone._api_alpha.request_action_4F(not not enabled)

    def _set_adaptive(self, adaptive: bool):
        if self.adaptive != adaptive:
            self._adaptive = adaptive
            self._vssl.event_bus.publish(VsslPowerSettings.Events.ADAPTIVE_CHANGE, 0, self.adaptive)

    def adaptive_toggle(self):
        self.adaptive = False if self.adaptive else True


@zone_data_class
class ZoneSettings:

    #
    # StereoMono
    #
    # 0: Stereo
    # 1: Mono
    #
    # DO NOT CHANGE - VSSL Defined
    #
    class StereoMono(VsslIntEnum):
        Stereo = 0 
        Mono = 1

    #
    # Setting Events
    #
    class Events():
        PREFIX          = 'zone.settings.'
        DISABLED_CHANGE = PREFIX+'disabled_changed'
        NAME_CHANGE     = PREFIX+'name_changed'
        MONO_CHANGE     = PREFIX+'mono_changed'


    def __init__(self, zone: 'zone.Zone'):
        self._zone = zone

        self._disabled = False
        self._name = f'Zone {zone.id}'

        # False = Stereo, True = Mono
        self._mono = False 

        self.eq = EQSettings(zone)
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
        self._zone._api_alpha.request_action_25(not not disabled)

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
        self._zone._api_bravo.request_action_5A_set(str(name))
        # Incase for some network reason _request_name arrives before the change
        # the setter will remove the request once set
        self._zone._poller.append(self._zone._request_name)
        self._zone._request_name()

    def _set_name(self, name: str):
        if name != self._name:
            self._name = name
            self._zone._poller.remove(self._zone._request_name)
            return True

    #
    # Mono
    # Set the output to mono
    #
    @property
    def mono(self):
        return self._mono

    @mono.setter
    def mono(self, mono: 'ZoneSettings.StereoMono'):
        if ZoneSettings.StereoMono.is_valid(mono):
            self._zone._api_alpha.request_action_mono_set(mono)
        else:
            self._zone._log_error(f"ZoneSettings.StereoMono {mono} doesnt exist")

    def _set_mono(self, mono: int):
        if self.mono != mono:
            if ZoneSettings.StereoMono.is_valid(mono):
                self._mono = ZoneSettings.StereoMono(mono)
                return True
            else:
                self._zone._log_error(f"ZoneSettings.StereoMono {mono} doesnt exist")
    
    def mono_toggle(self):
        self.mono = ZoneSettings.StereoMono.Stereo if self.mono == ZoneSettings.StereoMono.Mono else ZoneSettings.StereoMono.Mono


@zone_data_class
class VolumeSettings:

    #
    # Volume Setting Events
    #
    class Events():
        PREFIX              = 'zone.settings.volume.'
        DEFAULT_ON_CHANGE   = PREFIX+'default_on_changed'
        MAX_LEFT_CHANGE     = PREFIX+'max_left_changed'
        MAX_RIGHT_CHANGE    = PREFIX+'max_right_changed'

    #
    # Defaults
    #
    DEFAULTS = {
        'default_on': 75,
        'max_left': 75,
        'max_right': 75,
    }

    #
    # Key Map
    #
    KEY_MAP = {
        'vold': 'default_on',
        'voll': 'max_left',
        'volr': 'max_right'
    }

    def __init__(self, zone: 'zone.Zone'):
        self._zone = zone

        self._default_on = 75
        self._max_left = 75
        self._max_right = 75

    def __iter__(self):
        for key in VolumeSettings.DEFAULTS:
            yield key, getattr(self, key)

    def as_dict(self):
        return dict(self)

    #
    # Update from a JSON dict passed
    #
    def _map_response_dict(self, volume_data: Dict[str, int]) -> None:
        for volume_data_key, settings_prop in VolumeSettings.KEY_MAP.items():
            if volume_data_key in volume_data:
                set_func = f'_set_{settings_prop}'
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
        self._zone._api_alpha.request_action_05_08(vol)

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
        self._zone._api_alpha.request_action_05_01(vol)

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
        self._zone._api_alpha.request_action_05_02(vol)

    def _set_max_right(self, vol: int):
        vol = clamp_volume(vol)
        if self.max_right != vol:
            self._max_right = vol
            return True


@zone_data_class
class EQSettings:

    #
    # EQ Frequencies
    #
    # DO NOT CHANGE - VSSL Defined
    #
    class Freqs(VsslIntEnum):
        HZ60 = 1 # 60Hz
        HZ200 = 2 # 200Hz
        HZ500 = 3 # 500Hz
        KHZ1 = 4 # 1kHz
        KHZ4 = 5 # 4kHz
        KHZ8 = 6 # 8kHz
        KHZ15 = 7 # 16kHz

    #
    # Volume Setting Events
    #
    class Events():
        PREFIX          = 'zone.settings.eq.'
        ENABLED_CHANGE  = PREFIX+'enabled_change'
        HZ60_CHANGE     = PREFIX+'hz60_change'
        HZ200_CHANGE    = PREFIX+'hz200_change'
        HZ500_CHANGE    = PREFIX+'hz500_change'
        KHZ1_CHANGE     = PREFIX+'khz1_change'
        KHZ4_CHANGE     = PREFIX+'khz4_change'
        KHZ8_CHANGE     = PREFIX+'khz8_change'
        KHZ15_CHANGE    = PREFIX+'khz15_change'

    #
    # Defaults
    #
    DEFAULTS = {
        'enabled': False,
        'hz60': 100,
        'hz200': 100,
        'hz500': 100,
        'khz1': 100,
        'khz4': 100,
        'khz8': 100,
        'khz15': 100
    }

    #
    # Key Map
    #
    KEY_MAP = {
        'eq1': Freqs.HZ60,
        'eq2': Freqs.HZ200,
        'eq3': Freqs.HZ500,
        'eq4': Freqs.KHZ1,
        'eq5': Freqs.KHZ4,
        'eq6': Freqs.KHZ8,
        'eq7': Freqs.KHZ15
    }

    def __init__(self, zone: 'zone.Zone'):
        self._zone = zone

        self._enabled = False
        self._hz60 = 100
        self._hz200 = 100
        self._hz500 = 100
        self._khz1 = 100
        self._khz4 = 100
        self._khz8 = 100
        self._khz15 = 100


    def __iter__(self):
        for key in EQSettings.DEFAULTS:
            yield key, getattr(self, key)

    def as_dict(self, with_db = True):
        settings = dict(self)

        if with_db:
            for eq_data_key, freq_key in EQSettings.KEY_MAP.items():
                key = f'{freq_key.name.lower()}_db'
                settings[key] = getattr(self, key)

        return settings
        

    #
    # Clamp betwwen 90 and 110
    #
    def _clamp(self, value: int = 0):
        return int(max(90, min(value, 110)))
            

    #
    # Map between -10 and +10
    #
    # 90 = -10db
    # 100 = 0db
    # 110 = +10db
    #
    def _map_clamp(self, input_value: int = 0, to_db: bool = True):
        """
            Convert / Map values between 90 & 110 to their -10db & +10db equilivents
        """

        if to_db:
            # Ensure the mapped value is clamped between 90 and 110
            clamped_value = self._clamp(input_value)

            # Map the clamped value to the range -10 to 10
            return int(((clamped_value - 90) / (110 - 90)) * 20 - 10)
        else:
            # Map the input value from the range -10 to 10 to the range 90 to 110
            mapped_value = ((input_value + 10) / 20) * (110 - 90) + 90

            # Ensure the result is clamped between 90 and 110
            return self._clamp(mapped_value)

    #
    # Set EQ Value
    #
    # Expects a value between: 90 to 110
    #
    def _set_frequency_on_device(self, freq: 'EQSettings.Freqs', value: int):
        if EQSettings.Freqs.is_valid(freq):
            self._zone._api_alpha.request_action_0D(freq, self._clamp(value))
        else:
            self._zone._log_error(f"EQSettings.Freqs {freq} doesnt exist")
       

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
    def _set_eq_freq(self, freq: 'EQSettings.Freqs', new_value: int):
        if EQSettings.Freqs.is_valid(freq):
            
            freq = EQSettings.Freqs(freq)
            key = freq.name.lower()

            self._set_property(key, self._clamp(new_value))

        else:
            self._zone._log_error(f"EQSettings.Freqs {freq} doesnt exist")

    #
    # Update from a JSON dict passed
    #
    def _map_response_dict(self, eq_data: Dict[str, int]) -> None:
        for eq_data_key, freq_key in EQSettings.KEY_MAP.items():
            if eq_data_key in eq_data:
                self._set_eq_freq(freq_key, int(eq_data[eq_data_key]))

    #
    # EQ Enabled
    #
    @property
    def enabled(self):
        return self._enabled

    @enabled.setter
    def enabled(self, enabled: Union[bool, int]):
        self._zone._api_alpha.request_action_2D(enabled)

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
        self._set_frequency_on_device(EQSettings.Freqs.HZ60, val)

    @property
    def hz60_db(self):
        return self._map_clamp(self.hz60)

    @hz60_db.setter
    def hz60_db(self, val: int):
        self._set_frequency_on_device_db(EQSettings.Freqs.HZ60, val)

    #
    # EQ 200Hz
    #
    @property
    def hz200(self):
        return self._hz200

    @hz200.setter
    def hz200(self, val: int):
        self._set_frequency_on_device(EQSettings.Freqs.HZ200, val)

    @property
    def hz200_db(self):
        return self._map_clamp(self.hz200)

    @hz200_db.setter
    def hz200_db(self, val: int):
        self._set_frequency_on_device_db(EQSettings.Freqs.HZ200, val)

    #
    # EQ 500Hz
    #
    @property
    def hz500(self):
        return self._hz500

    @hz500.setter
    def hz500(self, val: int):
        self._set_frequency_on_device(EQSettings.Freqs.HZ500, val)

    @property
    def hz500_db(self):
        return self._map_clamp(self.hz500)

    @hz500_db.setter
    def hz500_db(self, val: int):
        self._set_frequency_on_device_db(EQSettings.Freqs.HZ500, val)

    #
    # EQ 1kHz
    #
    @property
    def khz1(self):
        return self._khz1

    @khz1.setter
    def khz1(self, val: int):
        self._set_frequency_on_device(EQSettings.Freqs.KHZ1, val)

    @property
    def khz1_db(self):
        return self._map_clamp(self.khz1)

    @khz1_db.setter
    def khz1_db(self, val: int):
        self._set_frequency_on_device_db(EQSettings.Freqs.KHZ1, val)

    #
    # EQ 4kHz
    #
    @property
    def khz4(self):
        return self._khz4

    @khz4.setter
    def khz4(self, val: int):
        self._set_frequency_on_device(EQSettings.Freqs.KHZ4, val)

    @property
    def khz4_db(self):
        return self._map_clamp(self.khz4)

    @khz4_db.setter
    def khz4_db(self, val: int):
        self._set_frequency_on_device_db(EQSettings.Freqs.KHZ4, val)

    #
    # EQ 8kHz
    #
    @property
    def khz8(self):
        return self._khz8

    @khz8.setter
    def khz8(self, val: int):
        self._set_frequency_on_device(EQSettings.Freqs.KHZ8, val)

    @property
    def khz8_db(self):
        return self._map_clamp(self.khz8)

    @khz8_db.setter
    def khz8_db(self, val: int):
        self._set_frequency_on_device_db(EQSettings.Freqs.KHZ8, val)

    #
    # EQ 15kHz
    #
    @property
    def khz15(self):
        return self._khz15

    @khz15.setter
    def khz15(self, val: int):
        self._set_frequency_on_device(EQSettings.Freqs.KHZ15, val)

    @property
    def khz15_db(self):
        return self._map_clamp(self.khz15)

    @khz15_db.setter
    def khz15_db(self, val: int):
        self._set_frequency_on_device_db(EQSettings.Freqs.KHZ15, val)