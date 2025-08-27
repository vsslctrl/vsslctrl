import time
import asyncio
import random
import pytest
import pytest_asyncio

import vsslctrl as vssl_module
from vsslctrl import Vssl, Zone
from vsslctrl.device import Models as DeviceModels
from vsslctrl.transport import ZoneTransport
from vsslctrl.group import ZoneGroup
from vsslctrl.io import AnalogOutput, InputRouter, AnalogInput
from vsslctrl.settings import (
    ZoneSettings,
    VolumeSettings,
    EQSettings,
    VsslSettings,
    VsslPowerSettings,
    SubwooferSettings,
    BluetoothSettings,
)
from vsslctrl.utils import generate_number_excluding
from vsslctrl.data_structure import ZoneIDs, DeviceFeatureFlags


FUTURE_TIMEOUT = 10

# Mark all tests in this module with the pytest custom "integration" marker so
# they can be selected or deselected as a whole, eg:
# py.test -m "integration"
# or
# py.test -m "no integration"
pytestmark = pytest.mark.integration


@pytest_asyncio.fixture(scope="session")
async def zone(request):
    ip = request.config.option.ip
    if ip is None:
        pytest.fail("No ip address specified. Use the --ip option.")

    vssl = Vssl()

    zone = vssl.add_zone(ip)

    await vssl.initialise()

    if not zone.initialised:
        pytest.fail(f"Zone not initialised, dunno!")

    orig_volume = zone.volume

    # Yield the device to the test function
    yield zone

    # Tear down. Restore state
    await vssl.shutdown()

    zone.volume = orig_volume


@pytest_asyncio.fixture(scope="session")
async def eb(zone):
    return zone.vssl.event_bus


@pytest_asyncio.fixture(scope="session")
async def vssl(zone):
    return zone.vssl


class TestVssl:
    @pytest.mark.asyncio(scope="session")
    async def test_fetch_model_name(self, zone, eb, vssl):
        future_model_name = eb.future(Zone.Events.MODEL_NAME_RECEIVED)
        vssl._request_model_name()
        model_name = await eb.wait_future(future_model_name, FUTURE_TIMEOUT)
        assert model_name

    @pytest.mark.asyncio(scope="session")
    async def test_name_change(self, zone, eb, vssl):
        if not zone.vssl.model.is_multizone:
            pytest.skip(f"A.1(x), doesn't support changing device name")

        original_name = vssl.settings.name
        test_name = str(int(time.time()))

        future_name = eb.future(VsslSettings.Events.NAME_CHANGE)
        vssl.settings.name = test_name
        assert await eb.wait_future(future_name, FUTURE_TIMEOUT) == test_name
        assert vssl.settings.name == test_name

        future_name = eb.future(VsslSettings.Events.NAME_CHANGE)
        vssl.settings.name = original_name
        assert await eb.wait_future(future_name, FUTURE_TIMEOUT) == original_name
        assert vssl.settings.name == original_name

    @pytest.mark.asyncio(scope="session")
    async def test_power_adaptive_change(self, zone, eb, vssl):
        orig_state = vssl.settings.power.adaptive

        future_state = eb.future(VsslPowerSettings.Events.ADAPTIVE_CHANGE)
        vssl.settings.power.adaptive_toggle()
        assert await eb.wait_future(future_state, FUTURE_TIMEOUT) == (not orig_state)
        assert vssl.settings.power.adaptive == (not orig_state)

        future_state = eb.future(VsslPowerSettings.Events.ADAPTIVE_CHANGE)
        vssl.settings.power.adaptive = orig_state
        assert await eb.wait_future(future_state, FUTURE_TIMEOUT) == orig_state
        assert vssl.settings.power.adaptive == orig_state

    @pytest.mark.asyncio(scope="session")
    async def test_bus_1_rename(self, zone, eb, vssl):
        original_name = vssl.settings.bus_1_name
        test_name = "TestName"

        future_name = eb.future(VsslSettings.Events.BUS_1_NAME_CHANGE)
        vssl.settings.bus_1_name = test_name
        # Feedback sometime isnt sent so poll to make sure it changes
        zone._request_status_bus()
        assert await eb.wait_future(future_name, FUTURE_TIMEOUT) == test_name
        assert vssl.settings.bus_1_name == test_name

        future_name = eb.future(VsslSettings.Events.BUS_1_NAME_CHANGE)
        vssl.settings.bus_1_name = original_name
        # Feedback sometime isnt sent so poll to make sure it changes
        zone._request_status_bus()
        assert await eb.wait_future(future_name, FUTURE_TIMEOUT) == original_name
        assert vssl.settings.bus_1_name == original_name

    @pytest.mark.asyncio(scope="session")
    async def test_bus_2_rename(self, zone, eb, vssl):
        original_name = vssl.settings.bus_2_name
        test_name = "TestName"

        future_name = eb.future(VsslSettings.Events.BUS_2_NAME_CHANGE)
        vssl.settings.bus_2_name = test_name
        # Feedback sometime isnt sent so poll to make sure it changes
        zone._request_status_bus()
        assert await eb.wait_future(future_name, FUTURE_TIMEOUT) == test_name
        assert vssl.settings.bus_2_name == test_name

        future_name = eb.future(VsslSettings.Events.BUS_2_NAME_CHANGE)
        vssl.settings.bus_2_name = original_name
        # Feedback sometime isnt sent so poll to make sure it changes
        zone._request_status_bus()
        assert await eb.wait_future(future_name, FUTURE_TIMEOUT) == original_name
        assert vssl.settings.bus_2_name == original_name

    @pytest.mark.asyncio(scope="session")
    async def test_bluetooth(self, zone, eb, vssl):
        if not zone.vssl.model.supports_feature(DeviceFeatureFlags.BLUETOOTH):
            pytest.skip(f"Model {zone.vssl.model.name} doesn't support bluetooth")

        orig_state = vssl.settings.bluetooth.state

        future_state = eb.future(BluetoothSettings.Events.STATE_CHANGE)

        if not vssl.settings.bluetooth.is_on:
            vssl.settings.bluetooth.on()
        else:
            vssl.settings.bluetooth.off()

        assert await eb.wait_future(future_state, FUTURE_TIMEOUT) != orig_state

        # Make sure we are off
        vssl.settings.bluetooth.off()

        # Pairing
        future_state = eb.future(BluetoothSettings.Events.STATE_CHANGE)
        vssl.settings.bluetooth.enter_pairing()
        assert (
            await eb.wait_future(future_state, FUTURE_TIMEOUT)
            == BluetoothSettings.States.PARING
        )

        # Exit Pairing
        future_state = eb.future(BluetoothSettings.Events.STATE_CHANGE)
        vssl.settings.bluetooth.exit_pairing()
        assert (
            await eb.wait_future(future_state, FUTURE_TIMEOUT)
            == BluetoothSettings.States.DISCONNECTED
        )


