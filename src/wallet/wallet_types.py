from typing import TypeVar
from eth_account.signers.local import LocalAccount
from web3 import AsyncWeb3

Web3Type = AsyncWeb3
AccountType = LocalAccount


class WalletInstance:
    _web3: Web3Type
    _account: AccountType


WalletType = TypeVar("WalletType", bound=WalletInstance)
