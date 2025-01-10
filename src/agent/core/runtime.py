from abc import ABC
from typing import Dict, Any, Optional, AsyncGenerator
import json
import logging
import shortuuid
from agent.core.memory.message_manager import MessageManager
from wallet.wallet import ZWallet
from agent.core.base_agent import BaseAgent
from agent.core.interfaces.message_stream import MessageStream


class Runtime(ABC):
    """Multi-agent runtime configuration and initialization"""

    def __init__(
        self,
        wallet: ZWallet | None,
        message_stream: MessageStream,
        entry_agent: BaseAgent,
        agents: list[BaseAgent],
        message_manager: MessageManager,
        debug: bool = False,
    ) -> None:
        """Initialize the runtime with multiple agents

        Args:
            wallet: Wallet instance for blockchain interactions
            message_stream: Stream for sending/receiving messages
            entry_agent: The initial agent that handles incoming messages
            agents: List of available agents for tool execution
            debug: Enable debug logging if True
        """
        self._debug = debug
        self._logger = None
        if debug:
            logging.basicConfig(level=logging.DEBUG)
            self._logger = logging.getLogger(__name__)

        self._generate_count = 0
        self._wallet = wallet
        self._message_manager = message_manager
        self._message_stream = message_stream

        self._agents = agents
        self._entry_agent = entry_agent
        self._current_agent: Optional[BaseAgent] = entry_agent

    async def _execute_tool(
        self, tool_call: Dict[str, Any]
    ) -> Dict[str, str | BaseAgent]:
        """Execute a tool call by finding the appropriate agent and method

        Returns:
            Dict[str, Any]: Result dictionary containing success status and result/error
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
                            return {"success": True, "result": result}
                        return {"success": True, "result": result}

            return {
                "success": False,
                "error": f"No agent found with tool method: {method_name}",
            }

        except Exception as e:
            error_message = f"Tool execution failed: {str(e)}"
            self._debug_log("Tool execution error", error_message)
            return {"success": False, "error": error_message}

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
            self._current_agent = self._entry_agent  # Reset agent on new message

            self._message_manager.add_message(message, "user")

            complete_response = ""
            message_id = shortuuid.uuid()
            async for chunk in self.agent_loop():
                await self._message_stream.send_partial(
                    json.dumps(
                        {
                            "type": "stream",
                            "id": message_id,
                            "chunk": chunk,
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
            await self._message_stream.send_message(
                json.dumps({"type": "error", "error": error_msg})
            )
            return error_msg

    async def agent_loop(self) -> AsyncGenerator[str, None]:
        """Generate a response from the current agent"""
        generation_count = 0
        status = "streaming"

        while generation_count < 3 and status == "streaming":
            generation_count += 1
            self._debug_log(f"Generation attempt {generation_count}")

            try:
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

                        # Process each tool call
                        for tool_call in chunk["tool_calls"]:
                            result = await self._execute_tool(tool_call)

                            if not result["success"]:
                                # Add error to message history
                                self._message_manager.add_message(
                                    result["error"], "tool", tool_id=tool_call["id"]
                                )
                                # Yield specific error and end loop
                                yield "I'm sorry, something went wrong and I was unable to complete your request"
                                status = "failed"
                                return

                            if isinstance(result["result"], BaseAgent):
                                self._current_agent = result["result"]
                                generation_count = 0
                                self._debug_log(
                                    "Switching to new agent, resetting generation count"
                                )
                                tool_result = f"Transferring to {result['result'].name}. You may continue."
                            else:
                                tool_result = result["result"]

                            # Add successful result to message history
                            self._message_manager.add_message(
                                tool_result, "tool", tool_id=tool_call["id"]
                            )

            except Exception as e:
                self._debug_log("Generation failed", str(e))
                status = "failed"
                yield "I apologize, but I encountered an error"
                break

        if status == "streaming":
            yield "Request could not be completed. Please try again."
