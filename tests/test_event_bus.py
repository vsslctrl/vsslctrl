import asyncio
import pytest
import pytest_asyncio
from vsslctrl.event_bus import event_bus as _event_bus


class TestEventBus:
    @pytest_asyncio.fixture(autouse=True)
    async def event_bus(self):
        event_bus = _event_bus()
        yield event_bus
        event_bus.stop()  # Ensure the event bus is stopped after each test

    @pytest.mark.asyncio
    async def test_event_bus(self, event_bus):
        # Instantiate the EventBus
        # event_bus = EventBus()

        async def publish_with_entity(self, entity=None):
            # Define a callback function to be subscribed to the event
            async def callback(data, *args, **kwargs):
                print("hello")
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
                assert hasattr(callback, "called") and callback.called is True
                assert getattr(callback, "data") == event_data
            finally:
                # Unsubscribe the callback function
                event_bus.unsubscribe(event_type, callback)
                # Ensure the callback function was not called after unsubscribing
                assert len(event_bus.subscribers.get(event_type)) == 0

        await publish_with_entity(None)
        await publish_with_entity(1)
        await publish_with_entity("test")

    @pytest.mark.asyncio
    async def test_event_bus_wildcard_event_type(self, event_bus):
        # Define a callback function to be subscribed to the event
        async def callback(data: int = 0, *args, **kwargs):
            callback.data = data + 1

        event_bus.subscribe(event_bus.WILDCARD, callback, 1)
        # Ensure the callback function is subscribed
        assert len(event_bus.subscribers.get(event_bus.WILDCARD)) == 1

        try:
            # Publish an event
            event_bus.publish("random_event_1", 1, 0)
            # Wait for a short time to allow the event to be processed
            await asyncio.sleep(0.1)
            assert getattr(callback, "data") == 1

            # Publish an event
            event_bus.publish("random_event_2.other", 1, 20)
            # Wait for a short time to allow the event to be processed
            await asyncio.sleep(0.1)
            assert getattr(callback, "data") == 21

            # Publish an event with different ID
            event_bus.publish("random_event_2", 2, 30)
            # Wait for a short time to allow the event to be processed
            await asyncio.sleep(0.1)
            assert getattr(callback, "data") == 21

        finally:
            # Unsubscribe the callback function
            event_bus.unsubscribe(event_bus.WILDCARD, callback)
            # Ensure the callback function was not called after unsubscribing
            assert len(event_bus.subscribers.get(event_bus.WILDCARD)) == 0

    @pytest.mark.asyncio
    async def test_event_bus_scoped_wildcard_event_type(self, event_bus):
        # Define a callback function to be subscribed to the event
        async def callback(data: int = 0, *args, **kwargs):
            callback.data = data + 1

        event_type = "zone.api." + event_bus.WILDCARD

        event_bus.subscribe(event_type, callback, 1)
        # Ensure the callback function is subscribed
        assert len(event_bus.subscribers.get(event_type)) == 1

        try:
            # Publish an event
            event_bus.publish("zone.api.connected", 1, 0)
            # Wait for a short time to allow the event to be processed
            await asyncio.sleep(0.1)
            assert getattr(callback, "data") == 1

            # Publish an event
            event_bus.publish("zone.api.disconnected", 1, 20)
            # Wait for a short time to allow the event to be processed
            await asyncio.sleep(0.1)
            assert getattr(callback, "data") == 21

            # Publish an different event
            event_bus.publish("zone.api", 1, 30)
            # Wait for a short time to allow the event to be processed
            await asyncio.sleep(0.1)
            assert getattr(callback, "data") == 21  # should be unchanged

            # Publish an different event
            event_bus.publish("zone", 1, 40)
            # Wait for a short time to allow the event to be processed
            await asyncio.sleep(0.1)
            assert getattr(callback, "data") == 21  # should be unchanged

        finally:
            # Unsubscribe the callback function
            event_bus.unsubscribe(event_type, callback)
            # Ensure the callback function was not called after unsubscribing
            assert len(event_bus.subscribers.get(event_type)) == 0

    @pytest.mark.asyncio
    async def test_event_bus_wildcard_entity(self, event_bus):
        # Define a callback function to be subscribed to the event
        async def callback(data: int = 0, *args, **kwargs):
            callback.data = data + 1

        test_event = "test_event"

        event_bus.subscribe(test_event, callback, event_bus.WILDCARD)
        # Ensure the callback function is subscribed
        assert len(event_bus.subscribers.get(test_event)) == 1

        try:
            # Publish an event
            event_bus.publish(test_event, 1, 0)
            await asyncio.sleep(0.1)
            assert getattr(callback, "data") == 1

            # Publish an event with different ID
            event_bus.publish(test_event, 2, 20)
            await asyncio.sleep(0.1)
            assert getattr(callback, "data") == 21

            # Publish an event with different ID
            event_bus.publish("different_event", 2, 20)
            await asyncio.sleep(0.1)
            assert getattr(callback, "data") == 21

        finally:
            # Unsubscribe the callback function
            event_bus.unsubscribe(test_event, callback)
            # Ensure the callback function was not called after unsubscribing
            assert len(event_bus.subscribers.get(test_event)) == 0

    @pytest.mark.asyncio
    async def test_event_bus_wildcard(self, event_bus):
        # Define a callback function to be subscribed to the event
        async def callback(data: int = 0, *args, **kwargs):
            callback.data = data + 1

        event_bus.subscribe(event_bus.WILDCARD, callback, event_bus.WILDCARD)
        # Ensure the callback function is subscribed
        assert len(event_bus.subscribers.get(event_bus.WILDCARD)) == 1

        try:
            # Publish an event
            event_bus.publish("random_event_1", 1, 0)
            await asyncio.sleep(0.1)
            assert getattr(callback, "data") == 1

            # Publish an event with different ID
            event_bus.publish("random_event_2", 2, 20)
            await asyncio.sleep(0.1)
            assert getattr(callback, "data") == 21

            # Publish an event with different ID
            event_bus.publish("random_event_3", 3, 30)
            await asyncio.sleep(0.1)
            assert getattr(callback, "data") == 31
        finally:
            # Unsubscribe the callback function
            event_bus.unsubscribe(event_bus.WILDCARD, callback)
            # Ensure the callback function was not called after unsubscribing
            assert len(event_bus.subscribers.get(event_bus.WILDCARD)) == 0

    @pytest.mark.asyncio
    async def test_event_bus_future(self, event_bus):
        # Subscribe the callback function to the event
        event_type = "test_future_event"
        future = event_bus.future(event_type, 1)
        # Publish event
        event_data = "test_data"
        event_bus.publish(event_type, 1, event_data)
        assert await future == event_data
        # Make sure future is unsubscribed
        assert len(event_bus.subscribers.get(event_type)) == 0
