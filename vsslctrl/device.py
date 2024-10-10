from .data_structure import VsslEnum, VsslIntEnum, ZoneIDs
from .io import AnalogOutput, InputRouter


"""
Model Physical IOs, sourced from the product manuals

A.1x:
SUB OUT
ANALOG IN 1
ANALOG OUT 1
COAXIAL IN (Are Coxial and Optical inputs linked?)
COAXIAL OUT
OPTICAL IN
OPTICAL OUT
IR REMOTE

A1:
SUB OUT
ANALOG IN 1
ANALOG OUT 1
COAXIAL IN (Are Coxial and Optical inputs linked?)
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


Source: https://vssl.gitbook.io/vssl-rest-api/zone-control/set-analog-input-source


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
INPUT_SOURCES_FOR_A6 = [
    source for source in InputRouter.Sources if source != InputRouter.Sources.OPTICAL_IN
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


class Features(VsslIntEnum):
    GROUPING = 1000
    BLUETOOTH = 1001
    PARTY_MODE = 1002
    SUBWOOFER_CROSSOVER = 1003


class Model:
    def __init__(self, model: dict):
        self.name = model.get("name")
        self.zones = model.get("zones", [])
        self.input_sources = model.get("input_sources", [])
        self.analog_output_sources = model.get("analog_output_sources", [])
        self.features = model.get("features", [])

    @property
    def zone_count(self):
        return len(self.zones)

    @property
    def is_multizone(self):
        return self.zone_count > 1

    def supports_feature(self, feature: Features):
        return feature in self.features


class Models(VsslEnum):
    A1 = Model(
        {
            "name": "A.1",
            "zones": SINGLE_ZONE,
            "input_sources": INPUT_SOURCES_FOR_1_ZONE_DEVICE,
            "analog_output_sources": ANALOG_OUTPUT_SOURCES_FOR_1_ZONE_DEVICE,
            "features": [Features.BLUETOOTH, Features.SUBWOOFER_CROSSOVER],
        }
    )
    A3 = Model(
        {
            "name": "A.3",
            "zones": THREE_ZONES,
            "input_sources": INPUT_SOURCES_FOR_A3,
            "analog_output_sources": ANALOG_OUTPUT_SOURCES_FOR_A3,
            "features": [Features.GROUPING, Features.PARTY_MODE],
        }
    )
    A6 = Model(
        {
            "name": "A.6",
            "zones": SIX_ZONES,
            "input_sources": INPUT_SOURCES_FOR_A6,
            "analog_output_sources": ANALOG_OUTPUT_SOURCES_FOR_A6,
            "features": [Features.GROUPING, Features.PARTY_MODE],
        }
    )
    A1X = Model(
        {
            "name": "A.1x",
            "zones": SINGLE_ZONE,
            "input_sources": INPUT_SOURCES_FOR_1_ZONE_DEVICE,
            "analog_output_sources": ANALOG_OUTPUT_SOURCES_FOR_1_ZONE_DEVICE,
            "features": [Features.BLUETOOTH, Features.SUBWOOFER_CROSSOVER],
        }
    )
    A3X = Model(
        {
            "name": "A.3x",
            "zones": THREE_ZONES,
            "input_sources": INPUT_SOURCES_FOR_3_ZONE_DEVICE,
            "analog_output_sources": ANALOG_OUTPUT_SOURCES_FOR_3_ZONE_DEVICE,
            "features": [Features.GROUPING],
        }
    )
    A6X = Model(
        {
            "name": "A.6x",
            "zones": SIX_ZONES,
            "input_sources": INPUT_SOURCES_FOR_6_ZONE_DEVICE,
            "analog_output_sources": ANALOG_OUTPUT_SOURCES_FOR_6_ZONE_DEVICE,
            "features": [Features.GROUPING],
        }
    )
