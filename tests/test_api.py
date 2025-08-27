import asyncio
import pytest
import pytest_asyncio

from vsslctrl import Vssl
from vsslctrl.api_alpha import APIAlpha
from vsslctrl.api_bravo import APIBravo

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

    vssl = Vssl()

    zone = vssl.add_zone(ip)

    await vssl.initialise()

    if not zone.initialised:
        pytest.fail(f"Zone not initialised, dunno!")

    # Yield the device to the test function
    yield zone

    # Tear down. Restore state
    await vssl.disconnect()


@pytest_asyncio.fixture(scope="session")
async def eb(zone):
    return zone.vssl.event_bus


@pytest_asyncio.fixture(scope="session")
async def vssl(zone):
    return zone.vssl


class TestAPI:
    @pytest.mark.asyncio
    async def test_api_has_events(self):
        required_events = [
            "CONNECTING",
            "CONNECTED",
            "DISCONNECTING",
            "DISCONNECTED",
            "RECONNECTING",
        ]

        for event in required_events:
            assert hasattr(APIAlpha.Events, event)
            assert hasattr(APIBravo.Events, event)