class TestVolume:
    """Integration tests for the volume property."""

    @pytest.mark.asyncio(scope="session")
    async def test_volume_change(self, zone, eb):
        orig_volume = zone.volume
        random_vol = generate_number_excluding(orig_volume, 5, 15)

        future_vol = eb.future(Zone.Events.VOLUME_CHANGE, zone.host)
        zone.volume = random_vol
        assert await eb.wait_future(future_vol, FUTURE_TIMEOUT) == random_vol
        assert zone.volume == random_vol

    @pytest.mark.asyncio(scope="session")
    async def test_mute_unmute(self, zone, eb):
        # Use self._mute since self.mute is dependant on volume
        if zone._mute == True:
            future_state = eb.future(Zone.Events.MUTE_CHANGE, zone.host)
            zone.mute = False
            # Dont check future since it returns zone.mute
            await eb.wait_future(future_state, FUTURE_TIMEOUT)
            assert zone._mute == False

        future_state = eb.future(Zone.Events.MUTE_CHANGE, zone.host)
        zone.mute_toggle()
        # Dont check future since it returns zone.mute
        await eb.wait_future(future_state, FUTURE_TIMEOUT)
        assert zone._mute == True

        future_state = eb.future(Zone.Events.MUTE_CHANGE, zone.host)
        zone.mute = False
        # Dont check future since it returns zone.mute
        await eb.wait_future(future_state, FUTURE_TIMEOUT)
        assert zone._mute == False

    @pytest.mark.asyncio(scope="session")
    async def test_mute_at_volume_zero(self, zone, eb):
        # Be sure we are not a volume 0
        if zone.volume != 0:
            future_vol = eb.future(Zone.Events.VOLUME_CHANGE, zone.host)
            zone.volume = 0
            assert await eb.wait_future(future_vol, FUTURE_TIMEOUT) == 0
            assert zone.volume == 0

        # Check mute is True
        assert zone.mute == True

        random_vol = generate_number_excluding(zone.volume, 16, 20)
        future_vol = eb.future(Zone.Events.VOLUME_CHANGE, zone.host)
        zone.volume = random_vol
        assert await eb.wait_future(future_vol, FUTURE_TIMEOUT) == random_vol
        assert zone.volume == random_vol

    @pytest.mark.asyncio(scope="session")
    async def test_unmute_when_volume_changed(self, zone, eb):
        base_volume = generate_number_excluding(zone.volume, 21, 25)

        # Be sure we are not a volume 0
        future_vol = eb.future(Zone.Events.VOLUME_CHANGE, zone.host)
        zone.volume = base_volume
        assert await eb.wait_future(future_vol, FUTURE_TIMEOUT) == base_volume
        assert zone.volume == base_volume

        if not zone.mute:
            future_state = eb.future(Zone.Events.MUTE_CHANGE, zone.host)
            zone.mute = True
            # Dont check future since it returns zone.mute
            await eb.wait_future(future_state, FUTURE_TIMEOUT)
            assert zone.mute == True

        """
            Volume wont unmute if the volume is 
            set to the same as value as before muting
        """
        future_state = eb.future(Zone.Events.MUTE_CHANGE, zone.host)
        future_vol = eb.future(Zone.Events.VOLUME_CHANGE, zone.host)

        zone.volume = base_volume + 2

        assert await eb.wait_future(future_state, FUTURE_TIMEOUT) == False
        assert zone.mute == False

        assert await eb.wait_future(future_vol, FUTURE_TIMEOUT) == (base_volume + 2)
        assert zone.volume == (base_volume + 2)

    @pytest.mark.asyncio(scope="session")
    async def test_volume_raise_lower(self, zone, eb):
        test_vol = generate_number_excluding(zone.volume, 26, 30)

        # Make sure we have room for test
        future_vol = eb.future(Zone.Events.VOLUME_CHANGE, zone.host)
        zone.volume = test_vol
        assert await eb.wait_future(future_vol, FUTURE_TIMEOUT) == test_vol
        assert zone.volume == test_vol

        future_vol = eb.future(Zone.Events.VOLUME_CHANGE, zone.host)
        zone.volume_raise()
        assert await eb.wait_future(future_vol, FUTURE_TIMEOUT) == test_vol + 1
        assert zone.volume == test_vol + 1

        future_vol = eb.future(Zone.Events.VOLUME_CHANGE, zone.host)
        zone.volume_lower()
        assert await eb.wait_future(future_vol, FUTURE_TIMEOUT) == test_vol
        assert zone.volume == test_vol

        future_vol = eb.future(Zone.Events.VOLUME_CHANGE, zone.host)
        zone.volume_lower(5)
        assert await eb.wait_future(future_vol, FUTURE_TIMEOUT) == test_vol - 5
        assert zone.volume == test_vol - 5

        future_vol = eb.future(Zone.Events.VOLUME_CHANGE, zone.host)
        zone.volume_raise(5)
        assert await eb.wait_future(future_vol, FUTURE_TIMEOUT) == test_vol
        assert zone.volume == test_vol

    @pytest.mark.asyncio(scope="session")
    async def test_invalid_volume_will_be_clamped(self, zone, eb):
        orig_volume = zone.volume
        base_volume = generate_number_excluding(orig_volume, 30, 35)

        # Be sure we are not a volume 0
        future_vol = eb.future(Zone.Events.VOLUME_CHANGE, zone.host)
        zone.volume = base_volume
        assert await eb.wait_future(future_vol, FUTURE_TIMEOUT) == base_volume
        assert zone.volume == base_volume

        future_vol = eb.future(Zone.Events.VOLUME_CHANGE, zone.host)
        zone.volume = -5
        assert await eb.wait_future(future_vol, FUTURE_TIMEOUT) == 0
        assert zone.volume == 0


