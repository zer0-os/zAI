from abc import ABC, abstractmethod
import logging
from typing import AsyncGenerator, Dict, Any, List, Optional, Union


class ModelProvider(ABC):
    """Abstract base class for AI model providers"""

    def __init__(self, debug: bool = False):
        self._logger = None
        if debug:
            self._logger = logging.getLogger(__name__)

    def _debug_log(self, message: str, *args: Any):
        if self._logger:
            self._logger.debug(message, *args)

    @abstractmethod
    def generate(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs: Any
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Generate text from the model

        Args:
            messages: List of conversation messages in the format:
                     [{"role": "user", "content": "..."}, ...]
            tools: Optional list of tool definitions available to the model
            **kwargs: Additional model parameters like temperature, max_tokens, etc.

        Returns:
            Either a string response or a dictionary containing tool calls in the format:
            {
                "content": str,
                "tool_calls": [
                    {
                        "id": str,
                        "function": {
                            "name": str,
                            "arguments": str
                        }
                    },
                    ...
                ]
            }
        """
        pass
