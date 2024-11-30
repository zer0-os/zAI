import uuid
from agent.core.interfaces.message_stream import MessageStream
from fastapi import WebSocket


class WebSocketStream(MessageStream):
    def __init__(self, websocket: WebSocket):
        self._websocket = websocket
        self._id = str(uuid.uuid4())

    async def send_message(self, message: str) -> None:
        await self._websocket.send_text(message)

    async def send_partial(self, chunk: str) -> None:
        await self._websocket.send_text(chunk)

    async def receive_message(self) -> str:
        return await self._websocket.receive_text()
