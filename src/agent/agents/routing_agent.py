from typing import Any, Dict, List

from agent.core.base_agent import BaseAgent
from agent.core.decorators.tool import ToolMetadata
from agent.core.memory.message_manager import MessageManager
from agent.core.providers.open_ai import OpenAIProvider
from agent.core.decorators.agent import agent
from agent.core.interfaces.message_stream import MessageStream


@agent
class RoutingAgent(BaseAgent):
    """
    Agent responsible for routing user requests to specialized agents.
    """

    @property
    def name(self) -> str:
        return "RoutingAgent"

    def __init__(
        self,
        agents: List[BaseAgent],
        message_manager: MessageManager,
        message_stream: MessageStream,
        debug: bool = False,
    ) -> None:
        """Initialize the routing agent"""
        self._agents = agents
        model_provider = OpenAIProvider(debug=debug)
        super().__init__(
            model_provider=model_provider,
            message_manager=message_manager,
            message_stream=message_stream,
            debug=debug,
        )

        # Initialize transfer tools list
        self._tools = []
        for agent in self._agents:
            for method_name in dir(agent):
                if method_name.startswith("transfer_to"):
                    method = getattr(agent, method_name)
                    if hasattr(method, "tool_metadata"):
                        metadata: ToolMetadata = method.tool_metadata
                        self._tools.append(metadata.description)

    def transfer_to(self) -> "BaseAgent":
        """Transfer control to the routing agent for handling routing to other agents"""
        return self

    def _get_tools(self) -> List[Dict[str, Any]]:
        return self._tools

    def get_system_prompt(self) -> str | None:
        return """You are a routing agent that directs user requests to specialized agents.
        Analyze each user message and determine which agent would be best suited to handle it."""
