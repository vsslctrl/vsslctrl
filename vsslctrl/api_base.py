from abc import ABC, abstractmethod
import asyncio
from asyncio.exceptions import IncompleteReadError
import logging
from typing import Callable, final

from .utils import add_logging_helpers, cancel_task_if_exists

class APIBase(ABC):
    
    def __init__(self, host, port):

        add_logging_helpers(self, 'Base API:')

        self.host = host
        self.port = port
        self._timeout = 5
        self.connection_event = None
        self.keep_alive_received = False
        
        self._keep_alive = 10
        self._reader = None
        self._writer = None
        self._writer_queue: asyncio.Queue = None
        self._disconnecting = False
        self._connecting = False
        
        self._task_receive_first_byte: asyncio.Task = None
        self._task_send_bytes: asyncio.Task = None
        self._task_keepalive: asyncio.Task = None


    @property
    def connected(self):
        if self.connection_event is None:
            return False
        return self.connection_event.is_set()

    #
    # Send a request
    #
    def send(self, data):
        if self._writer_queue and self.connected:
            self._writer_queue.put_nowait(data)

    #
    # Connect
    #
    def connect(self):
        self.connection_event = asyncio.Event() #Need event loop
        return asyncio.create_task(self._establish_connection())

    #
    # Disconnect
    #
    async def disconnect(self):
        return await self._disconnect()
    #
    # Disconnect
    #
    @final
    async def _disconnect(self):

        self._disconnecting = True

        # Make sure _establish_connection timeout has passed 
        # to make sure the loop is stopped by the finally statement
        # This is here so we can disconnect the zone before it has 
        # actually been established. Maybe this can be changed to using
        # a cancelable task with wiat_for
        if self._connecting:
            await asyncio.sleep(self._timeout)

        # Break Loops
        if self.connection_event:
            self.connection_event.clear()
        
        # Cancel the tasks
        await cancel_task_if_exists(self._task_receive_first_byte)
        await cancel_task_if_exists(self._task_send_bytes)
        await cancel_task_if_exists(self._task_keepalive)

        if self._writer:
            try:
                self._writer.close()
                #Writer hangs on disconnect sometimes
                await asyncio.wait_for(
                    self._writer.wait_closed(), self._timeout
                )
            except Exception:
                pass

        self._log_info(f'{self.host}:{self.port}: disconnected')

        self._disconnecting = False

    #
    # Reconnect
    #
    @final
    async def _reconnect(self):
        if not self._disconnecting:
            await self._disconnect()
            self._log_debug(f'{self.host}:{self.port}: reconnecting')
            return self.connect()

    #
    # Open Connection
    #
    @final
    async def _establish_connection(self):
        # Keep trying to connect until stopped
        while not self.connected and not self._disconnecting: 

            self._connecting = True

            try:
                
                self._log_debug(f"Attemping connection to {self.host}:{self.port}")
                self._reader, self._writer = await asyncio.wait_for(
                    asyncio.open_connection(self.host, self.port), self._timeout
                )

                # Connected
                self.connection_event.set()

                # Create queue in event loop
                self._writer_queue = asyncio.Queue()

                # Start workers
                self._task_receive_first_byte = asyncio.create_task(self._receive_first_byte())
                self._task_send_bytes = asyncio.create_task(self._send_bytes())
                self._task_keepalive = asyncio.create_task(self._send_keepalive_base())

                self._log_info(f"Connected to {self.host}:{self.port}")

            except asyncio.TimeoutError:
                # Handle timeout
                self._log_error(f"Connection to {self.host}:{self.port} timed out")
                self.connection_event.clear()
            except ConnectionRefusedError:
                # Handle timeout
                self._log_error(f"Connection to {self.host}:{self.port} refused")
                self.connection_event.clear()
            except Exception as e:
                self._log_error(f"Connection to {self.host}:{self.port} failed with exception {e}")
                self.connection_event.clear()
            finally:
                self._connecting = False
                if self._disconnecting:
                    break
        
        return self.connected

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
                    Exception('Currently only accept Bytearray!')

                # Send the data
                self._writer.write(data)
                await self._writer.drain()
                
                self._log_debug(f'Sent to {self.host}:{self.port}: {data.hex()}')

                # VSSL cant handle too many requests. 
                await asyncio.sleep(0.2)

        except (
            BrokenPipeError,
            ConnectionError,
            TimeoutError,
            OSError
        ) as e:
            self._log_error(f"Send Error {self.host}:{self.port}. Exception: {e}")
            await self._reconnect()

    #
    # Response Task Loop
    #
    @final
    async def _receive_first_byte(self):
        try:
            self._log_debug(f"Receive task started for {self.host}:{self.port}")
            while self.connected:

                inital_length = 1
                data = await asyncio.wait_for(
                    self._reader.readexactly(inital_length), 
                    self._keep_alive + self._timeout
                )

                if not data:
                    continue

                self.keep_alive_received = True

                await self._read_byte_stream(self._reader, data, inital_length)

        except asyncio.TimeoutError:
                pass
        except (
            IncompleteReadError,
            TimeoutError,
            ConnectionResetError,
            OSError,
        ) as e:
            self._log_error(f"Lost connection to host {self.host}:{self.port}. Exception: {e}")
            await self._reconnect()
            

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

                self.keep_alive_received = False

                #Send first then sleep
                self._send_keepalive()

                await asyncio.sleep(self._keep_alive)

                if not self.keep_alive_received:
                    self._log_info("Keep-alive not received. Reconnecting...")
                    await self._reconnect()

        except asyncio.CancelledError:
            self._log_debug(f"Cancelled the keepalive task for {self.host}:{self.port}")

    #
    # Send a keep alive
    #
    @abstractmethod
    def _send_keepalive(self):
        pass


        
