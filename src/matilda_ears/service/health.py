"""Health check server for Matilda Ears services."""

from __future__ import annotations

import os
import time
from typing import TYPE_CHECKING

from aiohttp import web

from ..core.config import setup_logging
from ..core.memory import current_rss_bytes, macos_footprint_summary, peak_rss_bytes
from ..core.mlx_memory import mlx_memory_stats

if TYPE_CHECKING:
    from ..transcription.server.core import MatildaWebSocketServer

logger = setup_logging(__name__, log_filename="transcription.txt")


async def health_handler(server: MatildaWebSocketServer, request: web.Request) -> web.Response:
    memory = {
        "rss_bytes": current_rss_bytes(),
        "peak_rss_bytes": peak_rss_bytes(),
        "pcm_buffer_bytes": server.sessions.pcm_buffer_bytes,
        "opus_pcm_buffer_bytes": server.sessions.opus_buffer_bytes,
        "wake_word_buffer_bytes": server.sessions.wake_word_buffer_bytes,
        "mlx": mlx_memory_stats(),
    }
    if request is not None and request.query.get("footprint", "").strip().lower() in {"1", "true", "yes", "on"}:
        memory.update(macos_footprint_summary())

    return web.json_response(
        {
            "status": "healthy",
            "service": "ears",
            "backend": server.backend_name,
            "model_loaded": server.backend.is_ready if server.backend else False,
            "connected_clients": len(server.connected_clients),
            "active_streaming_sessions": server.sessions.streaming_count,
            "active_pcm_sessions": server.sessions.pcm_count,
            "active_opus_sessions": server.sessions.opus_count,
            "ending_sessions": server.sessions.ending_count,
            "memory": memory,
            "transcriptions": {
                "started": server.transcriptions_started,
                "completed": server.transcriptions_completed,
                "failed": server.transcriptions_failed,
                "timed_out": server.transcriptions_timed_out,
                "inflight": server.transcriptions_inflight,
            },
            "timestamp": time.time(),
        }
    )


async def start_health_server(server: MatildaWebSocketServer, host: str, port: int) -> web.AppRunner:
    app = web.Application()

    async def _health(req: web.Request) -> web.Response:
        return await health_handler(server, req)

    app.router.add_get("/health", _health)
    runner = web.AppRunner(app)
    await runner.setup()
    try:
        await web.TCPSite(runner, host, port).start()
    except Exception:
        await runner.cleanup()
        raise
    logger.info("HTTP health endpoint available at http://%s:%s/health", host, port)
    return runner


async def start_health_server_unix(server: MatildaWebSocketServer, socket_path: str) -> web.AppRunner:
    app = web.Application()

    async def _health(req: web.Request) -> web.Response:
        return await health_handler(server, req)

    app.router.add_get("/health", _health)
    runner = web.AppRunner(app)
    await runner.setup()
    socket_dir = os.path.dirname(socket_path)
    if socket_dir:
        os.makedirs(socket_dir, exist_ok=True)
    if os.path.exists(socket_path):
        os.unlink(socket_path)
    try:
        await web.UnixSite(runner, socket_path).start()
    except Exception:
        await runner.cleanup()
        raise
    logger.info("HTTP health endpoint available at unix://%s/health", socket_path)
    return runner
