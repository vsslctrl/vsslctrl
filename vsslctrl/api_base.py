from abc import ABC, abstractmethod
import asyncio
from random import randrange
from asyncio.exceptions import IncompleteReadError
import logging
from typing import Callable, final

from .utils import cancel_task
from .exceptions import ZoneConnectionError
from .decorators import logging_helpers


class APITaskGroup:
    def __init__(self):
        self._tasks = []

    @property
    def tasks(self):
        return self._tasks

    def add(self, task_cr):
        task = asyncio.create_task(task_cr)
        self._tasks.append(task)

    def extend(self, tasks: list):
        for task in tasks:
            self.add(task)

    async def cancel(self):
        # Cancel all tasks in the group
        for task in self._tasks:
            cancel_task(task)
        self._tasks = []

    async def wait():
        return await asyncio.gather(*self._tasks)


@logging_helpers("Base API:")
class APIBase(ABC):
    TIMEOUT = 5  # seconds
    KEEP_ALIVE = 10  # seconds
    BACKOFF_MIN = 15  # seconds
    BACKOFF_MAX = 300  # 5 minutes

    FRIST_BYTE = 1

    def __init__(self, host, port):
        self.host = host
        self.port = port

        self._reader = None
        self._writer = None
        self._writer_queue: asyncio.Queue = asyncio.Queue()

        self._disconnecting = False
        self._connecting = False
        self.connection_event = asyncio.Event()

        self._keep_alive_received = False
        self._keep_connected_task = None
        self._reconnection_attempts = 0

        self._task_group = APITaskGroup()

    @property
    def connected(self):
        if self.connection_event is None:
            return False
        return self.connection_event.is_set()

    @property
    def _reconnecting(self):
        return self._disconnecting or self._connecting

    #
    # Send a request
    #
    def send(self, data):
        if self._writer_queue and self.connected:
            self._writer_queue.put_nowait(data)

    #
    # Connect
    #
    @final
    async def connect(self):
        if self.connected:
            return self.connected

        self._connecting = True

        try:
            self._log_debug(f"Attemping connection to {self.host}:{self.port}")
            self._reader, self._writer = await asyncio.wait_for(
                asyncio.open_connection(self.host, self.port), self.TIMEOUT
            )

            # Connected
            self.connection_event.set()

            # cancel any reconnecting loops
            self._cancel_keep_connected()

            # Groups tasks for easy handling
            self._task_group.extend(
                [
                    self._receive_first_byte(),
                    self._send_bytes(),
                    self._send_keepalive_base(),
                ]
            )

            self._log_info(f"Connected to {self.host}:{self.port}")

        except (asyncio.TimeoutError, asyncio.CancelledError):
            message = f"Connection to {self.host}:{self.port} timed out"
            self._log_error(message)
            self.connection_event.clear()
            raise ZoneConnectionError(message)
        except ConnectionRefusedError:
            message = f"Connection to {self.host}:{self.port} refused"
            self._log_error(message)
            self.connection_event.clear()
            raise ZoneConnectionError(message)
        except Exception as e:
            self._log_error(
                f"Connection to {self.host}:{self.port} failed with exception {e}"
            )
            self.connection_event.clear()
            raise
        finally:
            self._connecting = False

        return self.connected

    #
    # Disconnect
    #
    @final
    async def disconnect(self):
        self._disconnecting = True

        # cancel any reconnecting loops
        self._cancel_keep_connected()

        # Break Loops
        if self.connection_event:
            self.connection_event.clear()

        await self._task_group.cancel()

        if self._writer:
            try:
                # Writer hangs on disconnect sometimes
                self._writer.close()
                await asyncio.wait_for(self._writer.wait_closed(), self.TIMEOUT)

            except asyncio.CancelledError:
                self._log_debug(f"writer close timeout")
            except asyncio.TimeoutError as e:
                self._log_error(f"Timeout while closing connection: {e}")
                # Handle the timeout: log, retry, or take other actions
            except ConnectionResetError as e:
                self._log_error(f"Connection reset by peer: {e}")
                # Handle the error: log, retry, or take other actions
            except Exception as e:
                self._log_error(f"Unexpected error occurred while disconnecting: {e}")
                # Handle unexpected errors
            finally:
                self._writer = None

        self._reader = None

        self._log_info(f"{self.host}:{self.port}: disconnected")

        self._disconnecting = False

        return not self.connected

    #
    # Reconnect
    #
    @final
    async def reconnect(self):
        if not self._reconnecting and not self._is_keep_connected_running():
            await self.disconnect()
            self._keep_connected()

    #
    # Is keep connected task running
    #
    @final
    def _is_keep_connected_running(self):
        return (
            isinstance(self._keep_connected_task, asyncio.Task)
            and not self._keep_connected_task.done()
        )

    #
    # Keep connected
    #
    @final
    def _keep_connected(self):
        if not self._is_keep_connected_running():
            self._log_debug(f"{self.host}:{self.port}: creating keep_connected task")
            self._keep_connected_task = asyncio.create_task(self._keep_connected_loop())
            return self._keep_connected_task

    #
    # Keep connected loop
    #
    @final
    async def _keep_connected_loop(self):
        # break if we try to disconnect
        while not self.connected:
            try:
                await self.connect()
                self._cancel_keep_connected()
            except ZoneConnectionError as e:
                self._reconnection_attempts += 1

                backoff = min(
                    max(
                        self.BACKOFF_MIN,
                        self.BACKOFF_MIN * self._reconnection_attempts,
                    ),
                    self.BACKOFF_MAX,
                )

                self._log_info(
                    f"{self.host}:{self.port}: reconnecting in {backoff} seconds"
                )
                await asyncio.sleep(backoff)

    #
    # Cancel keep connected tasks
    #
    @final
    def _cancel_keep_connected(self):
        self._log_debug(f"{self.host}:{self.port}: canceling keep_connected task")
        cancel_task(self._keep_connected_task)
        self._reconnection_attempts = 0

    #
    # Send Bytes
    #
    @final
    async def _send_bytes(self):
        try:
            self._log_debug(f"Send task started for {self.host}:{self.port}")
            while self.connected:
                # Wait until there's data in the queue
                data = await self._writer_queue.get()

                if not isinstance(data, bytearray):
                    Exception("Currently only accept Bytearray!")

                # Send the data
                self._writer.write(data)
                await self._writer.drain()

                self._log_debug(f"Sent to {self.host}:{self.port}: {data.hex()}")

                # VSSL cant handle too many requests.
                await asyncio.sleep(0.2)

        except asyncio.CancelledError:
            self._log_debug(f"Cancelled send task for {self.host}:{self.port}")
        except (BrokenPipeError, ConnectionError, TimeoutError, OSError) as e:
            self._log_error(f"Lost connection to host {self.host}:{self.port}")
            await self.reconnect()

    #
    # Response Task Loop
    #
    @final
    async def _receive_first_byte(self):
        try:
            self._log_debug(f"Receive task started for {self.host}:{self.port}")
            while self.connected:
                data = await self._reader.readexactly(self.FRIST_BYTE)

                if not data:
                    continue

                self._keep_alive_received = True

                await self._read_byte_stream(self._reader, data)

        except asyncio.CancelledError:
            self._log_debug(f"Cancelled receive task for {self.host}:{self.port}")
        except (
            IncompleteReadError,
            TimeoutError,
            ConnectionResetError,
            OSError,
        ) as e:
            self._log_error(f"Lost connection to host {self.host}:{self.port}")
            await self.reconnect()

    #
    # Read the byte stream
    #
    @abstractmethod
    async def _read_byte_stream(self):
        pass

    #
    # Send a keep alive
    #
    async def _send_keepalive_base(self):
        try:
            while self.connected:
                self._keep_alive_received = False

                # Send first then sleep
                self._send_keepalive()

                await asyncio.sleep(self.KEEP_ALIVE)

                if not self._keep_alive_received:
                    self._log_error("Keep-alive not received")
                    await self.reconnect()

        except asyncio.CancelledError:
            self._log_debug(f"Cancelled the keepalive task for {self.host}:{self.port}")

    #
    # Send a keep alive
    #
    @abstractmethod
    def _send_keepalive(self):
        pass
