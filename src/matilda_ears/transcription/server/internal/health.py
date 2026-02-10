"""Health check server for WebSocket server.

This module provides HTTP health endpoints for service monitoring:
- health_handler: Health check endpoint handler
- start_health_server: Start the HTTP health server
"""

import os
import time
from typing import TYPE_CHECKING

from aiohttp import web

from ....core.config import setup_logging

if TYPE_CHECKING:
    from .core import MatildaWebSocketServer

logger = setup_logging(__name__, log_filename="transcription.txt")


async def health_handler(server: "MatildaWebSocketServer", request: web.Request) -> web.Response:
    """HTTP health check endpoint for service monitoring.

    Args:
        server: The MatildaWebSocketServer instance
        request: The HTTP request

    Returns:
        JSON response with health status

    """
    return web.json_response(
        {
            "status": "healthy",
            "service": "ears",
            "backend": server.backend_name,
            "model_loaded": server.backend.is_ready if server.backend else False,
            "connected_clients": len(server.connected_clients),
            "active_streaming_sessions": len(server.streaming_sessions),
            "active_pcm_sessions": len(server.pcm_sessions),
            "active_opus_sessions": len(server.opus_decoder.get_active_sessions()),
            "ending_sessions": len(server.ending_sessions),
            "timestamp": time.time(),
        }
    )


async def start_health_server(
    server: "MatildaWebSocketServer",
    host: str,
    port: int,
) -> web.AppRunner:
    """Start HTTP health check server.

    Args:
        server: The MatildaWebSocketServer instance
        host: Host to bind to
        port: Port to bind to

    Returns:
        The aiohttp AppRunner instance

    """
    app = web.Application()
    # Create a closure to pass server to handler
    app.router.add_get("/health", lambda req: health_handler(server, req))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host, port)
    await site.start()
    logger.info(f"HTTP health endpoint available at http://{host}:{port}/health")
    return runner


async def start_health_server_unix(server: "MatildaWebSocketServer", socket_path: str) -> web.AppRunner:
    app = web.Application()
    app.router.add_get("/health", lambda req: health_handler(server, req))
    runner = web.AppRunner(app)
    await runner.setup()
    socket_dir = os.path.dirname(socket_path)
    if socket_dir:
        os.makedirs(socket_dir, exist_ok=True)
    if os.path.exists(socket_path):
        os.unlink(socket_path)
    site = web.UnixSite(runner, socket_path)
    await site.start()
    logger.info("HTTP health endpoint available at unix://%s/health", socket_path)
    return runner
