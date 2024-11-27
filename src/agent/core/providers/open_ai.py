from typing import Dict, Any, List, Optional, Union, Callable
import requests
from agent.core.providers.model_provider import ModelProvider
import os
from dotenv import load_dotenv


class OpenAIProvider(ModelProvider):
    """
    OpenAI API provider implementation

    Handles communication with OpenAI's API for text generation
    """

    def __init__(
        self,
        base_url: str = "https://api.openai.com/v1",
        api_key: Optional[str] = None,
        debug_log: Optional[Callable[[str, Any], None]] = None,
    ):
        """
        Initialize OpenAI provider

        Args:
            base_url: Base URL for OpenAI API endpoints
            debug_log: Optional debug logging function
        """
        load_dotenv()

        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        assert self.api_key, "OPENAI_API_KEY is not set"
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }
        )
        self._debug_log = debug_log or (
            lambda *args: None
        )  # No-op if no debug_log provided

    async def generate(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs: Any,
    ) -> Union[str, Dict[str, Any]]:
        """
        Generate text using OpenAI's API

        Args:
            messages: List of conversation messages
            tools: Optional list of tool definitions
            **kwargs: Additional parameters for the API call including:
                     model: Model identifier
                     temperature: Sampling temperature

        Returns:
            Either a string response or a dictionary containing tool calls

        Raises:
            OpenAIAPIError: If the API request fails
        """
        self._debug_log("Generating with messages", messages)
        self._debug_log("Using tools", tools)
        endpoint = f"{self.base_url}/chat/completions"

        payload = {
            "messages": messages,
            "model": kwargs.get("model", "gpt-3.5-turbo-0125"),
            "temperature": kwargs.get("temperature", 0.7),
        }

        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = kwargs.get("tool_choice", "auto")

        self._debug_log("Payload", payload)

        try:
            response = self.session.post(endpoint, json=payload)
            response.raise_for_status()
            response_data = response.json()
            message = response_data["choices"][0]["message"]
            return message

        except requests.exceptions.RequestException as e:
            raise OpenAIAPIError(f"OpenAI API request failed: {str(e)}") from e


class OpenAIAPIError(Exception):
    """Custom exception for OpenAI API errors"""

    pass
