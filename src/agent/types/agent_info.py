"""Agent information type definitions."""

from dataclasses import dataclass
from typing import Optional


@dataclass
class AgentInfo:
    """Represents agent information in the system."""

    id: str
    user_id: str
    wallet_id: str
    name: str
    wallet_address: str
