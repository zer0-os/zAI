from functools import wraps
from typing import Type, Set

from agent.core.base_agent import BaseAgent
from agent.core.decorators.tool import agent_tool

_registered_transfer_names: Set[str] = set()


def agent(cls: Type[BaseAgent]) -> Type[BaseAgent]:
    """Decorator to ensure unique transfer_to implementations"""
    original_method = cls.transfer_to
    method_name = f"transfer_to_{cls.__name__.lower()}"

    if method_name in _registered_transfer_names:
        raise ValueError(f"Transfer method name '{method_name}' already registered")

    _registered_transfer_names.add(method_name)

    @agent_tool(exclude=True, name=method_name)
    @wraps(original_method)
    async def wrapped_transfer(self, *args, **kwargs):
        return await original_method(self, *args, **kwargs)

    setattr(cls, method_name, wrapped_transfer)
    return cls
