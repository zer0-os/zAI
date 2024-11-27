from typing import Optional, Dict
from decimal import Decimal

from agent.core.base_agent import BaseAgent
from agent.core.memory.message_manager import MessageManager
from agent.core.providers.open_ai import OpenAIProvider
from agent.core.decorators.tool import agent_tool
from wallet.wallet import ZWallet
from agent.core.decorators.agent import agent


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
        debug: bool = False,
    ) -> None:
        """Initialize the wallet agent

        Args:
            wallet: Wallet instance for blockchain interactions
            model_provider: Provider for model interactions
            message_manager: Manager for conversation history
            debug: Enable debug logging if True
        """
        model_provider = OpenAIProvider(debug_log=debug)
        super().__init__(
            wallet=wallet,
            model_provider=model_provider,
            message_manager=message_manager,
            debug=debug,
        )

    def get_system_prompt(self) -> str | None:
        return "You are a wallet agent that can perform operations on a wallet."

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
            str: The transaction hash
        """
        return await self._wallet.transfer(
            token_address=token_address, to_address=to_address, amount=amount
        )

    @agent_tool(
        descriptions={
            "token_in": "The address of the token to swap from",
            "token_out": "The address of the token to swap to",
            "amount_in": "The amount of input token to swap",
            "min_amount_out": "The minimum amount of output token to receive",
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
            token_in: The address of the token to swap from
            token_out: The address of the token to swap to
            amount_in: The amount of input token to swap
            min_amount_out: The minimum amount of output token to receive

        Returns:
            str: The transaction hash
        """
        pass
