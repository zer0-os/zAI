from abc import ABC
from typing import Dict
from dataclasses import dataclass
from wallet.wallet_types import WalletType


@dataclass
class MethodDescriptor:
    """Describes an adapter method and its functionality"""

    name: str
    description: str
    parameters: Dict[str, str]
    return_type: str


class BaseAdapter(ABC):
    """Base class for all wallet adapters"""

    def __init__(self, wallet: WalletType):
        self._wallet = wallet

    @property
    def namespace(self) -> str:
        """Return the namespace for this adapter"""
        return self.__class__.__name__.lower().replace("adapter", "")
