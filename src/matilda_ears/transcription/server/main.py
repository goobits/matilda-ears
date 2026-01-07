"""Main entry point and server startup for WebSocket server.

This module provides:
- start_server: Async method to start the WebSocket server
- main: Main entry point function
"""

import argparse
import asyncio
import sys
import traceback
from typing import TYPE_CHECKING, Optional

import websockets

from ...core.config import get_config, setup_logging
from .health import start_health_server

if TYPE_CHECKING:
    from .core import MatildaWebSocketServer

config = get_config()
logger = setup_logging(__name__, log_filename="transcription.txt")


async def start_server(
    server: "MatildaWebSocketServer",
    host: Optional[str] = None,
    port: Optional[int] = None,
) -> None:
    """Start the WebSocket server.

    Args:
        server: The MatildaWebSocketServer instance
        host: Host to bind to (optional, uses server default)
        port: Port to bind to (optional, uses server default)

    """
    # Use provided host/port or defaults
    server_host = host or server.host
    server_port = port or server.port

    # Load model first
    await server.load_model()

    # Start HTTP health server on port+1 (e.g., 8769 -> 8770 for health)
    # Actually, let's use the same port concept but offset by 100 to avoid conflicts
    # The Rust manager expects health on the same port, so use websocket_port for health too
    # We'll run health server on a separate port (websocket_port - 4) to avoid conflict
    health_port = server_port  # Health on same port - but we need different approach
    # Actually aiohttp and websockets can't share a port easily.
    # Let's use the standard health port pattern: websocket+1000 or a fixed offset
    health_port = server_port + 1  # e.g., 8769 -> 8770 for health
    try:
        server._health_runner = await start_health_server(server, server_host, health_port)
    except Exception as e:
        logger.warning(f"Failed to start health server on port {health_port}: {e}")
        # Try alternative port
        try:
            health_port = server_port + 100
            server._health_runner = await start_health_server(server, server_host, health_port)
        except Exception as e2:
            logger.warning(f"Health server disabled: {e2}")

    protocol = "wss" if server.ssl_enabled else "ws"
    logger.debug(f"Starting WebSocket server on {protocol}://{server_host}:{server_port}")
    logger.debug(f"Backend: {server.backend_name}")
    if server.backend_name == "faster_whisper":
        logger.debug(
            f"Model: {config.whisper_model}, Device: {config.whisper_device_auto}"
        )
    elif server.backend_name == "parakeet":
        logger.debug(f"Model: {config.get('parakeet.model', 'default')}")

    # Start WebSocket server with SSL support
    max_message_mb = config.get("server.websocket.max_message_mb", 10)
    try:
        max_message_mb = float(max_message_mb)
    except (TypeError, ValueError):
        max_message_mb = 10

    max_size = None if max_message_mb <= 0 else int(max_message_mb * 1024 * 1024)
    server_kwargs = {
        "ping_interval": 30,  # Send ping every 30 seconds
        "ping_timeout": 10,  # Wait 10 seconds for pong
        "max_size": max_size,
    }

    # Add SSL context if enabled
    if server.ssl_enabled and server.ssl_context:
        server_kwargs["ssl"] = server.ssl_context

    async with websockets.serve(server.handle_client, server_host, server_port, **server_kwargs):
        logger.info(f"✓ Ears ready ({server.backend_name}) on {protocol}://{server_host}:{server_port}")

        # Keep server running
        await asyncio.Future()


def main() -> None:
    """Main function to start the server.

    Supports command-line arguments for port and host configuration,
    allowing the Matilda manager to dynamically configure the server.
    """
    parser = argparse.ArgumentParser(description="Matilda Ears WebSocket Server")
    parser.add_argument("--port", type=int, default=None, help="Port to bind to (default: from config)")
    parser.add_argument("--host", type=str, default=None, help="Host to bind to (default: 0.0.0.0)")
    parser.add_argument("--model", type=str, default=None, help="Whisper model to use")
    parser.add_argument("--device", type=str, default=None, help="Device for inference (cuda, cpu, mlx)")
    args = parser.parse_args()

    from .core import MatildaWebSocketServer

    server = MatildaWebSocketServer()

    # Override port/host if provided via CLI
    if args.port is not None:
        server.port = args.port
    if args.host is not None:
        server.host = args.host

    try:
        asyncio.run(server.start_server())
    except KeyboardInterrupt:
        logger.info("Server shutdown requested")
    except Exception as e:
        logger.exception(f"Server error: {e}")
        logger.exception(traceback.format_exc())
        raise RuntimeError("WebSocket server failed") from e
