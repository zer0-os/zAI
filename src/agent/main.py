import asyncio
import argparse
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from agent.core.runtime import Runtime
from agent.core.streams.websocket_stream import WebSocketStream
from agent.core.streams.console_stream import ConsoleStream
from agent.core.agent_interface.interface import clear_screen
from wallet.wallet import ZWallet
from wallet.adapters.uniswap import UniswapAdapter
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os


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
    wallet.add_adapter(UniswapAdapter(wallet))
    return wallet


app = FastAPI()

# Get the directory containing main.py
current_dir = os.path.dirname(os.path.abspath(__file__))
static_dir = os.path.join(current_dir, "static")

# Mount the static directory
app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/")
async def get():
    """Serve the index.html file"""
    return FileResponse(os.path.join(static_dir, "index.html"))


@app.websocket("/chat")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()

    # Initialize components
    wallet = initialize_wallet()
    stream = WebSocketStream(websocket)
    runtime = Runtime(wallet=wallet, message_stream=stream, debug=app.state.debug)

    try:
        while True:
            message = await stream.receive_message()
            await runtime.process_message(message)
    except WebSocketDisconnect:
        print("Client disconnected")
    except Exception as e:
        try:
            await stream.send_message(f"Error: {str(e)}")
        except:
            pass
    finally:
        await websocket.close()


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
