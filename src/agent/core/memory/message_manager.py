from typing import List, Dict, Optional
from datetime import datetime


class MessageManager:
    """Manages recent message history and conversations"""

    def __init__(self) -> None:
        self._messages: List[Dict] = []

    def add_message(
        self,
        content: str,
        role: str,
        tool_calls: Optional[List[Dict]] = None,
        tool_id: Optional[str] = None,
        timestamp: Optional[datetime] = None,
    ) -> None:
        """
        Add a new message to the history

        Args:
            content: Message content
            role: Role of the message sender
            timestamp: Optional message timestamp
        """
        self._messages.append(
            {
                "content": content,
                "role": role,
                "tool_calls": tool_calls,
                "tool_call_id": tool_id,
                "timestamp": (timestamp or datetime.now()).isoformat(),
            }
        )

    def get_messages(self) -> List[Dict]:
        """Get all messages"""
        return self._messages

    def get_last_user_message(self) -> Optional[Dict]:
        """
        Get the most recent message from a user

        Returns:
            Optional[Dict]: The last user message as a dictionary, or None if no user messages exist
        """
        for message in reversed(self._messages):
            if message["role"] == "user":
                return message
        return None

    def get_last_message(self) -> Optional[Dict]:
        """
        Get the most recent message regardless of role

        Returns:
            Optional[Dict]: The last message as a dictionary, or None if no messages exist
        """
        return self._messages[-1] if self._messages else None

    def remove_last_tool_call_message(self) -> Optional[Dict]:
        """
        Removes and returns the most recent message that contains tool calls

        Returns:
            Optional[Dict]: The removed message as a dictionary, or None if no tool call messages exist
        """
        for i in range(len(self._messages) - 1, -1, -1):
            if self._messages[i].get("tool_calls"):
                return self._messages.pop(i)
        return None