class TestGroup:
    @pytest.mark.asyncio(scope="session")
    async def test_partymode(self, zone, eb, vssl):
        if not zone.vssl.model.supports_feature(DeviceFeatureFlags.PARTY_ZONE):
            pytest.skip(f"Model {zone.vssl.model.name} doesn't support party mode")

        orig_setting = zone.group.is_party_zone_member

        future_state = eb.future(SubwooferSettings.Events.IS_PARTY_ZONE_MEMBER_CHANGE)
        zone.group.is_party_zone_member_toggle()
        assert await eb.wait_future(future_state, FUTURE_TIMEOUT) == test_setting
        assert zone.group.is_party_zone_member == test_setting

        future_state = eb.future(SubwooferSettings.Events.IS_PARTY_ZONE_MEMBER_CHANGE)
        zone.group.is_party_zone_member = orig_setting
        assert await eb.wait_future(future_state, FUTURE_TIMEOUT) == orig_setting
        assert zone.group.is_party_zone_member == orig_setting

    @pytest.mark.asyncio(scope="session")
    async def test_group_is_master(self, zone, eb):
        if not zone.vssl.model.supports_feature(DeviceFeatureFlags.GROUPING):
            pytest.skip(f"Model {zone.vssl.model.name} doesn't support grouping")

        if not zone.transport.is_playing:
            pytest.skip("Cant test grouping when not playing a source")

        future_state = eb.future(ZoneGroup.Events.IS_MASTER_CHANGE, zone.host)
        zone.group.add_member(3)
        assert await eb.wait_future(future_state, FUTURE_TIMEOUT) == True
        assert zone.group.is_master == True

        future_state = eb.future(ZoneGroup.Events.IS_MASTER_CHANGE, zone.host)
        zone.group.remove_member(3)
        assert await eb.wait_future(future_state, FUTURE_TIMEOUT + 2) == False
        assert zone.group.is_master == False

        # Add again so we can check dissolve
        future_state = eb.future(ZoneGroup.Events.IS_MASTER_CHANGE, zone.host)
        zone.group.add_member(3)
        assert await eb.wait_future(future_state, FUTURE_TIMEOUT) == True
        assert zone.group.is_master == True

        future_state = eb.future(ZoneGroup.Events.IS_MASTER_CHANGE, zone.host)
        zone.group.dissolve()
        assert await eb.wait_future(future_state, FUTURE_TIMEOUT) == False
        assert zone.group.is_master == False


