import json
import os
import shortuuid
from typing import Optional, Dict
from decimal import Decimal

from agent.core.base_agent import BaseAgent
from agent.core.memory.message_manager import MessageManager
from agent.core.providers.open_ai import OpenAIProvider
from agent.core.decorators.tool import agent_tool
from agent.types.agent_info import AgentInfo
from wallet.wallet import ZWallet
from agent.core.decorators.agent import agent
from agent.core.interfaces.message_stream import MessageStream


@agent
class WalletAgent(BaseAgent):
    """
    Agent responsible for wallet operations including balance checking,
    transfers, and token swaps.
    """

    @property
    def name(self) -> str:
        return "WalletAgent"

    def __init__(
        self,
        wallet: ZWallet,
        message_manager: MessageManager,
        message_stream: MessageStream,
        agent_data: AgentInfo,
        debug: bool = False,
    ) -> None:
        """Initialize the wallet agent

        Args:
            wallet: Wallet instance for blockchain interactions
            message_manager: Manager for conversation history
            message_stream: Stream for sending/receiving messages
            debug: Enable debug logging if True
        """
        self._wallet = wallet
        self._agent_data = agent_data
        model_provider = OpenAIProvider(debug=debug)
        super().__init__(
            model_provider=model_provider,
            message_manager=message_manager,
            message_stream=message_stream,
            debug=debug,
        )

    def get_system_prompt(self) -> str | None:
        return """You are a wallet agent that can perform operations on a wallet.
        You must use the tools provided when responding."""

    async def transfer_to(self) -> "BaseAgent":
        """Transfer control to the wallet agent for handling wallet operations

        keywords: swap, balance, transfer, wallet
        examples: ["swap 0.1 ETH to USDC", "check my balance", "transfer 100 USD to 0x..."]
        """
        return self

    @agent_tool()
    async def get_balances(self) -> Dict[str, any]:
        """
        Get the balance of all tokens in the wallet.
        """
        return await self._wallet.get_balances()

    @agent_tool(
        descriptions={
            "token_address": "The address of the token to transfer",
            "to_address": "The recipient's address",
            "amount": "The amount to transfer",
        }
    )
    async def transfer(
        self, token_address: str, to_address: str, amount: Decimal
    ) -> str:
        """
        Transfer tokens to a specified address.

        Args:
            token_address: The address of the token to transfer
            to_address: The recipient's address
            amount: The amount to transfer

        Returns:
            str: The final transaction status as JSON
        """
        # Get initial pending status
        status = await self._wallet.transfer(
            to_address=to_address, amount=amount, token_address=token_address
        )

        # Send pending status
        await self._message_stream.send_message(
            json.dumps(
                {
                    "type": "transaction",
                    "id": shortuuid.uuid(name="pending"),
                    "message": status.get("message"),
                    "txHash": status.get("transaction_hash") or "",
                    "status": status.get("status"),
                }
            )
        )

        # Wait for receipt and get final status
        receipt = await self._wallet._web3.eth.wait_for_transaction_receipt(
            status["transaction_hash"], poll_latency=0.5
        )

        final_status = {
            "status": "success" if receipt["status"] == 1 else "failed",
            "message": (
                "Transaction confirmed"
                if receipt["status"] == 1
                else "Transaction failed"
            ),
            "transaction_hash": receipt["transactionHash"].hex(),
        }

        # Send final status
        await self._message_stream.send_message(
            json.dumps(
                {
                    "type": "transaction",
                    "id": shortuuid.uuid(name="final"),
                    "message": final_status.get("message"),
                    "txHash": final_status.get("transaction_hash") or "",
                    "status": final_status.get("status"),
                }
            )
        )

        return json.dumps(final_status)

    @agent_tool(
        descriptions={
            "token_in": "The address or symbol of the token to swap from",
            "token_out": "The address or symbol of the token to swap to",
            "amount_in": "The amount of input token to swap",
        }
    )
    async def swap(
        self,
        token_in: str,
        token_out: str,
        amount_in: Decimal,
        min_amount_out: Optional[Decimal] = None,
    ) -> str:
        """
        Swap one token for another using the wallet's swap functionality.

        Args:
            token_in: The address or symbol of the token to swap from
            token_out: The address or symbol of the token to swap to
            amount_in: The amount of input token to swap
            min_amount_out: The minimum amount of output token to receive

        Returns:
            str: The transaction hash
        """
        # Get the LiFi adapter
        lifi_adapter = self._wallet.get_adapter("lifi")

        # Get chain ID from wallet
        chain_id = self._wallet._chain_id

        # Get token information
        token_in_info = lifi_adapter.get_token_info(chain_id, token_in)
        token_out_info = lifi_adapter.get_token_info(chain_id, token_out)

        # Get quote for the swap
        quote = lifi_adapter.get_quote(
            chain_id=chain_id,
            token_in=token_in_info,
            token_out=token_out_info,
            amount_in=amount_in,
        )

        # Broadcast quote message
        quote_message_id = shortuuid.uuid()
        await self._message_stream.send_message(
            json.dumps(
                {
                    "type": "swap_quote",
                    "id": quote_message_id,
                    "quote": {
                        "fromToken": token_in_info,
                        "toToken": token_out_info,
                        "estimate": {
                            "fromAmount": quote["estimate"]["fromAmount"],
                            "toAmount": quote["estimate"]["toAmount"],
                            "fromAmountUSD": quote["estimate"]["fromAmountUSD"],
                            "toAmountUSD": quote["estimate"]["toAmountUSD"],
                        },
                    },
                }
            )
        )

        # If min_amount_out is specified, validate the quote
        if min_amount_out is not None:
            estimated_out = Decimal(quote["estimate"]["toAmount"]) / Decimal(
                10**token_out_info.decimals
            )
            if estimated_out < min_amount_out:
                raise ValueError(
                    f"Estimated output {estimated_out} is less than minimum required {min_amount_out}"
                )

        # Execute the swap
        swap_message_id = shortuuid.uuid()
        async for status in lifi_adapter.swap(quote):
            await self._message_stream.send_message(
                json.dumps(
                    {
                        "type": "swap_status",
                        "id": swap_message_id,
                        "message": status.get("message"),
                        "txHash": status.get("transaction_hash") or "",
                        "status": status.get("status"),
                    }
                )
            )

        return json.dumps(status)
