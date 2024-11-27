import asyncio
import os
from typing import List, Optional, Dict, Any, Set
from abc import ABC, abstractmethod
from eth_account import Account
from web3 import AsyncWeb3
from decimal import Decimal
from wallet.exceptions import (
    WalletError,
    InvalidAddressError,
)
from wallet.adapters.adapter_registry import AdapterRegistry
from wallet.adapters.base_adapter import BaseAdapter
from wallet.tools import wallet_tool
from wallet.adapters.common.contract_registry import common_contracts


class ZWallet:
    """
    A wrapper class around Web3 functionality to handle common blockchain operations.
    Provides simplified interfaces for transfers, token operations, and NFT interactions.
    """

    def __init__(self, key_path: Optional[str] = None):
        """
        Initialize the wallet wrapper.

        Args:
            key_path (Optional[str]): Path to the keyfile
        """
        rpc_url = os.getenv("RPC_URL")
        assert rpc_url, "RPC_URL is not set"
        self._web3 = AsyncWeb3(AsyncWeb3.AsyncHTTPProvider(rpc_url))
        hardhat_private_key = os.getenv("HARDHAT_PRIVATE_KEY")
        if hardhat_private_key:
            self._account = self._web3.eth.account.from_key(hardhat_private_key)
        else:
            private_key = self.load_private_key(key_path if key_path else "./keyfile")
            self._account = (
                None
                if not private_key
                else self._web3.eth.account.from_key(private_key)
            )
        self._adapter_registry = AdapterRegistry()
        common_contracts.initialize(self._web3)
        self._tracked_tokens: Set[str] = set()

    def load_private_key(self, key_path):
        with open(key_path) as keyfile:
            encrypted_key = keyfile.read()
            key_password = os.getenv("KEY_PASSWORD")
            assert key_password, "KEY_PASSWORD is not set"
            private_key = self._web3.eth.account.decrypt(encrypted_key, key_password)
            return private_key

    def add_adapter(self, adapter: BaseAdapter) -> None:
        """
        Register a new adapter with the wallet.

        Args:
            adapter (BaseAdapter): Adapter instance to register
        """
        self._adapter_registry.register(adapter)

    def get_adapter(self, namespace: str) -> BaseAdapter:
        """
        Get an adapter by its namespace.

        Args:
            namespace (str): Adapter namespace

        Returns:
            BaseAdapter: The requested adapter instance
        """
        return self._adapter_registry.get_adapter(namespace)

    def get_adapters(self) -> List[BaseAdapter]:
        """Get all registered adapters"""
        return list(self._adapter_registry._adapters.values())

    # @wallet_tool()
    async def get_address(self) -> str:
        """Returns wallet address for receiving deposits"""
        return f"Wallet address: {self._account.address}"

    @wallet_tool(descriptions={"token_address": "Token contract address, None for ETH"})
    async def transfer(
        self, to_address: str, amount: Decimal, token_address: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Send tokens or ETH to another wallet address. Use this method when:
        - User wants to send/transfer ETH to someone
        - User wants to send/transfer specific tokens to an address
        - User needs to move funds between wallets
        - User wants to pay someone in crypto

        Common triggers: "send eth", "transfer tokens", "pay", "send money to", "transfer to wallet"

        Args:
            to_address (str): Recipient address
            amount (Decimal): Amount to transfer
            token_address (Optional[str]): Token contract address, None for ETH

        Returns:
            Dict[str, Any]: Transaction receipt
        """
        if not self._web3.is_address(to_address):
            raise InvalidAddressError(f"Invalid recipient address: {to_address}")

        nonce = await self._web3.eth.get_transaction_count(self._account.address)
        if token_address:
            # ERC20 token transfer
            token_contract = common_contracts.get_contract("erc20", token_address)
            tx = token_contract.functions.transfer(
                to_address, amount
            ).build_transaction(
                {
                    "from": self._account.address,
                    "nonce": nonce,
                }
            )
            signed_tx = self._web3.eth.account.sign_transaction(tx, self._account.key)
            tx_hash = await self._web3.eth.send_raw_transaction(
                signed_tx.raw_transaction
            )
        else:
            # ETH transfer - Convert amount to Wei
            amount_wei = self._web3.to_wei(amount, "ether")
            tx = {
                "from": self._account.address,
                "to": to_address,
                "value": amount_wei,
                "nonce": nonce,
                "gas": 21000,  # Standard gas limit for ETH transfers
                "gasPrice": await self._web3.eth.gas_price,
            }

            signed_tx = self._web3.eth.account.sign_transaction(tx, self._account.key)
            tx_hash = await self._web3.eth.send_raw_transaction(
                signed_tx.raw_transaction
            )

        # Convert AttributeDict to regular dict before returning
        receipt = await self._web3.eth.wait_for_transaction_receipt(tx_hash)
        return {
            "transaction_hash": receipt["transactionHash"].hex(),
            "status": "success" if receipt["status"] == 1 else "failed",
        }

    @wallet_tool(
        descriptions={"token_type": "Type of tokens to fetch (erc20, erc721, etc)"}
    )
    async def get_balances(self, token_type: str = "erc20") -> Dict[str, Any]:
        """
        Check wallet balances for ETH and tokens. Use this method when:
        - User wants to check their ETH balance
        - User wants to see all their token balances
        - User needs to verify their available funds
        - User asks about their crypto holdings
        - User wants to know how much they own

        Common triggers: "check balance", "how much eth do i have", "show my tokens",
        "what's in my wallet", "view balance", "check my crypto"

        Args:
            token_type (str): Type of tokens to fetch (default: "erc20")

        Returns:
            Dict[str, Any]: Combined ETH and token balances
        """
        if not self._account:
            raise WalletError("Wallet not initialized with private key")

        # Get ETH balance
        try:
            eth_balance_wei = await self._web3.eth.get_balance(self._account.address)
            eth_balance = self._web3.from_wei(eth_balance_wei, "ether")
        except Exception as e:
            raise WalletError(f"Failed to fetch ETH balance: {str(e)}")

        # Get tracked token balances
        token_balances = {}
        for token_address in self._tracked_tokens:
            try:
                token_contract = common_contracts.get_contract("erc20", token_address)
                raw_balance = await token_contract.functions.balanceOf(
                    self._account.address
                ).call()
                # Get token symbol and decimals
                symbol = await token_contract.functions.symbol().call()
                decimals = await token_contract.functions.decimals().call()
                # Convert raw balance to token amount
                token_balance = Decimal(raw_balance) / Decimal(10**decimals)
                token_balances[symbol] = str(token_balance)
            except Exception as e:
                raise WalletError(
                    f"Failed to fetch balance for token {token_address}: {str(e)}"
                )

        balances = {
            "ETH": str(eth_balance),
            **token_balances,
        }
        return f"""
            Display the following wallet balances in a bulleted list using markdown
            {balances}
        """

    def get_tracked_tokens(self) -> List[str]:
        """Returns list of tracked token addresses"""
        return list(self._tracked_tokens)