class TestInputRouter:
    @pytest.mark.asyncio(scope="session")
    async def test_source_change(self, zone, eb):
        if not zone.vssl.model.supports_feature(DeviceFeatureFlags.INPUT_ROUTING):
            pytest.skip(f"Model {zone.vssl.model.name} doesn't support input routing")

        async def change_source(source):
            future_source = eb.future(InputRouter.Events.SOURCE_CHANGE, zone.host)
            zone.input.source = source
            assert await eb.wait_future(future_source, FUTURE_TIMEOUT) == source
            assert zone.input.source == source

        orig_source = zone.input.source

        # Test all supported sources
        for source in zone.vssl.model.input_sources:
            if source != orig_source:
                await change_source(source)

        # Back to original source
        await change_source(orig_source)

    @pytest.mark.asyncio(scope="session")
    async def test_priority_change(self, zone, eb):
        async def change_priority(priority):
            future_priority = eb.future(InputRouter.Events.PRIORITY_CHANGE, zone.host)
            zone.input.priority = priority
            assert await eb.wait_future(future_priority, FUTURE_TIMEOUT) == priority
            assert zone.input.priority == priority

        orig_priority = zone.input.priority

        for priority in InputRouter.Priorities:
            if priority != orig_priority:
                await change_priority(priority)

        # Back to original priority
        await change_priority(orig_priority)


