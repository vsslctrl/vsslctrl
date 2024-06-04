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
from vsslctrl.settings import ZoneSettings, VolumeSettings, EQSettings, VsslSettings, VsslPowerSettings



FUTURE_TIMEOUT = 5

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

    zone = request.config.option.zone
    if zone is None:
        pytest.fail("No Zone specified. Use the --zone option.")

    vssl_instance = vssl_module.Vssl()
    zone_instance = vssl_instance.add_zone(zone, ip)

    asyncio.create_task(vssl_instance.initialise())

    try:
        await asyncio.wait_for(zone_instance.initialisation.wait(), 3)
    except asyncio.TimeoutError:
        pytest.fail(f"Couldnt connect to Zone at {ip}, not initialised")
        

    if not zone_instance.transport.is_playing or zone_instance.input.source != InputRouter.Sources.STREAM:
        pytest.fail(
            "Integration tests on the VSSL class must be run "
            "with the VSSL zone playing a stream (not analog input)"
        )


    original_volume = zone_instance.volume

    future_vol = vssl_instance.event_bus.future(Zone.Events.VOLUME_CHANGE, zone_instance.id)
    zone_instance.volume = 50
    await vssl_instance.event_bus.wait_future(future_vol, FUTURE_TIMEOUT)

    # Yield the device to the test function
    yield zone_instance

    future_vol = vssl_instance.event_bus.future(Zone.Events.VOLUME_CHANGE, zone_instance.id)
    zone_instance.volume = original_volume
    await vssl_instance.event_bus.wait_future(future_vol, FUTURE_TIMEOUT)

    # Tear down. Restore state
    await vssl_instance.disconnect()


@pytest_asyncio.fixture(scope="session")
async def eb(zone):
    return zone.vssl.event_bus

@pytest_asyncio.fixture(scope="session")
async def vssl(zone):
    return zone.vssl

class TestVssl:

    @pytest.mark.asyncio(scope="session")
    async def test_name_change(self, zone, eb, vssl):

        original_name = vssl.settings.name
        test_name = str(int(time.time()))
        
        future_name = eb.future(VsslSettings.Events.NAME_CHANGE, 0)

        vssl.settings.name = test_name
        assert await eb.wait_future(future_name, FUTURE_TIMEOUT) == test_name
        assert vssl.settings.name == test_name

        future_name = eb.future(VsslSettings.Events.NAME_CHANGE, 0)

        vssl.settings.name = original_name
        assert await eb.wait_future(future_name, FUTURE_TIMEOUT) == original_name
        assert vssl.settings.name == original_name


    @pytest.mark.asyncio(scope="session")
    async def test_optical_input_name_change(self, zone, eb, vssl):

        original_name = vssl.settings.optical_input_name
        test_name = str(int(time.time()))

        future_name = eb.future(VsslSettings.Events.OPTICAL_INPUT_NAME_CHANGE, 0)

        vssl.settings.optical_input_name = test_name
        assert await  eb.wait_future(future_name, FUTURE_TIMEOUT) == test_name
        assert vssl.settings.optical_input_name == test_name

        future_name = eb.future(VsslSettings.Events.OPTICAL_INPUT_NAME_CHANGE, 0)

        vssl.settings.optical_input_name = original_name
        assert await  eb.wait_future(future_name, FUTURE_TIMEOUT) == original_name
        assert vssl.settings.optical_input_name == original_name


    @pytest.mark.asyncio(scope="session")
    async def test_power_adaptive_change(self, zone, eb, vssl):

        original_state = vssl.settings.power.adaptive

        if original_state != True:
            future_state = eb.future(VsslPowerSettings.Events.ADAPTIVE_CHANGE, 0)
            vssl.settings.power.adaptive = True
            await eb.wait_future(future_state, FUTURE_TIMEOUT)
            assert vssl.settings.power.adaptive == True

        future_state = eb.future(VsslPowerSettings.Events.ADAPTIVE_CHANGE, 0)
        vssl.settings.power.adaptive_toggle()
        assert await eb.wait_future(future_state, FUTURE_TIMEOUT) == False
        assert vssl.settings.power.adaptive == False

        if original_state != False:
            future_state = eb.future(VsslPowerSettings.Events.ADAPTIVE_CHANGE, 0)
            vssl.settings.power.adaptive = True
            await eb.wait_future(future_state, FUTURE_TIMEOUT)
            assert vssl.settings.power.adaptive == True

        assert vssl.settings.power.adaptive == original_state

 

