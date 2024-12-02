"""Connection manager for WebSocket connections."""

from typing import Set
import asyncio
from fastapi import WebSocket


class ConnectionManager:
    """Manages WebSocket connections and implements connection limits and heartbeats."""

    def __init__(self, max_connections: int = 1000, heartbeat_interval: int = 10):
        """
        Initialize the connection manager.

        Args:
            max_connections: Maximum number of concurrent connections allowed
            heartbeat_interval: Interval in seconds between heartbeat messages
        """
        self.active_connections: Set[WebSocket] = set()
        self.max_connections = max_connections
        self.heartbeat_interval = heartbeat_interval
        self.pong_timeout = 2.0  # 2 second timeout for pong response

    async def connect(self, websocket: WebSocket) -> bool:
        """
        Accept a new WebSocket connection if under the connection limit.

        Args:
            websocket: The WebSocket connection to accept

        Returns:
            bool: True if connection was accepted, False if rejected
        """
        if len(self.active_connections) >= self.max_connections:
            await websocket.close(code=1008)  # Connection limit exceeded
            return False

        await websocket.accept()
        self.active_connections.add(websocket)
        return True

    def disconnect(self, websocket: WebSocket) -> None:
        """
        Remove a WebSocket connection from active connections.

        Args:
            websocket: The WebSocket connection to remove
        """
        self.active_connections.remove(websocket)

    async def send_heartbeat(self, websocket: WebSocket) -> None:
        """
        Send periodic ping frames and wait for pong responses to keep connection alive.

        Args:
            websocket: The WebSocket connection to send pings to
        """
        while True:
            try:
                await asyncio.sleep(self.heartbeat_interval)
                try:
                    await asyncio.wait_for(websocket.ping(), timeout=self.pong_timeout)
                except asyncio.TimeoutError:
                    self.disconnect(websocket)
                    break
            except Exception:
                self.disconnect(websocket)
                break
