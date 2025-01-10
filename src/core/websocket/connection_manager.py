"""Connection manager for WebSocket connections."""

from typing import Dict, Set, Any, Callable, TypeVar
import asyncio
from fastapi import WebSocket
import json
from dataclasses import dataclass

T = TypeVar("T")


@dataclass(eq=True, frozen=True)
class WebSocketConnection:
    """Represents a websocket connection with associated metadata"""

    socket: WebSocket
    metadata: Any = None

    def __hash__(self) -> int:
        """Define custom hash based on the WebSocket object's id"""
        return id(self.socket)


class ConnectionManager:
    """Manages WebSocket connections and implements connection limits and heartbeats."""

    def __init__(self, max_connections: int = 1000):
        """
        Initialize the connection manager.

        Args:
            max_connections: Maximum number of concurrent connections allowed
        """
        self.active_connections: Set[WebSocketConnection] = set()
        self.max_connections = max_connections

    async def connect(self, websocket: WebSocket, metadata: Any = None) -> bool:
        """
        Accept a new WebSocket connection and store associated metadata.

        Args:
            websocket: The WebSocket connection to accept
            metadata: Any associated data to store with the connection

        Returns:
            bool: True if connection was accepted, False if rejected
        """
        if len(self.active_connections) >= self.max_connections:
            await websocket.close(code=1008)  # Connection limit exceeded
            return False

        try:
            await websocket.accept()
            connection = WebSocketConnection(socket=websocket, metadata=metadata)
            self.active_connections.add(connection)
            return True
        except Exception as e:
            print(f"Failed to establish websocket connection: {e}")
            return False

    def disconnect(self, websocket: WebSocket):
        """
        Remove a WebSocket connection from active connections.

        Args:
            websocket: The WebSocket connection to remove
        """
        self.active_connections = {
            conn for conn in self.active_connections if conn.socket != websocket
        }

    async def broadcast_filtered(
        self, message: dict, predicate: Callable[[Any], bool]
    ) -> None:
        """
        Broadcast a message to all connections where the predicate returns True for their metadata.

        Args:
            message: The message to broadcast
            predicate: Function that takes connection metadata and returns True if the connection
                      should receive the message
        """
        for connection in self.active_connections:
            if predicate(connection.metadata):
                try:
                    await connection.socket.send_json(message)
                except Exception as e:
                    print(f"Failed to send message to websocket: {e}")
