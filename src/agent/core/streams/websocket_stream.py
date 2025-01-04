import uuid
from typing import Optional
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

    async def wait_for_user_response(self) -> str:
        """
        Actively wait for and return a user response through the WebSocket.

        Returns:
            str: The user's response message

        Raises:
            WebSocketDisconnect: If the connection is closed while waiting
        """
        if not await self.is_connected():
            raise WebSocketDisconnect("Connection is already closed")

        try:
            return await self._websocket.receive_text()
        except Exception as e:
            if not await self.is_connected():
                raise WebSocketDisconnect(
                    "Connection closed while waiting for response"
                ) from e
            raise
