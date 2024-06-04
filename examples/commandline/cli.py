import asyncio
import logging
import json
from prompt_toolkit import HTML
from prompt_toolkit.patch_stdout import patch_stdout
from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory

from vsslctrl import Vssl, Zone

from logging.handlers import RotatingFileHandler
from vsslctrl.exceptions import VsslCtrlException
from vsslctrl.data_structure import DeviceModels

rfh = RotatingFileHandler(
    filename="vssl.log",
    mode="a",
    maxBytes=1 * 1024 * 1024,
    backupCount=0,
    encoding=None,
    delay=0,
)


logging.basicConfig(
    level=logging.DEBUG, format="%(asctime)s - %(message)s", handlers=[rfh]
)


async def main():
    vssl = Vssl(DeviceModels.A3X)
    zone1 = vssl.add_zone(Zone.IDs.ZONE_1, "10.10.30.10")
    zone2 = vssl.add_zone(Zone.IDs.ZONE_2, "10.10.30.11")
    zone3 = vssl.add_zone(Zone.IDs.ZONE_3, "10.10.30.12")

    try:
        # # print(await vssl.discover())

        await vssl.initialise()

        history = FileHistory("command_history.txt")
        session = PromptSession(history=history)

        while True:
            try:
                user_input = await session.prompt_async(
                    'Enter a message ("exit" to quit): '
                )

                if user_input.lower() == "exit":
                    break

                try:
                    exec(user_input)
                except Exception as e:
                    logging.info(e)

            except KeyboardInterrupt:
                print("\nReceived KeyboardInterrupt. Stopping...")

                break  # Handle KeyboardInterrupt gracefully
            except EOFError:
                break  # Handle EOFError (e.g., Ctrl+D) to exit the loop

    except Exception as e:
        print(e)
    finally:
        await vssl.shutdown()


asyncio.run(main())
