import asyncio
import base64
import os
from typing import List, Optional, Dict, Any, Set, AsyncGenerator
from eth_account import Account
from web3 import AsyncWeb3
from decimal import Decimal
from agent.types.agent_info import AgentInfo
from wallet.exceptions import (
    WalletError,
    InvalidAddressError,
)
from wallet.adapters.adapter_registry import AdapterRegistry
from wallet.adapters.base_adapter import BaseAdapter
from wallet.tools import wallet_tool
from wallet.adapters.common.contract_registry import common_contracts
from utils.privy_auth import PrivyAuthorizationSigner
import aiohttp


class ZWallet:
    """
    A wrapper class around Web3 functionality to handle common blockchain operations.
    Provides simplified interfaces for transfers, token operations, and NFT interactions.
    """

    def __init__(self, agent_data: AgentInfo):
        """
        Initialize the wallet wrapper.

        Args:
            key_path (Optional[str]): Path to the keyfile
        """
        rpc_url = os.getenv("RPC_URL")
        assert rpc_url, "RPC_URL is not set"
        self._web3 = AsyncWeb3(AsyncWeb3.AsyncHTTPProvider(rpc_url))
        self._adapter_registry = AdapterRegistry()
        common_contracts.initialize(self._web3)
        self._tracked_tokens: Set[str] = set()
        self._chain_id = int(os.getenv("CHAIN_ID") or 1)
        self._agent_data = agent_data
        self._wallet_address = agent_data.wallet_address
        self._privy_signer = PrivyAuthorizationSigner(
            app_id=os.getenv("PRIVY_APP_ID", "")
        )
        self._wallet_id = agent_data.wallet_id

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

    async def get_address(self) -> str:
        """Returns wallet address for receiving deposits"""
        return f"Wallet address: {self._wallet_address}"

    @wallet_tool(descriptions={"token_address": "Token contract address, None for ETH"})
    async def transfer(
        self, to_address: str, amount: Decimal, token_address: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Send tokens or ETH to another wallet address.

        Args:
            to_address (str): Recipient address
            amount (Decimal): Amount to transfer
            token_address (Optional[str]): Token contract address, None for ETH

        Returns:
            Dict[str, Any]: Transaction status and details
        """
        if not self._web3.is_address(to_address):
            raise InvalidAddressError(f"Invalid recipient address: {to_address}")

        nonce = await self._web3.eth.get_transaction_count(self._wallet_address)
        if (
            token_address
            and token_address != "0x0000000000000000000000000000000000000000"
            and token_address.upper() != "ETH"
        ):
            # ERC20 token transfer
            token_contract = common_contracts.get_contract("erc20", token_address)
            tx = token_contract.functions.transfer(
                to_address, amount
            ).build_transaction(
                {
                    "from": self._wallet_address,
                    "nonce": nonce,
                }
            )
        else:
            # ETH transfer
            amount_wei = self._web3.to_wei(amount, "ether")
            tx = {
                "from": self._wallet_address,
                "to": to_address,
                "value": amount_wei,
                "nonce": nonce,
                "gas": 21000,
                "gas_price": await self._web3.eth.gas_price,
            }

        response = await self.send_transaction(tx)

        tx_hash = response.get("data", {}).get("hash")
        if not tx_hash:
            raise WalletError("No transaction hash returned from Privy")

        return {
            "status": "pending",
            "message": "Transaction submitted, waiting for confirmation...",
            "transaction_hash": tx_hash,
        }

    @wallet_tool(
        descriptions={"token_type": "Type of tokens to fetch (erc20, erc721, etc)"}
    )
    async def get_balances(self) -> Dict[str, Any]:
        """
        Check wallet balances for ETH

        Common triggers: "check balance", "how much eth do i have", "view balance", "check my crypto"

        Returns:
            Dict[str, Any]: Combined ETH and token balances
        """
        # Get ETH balance
        try:
            eth_balance_wei = await self._web3.eth.get_balance(self._wallet_address)
            eth_balance = self._web3.from_wei(eth_balance_wei, "ether")
        except Exception as e:
            raise WalletError(f"Failed to fetch ETH balance: {str(e)}")

        return f"ETH: {str(eth_balance)}"

    def get_tracked_tokens(self) -> List[str]:
        """Returns list of tracked token addresses"""
        return list(self._tracked_tokens)

    async def _make_privy_request(
        self,
        method: str,
        transaction: Dict[str, Any],
        additional_body_params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Make a request to Privy's wallet API.

        Args:
            method (str): RPC method to execute (e.g., 'eth_sendTransaction', 'eth_signTransaction')
            transaction (Dict[str, Any]): Transaction parameters
            additional_body_params (Optional[Dict[str, Any]]): Additional parameters for request body

        Returns:
            Dict[str, Any]: Response from Privy API
        """
        url = f"https://api.privy.io/v1/wallets/{self._wallet_id}/rpc"

        privy_app_id = os.getenv("PRIVY_APP_ID")
        privy_app_secret = os.getenv("PRIVY_APP_SECRET")

        if not privy_app_id or not privy_app_secret:
            raise ValueError(
                "PRIVY_APP_ID and PRIVY_APP_SECRET environment variables must be set"
            )

        if "chain_id" not in transaction:
            transaction["chain_id"] = self._chain_id

        auth_string = f"{privy_app_id}:{privy_app_secret}"
        basic_auth = base64.b64encode(auth_string.encode()).decode()

        body = {
            "method": method,
            "params": {"transaction": transaction},
        }

        if additional_body_params:
            body.update(additional_body_params)

        headers = await self._privy_signer.get_auth_headers(
            url=url, body=body, method="POST"
        )
        headers["Content-Type"] = "application/json"
        headers["Authorization"] = f"Basic {basic_auth}"

        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=body, headers=headers) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise WalletError(f"API request failed: {error_text}")

                return await response.json()

    async def send_transaction(
        self, transaction: Dict[str, Any], gas_estimate: bool = True
    ) -> Dict[str, Any]:
        """
        Sign and send a transaction using Privy's wallet API.

        Args:
            transaction (Dict[str, Any]): Transaction parameters
            gas_estimate (bool): Whether to estimate gas if not provided

        Returns:
            Dict[str, Any]: Transaction response from Privy API
        """
        if gas_estimate and "gas" not in transaction:
            gas = await self._web3.eth.estimate_gas(transaction)
            transaction["gas"] = hex(gas)

        return await self._make_privy_request(
            method="eth_sendTransaction",
            transaction=transaction,
            additional_body_params={"caip2": f"eip155:{self._chain_id}"},
        )

    async def sign_transaction(self, transaction: Dict[str, Any]) -> Dict[str, Any]:
        """
        Sign a transaction using Privy's wallet API without broadcasting it.

        Args:
            transaction (Dict[str, Any]): Transaction parameters to sign

        Returns:
            Dict[str, Any]: Contains the signed transaction and encoding format
        """
        return await self._make_privy_request(
            method="eth_signTransaction", transaction=transaction
        )
