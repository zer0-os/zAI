from typing import Callable, Dict, Any, Optional, NamedTuple
from functools import wraps
import inspect
from decimal import Decimal


class ToolMetadata(NamedTuple):
    """Container for complete tool metadata including internal routing info"""

    description: Dict[str, Any]  # The OpenAI-compatible tool description
    namespace: Optional[str]  # The namespace for routing
    exclude: bool = (
        False  # If True, the tool will not be included in the agent's tools list
    )


TYPE_MAP = {
    str: "string",
    int: "integer",
    float: "number",
    bool: "boolean",
    list: "array",
    dict: "object",
    Decimal: "string",  # Keep Decimal as string for OpenAI compatibility
    type(None): "null",
}


def create_tool(
    func: Callable,
    descriptions: Dict[str, str] = None,
    namespace: Optional[str] = None,
    exclude: bool = False,
    name: Optional[str] = None,
) -> ToolMetadata:
    """Convert a wallet function into a tool description with metadata

    Args:
        func: The function to convert
        descriptions: Optional dictionary mapping parameter names to their descriptions
        namespace: Optional namespace for routing
        exclude: If True, the tool will not be included in the agent's tools list
        name: Optional name override for the tool
    """
    sig = inspect.signature(func)
    original_func = getattr(func, "__wrapped__", func)
    func_name = name if name is not None else original_func.__name__
    doc = inspect.getdoc(original_func) or ""
    descriptions = descriptions or {}

    parameters = {}
    for name, param in sig.parameters.items():
        if name == "self":
            continue

        # Handle Optional types
        if (
            hasattr(param.annotation, "__origin__")
            and param.annotation.__origin__ is Optional
        ):
            param_type = param.annotation.__args__[0]
        else:
            param_type = param.annotation

        # Use type map with fallback to string
        parameters[name] = {
            "type": TYPE_MAP.get(param_type, "string"),
            "description": descriptions.get(name, name),
        }

    # Only include parameters that don't have default values in required list
    required_params = [
        name
        for name, param in sig.parameters.items()
        if param.default is inspect.Parameter.empty and name != "self"
    ]

    # Create the OpenAI-compatible tool description
    tool_description = {
        "type": "function",
        "function": {
            "name": func_name,
            "description": doc.split("Args:")[0].strip(),
            "parameters": {
                "type": "object",
                "properties": parameters,
                "required": required_params,
            },
        },
    }

    return ToolMetadata(
        description=tool_description, namespace=namespace, exclude=exclude
    )


def agent_tool(
    descriptions: Dict[str, str] = None,
    namespace: Optional[str] = None,
    exclude: bool = False,
    name: Optional[str] = None,
) -> Callable:
    """Decorator to convert agent methods to tools

    Args:
        descriptions: Optional dictionary mapping parameter names to their descriptions
        namespace: Optional namespace for routing
        exclude: If True, the tool will not be included in the agent's tools list
        name: Optional name override for the tool
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(self, **kwargs):
            # Convert string amounts to Decimal where needed
            sig = inspect.signature(func)
            for param_name, param in sig.parameters.items():
                if param.annotation == Decimal and param_name in kwargs:
                    kwargs[param_name] = Decimal(kwargs[param_name])
            return await func(self, **kwargs)

        # Store tool metadata
        wrapper._param_descriptions = descriptions or {}
        wrapper.tool_metadata = create_tool(
            func, descriptions, namespace, exclude, name
        )
        return wrapper

    return decorator
