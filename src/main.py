import asyncio
import argparse
import tracemalloc
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.websockets import WebSocketState
from agent.core.runtime import Runtime
from agent.core.streams.websocket_stream import WebSocketStream
from agent.core.streams.console_stream import ConsoleStream
from agent.core.agent_interface.interface import clear_screen
from wallet.wallet import ZWallet
from wallet.adapters.lifi import LiFiAdapter
from core.websocket.connection_manager import ConnectionManager


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Agent runtime configuration")
    parser.add_argument(
        "--debug", action="store_true", default=False, help="Enable debug mode"
    )
    parser.add_argument(
        "--web", action="store_true", default=False, help="Run as web server"
    )
    parser.add_argument(
        "--port", type=int, default=8000, help="Port for web server mode"
    )
    return parser.parse_args()


def initialize_wallet(debug: bool = False) -> ZWallet:
    """Initialize the wallet with adapters"""
    wallet = ZWallet()
    wallet.add_adapter(LiFiAdapter(wallet))
    return wallet


app = FastAPI()

# Initialize connection manager
connection_manager = ConnectionManager()


@app.websocket("/chat")
async def websocket_endpoint(websocket: WebSocket):
    # Start memory tracking
    tracemalloc.start()
    snapshot_start = tracemalloc.take_snapshot()

    # Try to establish connection
    if not await connection_manager.connect(websocket):
        return

    # Initialize components
    wallet = initialize_wallet()
    stream = WebSocketStream(websocket)
    runtime = Runtime(wallet=wallet, message_stream=stream, debug=app.state.debug)

    try:
        while True:
            message = await stream.receive_message()
            await runtime.process_message(message)

            # Take memory snapshot and log usage
            snapshot = tracemalloc.take_snapshot()
            top_stats = snapshot.compare_to(snapshot_start, "lineno")
            print(f"Memory usage: {top_stats[0].size / 1024 / 1024:.2f} MB")

    except WebSocketDisconnect:
        print("Client disconnected")
    except Exception as e:
        try:
            await stream.send_message(f"Error: {str(e)}")
        except:
            pass
    finally:
        connection_manager.disconnect(websocket)
        if websocket.client_state != WebSocketState.DISCONNECTED:
            await websocket.close()
        tracemalloc.stop()


async def chat_loop(runtime: Runtime, stream: ConsoleStream) -> None:
    """Run the chat loop for console interaction"""
    while True:
        try:
            message = await stream.receive_message()
            await runtime.process_message(message)
        except (KeyboardInterrupt, EOFError):
            break
        except Exception as e:
            await stream.send_message(f"Error: {str(e)}")


def main() -> None:
    args = parse_args()

    if args.web:
        import uvicorn

        app.state.debug = args.debug
        uvicorn.run(app, host="0.0.0.0", port=args.port)
    else:
        wallet = initialize_wallet(args.debug)
        stream = ConsoleStream()
        runtime = Runtime(wallet=wallet, message_stream=stream, debug=args.debug)

        clear_screen()
        asyncio.run(chat_loop(runtime, stream))


if __name__ == "__main__":
    main()
