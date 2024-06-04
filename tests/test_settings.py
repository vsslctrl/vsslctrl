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
from vsslctrl.settings import (
    ZoneSettings,
    VolumeSettings,
    EQSettings,
    VsslSettings,
    VsslPowerSettings,
)
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


class TestVsslSettings:
    @pytest.mark.asyncio(scope="session")
    async def test_keys_exist(self, zone, eb):
        # check keys have events
        check_keys_have_events(VsslSettings.Keys, VsslSettings.Events)


class TestVolumeSettings:
    @pytest.mark.asyncio(scope="session")
    async def test_keys_exist(self, zone, eb):
        # check keys have events
        check_keys_have_events(VolumeSettings.Keys, VolumeSettings.Events)

    @pytest.mark.asyncio(scope="session")
    async def test_clamp(self, zone, eb):
        assert clamp_volume(110) == 100
        assert clamp_volume(-10) == 0
        assert clamp_volume(50) == 50


class TestEQSettings:
    @pytest.mark.asyncio(scope="session")
    async def test_keys_exist(self, zone, eb):
        # Check freq have keys
        for key, freq in enumerate(EQSettings.Freqs):
            assert hasattr(EQSettings.Keys, freq.name)

        # check keys have events
        check_keys_have_events(EQSettings.Keys, EQSettings.Events)

    @pytest.mark.asyncio(scope="session")
    async def test_clamp(self, zone, eb):
        eq = zone.settings.eq
        # check values are correctly maped and clamped to VSSL requirements
        assert eq._clamp(eq.MIN_VALUE - 30) == eq.MIN_VALUE
        assert eq._clamp(eq.MAX_VALUE + 30) == eq.MAX_VALUE

    @pytest.mark.asyncio(scope="session")
    async def test_map_clamp(self, zone, eb):
        eq = zone.settings.eq
        # Test mapping to DB
        assert eq._map_clamp(eq.MIN_VALUE, True) == eq.MIN_VALUE_DB
        assert eq._map_clamp(eq.MAX_VALUE, True) == eq.MAX_VALUE_DB
        assert eq._map_clamp(eq.MIN_VALUE_DB, False) == eq.MIN_VALUE
        assert eq._map_clamp(eq.MAX_VALUE_DB, False) == eq.MAX_VALUE
        assert eq._map_clamp(100, True) == 0  # 0db
        assert eq._map_clamp(0, False) == 100
        assert eq._map_clamp(95, True) == -5  # 5db
        assert eq._map_clamp(5, False) == 105

    @pytest.mark.asyncio(scope="session")
    async def test_setting_eq_values(self, zone, eb):
        eq = zone.settings.eq
        test_values = [90, 96, 100, 105, 108]

        for test_val in test_values:
            future_eq = eb.future(EQSettings.Events.KHZ1_CHANGE, zone.id)
            eq._set_eq_freq(EQSettings.Freqs.KHZ1, test_val)
            assert getattr(eq, EQSettings.Keys.KHZ1) == test_val
            assert await future_eq == test_val
            assert getattr(eq, f"{EQSettings.Keys.KHZ1}_db") == eq._map_clamp(
                test_val, True
            )
