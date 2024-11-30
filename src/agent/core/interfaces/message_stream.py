from abc import ABC, abstractmethod


class MessageStream(ABC):
    @abstractmethod
    async def send_message(self, message: str) -> None:
        pass

    @abstractmethod
    async def send_partial(self, chunk: str) -> None:
        pass

    @abstractmethod
    async def receive_message(self) -> str:
        pass
