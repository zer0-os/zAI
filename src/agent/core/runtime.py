from abc import ABC
from typing import Dict, Any, Optional
import json
import logging
from agent.agents import WalletAgent
from agent.core.providers import OpenAIProvider
from agent.core.memory.message_manager import MessageManager
from wallet.wallet import ZWallet
from agent.core.base_agent import BaseAgent
from agent.core.decorators.tool import ToolMetadata


class Runtime(ABC):
    """Multi-agent runtime configuration and initialization"""

    def __init__(self, wallet: ZWallet, debug: bool = False) -> None:
        """Initialize the runtime with multiple agents

        Args:
            wallet: Wallet instance for blockchain interactions
            agents: List of agent classes to instantiate
            debug: Enable debug logging if True
        """
        self._debug = debug
        self._logger = None
        if debug:
            logging.basicConfig(level=logging.DEBUG)
            self._logger = logging.getLogger(__name__)

        self._system_prompt = """You are a routing agent that directs user requests to specialized agents.
        Analyze each user message and determine which agent would be best suited to handle it."""
        self._generate_count = 0
        self._wallet = wallet
        self._model_provider = OpenAIProvider(debug_log=self._debug_log)
        self._message_manager = MessageManager()

        # Initialize all agents
        wallet_agent = WalletAgent(
            wallet, message_manager=self._message_manager, debug=debug
        )
        self._agents = [wallet_agent]

        # Initialize transfer tools list
        self._tools = []
        for agent in self._agents:
            for method_name in dir(agent):
                if method_name.startswith("transfer_to"):
                    method = getattr(agent, method_name)
                    if hasattr(method, "tool_metadata"):
                        metadata: ToolMetadata = method.tool_metadata
                        self._tools.append(metadata.description)

        self._current_agent: Optional[BaseAgent] = None

    async def _execute_tool(self, tool_call: Dict[str, Any]) -> str | BaseAgent:
        """Execute a tool call by finding the appropriate agent and method

        Returns:
            Union[str, BaseAgent]: Either a JSON serialized result string or a BaseAgent instance
        """
        try:
            method_name = tool_call["function"]["name"]
            args = json.loads(tool_call["function"]["arguments"])

            # First check for methods on Runtime class itself
            if hasattr(self, method_name):
                method = getattr(self, method_name)
                if hasattr(method, "tool_metadata"):
                    result = await method(**args)
                    # Special case for agent transfers
                    if isinstance(result, BaseAgent):
                        return result
                    return result

            # Then search through agents for the matching tool
            for agent in self._agents:
                if hasattr(agent, method_name):
                    method = getattr(agent, method_name)
                    if hasattr(method, "tool_metadata"):
                        result = await method(**args)
                        # Special case for agent transfers
                        if isinstance(result, BaseAgent):
                            return result
                        return result

            raise ValueError(f"No agent found with tool method: {method_name}")

        except Exception as e:
            return f"Error executing tool: {str(e)}"

    def _debug_log(self, message: str, data: Optional[Any] = None) -> None:
        """Log debug information if debug mode is enabled

        Args:
            message: Debug message to log
            data: Optional data to include in debug output
        """
        if self._debug and self._logger:
            if data:
                self._logger.debug(f"{message}: {data}")
            else:
                self._logger.debug(message)

    async def process_message(self, message: str) -> str:
        """Process a user message by routing it to the appropriate agent"""
        try:
            self._debug_log("Processing user message", message)
            self._current_agent = None  # Reset agent on new message

            self._message_manager.add_message(message, "user")
            response = await self.generate()
            self._message_manager.add_message(response, "assistant")

            return response

        except Exception as e:
            self._debug_log("Error processing message", str(e))
            return f"An error occurred: {str(e)}"

    async def generate(self) -> str:
        """Generate a response from the model

        Returns:
            str: The final response after potentially multiple generations and tool calls
        """
        generation_count = 0

        while generation_count < 3:
            generation_count += 1
            self._debug_log(f"Generation attempt {generation_count}")

            # Use current agent's generate if set, otherwise use model provider
            if self._current_agent:
                response = await self._current_agent.generate()
            else:
                response = await self.model_generate()

            # If no tool calls, we have our final response
            if "tool_calls" not in response:
                return response["content"]

            # Handle tool calls
            self._debug_log("Tool calls detected", response["tool_calls"])

            # Add the assistant's response with tool calls first
            self._message_manager.add_message(
                response["content"], "assistant", tool_calls=response["tool_calls"]
            )

            # Then process each tool call
            for tool_call in response["tool_calls"]:
                result = await self._execute_tool(tool_call)
                if isinstance(result, BaseAgent):
                    self._current_agent = result
                    generation_count = 0  # Reset count when switching to new agent
                    self._debug_log(
                        "Switching to new agent, resetting generation count"
                    )
                    result = f"Transferring to {result.name}"

                self._message_manager.add_message(
                    result, "tool", tool_id=tool_call["id"]
                )

        return "I'm sorry, I'm having trouble processing your request. Please try again later."

    async def model_generate(self) -> str:
        """Generate a response using the model provider

        Returns:
            str: Generated response
        """
        messages = self._message_manager.get_messages()
        tools = self._tools

        system_message = {"role": "system", "content": self._system_prompt}
        return await self._model_provider.generate(
            messages=[system_message] + messages, tools=tools
        )
