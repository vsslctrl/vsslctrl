import asyncio


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
def cancel_task(task: asyncio.Task):
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
