import uuid
from agent.core.interfaces.message_stream import MessageStream
from fastapi import WebSocket, WebSocketDisconnect
from fastapi.websockets import WebSocketState


class WebSocketStream(MessageStream):
    def __init__(self, websocket: WebSocket):
        self._websocket = websocket
        self._id = str(uuid.uuid4())

    async def is_connected(self) -> bool:
        return self._websocket.client_state == WebSocketState.CONNECTED

    async def send_message(self, message: str) -> None:
        if await self.is_connected():
            await self._websocket.send_text(message)

    async def send_partial(self, chunk: str) -> None:
        await self._websocket.send_text(chunk)

    async def receive_message(self) -> str:
        try:
            return await self._websocket.receive_text()
        except Exception as e:
            if not await self.is_connected():
                raise WebSocketDisconnect() from e
            raise