class TestVolume:
    """Integration tests for the volume property."""

    @pytest.mark.asyncio(scope="session")
    async def test_valid_volumes(self, zone, eb):
        random_vol = random.randint(15, 25) #less than whats set when setting up zone
        future_vol = eb.future(Zone.Events.VOLUME_CHANGE, zone.id)
        zone.volume = random_vol
        assert await eb.wait_future(future_vol, FUTURE_TIMEOUT) == random_vol
        assert zone.volume == random_vol

    @pytest.mark.asyncio(scope="session")
    async def test_mute_unmute(self, zone, eb):

        if zone.mute == True:
            future_state = eb.future(Zone.Events.MUTE_CHANGE, zone.id)
            zone.mute = False
            assert await eb.wait_future(future_state, FUTURE_TIMEOUT) == False

        future_state = eb.future(Zone.Events.MUTE_CHANGE, zone.id)
        zone.mute_toggle()
        assert await eb.wait_future(future_state, FUTURE_TIMEOUT) == True
        assert zone.mute == True

        future_state = eb.future(Zone.Events.MUTE_CHANGE, zone.id)
        zone.mute = False
        assert await eb.wait_future(future_state, FUTURE_TIMEOUT) == False

    @pytest.mark.asyncio(scope="session")
    async def test_unmute_when_volume_changed(self, zone, eb):
        original_vol = zone.volume

        if zone.mute == False:
            future_state = eb.future(Zone.Events.MUTE_CHANGE, zone.id)
            zone.mute = True
            assert await eb.wait_future(future_state, FUTURE_TIMEOUT) == True

        """
            Volume wont unmute if the volume is 
            set to the same as value as before muting
        """ 
        future_state = eb.future(Zone.Events.MUTE_CHANGE, zone.id)
        future_vol = eb.future(Zone.Events.VOLUME_CHANGE, zone.id)

        zone.volume = original_vol + 2

        assert await eb.wait_future(future_state, FUTURE_TIMEOUT) == False
        assert zone.mute == False

        assert await eb.wait_future(future_vol, FUTURE_TIMEOUT) == (original_vol + 2)
        assert zone.volume == (original_vol + 2)

    @pytest.mark.asyncio(scope="session")
    async def test_volume_raise_lower(self, zone, eb):
        original_vol = zone.volume

        future_vol = eb.future(Zone.Events.VOLUME_CHANGE, zone.id)
        zone.volume_raise()
        assert await eb.wait_future(future_vol, FUTURE_TIMEOUT) == original_vol + 1
        assert zone.volume == original_vol + 1

        future_vol = eb.future(Zone.Events.VOLUME_CHANGE, zone.id)
        zone.volume_lower()
        assert await eb.wait_future(future_vol, FUTURE_TIMEOUT) == original_vol
        assert zone.volume == original_vol

        future_vol = eb.future(Zone.Events.VOLUME_CHANGE, zone.id)
        zone.volume_lower(5)
        assert await eb.wait_future(future_vol, FUTURE_TIMEOUT) == original_vol - 5
        assert zone.volume == original_vol - 5

        future_vol = eb.future(Zone.Events.VOLUME_CHANGE, zone.id)
        zone.volume_raise(5)
        assert await eb.wait_future(future_vol, FUTURE_TIMEOUT) == original_vol
        assert zone.volume == original_vol


    @pytest.mark.asyncio(scope="session")
    async def test_invalid_volume_will_be_clamped(self, zone, eb):
        future_vol = eb.future(Zone.Events.VOLUME_CHANGE, zone.id)
        zone.volume = -5
        assert await eb.wait_future(future_vol, FUTURE_TIMEOUT) == 0
        assert zone.volume == 0

