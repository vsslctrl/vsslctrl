from .data_structure import VsslEnum, VsslIntEnum, ZoneIDs
from .io import AnalogOutput, InputRouter

SINGLE_ZONE = [ZoneIDs.ZONE_1]
THREE_ZONES = [ZoneIDs.ZONE_1, ZoneIDs.ZONE_2, ZoneIDs.ZONE_3]
SIX_ZONES = list(ZoneIDs)

INPUT_SOURCES_FOR_1_ZONE_DEVICE = [
    InputRouter.Sources.STREAM,
    InputRouter.Sources.ANALOG_IN_1,
    InputRouter.Sources.OPTICAL_IN,
]

INPUT_SOURCES_FOR_3_ZONE_DEVICE = INPUT_SOURCES_FOR_1_ZONE_DEVICE + [
    InputRouter.Sources.ANALOG_IN_2,
    InputRouter.Sources.ANALOG_IN_3,
]

INPUT_SOURCES_FOR_6_ZONE_DEVICE = list(InputRouter.Sources)

ANALOG_OUTPUT_SOURCES_FOR_1_ZONE_DEVICE = [
    AnalogOutput.Sources.OFF,
    AnalogOutput.Sources.ZONE_1,
    AnalogOutput.Sources.OPTICAL_IN,
]

ANALOG_OUTPUT_SOURCES_FOR_3_ZONE_DEVICE = ANALOG_OUTPUT_SOURCES_FOR_1_ZONE_DEVICE + [
    AnalogOutput.Sources.ZONE_2,
    AnalogOutput.Sources.ZONE_3,
]

ANALOG_OUTPUT_SOURCES_FOR_6_ZONE_DEVICE = list(AnalogOutput.Sources)


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
            "name": "A1",
            "zones": SINGLE_ZONE,
            "input_sources": INPUT_SOURCES_FOR_1_ZONE_DEVICE,
            "analog_output_sources": ANALOG_OUTPUT_SOURCES_FOR_1_ZONE_DEVICE,
            "features": [Features.BLUETOOTH, Features.SUBWOOFER_CROSSOVER],
        }
    )
    A3 = Model(
        {
            "name": "A3",
            "zones": THREE_ZONES,
            "input_sources": INPUT_SOURCES_FOR_3_ZONE_DEVICE,
            "analog_output_sources": ANALOG_OUTPUT_SOURCES_FOR_3_ZONE_DEVICE,
            "features": [Features.GROUPING, Features.PARTY_MODE],
        }
    )
    A6 = Model(
        {
            "name": "A6",
            "zones": SIX_ZONES,
            "input_sources": INPUT_SOURCES_FOR_6_ZONE_DEVICE,
            "analog_output_sources": ANALOG_OUTPUT_SOURCES_FOR_6_ZONE_DEVICE,
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
