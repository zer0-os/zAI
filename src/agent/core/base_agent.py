from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
import logging
from agent.core.memory.message_manager import MessageManager
from agent.core.providers.model_provider import ModelProvider
from agent.core.decorators.tool import ToolMetadata
from wallet.wallet import ZWallet


class BaseAgent(ABC):
    """Base class for all specialized agents in the system"""

    @property
    @abstractmethod
    def name(self) -> str:
        """The name of the agent

        Returns:
            str: The agent's identifier/name
        """
        pass

    def __init__(
        self,
        wallet: ZWallet,
        model_provider: ModelProvider,
        message_manager: MessageManager,
        debug: bool = False,
    ) -> None:
        """Initialize the base agent

        Args:
            wallet: Wallet instance for blockchain interactions
            model_provider: Provider for model interactions (e.g., OpenAIProvider)
            message_manager: Manager for conversation history
            debug: Enable debug logging if True
        """
        self._debug = debug
        self._logger = None
        if debug:
            self._logger = logging.getLogger(__name__)

        self._wallet = wallet
        self._model_provider = model_provider
        self._message_manager = message_manager

    @abstractmethod
    def get_system_prompt(self) -> Optional[str]:
        """Return the system prompt for this agent, if any

        Returns:
            Optional[str]: The system prompt defining the agent's role and capabilities,
                          or None if no system prompt is needed
        """
        pass

    @abstractmethod
    async def transfer_to(self) -> "BaseAgent":
        """Transfer control to this agent

        Each agent must implement this method with appropriate keywords and examples
        for when control should be transferred to it.

        Returns:
            BaseAgent: Returns self to indicate transfer of control
        """
        pass

    def _get_tools(self) -> List[Dict[str, Any]]:
        """Get all tools available to this agent

        Returns:
            List[Dict[str, Any]]: List of tool descriptions
        """
        tools = []

        # Get relevant agent tools
        for method_name in dir(self):
            method = getattr(self, method_name)
            if hasattr(method, "tool_metadata"):
                metadata: ToolMetadata = method.tool_metadata
                if not metadata.exclude:
                    tools.append(metadata.description)

        return tools

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
        """Process a user message and return the response

        Args:
            message: The user's input message

        Returns:
            str: The agent's response
        """
        try:
            self._debug_log("Processing message in agent", message)
            self._message_manager.add_message(message, "user")
            response = await self.generate()
            self._message_manager.add_message(response, "assistant")
            return response
        except Exception as e:
            self._debug_log("Error processing message", str(e))
            return f"An error occurred: {str(e)}"

    async def generate(self) -> str:
        """Generate a response using the model provider

        Returns:
            str: Generated response
        """
        messages = self._message_manager.get_messages()
        tools = self._get_tools()

        system_message = {"role": "system", "content": self.get_system_prompt()}
        return await self._model_provider.generate(
            messages=[system_message] + messages, tools=tools
        )
