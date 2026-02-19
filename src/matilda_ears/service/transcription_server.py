"""WebSocket transcription server entrypoint (runtime wiring)."""

from __future__ import annotations

import argparse
import asyncio
import os
import traceback
from typing import TYPE_CHECKING, Any, cast

import websockets
from aiohttp import ClientSession, web

from ..core.config import get_config, setup_logging
from .health import start_health_server, start_health_server_unix

if TYPE_CHECKING:
    from ..transcription.server.core import MatildaWebSocketServer

config = get_config()
logger = setup_logging(__name__, log_filename="transcription.txt")


async def start_server(server: MatildaWebSocketServer, host: str | None = None, port: int | None = None) -> None:
    """Start the WebSocket server and its health endpoint."""
    # Be defensive: older config objects sometimes treat host/port as optional.
    server_host: str | None = host if host is not None else (server.host or "0.0.0.0")
    server_port: int | None = port if port is not None else (server.port or 8769)

    from matilda_transport import ensure_pipe_supported, prepare_unix_socket, resolve_transport

    transport = resolve_transport("MATILDA_EARS_TRANSPORT", "MATILDA_EARS_ENDPOINT", server_host, server_port)

    await server.load_model()

    if transport.transport == "unix":
        health_socket = os.getenv("MATILDA_EARS_HEALTH_ENDPOINT", "/tmp/matilda/ears-health.sock")
        try:
            server._health_runner = await start_health_server_unix(server, health_socket)
        except Exception as e:
            logger.warning("Health server disabled: %s", e)
    elif transport.transport == "pipe":
        health_socket = os.getenv("MATILDA_EARS_HEALTH_ENDPOINT", r"\\.\pipe\matilda-ears-health")
        try:
            app = web.Application()

            async def _health(_: web.Request) -> web.Response:
                return web.json_response({"status": "healthy", "service": "ears"})

            app.router.add_get("/health", _health)
            runner = web.AppRunner(app)
            await runner.setup()
            site = web.NamedPipeSite(runner, health_socket)
            await site.start()
            server._health_runner = runner
        except Exception as e:
            logger.warning("Health server disabled: %s", e)
    elif server_port is not None and server_host is not None:
        health_port = server_port + 1
        try:
            server._health_runner = await start_health_server(server, server_host, health_port)
        except Exception as e:
            logger.warning("Failed to start health server on port %s: %s", health_port, e)
            try:
                health_port = server_port + 100
                server._health_runner = await start_health_server(server, server_host, health_port)
            except Exception as e2:
                logger.warning("Health server disabled: %s", e2)

    protocol = "wss" if server.ssl_enabled else "ws"

    max_message_mb = config.get("server.websocket.max_message_mb", 10)
    try:
        max_message_mb = float(max_message_mb)
    except (TypeError, ValueError):
        max_message_mb = 10

    max_size = None if max_message_mb <= 0 else int(max_message_mb * 1024 * 1024)
    server_kwargs: dict[str, Any] = {
        "ping_interval": 60,
        "ping_timeout": 120,
        "max_size": max_size,
    }

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

                    async def to_upstream() -> None:
                        async for msg in ws:
                            if msg.type == web.WSMsgType.TEXT:
                                await upstream.send_str(msg.data)
                            elif msg.type == web.WSMsgType.BINARY:
                                await upstream.send_bytes(msg.data)
                            elif msg.type == web.WSMsgType.CLOSE:
                                await upstream.close()

                    async def to_client() -> None:
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

    async with websockets.serve(server.handle_client, server_host, server_port, **cast("Any", server_kwargs)):
        logger.info("✓ Ears ready (%s) on %s://%s:%s", server.backend_name, protocol, server_host, server_port)
        await asyncio.Future()


def main() -> None:
    parser = argparse.ArgumentParser(description="Matilda Ears WebSocket Server")
    parser.add_argument("--port", type=int, default=None, help="Port to bind to (default: from config)")
    parser.add_argument("--host", type=str, default=None, help="Host to bind to (default: 0.0.0.0)")
    parser.add_argument("--model", type=str, default=None, help="Whisper model to use")
    parser.add_argument("--device", type=str, default=None, help="Device for inference (cuda, cpu, mlx)")
    args = parser.parse_args()

    from ..transcription.server.core import MatildaWebSocketServer

    server = MatildaWebSocketServer()

    if args.port is not None:
        server.port = args.port
    if args.host is not None:
        server.host = args.host

    try:
        asyncio.run(start_server(server, host=args.host, port=args.port))
    except KeyboardInterrupt:
        logger.info("Server shutdown requested")
    except Exception as e:
        logger.exception("Server error: %s", e)
        logger.exception(traceback.format_exc())
        raise RuntimeError("WebSocket server failed") from e


if __name__ == "__main__":
    main()
