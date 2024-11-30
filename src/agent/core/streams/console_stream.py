from agent.core.interfaces.message_stream import MessageStream
import asyncio
import sys


class ConsoleStream(MessageStream):
    async def send_message(self, message: str) -> None:
        print(f"\n{message}")

    async def send_partial(self, chunk: str) -> None:
        print(chunk, end="", flush=True)

    async def receive_message(self) -> str:
        # Use asyncio.get_event_loop().run_in_executor for non-blocking input
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, sys.stdin.readline)
