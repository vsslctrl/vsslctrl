from .data_structure import VsslEnum, VsslIntEnum, ZoneIDs, DeviceFeatureFlags
from .io import AnalogOutput, InputRouter


"""
Model Physical IOs, sourced from the product manuals

A.1x:
SUB OUT
ANALOG IN 1
ANALOG OUT 1
COAXIAL IN
COAXIAL OUT
OPTICAL IN
OPTICAL OUT
IR REMOTE

A1:
SUB OUT
ANALOG IN 1
ANALOG OUT 1
COAXIAL IN
COAXIAL OUT
OPTICAL IN
OPTICAL OUT
IR REMOTE



A.3x:
ANALOG IN 1
ANALOG IN 2
ANALOG IN 3
ANALOG OUT 1
ANALOG OUT 2
ANALOG OUT 3
OPTICAL IN
IR REMOTE

A3:
BUS 1 IN
BUS 1 OUT
ANALOG IN 1
ANALOG IN 2
ANALOG IN 3
OPTICAL IN



A.6x:
ANALOG IN 1
ANALOG IN 2
ANALOG IN 3
ANALOG IN 4
ANALOG IN 5
ANALOG IN 6
ANALOG OUT 1
ANALOG OUT 2
ANALOG OUT 3
ANALOG OUT 4
ANALOG OUT 5
ANALOG OUT 6
OPTICAL IN
IR REMOTE

A6:
BUS 1 IN
BUS 1 OUT
BUS 2 IN
BUS 2 OUT
ANALOG IN 1
ANALOG IN 2
ANALOG IN 3
ANALOG IN 4
ANALOG IN 5
ANALOG IN 6

---------------------------------

Following is from Source: https://vssl.gitbook.io/vssl-rest-api/zone-control/set-analog-input-source

Analog Input Source legend: input: inputs specific to model (e.g. A3 does not have zones 4-6 or bus input 2, only A3 has optical input, ...) 


0 - none 
1 - bus input 1 
2 - bus input 2 
3 - zone 1 local input 
4 - zone 2 local input 
5 - zone 3 local input 
6 - zone 4 local input 
7 - zone 5 local input 
8 - zone 6 local input 
16 - optical input


TODO COAX Input and output!

"""


""" 
    Zones 


"""
SINGLE_ZONE = [ZoneIDs.A1]
THREE_ZONES = [ZoneIDs.ZONE_1, ZoneIDs.ZONE_2, ZoneIDs.ZONE_3]
SIX_ZONES = THREE_ZONES + [ZoneIDs.ZONE_4, ZoneIDs.ZONE_5, ZoneIDs.ZONE_6]

""" 
    Input Sources


"""

# A.1 & A.1x
# These are not used since A.1(x) deosnt support routing, but keep them just to be complete
INPUT_SOURCES_FOR_1_ZONE_DEVICE = [
    InputRouter.Sources.STREAM,
    InputRouter.Sources.ANALOG_IN_1,
    InputRouter.Sources.OPTICAL_IN,
]

# A.3x
INPUT_SOURCES_FOR_3_ZONE_DEVICE = INPUT_SOURCES_FOR_1_ZONE_DEVICE + [
    InputRouter.Sources.ANALOG_IN_2,
    InputRouter.Sources.ANALOG_IN_3,
]

# A.3
INPUT_SOURCES_FOR_A3 = INPUT_SOURCES_FOR_3_ZONE_DEVICE + [InputRouter.Sources.BUS_IN_1]

# A.6x
INPUT_SOURCES_FOR_6_ZONE_DEVICE = INPUT_SOURCES_FOR_3_ZONE_DEVICE + [
    InputRouter.Sources.ANALOG_IN_4,
    InputRouter.Sources.ANALOG_IN_5,
    InputRouter.Sources.ANALOG_IN_6,
]

# A.6
# A.6 doenst have optical input
INPUT_SOURCES_FOR_A6 = [
    source for source in InputRouter.Sources if source != InputRouter.Sources.OPTICAL_IN
]


""" 
    Analog Outputs


"""

# A.1 & A.1x
ANALOG_OUTPUTS_FOR_1_ZONE_DEVICE = [AnalogOutput.IDs.ANALOG_OUTPUT_1]

# A.3x
ANALOG_OUTPUTS_FOR_3_ZONE_DEVICE = ANALOG_OUTPUTS_FOR_1_ZONE_DEVICE + [
    AnalogOutput.IDs.ANALOG_OUTPUT_2,
    AnalogOutput.IDs.ANALOG_OUTPUT_3,
]

# A.3
ANALOG_OUTPUTS_FOR_A3 = [AnalogOutput.IDs.ANALOG_OUTPUT_1]  # BUS_1

# A.6x
ANALOG_OUTPUTS_FOR_6_ZONE_DEVICE = ANALOG_OUTPUTS_FOR_3_ZONE_DEVICE + [
    AnalogOutput.IDs.ANALOG_OUTPUT_4,
    AnalogOutput.IDs.ANALOG_OUTPUT_5,
    AnalogOutput.IDs.ANALOG_OUTPUT_6,
]

# A.6
ANALOG_OUTPUTS_FOR_A6 = [
    AnalogOutput.IDs.ANALOG_OUTPUT_1,  # BUS_1
    AnalogOutput.IDs.ANALOG_OUTPUT_2,  # BUS_2
]

""" 
    Analog Output Sources


"""

# A.1 & A.1x
ANALOG_OUTPUT_SOURCES_FOR_1_ZONE_DEVICE = [
    AnalogOutput.Sources.OFF,
    AnalogOutput.Sources.ZONE_1,
    AnalogOutput.Sources.OPTICAL_IN,
]

