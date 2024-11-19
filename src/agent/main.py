import asyncio
import argparse
from fastapi import FastAPI, WebSocket
from agent.core.runtime import Runtime
from agent.core.agent_interface.interface import clear_screen, chat_loop
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


def initialize_agent(debug: bool = False) -> Runtime:
    """Initialize the agent with configuration"""
    wallet = ZWallet()
    wallet.add_adapter(UniswapAdapter(wallet))

    runtime = Runtime(wallet, debug)
    return runtime


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
    agent = initialize_agent(debug=False)

    try:
        while True:
            message = await websocket.receive_text()
            response = await agent.process_message(message)
            await websocket.send_text(response)
    except Exception as e:
        await websocket.send_text(f"Error: {str(e)}")
    finally:
        await websocket.close()


def main() -> None:
    args = parse_args()

    if args.web:
        import uvicorn

        uvicorn.run(app, host="0.0.0.0", port=args.port)
    else:
        agent = initialize_agent(args.debug)
        clear_screen()
        asyncio.run(chat_loop(agent))


if __name__ == "__main__":
    main()
