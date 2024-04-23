import logging
from enum import IntEnum
from typing import Dict, Union
from .utils import VsslIntEnum, clamp_volume
from .decorators import zone_data_class

@zone_data_class
class InputRouter:

    #
    # Input Priority
    #
    # 0: Stream -> Analog Input
    # 1: Analog Input -> Stream (Local first in App)
    #
    # DO NOT CHANGE - VSSL Defined
    #
    class Priorities(VsslIntEnum):
        STREAM = 0 
        LOCAL = 1

    #
    # Input Sources
    #
    # DO NOT CHANGE - VSSL Defined
    #
    class Sources(VsslIntEnum):
        STREAM = 0
        ANALOG_IN_1 = 3
        ANALOG_IN_2 = 4
        ANALOG_IN_3 = 5
        ANALOG_IN_4 = 6
        ANALOG_IN_5 = 7
        ANALOG_IN_6 = 8
        OPTICAL_IN = 16

    #
    # Router Events
    #
    class Events():
        PREFIX          = 'zone.input_router.'
        PRIORITY_CHANGE = PREFIX+'priority_change'
        SOURCE_CHANGE   = PREFIX+'source_change'

    #
    # Defaults
    #
    DEFAULTS = {
        'priority': Priorities.STREAM,
        'source': Sources.STREAM
    }

    def __init__(self, zone: 'zone.Zone'):
        self._zone = zone

        self._priority = InputRouter.Priorities.STREAM
        self._source = InputRouter.Sources.STREAM

    def __iter__(self):
        for key in InputRouter.DEFAULTS:
            yield key, getattr(self, key)

    def as_dict(self):
        return dict(self)

    #
    # Input Priority
    #
    @property
    def priority(self):
        return self._priority

    @priority.setter
    def priority(self, priority: 'InputRouter.Priorities'):
        if InputRouter.Priorities.is_valid(priority):
            self._zone._api_alpha.request_action_47(priority)
        else:
            self._zone._log_error(f"Input priority {priority} doesnt exist")

    def _set_priority(self, priority: int):
        if self.priority != priority:
            if InputRouter.Priorities.is_valid(priority):
                self._priority = InputRouter.Priorities(priority)
                return True
            else:
                self._zone._log_error(f"InputRouter.Priorities {priority} doesnt exist")

    #
    # Input Source
    #
    @property
    def source(self):
        return self._source

    @source.setter
    def source(self, src: 'InputRouter.Sources'):
        if InputRouter.Sources.is_valid(src):
            self._zone._api_alpha.request_action_03(src)
        else:
            self._zone._log_error(f"InputRouter.Sources {src} doesnt exist")
        
    def _set_source(self, src: int):
        if self.source != src:
            if InputRouter.Sources.is_valid(src):
                self._source = InputRouter.Sources(src)
                return True
            else:
                self._zone._log_error(f"InputRouter.Sources {src} doesnt exist")

@zone_data_class
class AnalogOutput:
    """
        Should this be on the VSSL or Zone? For now its on the zone, because the zone will
        receive feedback for the corrosponding analog output id
    """

    #
    # Sources
    #
    # DO NOT CHANGE - VSSL Defined
    #
    class Sources(VsslIntEnum):
        OFF = 0 # Disconnected / Off / No Output
        ZONE_1 = 3
        ZONE_2 = 4
        ZONE_3 = 5
        ZONE_4 = 6
        ZONE_5 = 7
        ZONE_6 = 8
        OPTICAL_IN = 16

    #
    # Output Events
    #
    class Events():
        PREFIX                  = 'zone.analog_output.'
        IS_FIXED_VOLUME_CHANGE  = PREFIX+'is_fixed_volume_change'
        SOURCE_CHANGE           = PREFIX+'source_change'

    #
    # Defaults
    #
    DEFAULTS = {
        'is_fixed_volume': False,
        'source': Sources.OFF
    }

    def __init__(self, zone: 'zone.Zone'):
        self._zone = zone

        self._is_fixed_volume = False
        self._source = AnalogOutput.Sources(zone.id + 3)


    def __iter__(self):
        for key in AnalogOutput.DEFAULTS:
            yield key, getattr(self, key)

    def as_dict(self):
        return dict(self)

    #
    # Analog Output Fix Volume
    #
    @property
    def is_fixed_volume(self):
        return self._is_fixed_volume

    @is_fixed_volume.setter
    def is_fixed_volume(self, state: Union[bool, int]):
        self._zone._api_alpha.request_action_49(state)

    def is_fixed_volume_toggle(self):
        self.is_fixed_volume = False if self.is_fixed_volume else True

    #
    # Analog Output Source
    #
    @property
    def source(self):
        return self._source

    @source.setter
    def source(self, src: 'AnalogOutput.Sources'):
        if AnalogOutput.Sources.is_valid(src):
            self._zone._api_alpha.request_action_1D(src)
        else:
            self._zone._log_error(f"AnalogOutput.Sources {src} doesnt exist")

    def _set_source(self, src: int):
        if self.source != src:
            if AnalogOutput.Sources.is_valid(src):
                self._source = AnalogOutput.Sources(src)
                return True
            else:
                self._zone._log_error(f"AnalogOutput.Sources {src} doesnt exist")

@zone_data_class
class AnalogInput:

    #
    # Analog Input Events
    #
    class Events():
        PREFIX              = 'zone.analog_input.'
        NAME_CHANGE         = PREFIX+'name_change'
        FIXED_GAIN_CHANGE   = PREFIX+'fixed_gain_change'

    #
    # Defaults
    #
    DEFAULTS = {
        'name': 'Analog In',
        'fixed_gain': 0
    }

    def __init__(self, zone: 'zone.Zone'):
        self._zone = zone

        self._name = f'Analog In {self._zone.id}'
        self._fixed_gain = 0

    def __iter__(self):
        for key in AnalogInput.DEFAULTS:
            yield key, getattr(self, key)

    def as_dict(self):
        return dict(self)


    #
    # Analog Input Name
    #
    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, name: str):
        self._zone._api_alpha.request_action_15(str(name))

    #
    # Analog Input Fixed Gain
    #
    # 0 is disabled or variable gain
    #
    @property
    def fixed_gain(self):
        return self._fixed_gain

    @fixed_gain.setter
    def fixed_gain(self, gain: int):
         self._zone._api_alpha.request_action_05_00(gain)

    def _set_fixed_gain(self, gain: int):
        gain = clamp_volume(gain)
        if self.fixed_gain != gain:
            self._fixed_gain = gain
            return True

    @property
    def has_fixed_gain(self):
        return not self.fixed_gain == 0
