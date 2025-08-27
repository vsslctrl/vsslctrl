from abc import ABC, abstractmethod
import asyncio
from random import randrange
from asyncio.exceptions import IncompleteReadError
import logging
from typing import Callable, final

from . import LOG_DIVIDER
from .utils import cancel_task
from .exceptions import ZoneConnectionError
from .decorators import logging_helpers


class APITaskGroup:
    def __init__(self):
        self._tasks: list[asyncio.Task] = []

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
        for task in self._tasks:
            cancel_task(task)
        self._tasks = []

    async def wait(self):
        return await asyncio.gather(*self._tasks, return_exceptions=True)


@logging_helpers("Base API:")
class APIBase(ABC):
    TIMEOUT = 10
    KEEP_ALIVE = 60
    BACKOFF_MIN = 15
    BACKOFF_MAX = 300

    FIRST_BYTE = 1
    ENCODING = "utf-8"

    def __init__(self, host, port):
        self.host = host
        self.port = port

        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._writer_queue: asyncio.Queue = asyncio.Queue()

        self._disconnecting = False
        self._connecting = False
        self.connection_event = asyncio.Event()

        self._keep_alive_received = False
        self._keep_connected_task: asyncio.Task | None = None
        self._reconnection_attempts = 0

        self._task_group = APITaskGroup()

    # -------------------
    # Properties
    # -------------------
    @property
    def connected(self):
        return self.connection_event.is_set() if self.connection_event else False

    @property
    def _reconnecting(self):
        return self._disconnecting or self._connecting

    # -------------------
    # Public API
    # -------------------
    def send(self, data):
        if self._writer_queue and self.connected:
            self._writer_queue.put_nowait(data)

    @final
    async def connect(self):
        if self.connected:
            return True

        self._connecting = True
        self._event_publish_base(self.Events.CONNECTING)

        try:
            self._log_debug(f"attempting connection to {self.host}:{self.port}")
            self._reader, self._writer = await asyncio.wait_for(
                asyncio.open_connection(self.host, self.port), self.TIMEOUT
            )

            self.connection_event.set()
            self._event_publish_base(self.Events.CONNECTED)

            self._task_group.extend(
                [
                    self._receive_first_byte(),
                    self._send_bytes(),
                    self._send_keepalive_base(),
                ]
            )

            self._log_info(LOG_DIVIDER)
            self._log_info(f"connected to {self.host}:{self.port}")
            self._log_info(LOG_DIVIDER)

        except (asyncio.TimeoutError, asyncio.CancelledError):
            msg = f"Connection to {self.host}:{self.port} timed out"
            self._log_error(msg)
            self.connection_event.clear()
            raise ZoneConnectionError(msg)
        except ConnectionRefusedError:
            msg = f"Connection to {self.host}:{self.port} refused"
            self._log_error(msg)
            self.connection_event.clear()
            raise ZoneConnectionError(msg)
        except Exception as e:
            msg = f"Connection to {self.host}:{self.port} failed with exception {e}"
            self._log_error(msg)
            self.connection_event.clear()
            raise ZoneConnectionError(msg)
        finally:
            self._connecting = False
            self._keep_connected()

        return self.connected

    @final
    async def disconnect(self):
        self._disconnecting = True
        self._event_publish_base(self.Events.DISCONNECTING)

        if self.connection_event:
            self.connection_event.clear()

        await self._task_group.cancel()

        if self._writer:
            try:
                await self._writer.drain()
                if not self._writer.is_closing():
                    self._writer.close()
                    await asyncio.wait_for(self._writer.wait_closed(), self.TIMEOUT)
            except asyncio.CancelledError:
                self._log_debug("writer close cancelled")
            except asyncio.TimeoutError as e:
                self._log_error(f"Timeout while closing connection: {e}")
            except ConnectionResetError as e:
                self._log_error(f"Connection reset by peer: {e}")
            except Exception as e:
                self._log_error(f"Unexpected error while disconnecting: {e}")
            finally:
                self._writer = None

        self._reader = None
        self._disconnecting = False

        self._event_publish_base(self.Events.DISCONNECTED)
        self._log_info(f"{self.host}:{self.port}: disconnected")

        return not self.connected

    @final
    async def reconnect(self):
        if not self._reconnecting:
            self._event_publish_base(self.Events.RECONNECTING)
            await self.disconnect()
            await asyncio.sleep(1)
            self._keep_connected()

    @final
    async def shutdown(self):
        await self.disconnect()
        self._cancel_keep_connected()

    # -------------------
    # Keep Connected
    # -------------------
    @final
    def _is_keep_connected_running(self):
        return (
            isinstance(self._keep_connected_task, asyncio.Task)
            and not self._keep_connected_task.done()
        )

    @final
    def _keep_connected(self):
        if not self._is_keep_connected_running():
            self._log_debug(f"{self.host}:{self.port}: creating keep_connected task")
            self._keep_connected_task = asyncio.create_task(self._keep_connected_loop())
        return self._keep_connected_task

    @final
    async def _keep_connected_loop(self):
        """Retry connection forever until shutdown() is called."""
        while not self._disconnecting:
            if not self.connected:
                try:
                    await self.connect()
                    self._reconnection_attempts = 0
                    self._log_info(f"{self.host}:{self.port}: connected/reconnected")
                except ZoneConnectionError:
                    self._reconnection_attempts += 1
                    backoff = min(
                        max(
                            self.BACKOFF_MIN,
                            self.BACKOFF_MIN * self._reconnection_attempts,
                        ),
                        self.BACKOFF_MAX,
                    )
                    backoff += randrange(0, 5)  # jitter
                    self._log_info(
                        f"{self.host}:{self.port}: reconnecting in {backoff} seconds"
                    )
                    await asyncio.sleep(backoff)
            else:
                await asyncio.sleep(5)

    @final
    def _cancel_keep_connected(self):
        self._log_debug(f"{self.host}:{self.port}: canceling keep_connected task")
        cancel_task(self._keep_connected_task)
        self._reconnection_attempts = 0

    # -------------------
    # Internal Tasks
    # -------------------
    @final
    async def _send_bytes(self):
        try:
            self._log_debug(f"Send task started for {self.host}:{self.port}")
            while self.connected:
                data = await self._writer_queue.get()
                if not isinstance(data, bytearray):
                    raise Exception("Currently only accepts Bytearray!")

                self._writer.write(data)
                await self._writer.drain()

                self._log_debug(
                    f"↑ req: {self.host}:{self.port}: {data.hex(' ').upper()}"
                )
                await asyncio.sleep(0.2)
        except asyncio.CancelledError:
            self._log_debug(f"Cancelled send task for {self.host}:{self.port}")
        except (BrokenPipeError, ConnectionError, TimeoutError, OSError):
            self._log_error(f"Lost connection to host {self.host}:{self.port}")
            await self.reconnect()

    @final
    async def _receive_first_byte(self):
        try:
            self._log_debug(f"Receive task started for {self.host}:{self.port}")
            while self.connected:
                first_byte = await self._reader.readexactly(self.FIRST_BYTE)
                if not first_byte:
                    continue
                self._keep_alive_received = True
                await self._read_byte_stream(self._reader, first_byte)
        except asyncio.CancelledError:
            self._log_debug(f"Cancelled receive task for {self.host}:{self.port}")
        except (IncompleteReadError, TimeoutError, ConnectionResetError, OSError):
            self._log_error(f"Lost connection to host {self.host}:{self.port}")
            await self.reconnect()

    # -------------------
    # Abstract Methods
    # -------------------
    @abstractmethod
    async def _read_byte_stream(self, reader, first_byte):
        pass

    @abstractmethod
    def _event_publish(self, event_type, data=None):
        pass

    # -------------------
    # Event Helpers
    # -------------------
    def _event_publish_base(self, event_type, data=None):
        self._event_publish(event_type, (self.host, self.port))

    # -------------------
    # Encode / Decode
    # -------------------
    def _decode_frame_data(self, frame_data: bytes):
        try:
            return frame_data.decode(self.ENCODING, errors="replace")
        except Exception as e:
            self._log_error(
                f"unable to decode response data. error: {e} | data: {frame_data}"
            )

    def _encode_frame_data(self, string_data: str):
        return string_data.encode(self.ENCODING)

    # -------------------
    # Keep Alive
    # -------------------
    async def _send_keepalive_base(self):
        try:
            while self.connected:
                self._keep_alive_received = False
                self._send_keepalive()
                await asyncio.sleep(self.KEEP_ALIVE)
                if not self._keep_alive_received:
                    self._log_error("keep-alive not received")
                    await self.reconnect()
        except asyncio.CancelledError:
            self._log_debug(
                f"cancelled the keep-alive task for {self.host}:{self.port}"
            )

    @abstractmethod
    def _send_keepalive(self):
        pass