# A.3x
ANALOG_OUTPUT_SOURCES_FOR_3_ZONE_DEVICE = ANALOG_OUTPUT_SOURCES_FOR_1_ZONE_DEVICE + [
    AnalogOutput.Sources.ZONE_2,
    AnalogOutput.Sources.ZONE_3,
]

# A.3
ANALOG_OUTPUT_SOURCES_FOR_A3 = ANALOG_OUTPUT_SOURCES_FOR_3_ZONE_DEVICE + [
    AnalogOutput.Sources.BUS_IN_1
]

# A.6x
ANALOG_OUTPUT_SOURCES_FOR_6_ZONE_DEVICE = ANALOG_OUTPUT_SOURCES_FOR_3_ZONE_DEVICE + [
    AnalogOutput.Sources.ZONE_4,
    AnalogOutput.Sources.ZONE_5,
    AnalogOutput.Sources.ZONE_6,
]

# A.6
ANALOG_OUTPUT_SOURCES_FOR_A6 = list(AnalogOutput.Sources)


class Model:
    def __init__(self, model: dict):
        self.name = model.get("name")
        self.zones = model.get("zones", [])
        self.input_sources = model.get("input_sources", [])
        self.analog_outputs = model.get("analog_outputs", [])
        self.analog_output_sources = model.get("analog_output_sources", [])
        self.features = model.get("features", [])

    @property
    def zone_count(self):
        return len(self.zones)

    @property
    def is_multizone(self):
        return self.zone_count > 1

    def supports_feature(self, feature: DeviceFeatureFlags):
        return feature in self.features


class Models(VsslEnum):
    A1X = Model(
        {
            "name": "A.1x",
            "zones": SINGLE_ZONE,
            "input_sources": INPUT_SOURCES_FOR_1_ZONE_DEVICE,
            "analog_outputs": ANALOG_OUTPUTS_FOR_1_ZONE_DEVICE,
            "analog_output_sources": ANALOG_OUTPUT_SOURCES_FOR_1_ZONE_DEVICE,
            "features": [
                DeviceFeatureFlags.BLUETOOTH,
                DeviceFeatureFlags.SUBWOOFER_CROSSOVER,
            ],
        }
    )
    A3X = Model(
        {
            "name": "A.3x",
            "zones": THREE_ZONES,
            "input_sources": INPUT_SOURCES_FOR_3_ZONE_DEVICE,
            "analog_outputs": ANALOG_OUTPUTS_FOR_3_ZONE_DEVICE,
            "analog_output_sources": ANALOG_OUTPUT_SOURCES_FOR_3_ZONE_DEVICE,
            "features": [
                DeviceFeatureFlags.INPUT_ROUTING,
                DeviceFeatureFlags.OUTPUT_ROUTING,
            ],
        }
    )
    A6X = Model(
        {
            "name": "A.6x",
            "zones": SIX_ZONES,
            "input_sources": INPUT_SOURCES_FOR_6_ZONE_DEVICE,
            "analog_outputs": ANALOG_OUTPUTS_FOR_6_ZONE_DEVICE,
            "analog_output_sources": ANALOG_OUTPUT_SOURCES_FOR_6_ZONE_DEVICE,
            "features": [
                DeviceFeatureFlags.INPUT_ROUTING,
                DeviceFeatureFlags.OUTPUT_ROUTING,
            ],
        }
    )
    A1 = Model(
        {
            "name": "A.1",
            "zones": SINGLE_ZONE,
            "input_sources": INPUT_SOURCES_FOR_1_ZONE_DEVICE,
            "analog_outputs": ANALOG_OUTPUTS_FOR_1_ZONE_DEVICE,
            "analog_output_sources": ANALOG_OUTPUT_SOURCES_FOR_1_ZONE_DEVICE,
            "features": [
                DeviceFeatureFlags.BLUETOOTH,
                DeviceFeatureFlags.SUBWOOFER_CROSSOVER,
            ],
        }
    )
    A3 = Model(
        {
            "name": "A.3",
            "zones": THREE_ZONES,
            "input_sources": INPUT_SOURCES_FOR_A3,
            "analog_outputs": ANALOG_OUTPUTS_FOR_A3,
            "analog_output_sources": ANALOG_OUTPUT_SOURCES_FOR_A3,
            "features": [
                DeviceFeatureFlags.INPUT_ROUTING,
                DeviceFeatureFlags.OUTPUT_ROUTING,
                DeviceFeatureFlags.GROUPING,
                DeviceFeatureFlags.PARTY_ZONE,
            ],
        }
    )
    A6 = Model(
        {
            "name": "A.6",
            "zones": SIX_ZONES,
            "input_sources": INPUT_SOURCES_FOR_A6,
            "analog_outputs": ANALOG_OUTPUTS_FOR_A6,
            "analog_output_sources": ANALOG_OUTPUT_SOURCES_FOR_A6,
            "features": [
                DeviceFeatureFlags.INPUT_ROUTING,
                DeviceFeatureFlags.OUTPUT_ROUTING,
                DeviceFeatureFlags.GROUPING,
                DeviceFeatureFlags.PARTY_ZONE,
            ],
        }
    )

    @classmethod
    def get_model_names(cls):
        return [model.value.name for model in cls]

    @classmethod
    def get_model_by_name(cls, name):
        # Preprocess input name: convert to lowercase and remove dots
        name_cleaned = name.lower().replace(".", "")

        for model in cls:
            # Preprocess model name: convert to lowercase and remove dots
            if model.value.name.lower().replace(".", "") == name_cleaned:
                return model.value
        return None  # Return None if no match is found
