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
class IntroAgent(BaseAgent):
    """
    Agent responsible for introducing the user to the system and helping them register
    new agents.
    """

    @property
    def name(self) -> str:
        return "IntroAgent"

    def __init__(
        self,
        message_manager: MessageManager,
        message_stream: MessageStream,
        user_id: str,
        debug: bool = False,
    ) -> None:
        """Initialize the intro agent"""
        model_provider = OpenAIProvider(debug=debug)
        super().__init__(
            model_provider=model_provider,
            message_manager=message_manager,
            message_stream=message_stream,
            debug=debug,
        )

        self._user_id = user_id
        self._tools = [self.create_agent_wizard.tool_metadata.description]
        self._db = DatabaseConnection()

    async def _create_privy_wallet(self) -> Tuple[str, str]:
        """
        Create a new Privy wallet for an agent.

        Returns:
            Tuple[str, str]: A tuple containing (wallet_id, wallet_address)
        """
        privy_app_id = os.getenv("PRIVY_APP_ID")

        privy_app_secret = os.getenv("PRIVY_APP_SECRET")

        if not privy_app_id or not privy_app_secret:
            raise ValueError(
                "PRIVY_APP_ID and PRIVY_APP_SECRET environment variables must be set"
            )

        # Initialize the Privy signer
        privy_signer = PrivyAuthorizationSigner(privy_app_id)

        url = "https://api.privy.io/v1/wallets"
        body = {"chain_type": "ethereum"}

        # Create basic auth header from app_id:app_secret
        auth_string = f"{privy_app_id}:{privy_app_secret}"
        basic_auth = base64.b64encode(auth_string.encode()).decode()

        # Get authorization headers
        headers = privy_signer.get_auth_headers(url, body)
        headers.update(
            {
                "Content-Type": "application/json",
                "Authorization": f"Basic {basic_auth}",
            }
        )

        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                json=body,
                headers=headers,
            )

            if response.status_code != 200:
                raise Exception(f"Failed to create Privy wallet: {response.text}")

            data = response.json()
            return data["id"], data["address"]

    def transfer_to(self) -> "BaseAgent":
        """Transfer control to the intro agent for handling information about the system and registering new agents"""
        return self

    def _get_tools(self) -> List[Dict[str, Any]]:
        return self._tools

    def get_system_prompt(self) -> str | None:
        return """[MODE: IMMUTABLE] You are an agent responsible for introducing the user to the system and helping them register new agents.
        You will be given a tool to create a new agent and may only use this tool. All other requests should be politely declined.
        """

    async def _create_agent_in_db(
        self, name: str, wallet_id: str, wallet_address: str, user_id: str
    ) -> None:
        """
        Create a new agent entry in the database and map it to the user.

        Args:
            name: The name of the agent
            wallet_id: The wallet ID associated with the agent
            wallet_address: The wallet address of the agent
            user_id: The ID of the user creating the agent

        Raises:
            ValueError: If any input parameters are empty or invalid
            DatabaseError: If there's an error during database operations
        """
        if not all([name, wallet_id, wallet_address, user_id]):
            raise ValueError(
                "All parameters (name, wallet_id, wallet_address, user_id) are required"
            )

        try:
            with self._db.get_connection() as conn:
                with conn.cursor() as cur:
                    # Create the agent
                    cur.execute(
                        "INSERT INTO agents (wallet_id, name, wallet_address) VALUES (%s, %s, %s) RETURNING id",
                        (wallet_id, name, wallet_address),
                    )
                    agent_id = cur.fetchone()[0]

                    # Create user-agent mapping
                    cur.execute(
                        "INSERT INTO user_agent_mapping (user_id, agent_id) VALUES (%s, %s)",
                        (user_id, agent_id),
                    )
                    conn.commit()
        except Exception as e:
            self._logger.error(f"Unexpected error while creating agent: {str(e)}")
            raise

    @agent_tool()
    async def create_agent_wizard(self) -> None:
        """
        Walk the user through the process of creating a new agent step by step.

        This wizard guides users through the agent creation process, starting with
        naming the agent and creating necessary database entries.
        """
        try:
            # Get agent name from user
            message_id = shortuuid.uuid()
            await self._message_stream.send_message(
                json.dumps(
                    {
                        "type": "stream",
                        "id": message_id,
                        "chunk": "Let's create a new agent together! What would you like to name your agent?",
                    }
                )
            )
            agent_name = await self._message_stream.wait_for_user_response()

            # Create Privy wallet for the agent
            wallet_id, wallet_address = await self._create_privy_wallet()

            # Create the agent in the database
            await self._create_agent_in_db(
                agent_name, wallet_id, wallet_address, self._user_id
            )

            return f"Great! I've created an agent named '{agent_name}' with wallet address {wallet_address} and registered it in the system."

        except WebSocketDisconnect:
            self._logger.warning("User disconnected during agent creation wizard")
            raise
        except Exception as e:
            self._logger.error(f"Error creating agent: {str(e)}")
            raise
