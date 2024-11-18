from typing import Callable, Dict, Any, Optional, NamedTuple
from functools import wraps
import inspect
from decimal import Decimal


class ToolMetadata(NamedTuple):
    """Container for complete tool metadata including internal routing info"""

    description: Dict[str, Any]  # The OpenAI-compatible tool description
    namespace: Optional[str]  # The namespace for routing


def create_tool(
    func: Callable,
    descriptions: Dict[str, str] = None,
    namespace: Optional[str] = None,
) -> ToolMetadata:
    """Convert a wallet function into a tool description with metadata

    Args:
        func: The function to convert
        descriptions: Optional dictionary mapping parameter names to their descriptions
        namespace: Optional namespace for routing
    """
    sig = inspect.signature(func)
    doc = inspect.getdoc(func) or ""
    descriptions = descriptions or {}

    parameters = {}
    for name, param in sig.parameters.items():
        if name == "self":
            continue

        param_type = (
            param.annotation.__name__
            if hasattr(param.annotation, "__name__")
            else str(param.annotation)
        )

        # Handle Optional types
        if "Optional" in param_type:
            param_type = (
                str(param.annotation).replace("typing.Optional[", "").replace("]", "")
            )

        parameters[name] = {
            "type": (
                "string"
                if param_type in ["decimal.Decimal", "Decimal", "str"]
                else "integer" if param_type == "int" else param_type.lower()
            ),
            "description": descriptions.get(
                name, name
            ),  # Use provided description or fallback to name
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
            "name": func.__name__,
            "description": doc.split("Args:")[0].strip(),
            "parameters": {
                "type": "object",
                "properties": parameters,
                "required": required_params,
            },
        },
    }

    return ToolMetadata(description=tool_description, namespace=namespace)


def wallet_tool(
    descriptions: Dict[str, str] = None, namespace: Optional[str] = None
) -> Callable:
    """Decorator to convert wallet methods to tools

    Args:
        descriptions: Optional dictionary mapping parameter names to their descriptions
        namespace: Optional namespace for routing
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
        wrapper.tool_metadata = create_tool(func, descriptions, namespace)
        return wrapper

    return decorator
