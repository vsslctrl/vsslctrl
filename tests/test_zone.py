import time
import asyncio
import random
import pytest
import pytest_asyncio

import vsslctrl as vssl_module
from vsslctrl.core import Vssl
from vsslctrl.zone import Zone
from vsslctrl.transport import ZoneTransport
from vsslctrl.group import ZoneGroup
from vsslctrl.io import AnalogOutput, InputRouter, AnalogInput
from vsslctrl.track import TrackMetadata
from vsslctrl.utils import clamp_volume


@pytest_asyncio.fixture(scope="session")
async def zone(request):
    vssl_instance = vssl_module.Vssl()
    zone_instance = vssl_instance.add_zone(1, "192.168.168.1")

    # Yield the device to the test function
    yield zone_instance

    # Tear down. Restore state
    await vssl_instance.disconnect()


@pytest_asyncio.fixture(scope="session")
async def eb(zone):
    return zone.vssl.event_bus


@pytest_asyncio.fixture(scope="session")
async def vssl(zone):
    return zone.vssl


def check_keys_have_events(keys_obj, events_obj):
    # check keys have events
    for attr_name in dir(keys_obj):
        if not attr_name.startswith("__") and not attr_name.endswith("__"):
            assert hasattr(events_obj, f"{attr_name}_CHANGE")


def check_keys_have_default(keys_obj, defaults_obj):
    # check keys have events
    for attr_name in dir(keys_obj):
        if not attr_name.startswith("__") and not attr_name.endswith("__"):
            assert getattr(keys_obj, attr_name) in defaults_obj


class TestTrackMetadata:
    @pytest.mark.asyncio(scope="session")
    async def test_keys_exist(self, zone, eb):
        # check keys have events
        check_keys_have_events(TrackMetadata.Keys, TrackMetadata.Events)
        check_keys_have_default(TrackMetadata.Keys, TrackMetadata.DEFAULTS)
