from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, AsyncGenerator
import logging
from agent.core.memory.message_manager import MessageManager
from agent.core.providers.model_provider import ModelProvider
from agent.core.decorators.tool import ToolMetadata
from agent.core.interfaces.message_stream import MessageStream


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
        model_provider: ModelProvider,
        message_manager: MessageManager,
        message_stream: MessageStream,
        debug: bool = False,
    ) -> None:
        """Initialize the base agent

        Args:
            model_provider: Provider for model interactions (e.g., OpenAIProvider)
            message_manager: Manager for conversation history
            message_stream: Stream for sending/receiving messages
            debug: Enable debug logging if True
        """
        self._debug = debug
        self._logger = None
        if debug:
            self._logger = logging.getLogger(__name__)

        self._model_provider = model_provider
        self._message_manager = message_manager
        self._message_stream = message_stream

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

    @abstractmethod
    def get_capabilities(self) -> List[str]:
        """Get the capabilities of this agent"""
        pass

    def _get_tools(self) -> List[Dict[str, Any]]:
        """Get all tools available to this agent. This method can be overridden by subclasses
        to provide custom tool discovery logic.

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

    async def generate(self, capabilities: str) -> AsyncGenerator[str, None]:
        """Generate a response using the model provider"""
        messages = self._message_manager.get_messages()
        tools = self._get_tools()
        system_message = {"role": "developer", "content": self.get_system_prompt()}
        capabilities_message = {"role": "developer", "content": capabilities}

        response = await self._model_provider.generate(
            messages=[system_message, capabilities_message] + messages,
            tools=tools,
            stream=True,
        )
        async for chunk in response:
            yield chunk
