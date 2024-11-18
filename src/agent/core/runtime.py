from abc import ABC
from typing import List, Dict, Any, Optional
import json
import logging
from agent.core.providers import OpenAIProvider
from agent.core.memory.message_manager import MessageManager
from wallet.wallet import ZWallet


class Runtime(ABC):
    """Base runtime configuration and initialization"""

    def __init__(self, wallet: ZWallet, debug: bool = False) -> None:
        # Initialize debug logging first
        self._debug = debug
        self._logger = None
        if debug:
            logging.basicConfig(level=logging.DEBUG)
            self._logger = logging.getLogger(__name__)
        self._generate_count = 0

        # Initialize components with debug log method
        self._wallet = wallet
        self._model_provider = OpenAIProvider(debug_log=self._debug_log)
        self._message_manager = MessageManager()

        # Get wallet capabilities and register tools
        self._tools = self._get_wallet_tools()

        # Add system message with capabilities
        system_message = "You are an ai agent that can interact with a wallet. Take onchain actions as directed by the user"
        self._message_manager.add_message(system_message, "system")

    def _get_wallet_tools(self) -> List[Dict[str, Any]]:
        """Extract tool descriptions from wallet methods and adapters"""
        tools = []

        # Get base wallet tools
        for method_name in dir(self._wallet):
            method = getattr(self._wallet, method_name)
            if hasattr(method, "tool_metadata"):
                # Only use the OpenAI-compatible description
                tools.append(method.tool_metadata.description)

        # Get adapter tools using the adapter registry
        adapter_registry = self._wallet._adapter_registry
        for adapter in adapter_registry._adapters.values():
            for method_name in dir(adapter):
                method = getattr(adapter, method_name)
                if hasattr(method, "tool_metadata"):
                    tools.append(method.tool_metadata.description)

        return tools

    async def _execute_tool(self, tool_call: Dict[str, Any]) -> str:
        """Execute a tool call and return the result"""
        try:
            method_name = tool_call["function"]["name"]
            method = None
            namespace = None

            # First check wallet methods
            if hasattr(self._wallet, method_name):
                method = getattr(self._wallet, method_name)
            else:
                # Check adapters
                for adapter in self._wallet.get_adapters():
                    if hasattr(adapter, method_name):
                        method = getattr(adapter, method_name)
                        if hasattr(method, "tool_metadata"):
                            namespace = method.tool_metadata.namespace
                            break

            adapter = self._wallet.get_adapter(namespace) if namespace else self._wallet
            args = json.loads(tool_call["function"]["arguments"])
            result = await method(**args)
            return json.dumps(result)
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
        """Process a user message"""
        self._generate_count = 0
        self._debug_log("Processing user message", message)

        self._message_manager.add_message(message, "user")

        response = await self.generate()

        self._message_manager.add_message(response, "assistant")
        return response

    async def generate(self) -> str:
        """Generate a response from the model"""
        self._generate_count += 1
        messages = self._message_manager.get_messages()

        if self._generate_count > 3:
            return "I'm sorry, I'm having trouble processing your request. Please try again later."

        response = await self._model_provider.generate(
            messages=messages, tools=self._tools
        )

        # Handle tool calls if present
        if "tool_calls" in response:
            self._debug_log("Tool calls detected", response["tool_calls"])
            for tool_call in response["tool_calls"]:
                result = await self._execute_tool(tool_call)
                self._message_manager.add_message(result, "assistant")

        return await self._model_provider.generate(messages)
