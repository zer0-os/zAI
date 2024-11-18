import asyncio
import argparse
from agent.core.runtime import Runtime
from agent.core.agent_interface.interface import clear_screen, chat_loop
from wallet.wallet import ZWallet
from wallet.adapters.uniswap import UniswapAdapter


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Agent runtime configuration")
    parser.add_argument(
        "--debug", action="store_true", default=False, help="Enable debug mode"
    )
    return parser.parse_args()


def initialize_agent(debug: bool = False) -> Runtime:
    """Initialize the agent with configuration"""
    wallet = ZWallet()
    wallet.add_adapter(UniswapAdapter(wallet))

    runtime = Runtime(wallet, debug)
    return runtime


def main() -> None:
    args = parse_args()
    agent = initialize_agent(args.debug)
    clear_screen()
    asyncio.run(chat_loop(agent))


if __name__ == "__main__":
    main()
