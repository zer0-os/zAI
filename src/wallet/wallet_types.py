from typing import TypeVar, Dict, Any
from eth_account.signers.local import LocalAccount
from web3 import AsyncWeb3

Web3Type = AsyncWeb3
AccountType = LocalAccount


class WalletInstance:
    _web3: Web3Type
    _wallet_address: str
    _chain_id: int

    async def sign_transaction(self, transaction: Dict[str, Any]) -> Dict[str, Any]:
        """Sign transaction"""
        pass

    async def send_transaction(self, transaction: Dict[str, Any]) -> Dict[str, Any]:
        """Sign and send transaction"""
        pass


WalletType = TypeVar("WalletType", bound=WalletInstance)