class TestGroup:

    @pytest.mark.asyncio(scope="session")
    async def test_group_is_master(self, zone, eb):
        assert isinstance(zone.group.index, int)
        assert zone.group.index != zone.id
        assert zone.group.index != 0
        assert zone.group.is_master == False

        future_state = eb.future(ZoneGroup.Events.IS_MASTER_CHANGE, zone.id)
        zone.group.add_member(3)
        assert await eb.wait_future(future_state, FUTURE_TIMEOUT) == True
        assert zone.group.is_master == True

        future_state = eb.future(ZoneGroup.Events.IS_MASTER_CHANGE, zone.id)
        zone.group.remove_member(3)
        assert await eb.wait_future(future_state, FUTURE_TIMEOUT + 2) == False
        assert zone.group.is_master == False

        # Add again so we can check dissolve
        future_state = eb.future(ZoneGroup.Events.IS_MASTER_CHANGE, zone.id)
        zone.group.add_member(3)
        assert await eb.wait_future(future_state, FUTURE_TIMEOUT) == True
        assert zone.group.is_master == True

        future_state = eb.future(ZoneGroup.Events.IS_MASTER_CHANGE, zone.id)
        zone.group.dissolve()
        assert await eb.wait_future(future_state, FUTURE_TIMEOUT) == False
        assert zone.group.is_master == False

class TestInputRouter:

    @pytest.mark.asyncio(scope="session")
    async def test_source_change(self, zone, eb):

        original_source = zone.input.source

        if original_source != InputRouter.Sources.STREAM:
            future_source = eb.future(InputRouter.Events.SOURCE_CHANGE, zone.id)
            zone.input.source = InputRouter.Sources.STREAM
            assert await eb.wait_future(future_source, FUTURE_TIMEOUT) == InputRouter.Sources.STREAM
            assert zone.input.source == InputRouter.Sources.STREAM

        # Optical
        future_source = eb.future(InputRouter.Events.SOURCE_CHANGE, zone.id)
        zone.input.source = InputRouter.Sources.OPTICAL_IN
        assert await eb.wait_future(future_source, FUTURE_TIMEOUT) == InputRouter.Sources.OPTICAL_IN
        assert zone.input.source == InputRouter.Sources.OPTICAL_IN

        # AI 1
        future_source = eb.future(InputRouter.Events.SOURCE_CHANGE, zone.id)
        zone.input.source = InputRouter.Sources.ANALOG_IN_1
        assert await eb.wait_future(future_source, FUTURE_TIMEOUT) == InputRouter.Sources.ANALOG_IN_1
        assert zone.input.source == InputRouter.Sources.ANALOG_IN_1

        #Back to original source
        future_source = eb.future(InputRouter.Events.SOURCE_CHANGE, zone.id)
        zone.input.source = original_source
        assert await eb.wait_future(future_source, FUTURE_TIMEOUT) == original_source
        assert zone.input.source == original_source


    @pytest.mark.asyncio(scope="session")
    async def test_priority_change(self, zone, eb):

        oringal_router_priority = zone.input.priority

        if zone.input.priority != InputRouter.Priorities.STREAM:
            future_priority = eb.future(InputRouter.Events.PRIORITY_CHANGE, zone.id)
            zone.input.priority = InputRouter.Priorities.STREAM
            assert await eb.wait_future(future_priority, FUTURE_TIMEOUT) == InputRouter.Priorities.STREAM
            assert zone.input.priority == InputRouter.Priorities.STREAM

        future_priority = eb.future(InputRouter.Events.PRIORITY_CHANGE, zone.id)
        zone.input.priority = InputRouter.Priorities.LOCAL
        assert await eb.wait_future(future_priority, FUTURE_TIMEOUT) == InputRouter.Priorities.LOCAL
        assert zone.input.priority == InputRouter.Priorities.LOCAL

        if zone.input.priority != oringal_router_priority:
            future_priority = eb.future(InputRouter.Events.PRIORITY_CHANGE, zone.id)
            zone.input.priority = oringal_router_priority
            assert await eb.wait_future(future_priority, FUTURE_TIMEOUT) == oringal_router_priority
            assert zone.input.priority == oringal_router_priority
