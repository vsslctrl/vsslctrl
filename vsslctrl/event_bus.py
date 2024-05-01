import asyncio
from enum import IntEnum
from typing import Callable
from .utils import add_logging_helpers
from .exceptions import VsslCtrlException

#
# Event Bus
#
class EventBus:

    FUTURE_TIMEOUT = 5

    def __init__(self):

        add_logging_helpers(self, 'EventBus:')

        self.subscribers = {}
        self.event_queue = asyncio.Queue()

        self.running = False

        asyncio.create_task(self.process_events())

    #
    # Stop 
    #
    def stop(self):
        self.running = False

    #
    # Subscribe 
    #
    def subscribe(self, event_type, callback: Callable, entity='*', once=False):
        #Make sure we are using async callbacks
        if callback is not None and asyncio.iscoroutinefunction(callback):
            event_type = event_type.lower()
            if event_type not in self.subscribers:
                self.subscribers[event_type] = []
            self._log_debug(f"subscription for event: {event_type} | entity: {entity} | cb: {callback.__name__}")
            self.subscribers[event_type].append((callback, entity, once))
        else:
            message = f"EventBus: {callback.__name__} must be a coroutine. Event: {event_type} | Entity: {entity}"
            self._log_error(message)
            raise VsslCtrlException(message)
        
    #
    # Unsubscribe 
    #
    def unsubscribe(self, event_type, callback):
        event_type = event_type.lower()
        if event_type in self.subscribers:
            self.subscribers[event_type] = [cb for cb in self.subscribers[event_type] if cb[0] != callback]

    #
    # Get a future value from the event bus
    #
    def future(self, event_type, entity=None) -> asyncio.Future:
        
        future = asyncio.Future()

        async def future_callback(data, *args):
            nonlocal future
            future.set_result(data)

        self.subscribe(event_type, future_callback, entity, once=True)

        return future

    #
    # Helper to await a future with a timeout and timeout result
    #
    async def wait_future(self, future, timeout: int = FUTURE_TIMEOUT):
        if timeout != 0:
            try:
                return await asyncio.wait_for(future, timeout)
            except asyncio.TimeoutError as error:
                self._log_error(f"timeout waiting for future")
                raise error
        else:
            return await future
    #
    # wait_for, will wait for an event to be fired and return the result
    #
    async def wait_for(self, event_type, entity=None, timeout: int = FUTURE_TIMEOUT, timeout_result=None):
        future = self.future(event_type, entity)
        try:
            return await self.wait_future(future, timeout=timeout)
        except asyncio.TimeoutError as error:
            return timeout_result
        

    #
    # Publish 
    #
    def publish(self, event_type, entity=None, data=None):
        asyncio.create_task(self.publish_async(event_type, entity, data))

    #
    # Publish Async (Use when inside events loop)
    #
    async def publish_async(self, event_type, entity=None, data=None):
        event_type = event_type.lower()
        await self.event_queue.put((event_type, entity, data))
        # All events can still be scroped to entity
        #await self.event_queue.put(('*', entity, data, args, kwargs))

    #
    # Process Events
    #
    async def process_events(self):
        
        self.running = True
        
        self._log_debug(f"Started")

        while self.running:
            
            try:
                event_type, entity, data = await self.event_queue.get()

                message = f'processing event: {event_type} | entity: {entity} | data: '
                if isinstance(data, IntEnum):
                    message += f'{data.name} ({data.value})'
                else:
                    message += f"{data}"

                self._log_debug(message)

                if event_type in self.subscribers:
                    for callback, subscribed_entity, once in self.subscribers[event_type]:
                        if entity is None or subscribed_entity == entity or subscribed_entity == '*':
                            print(data, entity, event_type)
                            await callback(data, entity, event_type)
                            if once:
                                self.unsubscribe(event_type, callback)

                if '*' in self.subscribers:
                    for callback, subscribed_entity, once in self.subscribers['*']:
                        if entity is None or subscribed_entity == entity or subscribed_entity == '*':
                            print(data, entity, event_type)
                            await callback(data, entity, event_type)
                            if once:
                                self.unsubscribe('*', callback)

            except asyncio.CancelledError:
                break
            except Exception as e:
                self._log_error(f"error processing event exception: {e}")