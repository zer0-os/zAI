import asyncio
import argparse
import tracemalloc
from typing import Optional
from google.oauth2 import id_token
from google.auth.transport import requests
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Request
from fastapi.websockets import WebSocketState
from agent.agents.conversational_agent import ConversationalAgent
from agent.agents.intro_agent import IntroAgent
from agent.agents.routing_agent import RoutingAgent
from agent.agents.wallet_agent import WalletAgent
from agent.core.memory.message_manager import MessageManager
from agent.core.runtime import Runtime
from agent.core.streams.websocket_stream import WebSocketStream
from agent.core.streams.console_stream import ConsoleStream
from agent.core.agent_interface.interface import clear_screen
from agent.types.agent_info import AgentInfo
from core.models.webhook_events import WebhookEvent
from wallet.wallet import ZWallet
from wallet.adapters.lifi import LiFiAdapter
from core.websocket.connection_manager import ConnectionManager
import os
from dotenv import load_dotenv
import aiohttp
from db.agent_repository import AgentRepository
from db.connection import DatabaseConnection
from contextlib import asynccontextmanager
from utils.privy_auth import PrivyAuthorizationSigner
from typing import Dict, Any

# Load environment variables
load_dotenv(override=True)

API_URL = os.getenv("ZOS_USER_API_URL")


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


def initialize_wallet(agent_data: AgentInfo) -> ZWallet:
    """Initialize the wallet with adapters"""
    wallet = ZWallet(agent_data=agent_data)
    wallet.add_adapter(LiFiAdapter(wallet))
    return wallet


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage database connection lifecycle."""
    app.state.db_connection = DatabaseConnection()
    yield
    if hasattr(app.state, "db_connection"):
        app.state.db_connection.close()


app = FastAPI(lifespan=lifespan)

# Initialize connection manager
connection_manager = ConnectionManager()

# Initialize Privy signer
privy_signer = PrivyAuthorizationSigner()


async def verify_access_token(token: str) -> Optional[dict]:
    """
    Verify the access token by checking against the users/current endpoint.

    Args:
        token: The access token

    Returns:
        dict: User information if token is valid
        None: If token is invalid
    """
    try:
        headers = {"Authorization": f"Bearer {token}"}

        async with aiohttp.ClientSession() as session:
            async with session.get(API_URL, headers=headers) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    print(f"Token verification failed with status: {response.status}")
                    return None

    except Exception as e:
        print(f"Token verification failed: {str(e)}")
        return None


@app.websocket("/chat")
async def websocket_endpoint(websocket: WebSocket):
    # Get token from URL query parameters
    token = websocket.query_params.get("access_token")
    if not token:
        await websocket.close(code=4001, reason="Missing access token")
        return

    user_info = await verify_access_token(token)
    if not user_info:
        await websocket.close(code=4001, reason="Invalid authentication token")
        return

    agent_id = websocket.query_params.get("agent_id")
    if not agent_id:
        await websocket.close(code=4002, reason="Missing agent_id")
        return

    agent_repo = AgentRepository(app.state.db_connection)
    agent_data = agent_repo.fetch_agent(agent_id)

    if not agent_data or agent_data.user_id != user_info.get("id"):
        await websocket.close(code=4003, reason="Invalid agent access")
        return

    # Try to establish connection with agent data as metadata
    if not await connection_manager.connect(websocket, metadata=agent_data):
        return

    # Start memory tracking
    tracemalloc.start()
    snapshot_start = tracemalloc.take_snapshot()

    # Add user info to the websocket state
    websocket.state.user = user_info

    # Initialize components
    wallet = initialize_wallet(agent_data)
    stream = WebSocketStream(websocket)
    message_manager = MessageManager()

    # Initialize all agents with agent data
    wallet_agent = WalletAgent(
        wallet=wallet,
        message_manager=message_manager,
        message_stream=stream,
        debug=app.state.debug,
        agent_data=agent_data,
    )
    conversational_agent = ConversationalAgent(
        agent_name=agent_data.name,
        message_manager=message_manager,
        message_stream=stream,
        debug=app.state.debug,
    )
    agents = [wallet_agent, conversational_agent]

    routing_agent = RoutingAgent(
        agents=agents,
        message_manager=message_manager,
        message_stream=stream,
        debug=app.state.debug,
    )

    runtime = Runtime(
        wallet=wallet,
        message_stream=stream,
        entry_agent=routing_agent,
        agents=agents,
        message_manager=message_manager,
        debug=app.state.debug,
    )

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
        if websocket.client_state != WebSocketState.DISCONNECTED:
            try:
                await stream.send_message(f"Error: {str(e)}")
            except:
                pass
    finally:
        connection_manager.disconnect(websocket)
        # Only attempt to close if the connection is still open
        try:
            if websocket.client_state != WebSocketState.DISCONNECTED:
                await websocket.close()
        except:
            pass
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


@app.post("/webhook/wallet-events")
async def wallet_events_webhook(event: WebhookEvent):
    """Handle webhook events from Privy for wallet transactions"""
    try:
        type = "funds_received" if event.amount_received else "funds_sent"
        message = {"type": type, "data": event.model_dump()}

        # Broadcast to connections where the agent's wallet_id matches the event
        await connection_manager.broadcast_filtered(
            message,
            predicate=lambda metadata: (
                metadata is not None
                and hasattr(metadata, "wallet_id")
                and metadata.wallet_id == event.wallet_id
            ),
        )

        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/wallet/sign")
async def sign_wallet_payload(request: Request) -> Dict[str, str]:
    """
    Sign a wallet payload using Privy authorization.

    Args:
        request: FastAPI request containing the payload to sign

    Returns:
        Dict containing the signature
    """
    try:
        payload = await request.json()
        signature = privy_signer.get_auth_signature(payload)
        return {"signature": signature}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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
