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


async def _start_pipe_health(endpoint: str) -> web.AppRunner:
    app = web.Application()

    async def health(_: web.Request) -> web.Response:
        return web.json_response({"status": "healthy", "service": "ears"})

    app.router.add_get("/health", health)
    runner = web.AppRunner(app)
    await runner.setup()
    try:
        await web.NamedPipeSite(runner, endpoint).start()
    except Exception:
        await runner.cleanup()
        raise
    return runner


async def _start_pipe_proxy(endpoint: str, target_url: str) -> web.AppRunner:
    async def proxy_handler(request: web.Request) -> web.WebSocketResponse:
        websocket = web.WebSocketResponse()
        await websocket.prepare(request)
        async with ClientSession() as session:
            async with session.ws_connect(target_url) as upstream:

                async def to_upstream() -> None:
                    async for message in websocket:
                        if message.type == web.WSMsgType.TEXT:
                            await upstream.send_str(message.data)
                        elif message.type == web.WSMsgType.BINARY:
                            await upstream.send_bytes(message.data)
                        elif message.type == web.WSMsgType.CLOSE:
                            await upstream.close()

                async def to_client() -> None:
                    async for message in upstream:
                        if message.type == web.WSMsgType.TEXT:
                            await websocket.send_str(message.data)
                        elif message.type == web.WSMsgType.BINARY:
                            await websocket.send_bytes(message.data)
                        elif message.type == web.WSMsgType.CLOSE:
                            await websocket.close()

                await asyncio.gather(to_upstream(), to_client())
        return websocket

    app = web.Application()
    app.router.add_get("/v1/ears/socket", proxy_handler)
    runner = web.AppRunner(app)
    await runner.setup()
    try:
        await web.NamedPipeSite(runner, endpoint).start()
    except Exception:
        await runner.cleanup()
        raise
    return runner


async def _stop_runner(runner: web.AppRunner | None) -> None:
    if runner is None:
        return
    try:
        await runner.cleanup()
    except Exception as exc:
        logger.warning("Failed to stop service runner: %s", exc)


def _unlink_socket(path: str | None) -> None:
    if not path:
        return
    try:
        os.unlink(path)
    except FileNotFoundError:
        pass
    except OSError as exc:
        logger.warning("Failed to remove Unix socket %s: %s", path, exc)


async def start_server(server: MatildaWebSocketServer, host: str | None = None, port: int | None = None) -> None:
    """Start the WebSocket server and its health endpoint."""
    from matilda_transport import ensure_pipe_supported, prepare_unix_socket, resolve_transport

    server_host = host if host is not None else (server.host or "0.0.0.0")
    server_port = port if port is not None else (server.port or 8769)
    transport = resolve_transport("MATILDA_EARS_TRANSPORT", "MATILDA_EARS_ENDPOINT", server_host, server_port)
    websocket_host: str | None = server_host
    websocket_port: int | None = server_port
    pipe_runner: web.AppRunner | None = None
    unix_socket: str | None = None
    health_unix_socket: str | None = None

    try:
        await server.load_model()

        if transport.transport == "unix":
            health_socket = os.getenv("MATILDA_EARS_HEALTH_ENDPOINT", "/tmp/matilda/ears-health.sock")
            try:
                server._health_runner = await start_health_server_unix(server, health_socket)
                health_unix_socket = health_socket
            except Exception as exc:
                logger.warning("Health server disabled: %s", exc)
        elif transport.transport == "pipe":
            health_socket = os.getenv("MATILDA_EARS_HEALTH_ENDPOINT", r"\\.\pipe\matilda-ears-health")
            try:
                server._health_runner = await _start_pipe_health(health_socket)
            except Exception as exc:
                logger.warning("Health server disabled: %s", exc)
        else:
            health_port = server_port + 1
            try:
                server._health_runner = await start_health_server(server, server_host, health_port)
            except Exception as exc:
                logger.error("Failed to start health server on expected port %s: %s", health_port, exc)
                raise RuntimeError(f"Health server failed on expected port {health_port}") from exc

        max_message_mb = config.get("server.websocket.max_message_mb", 10)
        try:
            max_message_mb = float(max_message_mb)
        except (TypeError, ValueError):
            max_message_mb = 10

        server_kwargs: dict[str, Any] = {
            "ping_interval": 60,
            "ping_timeout": 120,
            "max_size": None if max_message_mb <= 0 else int(max_message_mb * 1024 * 1024),
        }
        if server.ssl_enabled and server.ssl_context:
            server_kwargs["ssl"] = server.ssl_context

        if transport.transport == "unix" and transport.endpoint:
            prepare_unix_socket(transport.endpoint)
            unix_socket = transport.endpoint
            server_kwargs.update(unix=True, path=transport.endpoint)
            websocket_host = None
            websocket_port = None
        elif transport.transport == "pipe":
            ensure_pipe_supported(transport)
            pipe_runner = await _start_pipe_proxy(transport.endpoint, f"ws://{server_host}:{server_port}")

        protocol = "wss" if server.ssl_enabled else "ws"
        async with websockets.serve(
            server.handle_client,
            websocket_host,
            websocket_port,
            **cast("Any", server_kwargs),
        ):
            logger.info(
                "✓ Ears ready (%s) on %s://%s:%s",
                server.backend_name,
                protocol,
                websocket_host,
                websocket_port,
            )
            await asyncio.Future()
    finally:
        await _stop_runner(pipe_runner)
        await _stop_runner(server._health_runner)
        server._health_runner = None
        try:
            server.close()
        finally:
            _unlink_socket(unix_socket)
            _unlink_socket(health_unix_socket)


def main() -> None:
    parser = argparse.ArgumentParser(description="Matilda Ears WebSocket Server")
    parser.add_argument("--port", type=int, default=None, help="Port to bind to (default: from config)")
    parser.add_argument("--host", type=str, default=None, help="Host to bind to (default: 0.0.0.0)")
    parser.add_argument("--model", type=str, default=None, help="Whisper model to use")
    parser.add_argument("--device", type=str, default=None, help="Device for inference (cuda, cpu, mlx)")
    args = parser.parse_args()

    if args.model:
        os.environ["EARS_MODEL"] = args.model
    if args.device:
        os.environ["EARS_DEVICE"] = args.device

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
