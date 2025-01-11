import json
import os
import httpx
from typing import Any, Dict, List, Tuple

import shortuuid
import base64
import psycopg2

from agent.core.base_agent import BaseAgent
from agent.core.decorators.tool import agent_tool
from agent.core.memory.message_manager import MessageManager
from agent.core.providers.open_ai import OpenAIProvider
from agent.core.decorators.agent import agent
from agent.core.interfaces.message_stream import MessageStream
from fastapi import WebSocketDisconnect
from db import DatabaseConnection
from utils.privy_auth import PrivyAuthorizationSigner


@agent
class ConversationalAgent(BaseAgent):
    """
    Agent responsible for answering questions and providing assistance to the user.
    """

    @property
    def name(self) -> str:
        return "ConversationalAgent"

    def __init__(
        self,
        message_manager: MessageManager,
        message_stream: MessageStream,
        agent_name: str,
        debug: bool = False,
    ) -> None:
        """Initialize the conversational agent"""
        model_provider = OpenAIProvider(debug=debug)
        super().__init__(
            model_provider=model_provider,
            message_manager=message_manager,
            message_stream=message_stream,
            debug=debug,
        )

        self._agent_name = agent_name
        self._tools = []

        # Load character text during initialization
        character_path = os.path.join(
            os.path.dirname(__file__), "character", "character.txt"
        )
        try:
            with open(character_path, "r") as f:
                character_template = f.read().strip()
                self._system_prompt = character_template.replace(
                    "{CHARACTER_NAME}", self._agent_name
                )
        except FileNotFoundError:
            raise RuntimeError(f"Character file not found at {character_path}")

    async def transfer_to(self) -> "BaseAgent":
        """Transfer control to the conversational agent anytime the user seems like they just want to chat"""
        return self

    def _get_tools(self) -> List[Dict[str, Any]]:
        return self._tools

    def get_system_prompt(self) -> str | None:
        return self._system_prompt

    def get_capabilities(self) -> str:
        return """
        Casual conversation
        """
