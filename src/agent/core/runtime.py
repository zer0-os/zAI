from abc import ABC
from typing import Dict, Any, Optional, Union, AsyncGenerator
import json
import logging
from agent.agents import WalletAgent
from agent.agents.routing_agent import RoutingAgent
from agent.core.providers import OpenAIProvider
from agent.core.memory.message_manager import MessageManager
from wallet.wallet import ZWallet
from agent.core.base_agent import BaseAgent
from agent.core.decorators.tool import ToolMetadata
from agent.core.interfaces.message_stream import MessageStream


class Runtime(ABC):
    """Multi-agent runtime configuration and initialization"""

    def __init__(
        self, wallet: ZWallet, message_stream: MessageStream, debug: bool = False
    ) -> None:
        """Initialize the runtime with multiple agents

        Args:
            wallet: Wallet instance for blockchain interactions
            message_stream: Stream for sending/receiving messages
            debug: Enable debug logging if True
        """
        self._debug = debug
        self._logger = None
        if debug:
            logging.basicConfig(level=logging.DEBUG)
            self._logger = logging.getLogger(__name__)

        self._generate_count = 0
        self._wallet = wallet
        self._message_manager = MessageManager()
        self._message_stream = message_stream

        # Initialize all agents
        wallet_agent = WalletAgent(
            wallet=wallet,
            message_manager=self._message_manager,
            message_stream=self._message_stream,
            debug=debug,
        )
        self._agents = [wallet_agent]

        routing_agent = RoutingAgent(
            agents=self._agents,
            message_manager=self._message_manager,
            message_stream=self._message_stream,
            debug=debug,
        )
        self._routing_agent = routing_agent
        self._current_agent: Optional[BaseAgent] = routing_agent

    async def _execute_tool(self, tool_call: Dict[str, Any]) -> str | BaseAgent:
        """Execute a tool call by finding the appropriate agent and method

        Returns:
            Union[str, BaseAgent]: Either a JSON serialized result string or a BaseAgent instance
        """
        try:
            method_name = tool_call["function"]["name"]
            arguments = tool_call["function"]["arguments"]
            args = json.loads(arguments)

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
            self._current_agent = self._routing_agent  # Reset agent on new message

            self._message_manager.add_message(message, "user")

            complete_response = ""
            async for chunk in self.agent_loop():
                await self._message_stream.send_partial(
                    json.dumps(
                        {
                            "id": len(self._message_manager.get_messages()),
                            "c": chunk,
                        }
                    )
                )
                complete_response += chunk

            # Add the complete response to message history
            self._message_manager.add_message(complete_response, "assistant")
            return complete_response

        except Exception as e:
            self._debug_log("Error processing message", str(e))
            error_msg = f"An error occurred: {str(e)}"
            await self._message_stream.send_message(error_msg)
            return error_msg

    async def agent_loop(self) -> AsyncGenerator[str, None]:
        """Generate a response from the current agent"""
        generation_count = 0
        status = "streaming"
        while generation_count < 3 and status == "streaming":
            generation_count += 1
            self._debug_log(f"Generation attempt {generation_count}")

            async for chunk in self._current_agent.generate():
                if chunk == "stop":
                    status = "complete"
                    break

                if "tool_calls" not in chunk:
                    yield chunk["content"]
                else:
                    self._debug_log("Tool calls detected", chunk)
                    self._message_manager.add_message(
                        chunk["content"],
                        "assistant",
                        tool_calls=chunk["tool_calls"],
                    )

                    # Then process each tool call
                    for tool_call in chunk["tool_calls"]:
                        result = await self._execute_tool(tool_call)
                        if isinstance(result, BaseAgent):
                            self._current_agent = result
                            generation_count = 0
                            self._debug_log(
                                "Switching to new agent, resetting generation count"
                            )
                            result = f"Transferring to {result.name}"

                        self._message_manager.add_message(
                            result, "tool", tool_id=tool_call["id"]
                        )

        if status != "complete":
            yield "I'm sorry, I'm having trouble processing your request. Please try again later."
