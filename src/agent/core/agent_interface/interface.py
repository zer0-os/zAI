import os
import asyncio
from agent.core.runtime import Runtime
from halo import Halo


def clear_screen() -> None:
    """Clear the terminal screen"""
    os.system("cls" if os.name == "nt" else "clear")


def display_chat_header(address: str) -> None:
    """Display the chat interface header"""
    print("\n=== AI Agent Chat Interface ===")
    print(f"Wallet Address: {address}")
    print("Type 'exit' or 'quit' to end the conversation")
    print("================================\n")


async def chat_loop(runtime: Runtime) -> None:
    """Run the main chat interaction loop

    Args:
        runtime: The initialized agent runtime
    """
    wallet_address = runtime._wallet._account.address
    display_chat_header(wallet_address)

    # Initialize spinner
    spinner = Halo(text="Agent is thinking...", spinner="dots")

    while True:
        try:
            user_input = input("\nYou: ").strip()

            if user_input.lower() in ["exit", "quit"]:
                print("\nGoodbye! 👋")
                break

            if user_input.lower() == "clear":
                clear_screen()
                display_chat_header(wallet_address)
                continue

            if user_input:
                spinner.start()
                response = await runtime.process_message(user_input)
                spinner.stop()
                print(f"\nAgent: {response}")

        except KeyboardInterrupt:
            spinner.stop()
            print("\nGoodbye! 👋")
            break
