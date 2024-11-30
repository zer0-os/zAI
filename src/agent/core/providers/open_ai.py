from typing import Dict, Any, List, Optional, Union, Callable, AsyncGenerator
import aiohttp
import json
from deepmerge import always_merger
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
        debug: bool = False,
    ):
        """
        Initialize OpenAI provider

        Args:
            base_url: Base URL for OpenAI API endpoints
            debug: Enable debug logging if True
        """
        load_dotenv()

        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        assert self.api_key, "OPENAI_API_KEY is not set"
        self.base_url = base_url.rstrip("/")
        super().__init__(debug=debug)

    async def generate(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        stream: bool = False,
        **kwargs: Any,
    ) -> Union[str, Dict[str, Any], AsyncGenerator[str, None]]:
        """Generate text using OpenAI's API with optional streaming

        Args:
            messages: List of conversation messages
            tools: Optional list of tool definitions
            stream: Whether to stream the response
            **kwargs: Additional parameters

        Returns:
            Either a string response, a dictionary containing tool calls,
            or an async generator yielding response chunks if streaming
        """
        if stream:
            return self.generate_stream(messages, tools, **kwargs)

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

        async with aiohttp.ClientSession() as session:
            async with session.post(
                endpoint,
                json=payload,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
            ) as response:
                response.raise_for_status()
                response_data = await response.json()
                return response_data["choices"][0]["message"]

    async def generate_stream(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs: Any,
    ) -> AsyncGenerator[str, None]:
        """Stream text generation from OpenAI's API

        Args:
            messages: List of conversation messages
            tools: Optional list of tool definitions
            **kwargs: Additional parameters

        Yields:
            Chunks of the generated response or complete tool call response
        """
        endpoint = f"{self.base_url}/chat/completions"
        payload = {
            "messages": messages,
            "model": kwargs.get("model", "gpt-3.5-turbo-0125"),
            "temperature": kwargs.get("temperature", 0.7),
            "stream": True,
        }

        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = kwargs.get("tool_choice", "auto")

        tool_call_response = {}
        async with aiohttp.ClientSession() as session:
            async with session.post(
                endpoint,
                json=payload,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
            ) as response:
                response.raise_for_status()
                async for line in response.content:
                    if not line:
                        continue

                    line = line.decode("utf-8").strip()
                    if not (line.startswith("data: ") and line != "data: [DONE]"):
                        continue

                    data = json.loads(line[6:])
                    choice = data["choices"][0]

                    if choice["finish_reason"] == "stop":
                        yield "stop"

                    # Handle tool calls
                    if "delta" in choice:
                        delta = choice["delta"]
                        self._debug_log("Delta: " + str(delta))
                        if "tool_calls" in delta:
                            if "tool_calls" not in tool_call_response:
                                tool_call_response = delta
                                if not "content" in tool_call_response:
                                    tool_call_response["content"] = None
                            else:
                                # Merge the new delta into our accumulated response
                                for new_tool_call in delta["tool_calls"]:
                                    index = new_tool_call["index"]
                                    for existing_tool_call in tool_call_response[
                                        "tool_calls"
                                    ]:
                                        if existing_tool_call["index"] == index:
                                            if "function" in new_tool_call:
                                                if "function" not in existing_tool_call:
                                                    existing_tool_call["function"] = {}
                                                existing_tool_call["function"].update(
                                                    new_tool_call["function"]
                                                )
                                            for key, value in new_tool_call.items():
                                                if key != "function":
                                                    existing_tool_call[key] = value

                        # If we've reached the end of tool calls, yield the complete response
                        elif choice.get("finish_reason") == "tool_calls":
                            yield tool_call_response
                            tool_call_response = {}
                        else:
                            if delta.get("content"):
                                yield delta


class OpenAIAPIError(Exception):
    """Custom exception for OpenAI API errors"""

    pass