class TestAnalogOutput:

    @pytest.mark.asyncio(scope="session")
    async def test_source_change(self, zone, eb):

        original_source = zone.analog_output.source

        if original_source != AnalogOutput.Sources.OFF:
            future_source = eb.future(AnalogOutput.Events.SOURCE_CHANGE, zone.id)
            zone.analog_output.source = AnalogOutput.Sources.OFF
            assert await eb.wait_future(future_source, FUTURE_TIMEOUT) == AnalogOutput.Sources.OFF
            assert zone.analog_output.source == AnalogOutput.Sources.OFF

        future_source = eb.future(AnalogOutput.Events.SOURCE_CHANGE, zone.id)
        zone.analog_output.source = AnalogOutput.Sources.ZONE_1
        assert await eb.wait_future(future_source, FUTURE_TIMEOUT) == AnalogOutput.Sources.ZONE_1
        assert zone.analog_output.source == AnalogOutput.Sources.ZONE_1

        future_source = eb.future(AnalogOutput.Events.SOURCE_CHANGE, zone.id)
        zone.analog_output.source = AnalogOutput.Sources.OPTICAL_IN
        assert await eb.wait_future(future_source, FUTURE_TIMEOUT) == AnalogOutput.Sources.OPTICAL_IN
        assert zone.analog_output.source == AnalogOutput.Sources.OPTICAL_IN

        if zone.analog_output.source != original_source:
            future_source = eb.future(AnalogOutput.Events.SOURCE_CHANGE, zone.id)
            zone.analog_output.source = original_source
            assert await eb.wait_future(future_source, FUTURE_TIMEOUT) == original_source
            assert zone.analog_output.source == original_source

    @pytest.mark.asyncio(scope="session")
    async def test_is_fixed_volume(self, zone, eb):

        original_state = zone.analog_output.is_fixed_volume
        
        assert isinstance(original_state, bool)

        new_state = not original_state

        future_state = eb.future(AnalogOutput.Events.IS_FIXED_VOLUME_CHANGE, zone.id)
        zone.analog_output.is_fixed_volume = new_state
        assert await eb.wait_future(future_state, FUTURE_TIMEOUT) == new_state
        assert zone.analog_output.is_fixed_volume == new_state


        future_state = eb.future(AnalogOutput.Events.IS_FIXED_VOLUME_CHANGE, zone.id)
        zone.analog_output.is_fixed_volume_toggle()
        assert await eb.wait_future(future_state, FUTURE_TIMEOUT) == original_state
        assert zone.analog_output.is_fixed_volume == original_state
class TestVolumeSettings:

    @pytest.mark.asyncio(scope="session")
    async def test_vol_setting_default_on(self, zone, eb):

        original_vol = zone.settings.volume.default_on
        test_vol = 50 if original_vol != 50 else 40

        future_vol = eb.future(VolumeSettings.Events.DEFAULT_ON_CHANGE, zone.id)
        zone.settings.volume.default_on = test_vol
        assert await eb.wait_future(future_vol, FUTURE_TIMEOUT) == test_vol
        assert zone.settings.volume.default_on == test_vol

        future_vol = eb.future(VolumeSettings.Events.DEFAULT_ON_CHANGE, zone.id)
        zone.settings.volume.default_on = original_vol
        assert await eb.wait_future(future_vol, FUTURE_TIMEOUT) == original_vol
        assert zone.settings.volume.default_on == original_vol


    @pytest.mark.asyncio(scope="session")
    async def test_vol_setting_max_left(self, zone, eb):

        original_vol = zone.settings.volume.max_left
        test_vol = 50 if original_vol != 50 else 40

        future_vol = eb.future(VolumeSettings.Events.MAX_LEFT_CHANGE, zone.id)
        zone.settings.volume.max_left = test_vol
        assert await eb.wait_future(future_vol, FUTURE_TIMEOUT) == test_vol
        assert zone.settings.volume.max_left == test_vol

        future_vol = eb.future(VolumeSettings.Events.MAX_LEFT_CHANGE, zone.id)
        zone.settings.volume.max_left = original_vol
        assert await eb.wait_future(future_vol, FUTURE_TIMEOUT) == original_vol
        assert zone.settings.volume.max_left == original_vol

    @pytest.mark.asyncio(scope="session")
    async def test_vol_setting_max_right(self, zone, eb):

        original_vol = zone.settings.volume.max_right
        test_vol = 50 if original_vol != 50 else 40

        future_vol = eb.future(VolumeSettings.Events.MAX_RIGHT_CHANGE, zone.id)
        zone.settings.volume.max_right = test_vol
        assert await eb.wait_future(future_vol, FUTURE_TIMEOUT) == test_vol
        assert zone.settings.volume.max_right == test_vol

        future_vol = eb.future(VolumeSettings.Events.MAX_RIGHT_CHANGE, zone.id)
        zone.settings.volume.max_right = original_vol
        assert await eb.wait_future(future_vol, FUTURE_TIMEOUT) == original_vol
        assert zone.settings.volume.max_right == original_vol

