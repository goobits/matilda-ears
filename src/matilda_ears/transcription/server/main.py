"""Main entry point and server startup for WebSocket server.

This module provides:
- start_server: Async method to start the WebSocket server
- main: Main entry point function
"""

import argparse
import asyncio
import traceback
from typing import TYPE_CHECKING

import websockets
import os

from ...core.config import get_config, setup_logging
from .internal.health import start_health_server, start_health_server_unix
from matilda_transport import ensure_pipe_supported, prepare_unix_socket, resolve_transport
from aiohttp import web, ClientSession

if TYPE_CHECKING:
    from .core import MatildaWebSocketServer

config = get_config()
logger = setup_logging(__name__, log_filename="transcription.txt")


async def start_server(
    server: "MatildaWebSocketServer",
    host: str | None = None,
    port: int | None = None,
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
    transport = resolve_transport("MATILDA_EARS_TRANSPORT", "MATILDA_EARS_ENDPOINT", server_host, server_port)

    # Load model first
    await server.load_model()

    if transport.transport == "unix":
        health_socket = os.getenv("MATILDA_EARS_HEALTH_ENDPOINT", "/tmp/matilda/ears-health.sock")
        try:
            server._health_runner = await start_health_server_unix(server, health_socket)
        except Exception as e:
            logger.warning(f"Health server disabled: {e}")
    elif transport.transport == "pipe":
        health_socket = os.getenv("MATILDA_EARS_HEALTH_ENDPOINT", r"\\.\pipe\matilda-ears-health")
        try:
            app = web.Application()
            app.router.add_get("/health", lambda req: web.json_response({"status": "healthy", "service": "ears"}))
            runner = web.AppRunner(app)
            await runner.setup()
            site = web.NamedPipeSite(runner, health_socket)
            await site.start()
            server._health_runner = runner
        except Exception as e:
            logger.warning(f"Health server disabled: {e}")
    elif server_port is not None and server_host is not None:
        health_port = server_port + 1
        try:
            server._health_runner = await start_health_server(server, server_host, health_port)
        except Exception as e:
            logger.warning(f"Failed to start health server on port {health_port}: {e}")
            try:
                health_port = server_port + 100
                server._health_runner = await start_health_server(server, server_host, health_port)
            except Exception as e2:
                logger.warning(f"Health server disabled: {e2}")

    protocol = "wss" if server.ssl_enabled else "ws"
    logger.debug(f"Starting WebSocket server on {protocol}://{server_host}:{server_port}")
    logger.debug(f"Backend: {server.backend_name}")
    if server.backend_name == "faster_whisper":
        logger.debug(f"Model: {config.whisper_model}, Device: {config.whisper_device_auto}")
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
        "ping_interval": 60,  # Send ping every 60 seconds
        "ping_timeout": 120,  # Wait 120 seconds for pong (transcription can block event loop)
        "max_size": max_size,
    }

    # Add SSL context if enabled
    if server.ssl_enabled and server.ssl_context:
        server_kwargs["ssl"] = server.ssl_context

    if transport.transport == "unix" and transport.endpoint:
        prepare_unix_socket(transport.endpoint)
        server_kwargs["unix"] = True
        server_kwargs["path"] = transport.endpoint
        server_host = None
        server_port = None
    elif transport.transport == "pipe":
        ensure_pipe_supported(transport)

        async def proxy_handler(request: web.Request) -> web.WebSocketResponse:
            ws = web.WebSocketResponse()
            await ws.prepare(request)
            target_url = f"ws://{server_host}:{server_port}"
            async with ClientSession() as session:
                async with session.ws_connect(target_url) as upstream:
                    async def to_upstream():
                        async for msg in ws:
                            if msg.type == web.WSMsgType.TEXT:
                                await upstream.send_str(msg.data)
                            elif msg.type == web.WSMsgType.BINARY:
                                await upstream.send_bytes(msg.data)
                            elif msg.type == web.WSMsgType.CLOSE:
                                await upstream.close()

                    async def to_client():
                        async for msg in upstream:
                            if msg.type == web.WSMsgType.TEXT:
                                await ws.send_str(msg.data)
                            elif msg.type == web.WSMsgType.BINARY:
                                await ws.send_bytes(msg.data)
                            elif msg.type == web.WSMsgType.CLOSE:
                                await ws.close()

                    await asyncio.gather(to_upstream(), to_client())
            return ws

        pipe_app = web.Application()
        pipe_app.router.add_get("/v1/ears/socket", proxy_handler)
        runner = web.AppRunner(pipe_app)
        await runner.setup()
        site = web.NamedPipeSite(runner, transport.endpoint)
        await site.start()

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


if __name__ == "__main__":
    main()
