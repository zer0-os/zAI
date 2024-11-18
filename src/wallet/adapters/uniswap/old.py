from decimal import Decimal
from typing import Dict, List, Any, Optional
from wallet.adapters.base_adapter import BaseAdapter, MethodDescriptor
from wallet.adapters.uniswap.contract_registry import uniswap_contracts
from wallet.adapters.common.contract_registry import common_contracts
from eth_abi import encode
from wallet.tools import wallet_tool
from wallet.wallet_types import WalletType


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
    ) -> int:
        """
        Get quote for exact input swap from Uniswap V3 Quoter

        Args:
            token_in_address: Address of input token
            token_out_address: Address of output token
            amount_in_wei: Amount of input token in Wei

        Returns:
            int: Expected output amount in Wei
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
            # Handle ETH to WETH conversion first if needed
            is_native_eth = (
                token_in_address.lower() == "eth"
                or token_in_address.lower()
                == self._wallet._web3.to_checksum_address(
                    "0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee"
                )
            )

            if is_native_eth:
                # Get WETH contract
                weth_contract = common_contracts.get_contract("weth")
                weth_address = weth_contract.address
                amount_in_wei = int(amount_in * 10**18)

                # Wrap ETH to WETH
                wrap_tx = await weth_contract.functions.deposit().build_transaction(
                    {
                        "from": self._wallet._account.address,
                        "value": amount_in_wei,
                        "nonce": await self._wallet._web3.eth.get_transaction_count(
                            self._wallet._account.address
                        ),
                    }
                )

                signed_wrap_tx = self._wallet._web3.eth.account.sign_transaction(
                    wrap_tx, self._wallet._account.key
                )
                wrap_tx_hash = await self._wallet._web3.eth.send_raw_transaction(
                    signed_wrap_tx.raw_transaction
                )
                await self._wallet._web3.eth.wait_for_transaction_receipt(wrap_tx_hash)

                # Update token_in_address to WETH for the swap
                token_in_address = weth_address

            # Convert addresses to checksum format
            token_in_address = self._wallet._web3.to_checksum_address(token_in_address)
            token_out_address = self._wallet._web3.to_checksum_address(
                token_out_address
            )

            # Validate addresses
            if not self._wallet._web3.is_address(token_in_address):
                raise ValueError(f"Invalid token_in_address: {token_in_address}")
            if not self._wallet._web3.is_address(token_out_address):
                raise ValueError(f"Invalid token_out_address: {token_out_address}")

            # Convert amount_in to Wei for ERC20
            token_in_contract = common_contracts.get_contract("erc20", token_in_address)
            decimals = await token_in_contract.functions.decimals().call()
            amount_in_wei = int(amount_in * 10**decimals)

            # Get Permit2 contract
            permit2 = uniswap_contracts.get_contract("permit2")

            # Check and update Permit2 allowance if needed
            current_permit2_allowance = await token_in_contract.functions.allowance(
                self._wallet._account.address, permit2.address
            ).call()

            if current_permit2_allowance < amount_in_wei:
                approve_tx = await token_in_contract.functions.approve(
                    permit2.address, 2**256 - 1  # max approval for Permit2
                ).build_transaction(
                    {
                        "from": self._wallet._account.address,
                        "nonce": await self._wallet._web3.eth.get_transaction_count(
                            self._wallet._account.address
                        ),
                    }
                )

                signed_approve_tx = self._wallet._web3.eth.account.sign_transaction(
                    approve_tx, self._wallet._account.key
                )
                approve_tx_hash = await self._wallet._web3.eth.send_raw_transaction(
                    signed_approve_tx.raw_transaction
                )
                await self._wallet._web3.eth.wait_for_transaction_receipt(
                    approve_tx_hash
                )

            # Load Universal Router contract instead of SwapRouter
            universal_router = uniswap_contracts.get_contract("universal_router")

            # Calculate min_amount_out
            expected_out = await self._get_quote(
                token_in_address, token_out_address, amount_in_wei
            )
            gas_estimate = expected_out[3]
            min_amount_out_wei = int(expected_out[0] * (1 - slippage_percentage / 100))

            # Get the optimal fee tier
            fee = await self._get_pool_fee(token_in_address, token_out_address)

            # Encode the path (token_in -> fee -> token_out)
            path = (
                token_in_address.replace("0x", "")  # Remove 0x prefix
                + fee.to_bytes(3, "big").hex()  # 3 bytes for fee
                + token_out_address.replace("0x", "")  # Remove 0x prefix
            )
            encoded_path = bytes.fromhex(path)

            # Build commands and inputs
            commands = bytes([0x00])  # V3_SWAP_EXACT_IN command

            # Always set permit flag to True as funds come from msg.sender
            v3_swap_exact_in_params = encode(
                ["address", "uint256", "uint256", "bytes", "bool"],
                [
                    self._wallet._account.address,  # recipient
                    amount_in_wei,
                    min_amount_out_wei,
                    encoded_path,
                    True,  # permit flag - funds come from msg.sender through Permit2
                ],
            )

            inputs = [v3_swap_exact_in_params]

            # Build transaction
            swap_tx = await universal_router.functions.execute(
                commands, inputs
            ).build_transaction(
                {
                    "from": self._wallet._account.address,
                    "gas": gas_estimate,
                    "nonce": await self._wallet._web3.eth.get_transaction_count(
                        self._wallet._account.address
                    ),
                }
            )

            # Sign and send transaction
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
                "amount_in": amount_in,
            }

        except ValueError as e:
            raise ValueError(f"Swap failed: {str(e)}")
        except Exception as e:
            raise Exception(f"Unexpected error during swap: {str(e)}")