class TestAnalogInput:

    @pytest.mark.asyncio(scope="session")
    async def test_name_change(self, zone, eb):

        original_name = zone.settings.analog_input.name
        test_name = str(int(time.time()))
        
        future_name = eb.future(AnalogInput.Events.NAME_CHANGE, zone.id)
        zone.settings.analog_input.name = test_name
        assert await eb.wait_future(future_name, FUTURE_TIMEOUT) == test_name
        assert zone.settings.analog_input.name == test_name

        future_name = eb.future(AnalogInput.Events.NAME_CHANGE, zone.id)
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
            future_gain = eb.future(AnalogInput.Events.FIXED_GAIN_CHANGE, zone.id)
            zone.settings.analog_input.fixed_gain = 0
            assert await eb.wait_future(future_gain, FUTURE_TIMEOUT) == 0
            assert zone.settings.analog_input.has_fixed_gain == False

        future_gain = eb.future(AnalogInput.Events.FIXED_GAIN_CHANGE, zone.id)
        zone.settings.analog_input.fixed_gain = 52
        assert await eb.wait_future(future_gain, FUTURE_TIMEOUT) == 52
        assert zone.settings.analog_input.fixed_gain == 52
        assert zone.settings.analog_input.has_fixed_gain == True

        #Check clamped
        future_gain = eb.future(AnalogInput.Events.FIXED_GAIN_CHANGE, zone.id)
        zone.settings.analog_input.fixed_gain = 120
        assert await eb.wait_future(future_gain, FUTURE_TIMEOUT) == 100
        assert zone.settings.analog_input.fixed_gain == 100
        assert zone.settings.analog_input.has_fixed_gain == True

        if zone.settings.analog_input.fixed_gain != original_gain:
            future_gain = eb.future(AnalogInput.Events.FIXED_GAIN_CHANGE, zone.id)
            zone.settings.analog_input.fixed_gain = original_gain
            assert await eb.wait_future(future_gain, FUTURE_TIMEOUT) == original_gain
            assert zone.settings.analog_input.fixed_gain == original_gain

class TestZoneSettings:

    @pytest.mark.asyncio(scope="session")
    async def test_name_change(self, zone, eb):

        original_name = zone.settings.name
        test_name = str(int(time.time()))
        
        future_name = eb.future(ZoneSettings.Events.NAME_CHANGE, zone.id)
        zone.settings.name = test_name
        assert await eb.wait_future(future_name, FUTURE_TIMEOUT) == test_name
        assert zone.settings.name == test_name

        future_name = eb.future(ZoneSettings.Events.NAME_CHANGE, zone.id)
        zone.settings.name = original_name
        assert await eb.wait_future(future_name, FUTURE_TIMEOUT) == original_name
        assert zone.settings.name == original_name


    @pytest.mark.asyncio(scope="session")
    async def test_stereo_mono(self, zone, eb):

        original_state = zone.settings.mono
        
        assert isinstance(original_state, ZoneSettings.StereoMono)

        new_state = not original_state

        future_state = eb.future(ZoneSettings.Events.MONO_CHANGE, zone.id)
        zone.settings.mono = new_state
        assert await eb.wait_future(future_state, FUTURE_TIMEOUT) == new_state
        assert zone.settings.mono == new_state


        future_state = eb.future(ZoneSettings.Events.MONO_CHANGE, zone.id)
        zone.settings.mono_toggle()
        assert await eb.wait_future(future_state, FUTURE_TIMEOUT) == original_state
        assert zone.settings.mono == original_state




