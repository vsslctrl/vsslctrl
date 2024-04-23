import asyncio
import pytest
import pytest_asyncio
from vsslctrl.event_bus import EventBus


class TestEventBus:

    @pytest_asyncio.fixture(autouse=True)
    async def event_bus(self):
        bus = EventBus()
        yield bus
        bus.stop()  # Ensure the event bus is stopped after each test


    @pytest.mark.asyncio
    async def test_event_bus(self, event_bus):
        # Instantiate the EventBus
        #event_bus = EventBus()

        async def publish_with_entity(self, entity = None):

            # Define a callback function to be subscribed to the event
            async def callback(data, *args, **kwargs):
                callback.called = True
                callback.data = data

            # Subscribe the callback function to the event
            event_type = "test_event"
            event_bus.subscribe(event_type, callback, entity)
            assert event_bus.subscribers.get(event_type) is not None
            assert len(event_bus.subscribers.get(event_type)) == 1
            assert event_bus.subscribers.get(event_type)[0][0] == callback


            try:
                # Publish the event
                event_data = "test_data"
                event_bus.publish(event_type, data=event_data, entity=entity)

                # Wait for a short time to allow the event to be processed
                await asyncio.sleep(0.1)

                # Assert that the callback function has been called
                assert hasattr(callback, 'called') and callback.called is True
                assert getattr(callback, 'data') == event_data
            finally:
                # Unsubscribe the callback function
                event_bus.unsubscribe(event_type, callback)
                # Ensure the callback function was not called after unsubscribing
                assert len(event_bus.subscribers.get(event_type)) == 0


        await publish_with_entity(None)
        await publish_with_entity(1)
        await publish_with_entity('tet')

    @pytest.mark.asyncio
    async def test_event_bus_future(self, event_bus):

        # Subscribe the callback function to the event
        event_type = "test_event"
        future = event_bus.future(event_type, 1)
        event_data = "test_data"
        event_bus.publish(event_type, data=event_data, entity=1)
        data = await future
        assert data == event_data
        assert len(event_bus.subscribers.get(event_type)) == 0