class TestInput:
    @pytest.mark.asyncio(scope="session")
    async def test_name_change(self, zone, eb):
        original_name = zone.settings.analog_input.name
        test_name = str(int(time.time()))

        future_name = eb.future(AnalogInput.Events.NAME_CHANGE, zone.host)
        zone.settings.analog_input.name = test_name
        assert await eb.wait_future(future_name, FUTURE_TIMEOUT) == test_name
        assert zone.settings.analog_input.name == test_name

        future_name = eb.future(AnalogInput.Events.NAME_CHANGE, zone.host)
        zone.settings.analog_input.name = original_name
        assert await eb.wait_future(future_name, FUTURE_TIMEOUT) == original_name
        assert zone.settings.analog_input.name == original_name

    @pytest.mark.asyncio(scope="session")
    async def test_fixed_gain(self, zone, eb):
        original_gain = zone.settings.analog_input.fixed_gain

        if original_gain == 0:
            assert zone.settings.analog_input.has_fixed_gain == False
        else:
            assert zone.settings.analog_input.has_fixed_gain == True
            future_gain = eb.future(AnalogInput.Events.FIXED_GAIN_CHANGE, zone.host)
            zone.settings.analog_input.fixed_gain = 0
            assert await eb.wait_future(future_gain, FUTURE_TIMEOUT) == 0
            assert zone.settings.analog_input.has_fixed_gain == False

        future_gain = eb.future(AnalogInput.Events.FIXED_GAIN_CHANGE, zone.host)
        zone.settings.analog_input.fixed_gain = 52
        assert await eb.wait_future(future_gain, FUTURE_TIMEOUT) == 52
        assert zone.settings.analog_input.fixed_gain == 52
        assert zone.settings.analog_input.has_fixed_gain == True

        # Check clamped
        future_gain = eb.future(AnalogInput.Events.FIXED_GAIN_CHANGE, zone.host)
        zone.settings.analog_input.fixed_gain = 120
        assert await eb.wait_future(future_gain, FUTURE_TIMEOUT) == 100
        assert zone.settings.analog_input.fixed_gain == 100
        assert zone.settings.analog_input.has_fixed_gain == True

        if zone.settings.analog_input.fixed_gain != original_gain:
            future_gain = eb.future(AnalogInput.Events.FIXED_GAIN_CHANGE, zone.host)
            zone.settings.analog_input.fixed_gain = original_gain
            assert await eb.wait_future(future_gain, FUTURE_TIMEOUT) == original_gain
            assert zone.settings.analog_input.fixed_gain == original_gain


class TestOutputs:
    @pytest.mark.asyncio(scope="session")
    async def test_source_change(self, zone, eb):
        if not zone.vssl.model.supports_feature(DeviceFeatureFlags.OUTPUT_ROUTING):
            pytest.skip(f"Model {zone.vssl.model.name} doesn't support output routing")

        async def change_source(source):
            future_source = eb.future(AnalogOutput.Events.SOURCE_CHANGE, zone.host)
            zone.analog_output.source = source
            assert await eb.wait_future(future_source, FUTURE_TIMEOUT) == source
            assert zone.analog_output.source == source

        orig_source = zone.analog_output.source

        for source in zone.vssl.model.analog_output_sources:
            if source != orig_source:
                await change_source(source)

        # Back to original source
        await change_source(orig_source)

    @pytest.mark.asyncio(scope="session")
    async def test_is_fixed_volume(self, zone, eb):
        orig_state = zone.analog_output.is_fixed_volume

        assert isinstance(orig_state, bool)

        new_state = not orig_state

        future_state = eb.future(AnalogOutput.Events.IS_FIXED_VOLUME_CHANGE, zone.host)
        zone.analog_output.is_fixed_volume = new_state
        assert await eb.wait_future(future_state, FUTURE_TIMEOUT) == new_state
        assert zone.analog_output.is_fixed_volume == new_state

        future_state = eb.future(AnalogOutput.Events.IS_FIXED_VOLUME_CHANGE, zone.host)
        zone.analog_output.is_fixed_volume_toggle()
        assert await eb.wait_future(future_state, FUTURE_TIMEOUT) == orig_state
        assert zone.analog_output.is_fixed_volume == orig_state

    @pytest.mark.asyncio(scope="session")
    async def test_crossover(self, zone, eb, vssl):
        if not zone.vssl.model.supports_feature(DeviceFeatureFlags.SUBWOOFER_CROSSOVER):
            pytest.skip(f"Model {zone.vssl.model.name} doesn't support sub output")

        orig_setting = zone.settings.subwoofer.crossover
        test_setting = generate_number_excluding(
            orig_setting, SubwooferSettings.MIN_VALUE, SubwooferSettings.MAX_VALUE
        )

        future_state = eb.future(SubwooferSettings.Events.CROSSOVER_CHANGE)
        zone.settings.subwoofer.crossover = test_setting
        assert await eb.wait_future(future_state, FUTURE_TIMEOUT) == test_setting
        assert zone.settings.subwoofer.crossover == test_setting

        future_state = eb.future(SubwooferSettings.Events.CROSSOVER_CHANGE)
        zone.settings.subwoofer.crossover = orig_setting
        assert await eb.wait_future(future_state, FUTURE_TIMEOUT) == orig_setting
        assert zone.settings.subwoofer.crossover == orig_setting


