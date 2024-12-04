from abc import ABC, abstractmethod


class MessageStream(ABC):
    @abstractmethod
    async def is_connected(self) -> bool:
        """Check if the message stream is still connected"""
        pass

    @abstractmethod
    async def send_message(self, message: str) -> None:
        """Send a message if the connection is still active"""
        if not await self.is_connected():
            raise RuntimeError("Cannot send message: connection is closed")

    @abstractmethod
    async def send_partial(self, chunk: str) -> None:
        pass

    @abstractmethod
    async def receive_message(self) -> str:
        pass
