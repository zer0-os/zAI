from decimal import Decimal
from typing import Dict, List, Any, Optional, Tuple
from wallet.adapters.base_adapter import BaseAdapter, MethodDescriptor
from wallet.adapters.uniswap.contract_registry import uniswap_contracts
from wallet.adapters.common.contract_registry import common_contracts
from eth_abi import encode
from wallet.tools import wallet_tool
from wallet.wallet_types import WalletType
import time


class UniswapAdapter(BaseAdapter):
    """Adapter for Uniswap DEX operations"""

    def __init__(self, wallet: WalletType):
        super().__init__(wallet)
        uniswap_contracts.initialize(self._wallet._web3)
        common_contracts.initialize(self._wallet._web3)

    async def _get_pool_fee(self, token_in_address: str, token_out_address: str) -> int:
        """
        Get the most liquid fee tier for a token pair

        Args:
            token_in_address: Address of input token
            token_out_address: Address of output token

        Returns:
            int: Fee tier (100, 500, 3000, or 10000)
        """
        factory = uniswap_contracts.get_contract("factory")
        fee_tiers = [100, 500, 3000, 10000]

        # Find the pool with highest liquidity
        highest_liquidity = 0
        best_fee = 3000  # Default to 0.3% if no pools found

        for fee in fee_tiers:
            pool_address = await factory.functions.getPool(
                token_in_address, token_out_address, fee
            ).call()

            if pool_address != "0x0000000000000000000000000000000000000000":
                pool = uniswap_contracts.get_contract("pool", pool_address)

                # Get current liquidity
                liquidity = await pool.functions.liquidity().call()

                if liquidity > highest_liquidity:
                    highest_liquidity = liquidity
                    best_fee = fee

        return best_fee

    async def _get_quote(
        self, token_in_address: str, token_out_address: str, amount_in_wei: int
    ) -> Tuple[int, List[int], List[int], int]:
        """
        Get quote for exact input swap from Uniswap V3 Quoter

        Args:
            token_in_address: Address of input token
            token_out_address: Address of output token
            amount_in_wei: Amount of input token in Wei

        Returns:
            Tuple[int, List[int], List[int], int]: Expected output amount in Wei, sqrtPriceX96AfterList, initializedTicksCrossedList, gasEstimate
        """
        # Get the optimal fee tier
        fee = await self._get_pool_fee(token_in_address, token_out_address)

        # Get Quoter contract
        quoter = uniswap_contracts.get_contract("quoter")

        # Encode the path (token_in -> fee -> token_out)
        path = (
            token_in_address.replace("0x", "")
            + fee.to_bytes(3, "big").hex()
            + token_out_address.replace("0x", "")
        )
        encoded_path = bytes.fromhex(path)

        try:
            # Call quoteExactInput function
            quote = await quoter.functions.quoteExactInput(
                encoded_path, amount_in_wei
            ).call()
            return quote
        except Exception as e:
            raise ValueError(f"Failed to get quote: {str(e)}")

    @wallet_tool(
        {
            "token_in_address": "Address of token to swap from",
            "token_out_address": "Address of token to swap to",
            "amount_in": "Amount of input token to swap",
            "slippage_percentage": "Maximum acceptable slippage in percentage (default 0.5%)",
        },
        namespace="uniswap",
    )
    async def swap(
        self,
        token_in_address: str,
        token_out_address: str,
        amount_in: Decimal,
        slippage_percentage: Decimal = Decimal("0.5"),
    ) -> Dict[str, Any]:
        """
        Exchange one token for another on Uniswap V3. Use this method when:
        - User wants to trade/exchange/swap between any two tokens on Uniswap
        - User wants to convert ETH to any token (using 'eth' as input address)
        - User wants to convert any token to another token
        - User needs to specify slippage tolerance for the trade

        Common triggers: "swap tokens", "exchange crypto", "trade ETH for", "convert tokens"

        Args:
            token_in_address: Address of token to swap from (use 'eth' for native ETH)
            token_out_address: Address of token to swap to
            amount_in: Amount of input token to swap
            slippage_percentage: Maximum acceptable slippage in percentage (default 0.5%)

        Returns:
            Dict containing transaction receipt and swap details
        """
        try:
            # Handle ETH/WETH conversion
            if token_in_address.lower() == "eth":
                token_in_address = common_contracts.get_contract("weth").address
                is_native_eth = True
            else:
                is_native_eth = False

            # Convert addresses to checksum
            token_in_address = self._wallet._web3.to_checksum_address(token_in_address)
            token_out_address = self._wallet._web3.to_checksum_address(
                token_out_address
            )

            # Track both tokens
            self._wallet._tracked_tokens.add(token_in_address)
            self._wallet._tracked_tokens.add(token_out_address)

            # Get token decimals and convert amount to Wei
            token_in = common_contracts.get_contract("erc20", token_in_address)
            decimals = await token_in.functions.decimals().call()
            amount_in_wei = int(amount_in * 10**decimals)

            # Get optimal fee tier
            fee = await self._get_pool_fee(token_in_address, token_out_address)

            # Check if there's sufficient liquidity before proceeding
            factory = uniswap_contracts.get_contract("factory")
            pool_address = await factory.functions.getPool(
                token_in_address, token_out_address, fee
            ).call()

            if pool_address == "0x0000000000000000000000000000000000000000":
                raise ValueError("No liquidity pool exists for this token pair")

            # For non-ETH input tokens, check balance and allowance
            if not is_native_eth:
                balance = await token_in.functions.balanceOf(
                    self._wallet._account.address
                ).call()
                if balance < amount_in_wei:
                    raise ValueError(
                        f"Insufficient token balance. Required: {amount_in}, Available: {Decimal(balance) / 10**decimals}"
                    )

            # Get quote and validate
            quote = await self._get_quote(
                token_in_address, token_out_address, amount_in_wei
            )

            if quote[0] == 0:
                raise ValueError(
                    "Quote returned zero. Insufficient liquidity or invalid token pair"
                )

            min_amount_out = int(quote[0] * (1 - slippage_percentage / 100))

            # Get SwapRouter contract
            swap_router = uniswap_contracts.get_contract("swap_router")

            if is_native_eth:
                # Handle native ETH wrapping and approval in single transaction
                value = amount_in_wei
            else:
                # Approve SwapRouter for ERC20
                await self._approve_erc20(token_in, swap_router.address, amount_in_wei)
                value = 0

            # Prepare swap parameters
            params = {
                "tokenIn": token_in_address,
                "tokenOut": token_out_address,
                "fee": fee,
                "recipient": self._wallet._account.address,
                "deadline": int(time.time()) + 1800,  # 30 minutes
                "amountIn": amount_in_wei,
                "amountOutMinimum": min_amount_out,
                "sqrtPriceLimitX96": 0,  # No price limit
            }

            # Execute swap
            swap_tx = await swap_router.functions.exactInputSingle(
                params
            ).build_transaction(
                {
                    "from": self._wallet._account.address,
                    "value": value,
                    "nonce": await self._wallet._web3.eth.get_transaction_count(
                        self._wallet._account.address
                    ),
                }
            )

            signed_tx = self._wallet._web3.eth.account.sign_transaction(
                swap_tx, self._wallet._account.key
            )
            tx_hash = await self._wallet._web3.eth.send_raw_transaction(
                signed_tx.raw_transaction
            )
            receipt = await self._wallet._web3.eth.wait_for_transaction_receipt(tx_hash)

            return {
                "transaction_hash": receipt["transactionHash"].hex(),
                "status": "success" if receipt["status"] == 1 else "failed",
                "token_in": token_in_address,
                "token_out": token_out_address,
                "amount_in": str(amount_in),
                "amount_out_min": min_amount_out,
            }

        except Exception as e:
            if "Transaction reverted without a reason" in str(e):
                # Try to provide more specific error messages
                if "insufficient allowance" in str(e).lower():
                    raise Exception("Insufficient token allowance for swap")
                elif "insufficient balance" in str(e).lower():
                    raise Exception("Insufficient token balance")
                else:
                    raise Exception(
                        "Swap failed. This might be due to:\n"
                        "1. High price impact\n"
                        "2. Insufficient liquidity\n"
                        "3. Slippage tolerance exceeded\n"
                        f"Original error: {str(e)}"
                    )
            raise Exception(f"Swap failed: {str(e)}")

    async def _approve_erc20(self, token_contract, spender: str, amount: int) -> None:
        """Helper method to approve ERC20 spending"""
        current_allowance = await token_contract.functions.allowance(
            self._wallet._account.address, spender
        ).call()

        if current_allowance < amount:
            tx = await token_contract.functions.approve(
                spender, amount
            ).build_transaction(
                {
                    "from": self._wallet._account.address,
                    "nonce": await self._wallet._web3.eth.get_transaction_count(
                        self._wallet._account.address
                    ),
                }
            )
            signed_tx = self._wallet._web3.eth.account.sign_transaction(
                tx, self._wallet._account.key
            )
            tx_hash = await self._wallet._web3.eth.send_raw_transaction(
                signed_tx.raw_transaction
            )
            await self._wallet._web3.eth.wait_for_transaction_receipt(tx_hash)
