import logging
from enum import IntEnum
from typing import Dict, Union
from .utils import clamp_volume
from .data_structure import VsslIntEnum, ZoneDataClass, DeviceFeatureFlags


class InputRouter(ZoneDataClass):
    """

    What is going to be routed out the zones speakers

    """

    #
    # Input Priority
    #
    # 0 = Stream -> Party Zone -> Bus 1 In -> Bus 2 In -> Optical Input -> Coaxial Input -> Analog Input (Stream First)
    # 1 = Bus 1 In -> Bus 2 In -> Optical Input -> Coaxial Input -> Analog Input -> Stream -> Party Zone (Local First)
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
    # A.1(x) doesnt support input routing, but has a fixed routing order of its inputs:
    # Optical Input -> Coaxial Input -> Analog Input
    #
    class Sources(VsslIntEnum):
        STREAM = 0
        BUS_IN_1 = 1
        BUS_IN_2 = 2
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
    class Events:
        PREFIX = "zone.input_router."
        PRIORITY_CHANGE = PREFIX + "priority_change"
        SOURCE_CHANGE = PREFIX + "source_change"

    #
    # Defaults
    #
    DEFAULTS = {"priority": Priorities.STREAM, "source": Sources.STREAM}

    def __init__(self, zone: "zone.Zone"):
        self.zone = zone

        self._priority = self.DEFAULTS["priority"]
        self._source = self.DEFAULTS["source"]

    #
    # Input Priority
    #
    @property
    def priority(self):
        return self._priority

    @priority.setter
    def priority(self, priority: "InputRouter.Priorities"):
        if self.Priorities.is_valid(priority):
            self.zone.api_alpha.request_action_47(priority)
        else:
            self.zone._log_error(f"Input priority {priority} doesnt exist")

    def _set_priority(self, priority: int):
        if self.priority != priority:
            if self.Priorities.is_valid(priority):
                self._priority = self.Priorities(priority)
                return True
            else:
                self.zone._log_error(f"InputRouter.Priorities {priority} doesnt exist")

    #
    # Input Source
    #
    @property
    def source(self):
        return self._source

    @source.setter
    def source(self, src: "InputRouter.Sources"):
        # Check model supports input routing
        if not self.zone.vssl.model.supports_feature(DeviceFeatureFlags.INPUT_ROUTING):
            self.zone._log_error(
                f"VSSL {self.zone.vssl.model.name} does not support input routing."
            )
            return

        # Check device has this input
        if src not in self.zone.vssl.model.input_sources:
            self.zone._log_error(
                f"InputRouter.Sources {src} doesnt exist in {list(self.zone.vssl.model.input_sources)}"
            )
            return

        self.zone.api_alpha.request_action_03(src)

    def _set_source(self, src: int):
        if self.source != src:
            if self.Sources.is_valid(src):
                self._source = self.Sources(src)
                return True
            else:
                self.zone._log_error(f"InputRouter.Sources {src} doesnt exist")