class TestEQSettings:
    @pytest.mark.asyncio(scope="session")
    async def test_settings_eq_enable(self, zone, eb):

        original_state = zone.settings.eq.enabled

        assert isinstance(original_state, bool)

        new_state = not original_state

        future_state = eb.future(EQSettings.Events.ENABLED_CHANGE, zone.id)
        zone.settings.eq.enabled = new_state
        assert await eb.wait_future(future_state, FUTURE_TIMEOUT) == new_state
        assert zone.settings.eq.enabled == new_state


        future_state = eb.future(EQSettings.Events.ENABLED_CHANGE, zone.id)
        zone.settings.eq.enabled_toggle()
        assert await eb.wait_future(future_state, FUTURE_TIMEOUT) == original_state
        assert zone.settings.eq.enabled == original_state


    @pytest.mark.asyncio(scope="session")
    async def test_settings_set_eq_freqs(self, zone, eb):

        for freq in EQSettings.Freqs:

            # Noraml Values
            freq_key = freq.name.lower()
            original_val = getattr(zone.settings.eq, freq_key)
            test_val = 99 if original_val != 99 else 98

            future_val = eb.future(getattr(EQSettings.Events, f'{freq.name}_CHANGE'), zone.id)
            setattr(zone.settings.eq, freq_key, test_val)
            assert await eb.wait_future(future_val, FUTURE_TIMEOUT) == test_val
            assert getattr(zone.settings.eq, freq_key) == test_val

            future_val = eb.future(getattr(EQSettings.Events, f'{freq.name}_CHANGE'), zone.id)
            setattr(zone.settings.eq, freq_key, original_val)
            assert await eb.wait_future(future_val, FUTURE_TIMEOUT) == original_val
            assert getattr(zone.settings.eq, freq_key) == original_val

            # DB Values
            freq_key = f'{freq.name.lower()}_db'
            original_val = getattr(zone.settings.eq, freq_key)
            test_val = -7 if original_val != -7 else -6

            future_val = eb.future(getattr(EQSettings.Events, f'{freq.name}_CHANGE'), zone.id)
            setattr(zone.settings.eq, freq_key, test_val)
            # Always returns value in 90 - 110 range
            assert await eb.wait_future(future_val, FUTURE_TIMEOUT) == zone.settings.eq._map_clamp(test_val, False)
            assert getattr(zone.settings.eq, freq_key) == test_val

            future_val = eb.future(getattr(EQSettings.Events, f'{freq.name}_CHANGE'), zone.id)
            setattr(zone.settings.eq, freq_key, original_val)
            # Always returns value in 90 - 110 range
            assert await eb.wait_future(future_val, FUTURE_TIMEOUT) == zone.settings.eq._map_clamp(original_val, False)
            assert getattr(zone.settings.eq, freq_key) == original_val

class TestTransport:

    @pytest.mark.asyncio(scope="session")
    async def test_transport(self, zone, eb):
        assert zone.transport.state == ZoneTransport.States.PLAY
        assert zone.transport.is_playing

        future_state = eb.future(ZoneTransport.Events.STATE_CHANGE_PAUSE, zone.id)
        zone.transport.state = ZoneTransport.States.PAUSE
        assert await eb.wait_future(future_state, FUTURE_TIMEOUT) == True
        assert zone.transport.state == ZoneTransport.States.PAUSE
        assert zone.transport.is_paused

        future_state = eb.future(ZoneTransport.Events.STATE_CHANGE_PLAY, zone.id)
        zone.transport.play()
        assert await eb.wait_future(future_state, FUTURE_TIMEOUT) == True
        assert zone.transport.is_playing

        future_state = eb.future(ZoneTransport.Events.STATE_CHANGE, zone.id)
        zone.pause()
        assert await eb.wait_future(future_state, FUTURE_TIMEOUT) == ZoneTransport.States.PAUSE
        assert zone.transport.is_paused

        future_state = eb.future(ZoneTransport.Events.STATE_CHANGE, zone.id)
        zone.play()
        assert await eb.wait_future(future_state, FUTURE_TIMEOUT) == ZoneTransport.States.PLAY
        assert zone.transport.is_playing

        future_state = eb.future(ZoneTransport.Events.STATE_CHANGE, zone.id)
        zone.stop()
        assert await eb.wait_future(future_state, FUTURE_TIMEOUT) == ZoneTransport.States.STOP
        assert zone.transport.is_stopped




 



        
