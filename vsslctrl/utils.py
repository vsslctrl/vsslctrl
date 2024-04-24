import json
import asyncio
import logging
from enum import IntEnum
from typing import Callable
from .exceptions import VsslException

_LOGGER = logging.getLogger(__name__)

def add_logging_helpers(InstanceClass, message_prefix = ''):

    LOG_LEVELS = {
        'debug': _LOGGER.debug,
        'info': _LOGGER.info,
        'warning': _LOGGER.warning,
        'error': _LOGGER.error,
        'critical': _LOGGER.critical
    }

    # Dynamically create methods for each log level
    for level, log_func in LOG_LEVELS.items():
        setattr(
            InstanceClass, 
            f"_log_{level}", 
            lambda message, message_prefix=message_prefix, log_func=log_func: log_func(f"{message_prefix} {message}")
        )


class VsslIntEnum(IntEnum):

    @classmethod
    def is_valid(cls, value):
        try:
            cls(value)
            return True
        except ValueError:
            return False

    @classmethod
    def is_not_valid(cls, value):
        return not cls.is_valid(value)

    @classmethod
    def get(cls, value, default = None):
        try:
            return cls(value)
        except ValueError:
            return default

#
# Hex to Int
#
def hex_to_int(str: str, base: int = 16):
    return int(str, base)

#
# Clamp Volume
#
def clamp_volume(vol: int):
    return max(0, min(int(vol), 100))

#
# Cancel a task if it exsists
#
async def cancel_task_if_exists(task: asyncio.Task):
    if isinstance(task, asyncio.Task) and not task.done():
        try:
            task.cancel()
        except asyncio.CancelledError:
            pass

#
# Groups dicts by property
#
def group_list_by_property(input_list, property_key):
    grouped_dict = {}
    for item in input_list:
        property_value = item.get(property_key)
        if property_value is not None:
            grouped_dict.setdefault(property_value, []).append(item)
    return grouped_dict

#
# Repeat Timer
#
class RepeatTimer:
    
    def __init__(self, interval, function, start_delay=False, *args, **kwargs):
        self.interval = interval
        self.function = function
        self.start_delay = start_delay
        self.args = args
        self.kwargs = kwargs
        self.task = None
        self.running = False

    async def _run(self):
        while self.running:
            if self.start_delay:
                await asyncio.sleep(self.interval)

            if asyncio.iscoroutinefunction(self.function):
                await self.function(*self.args, **self.kwargs)
            else:
                self.function(*self.args, **self.kwargs)

            if not self.start_delay:
                await asyncio.sleep(self.interval)

    def start(self):
        if not self.running:
            self.running = True
            self.task = asyncio.create_task(self._run())

    def cancel(self):
        if self.running:
            self.running = False
            self.task.cancel()