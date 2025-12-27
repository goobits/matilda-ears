"""Main entry point and server startup for WebSocket server.

This module provides:
- start_server: Async method to start the WebSocket server
- main: Main entry point function
"""

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
    logger.info(f"Starting WebSocket server on {protocol}://{server_host}:{server_port}")
    logger.info(f"Your Ubuntu IP: {server_host} (Mac clients should connect to this IP)")
    logger.info("Authentication: JWT required")
    logger.info(f"Backend: {server.backend_name}")
    if server.backend_name == "faster_whisper":
        logger.info(
            f"Model: {config.whisper_model}, Device: {config.whisper_device_auto}, Compute: {config.whisper_compute_type_auto}"
        )
    elif server.backend_name == "parakeet":
        logger.info(f"Model: {config.get('parakeet.model', 'default')}")

    if server.ssl_enabled:
        logger.info(f"SSL enabled - cert: {config.ssl_cert_file}, verify: {config.ssl_verify_mode}")

    # Start WebSocket server with SSL support
    server_kwargs = {
        "ping_interval": 30,  # Send ping every 30 seconds
        "ping_timeout": 10,  # Wait 10 seconds for pong
        "max_size": 10 * 1024 * 1024,  # 10MB limit for large audio files
    }

    # Add SSL context if enabled
    if server.ssl_enabled and server.ssl_context:
        server_kwargs["ssl"] = server.ssl_context

    async with websockets.serve(server.handle_client, server_host, server_port, **server_kwargs):
        logger.info("WebSocket Matilda Server is ready for connections!")
        logger.info(f"Protocol: {protocol.upper()}")
        logger.info(f"Active clients: {len(server.connected_clients)}")

        # Keep server running
        await asyncio.Future()


def main() -> None:
    """Main function to start the server."""
    from .core import MatildaWebSocketServer

    server = MatildaWebSocketServer()

    try:
        asyncio.run(server.start_server())
    except KeyboardInterrupt:
        logger.info("Server shutdown requested")
    except Exception as e:
        logger.exception(f"Server error: {e}")
        logger.exception(traceback.format_exc())
        sys.exit(1)