class TestVolumeSettings:
    @pytest.mark.asyncio(scope="session")
    async def test_vol_setting_default_on(self, zone, eb):
        orig_volume = zone.settings.volume.default_on
        test_vol = generate_number_excluding(orig_volume, 10, 20)

        future_vol = eb.future(VolumeSettings.Events.DEFAULT_ON_CHANGE, zone.host)
        zone.settings.volume.default_on = test_vol
        assert await eb.wait_future(future_vol, FUTURE_TIMEOUT) == test_vol
        assert zone.settings.volume.default_on == test_vol

        future_vol = eb.future(VolumeSettings.Events.DEFAULT_ON_CHANGE, zone.host)
        zone.settings.volume.default_on = orig_volume
        assert await eb.wait_future(future_vol, FUTURE_TIMEOUT) == orig_volume
        assert zone.settings.volume.default_on == orig_volume

    @pytest.mark.asyncio(scope="session")
    async def test_vol_setting_max_left(self, zone, eb):
        orig_volume = zone.settings.volume.max_left
        test_vol = generate_number_excluding(orig_volume, 10, 50)

        future_vol = eb.future(VolumeSettings.Events.MAX_LEFT_CHANGE, zone.host)
        zone.settings.volume.max_left = test_vol
        assert await eb.wait_future(future_vol, FUTURE_TIMEOUT) == test_vol
        assert zone.settings.volume.max_left == test_vol

        future_vol = eb.future(VolumeSettings.Events.MAX_LEFT_CHANGE, zone.host)
        zone.settings.volume.max_left = orig_volume
        assert await eb.wait_future(future_vol, FUTURE_TIMEOUT) == orig_volume
        assert zone.settings.volume.max_left == orig_volume

    @pytest.mark.asyncio(scope="session")
    async def test_vol_setting_max_right(self, zone, eb):
        orig_volume = zone.settings.volume.max_right
        test_vol = generate_number_excluding(orig_volume, 10, 50)

        future_vol = eb.future(VolumeSettings.Events.MAX_RIGHT_CHANGE, zone.host)
        zone.settings.volume.max_right = test_vol
        assert await eb.wait_future(future_vol, FUTURE_TIMEOUT) == test_vol
        assert zone.settings.volume.max_right == test_vol

        future_vol = eb.future(VolumeSettings.Events.MAX_RIGHT_CHANGE, zone.host)
        zone.settings.volume.max_right = orig_volume
        assert await eb.wait_future(future_vol, FUTURE_TIMEOUT) == orig_volume
        assert zone.settings.volume.max_right == orig_volume


class TestZoneSettings:
    @pytest.mark.asyncio(scope="session")
    async def test_name_change(self, zone, eb):
        original_name = zone.settings.name
        test_name = str(int(time.time()))

        future_name = eb.future(ZoneSettings.Events.NAME_CHANGE, zone.host)
        zone.settings.name = test_name
        assert await eb.wait_future(future_name, FUTURE_TIMEOUT) == test_name
        assert zone.settings.name == test_name

        future_name = eb.future(ZoneSettings.Events.NAME_CHANGE, zone.host)
        zone.settings.name = original_name
        assert await eb.wait_future(future_name, FUTURE_TIMEOUT) == original_name
        assert zone.settings.name == original_name

    @pytest.mark.asyncio(scope="session")
    async def test_stereo_mono(self, zone, eb):
        orig_state = zone.settings.mono

        assert isinstance(orig_state, ZoneSettings.StereoMono)

        new_state = not orig_state

        future_state = eb.future(ZoneSettings.Events.MONO_CHANGE, zone.host)
        zone.settings.mono = new_state
        assert await eb.wait_future(future_state, FUTURE_TIMEOUT) == new_state
        assert zone.settings.mono == new_state

        future_state = eb.future(ZoneSettings.Events.MONO_CHANGE, zone.host)
        zone.settings.mono_toggle()
        assert await eb.wait_future(future_state, FUTURE_TIMEOUT) == orig_state
        assert zone.settings.mono == orig_state