class AnalogOutput(ZoneDataClass):
    """

    AnalogOutput.Sources is the source which will play out the corrosponding analog output


    On X series the zone will receive feedback for the corrosponding analog output id

    TODO: Confirm on original series amps:
        Zone 1 == ANALOG_OUTPUT_1 == Bus output 1
        Zone 2 == ANALOG_OUTPUT_2 == Bus output 2

    TODO: A.1(x) what ao_id need to be sent to fix the volume or change the input gain?

    Zones will be determined by source Input Priority @see InputRouter class

    A1(x): Source cant be changed

    """

    #
    # Output IDs
    #
    # DO NOT CHANGE - VSSL Defined
    #
    class IDs(VsslIntEnum):
        ANALOG_OUTPUT_1 = 1  # TODO: Confirm BUS 1 Output on A.3/A.6
        ANALOG_OUTPUT_2 = 2  # TODO: Confirm BUS 2 Output on A.3/A.6
        ANALOG_OUTPUT_3 = 3
        ANALOG_OUTPUT_4 = 4
        ANALOG_OUTPUT_5 = 5
        ANALOG_OUTPUT_6 = 6

    #
    # Sources
    #
    # DO NOT CHANGE - VSSL Defined
    #
    class Sources(VsslIntEnum):
        OFF = 0  # Disconnected / Off / No Output
        BUS_IN_1 = 1
        BUS_IN_2 = 2
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
    class Events:
        PREFIX = "zone.analog_output."
        IS_FIXED_VOLUME_CHANGE = PREFIX + "is_fixed_volume_change"
        SOURCE_CHANGE = PREFIX + "source_change"

    #
    # Defaults
    #
    DEFAULTS = {"is_fixed_volume": False, "source": Sources.OFF}

    def __init__(self, zone: "zone.Zone"):
        self.zone = zone

        self._is_fixed_volume = self.DEFAULTS["is_fixed_volume"]
        self._source = self.DEFAULTS["source"]

    #
    # Analog Output Fix Volume. i.e output wont respond to volume control
    #
    @property
    def is_fixed_volume(self):
        return self._is_fixed_volume

    @is_fixed_volume.setter
    def is_fixed_volume(self, state: Union[bool, int]):
        # TODO - this needs testing on A.1(x)
        # Default to zone 1 for A.1(x)
        ao_id = (
            self.zone.id
            if self.IDs.is_valid(self.zone.id)
            else self.IDs.ANALOG_OUTPUT_1
        )

        if ao_id not in self.zone.vssl.model.analog_outputs:
            self.zone._log_error(
                f"AnalogOutput.IDs {ao_id} doesnt exist in {list(self.zone.vssl.model.analog_outputs)}"
            )
            return

        self.zone.api_alpha.request_action_49(ao_id, state)

    def is_fixed_volume_toggle(self):
        self.is_fixed_volume = False if self.is_fixed_volume else True

    #
    # Analog Output Source
    #
    # Audio source which is going to be sent to the analog output.
    #
    @property
    def source(self):
        return self._source

    @source.setter
    def source(self, src: "AnalogOutput.Sources"):
        # Check model supports output routing
        if not self.zone.vssl.model.supports_feature(DeviceFeatureFlags.OUTPUT_ROUTING):
            self.zone._log_error(
                f"VSSL {self.zone.vssl.model.name} does not support output routing."
            )
            return

        # A.1(x) doesnt support routing to so the Zone ID == output ID
        ao_id = self.zone.id

        # Check model has the output
        if ao_id not in self.zone.vssl.model.analog_outputs:
            self.zone._log_error(
                f"AnalogOutput.IDs {ao_id} doesnt exist in {list(self.zone.vssl.model.analog_outputs)}"
            )
            return

        # Check model has the src
        if src not in self.zone.vssl.model.analog_output_sources:
            self.zone._log_error(
                f"AnalogOutput.Sources {src} doesnt exist in {list(self.zone.vssl.model.analog_output_sources)}"
            )
            return

        self.zone.api_alpha.request_action_1D(ao_id, src)

    def _set_source(self, src: int):
        if self.source != src:
            if self.Sources.is_valid(src):
                self._source = self.Sources(src)
                return True
            else:
                self.zone._log_error(f"AnalogOutput.Sources {src} doesnt exist")


class AnalogInput(ZoneDataClass):
    #
    # Analog Input Events
    #
    # One AiN per zone
    #
    class Events:
        PREFIX = "zone.analog_input."
        NAME_CHANGE = PREFIX + "name_change"
        FIXED_GAIN_CHANGE = PREFIX + "fixed_gain_change"

    #
    # Defaults
    #
    DEFAULTS = {"name": "Analog In", "fixed_gain": 0}

    def __init__(self, zone: "zone.Zone"):
        self.zone = zone

        self._name = f"Analog In {self.zone.id}"
        self._fixed_gain = self.DEFAULTS["fixed_gain"]

    #
    # Analog Input Name
    #
    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, name: str):
        self.zone.api_alpha.request_action_15(str(name))

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
        self.zone.api_alpha.request_action_05_00(gain)

    def _set_fixed_gain(self, gain: int):
        gain = clamp_volume(gain)
        if self.fixed_gain != gain:
            self._fixed_gain = gain
            return True

    @property
    def has_fixed_gain(self):
        return not self.fixed_gain == 0
