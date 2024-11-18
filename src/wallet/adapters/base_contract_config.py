from abc import ABC
from dataclasses import dataclass
from typing import Dict, Any, Optional
from web3 import Web3


@dataclass
class ContractConfig:
    """Configuration for a smart contract"""

    address: str
    abi: Dict[str, Any]


class ContractRegistry(ABC):
    """Base registry for managing smart contract configurations and instances"""

    def __init__(self):
        self._configs: Dict[str, ContractConfig] = {}
        self._abis: Dict[str, Dict[str, Any]] = {}
        self._instances: Dict[str, Any] = {}
        self._web3: Optional[Web3] = None

    def initialize(self, web3: Web3) -> None:
        """Initialize the registry with Web3 instance"""
        self._web3 = web3

    def get_contract(self, name: str, address: Optional[str] = None) -> Any:
        """Get or create a contract instance"""
        if name not in self._instances:
            if name not in self._configs:
                raise KeyError(f"Contract configuration not found: {name}")
            if not self._web3:
                raise RuntimeError("Registry not initialized with Web3 instance")

            config = self._configs[name]
            self._instances[name] = self._web3.eth.contract(
                address=config.address if address is None else address, abi=config.abi
            )
        return self._instances[name]

    def get_abi(self, name: str) -> Dict[str, Any]:
        """Get ABI by name"""
        if name not in self._abis:
            raise KeyError(f"ABI not found: {name}")
        return self._abis[name]