class TestEQSettings:
    @pytest.mark.asyncio(scope="session")
    async def test_settings_eq_enable(self, zone, eb):
        orig_state = zone.settings.eq.enabled

        assert isinstance(orig_state, bool)

        new_state = not orig_state

        future_state = eb.future(EQSettings.Events.ENABLED_CHANGE, zone.host)
        zone.settings.eq.enabled = new_state
        assert await eb.wait_future(future_state, FUTURE_TIMEOUT) == new_state
        assert zone.settings.eq.enabled == new_state

        future_state = eb.future(EQSettings.Events.ENABLED_CHANGE, zone.host)
        zone.settings.eq.enabled_toggle()
        assert await eb.wait_future(future_state, FUTURE_TIMEOUT) == orig_state
        assert zone.settings.eq.enabled == orig_state

    @pytest.mark.asyncio(scope="session")
    async def test_settings_set_eq_freqs(self, zone, eb):
        for freq in EQSettings.Freqs:
            # 90 - 110 range
            freq_key = freq.name.lower()
            original_val = getattr(zone.settings.eq, freq_key)
            test_val = generate_number_excluding(
                original_val, EQSettings.MIN_VALUE, EQSettings.MAX_VALUE
            )

            future_val = eb.future(
                getattr(EQSettings.Events, f"{freq.name}_CHANGE"), zone.host
            )
            setattr(zone.settings.eq, freq_key, test_val)
            assert await eb.wait_future(future_val, FUTURE_TIMEOUT) == test_val
            assert getattr(zone.settings.eq, freq_key) == test_val

            future_val = eb.future(
                getattr(EQSettings.Events, f"{freq.name}_CHANGE"), zone.host
            )
            setattr(zone.settings.eq, freq_key, original_val)
            assert await eb.wait_future(future_val, FUTURE_TIMEOUT) == original_val
            assert getattr(zone.settings.eq, freq_key) == original_val

            # DB Values
            freq_key = f"{freq.name.lower()}_db"
            original_val = getattr(zone.settings.eq, freq_key)
            test_val = generate_number_excluding(
                original_val, EQSettings.MIN_VALUE_DB, EQSettings.MAX_VALUE_DB
            )

            future_val = eb.future(
                getattr(EQSettings.Events, f"{freq.name}_CHANGE"), zone.host
            )
            setattr(zone.settings.eq, freq_key, test_val)
            # Always returns value in 90 - 110 range
            assert await eb.wait_future(
                future_val, FUTURE_TIMEOUT
            ) == zone.settings.eq._map_clamp(test_val, False)
            assert getattr(zone.settings.eq, freq_key) == test_val

            future_val = eb.future(
                getattr(EQSettings.Events, f"{freq.name}_CHANGE"), zone.host
            )
            setattr(zone.settings.eq, freq_key, original_val)
            # Always returns value in 90 - 110 range
            assert await eb.wait_future(
                future_val, FUTURE_TIMEOUT
            ) == zone.settings.eq._map_clamp(original_val, False)
            assert getattr(zone.settings.eq, freq_key) == original_val


class TestTransport:
    @pytest.mark.asyncio(scope="session")
    async def test_transport(self, zone, eb):
        if not zone.transport.is_playing:
            pytest.skip("Cant test transport when not playing a source")

        assert zone.transport.state == ZoneTransport.States.PLAY
        assert zone.transport.is_playing

        future_state = eb.future(ZoneTransport.Events.STATE_CHANGE_PAUSE, zone.host)
        zone.transport.state = ZoneTransport.States.PAUSE
        assert await eb.wait_future(future_state, FUTURE_TIMEOUT) == True
        assert zone.transport.state == ZoneTransport.States.PAUSE
        assert zone.transport.is_paused

        future_state = eb.future(ZoneTransport.Events.STATE_CHANGE_PLAY, zone.host)
        zone.transport.play()
        assert await eb.wait_future(future_state, FUTURE_TIMEOUT) == True
        assert zone.transport.is_playing

        future_state = eb.future(ZoneTransport.Events.STATE_CHANGE, zone.host)
        zone.pause()
        assert (
            await eb.wait_future(future_state, FUTURE_TIMEOUT)
            == ZoneTransport.States.PAUSE
        )
        assert zone.transport.is_paused

        future_state = eb.future(ZoneTransport.Events.STATE_CHANGE, zone.host)
        zone.play()
        assert (
            await eb.wait_future(future_state, FUTURE_TIMEOUT)
            == ZoneTransport.States.PLAY
        )
        assert zone.transport.is_playing

        # future_state = eb.future(ZoneTransport.Events.STATE_CHANGE, zone.host)
        # zone.stop()
        # assert (
        #     await eb.wait_future(future_state, FUTURE_TIMEOUT)
        #     == ZoneTransport.States.STOP
        # )
        # assert zone.transport.is_stopped
