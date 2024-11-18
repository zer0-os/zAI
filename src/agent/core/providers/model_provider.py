from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Union


class ModelProvider(ABC):
    """Abstract base class for AI model providers"""

    @abstractmethod
    def generate(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs: Any
    ) -> Union[str, Dict[str, Any]]:
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
