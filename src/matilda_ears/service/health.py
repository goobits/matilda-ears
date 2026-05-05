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


def _pcm_buffer_bytes(server: MatildaWebSocketServer) -> int:
    total = 0
    for session in server.pcm_sessions.values():
        if not isinstance(session, dict):
            continue
        for samples in session.get("samples", []):
            total += int(getattr(samples, "nbytes", 0))
    return total


def _wake_word_buffer_bytes(server: MatildaWebSocketServer) -> int:
    return sum(int(getattr(buffer, "nbytes", 0)) for buffer in server.wake_word_buffers.values())


async def health_handler(server: MatildaWebSocketServer, request: web.Request) -> web.Response:
    memory = {
        "rss_bytes": current_rss_bytes(),
        "peak_rss_bytes": peak_rss_bytes(),
        "pcm_buffer_bytes": _pcm_buffer_bytes(server),
        "opus_pcm_buffer_bytes": server.opus_decoder.get_total_buffer_bytes(),
        "wake_word_buffer_bytes": _wake_word_buffer_bytes(server),
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
            "active_streaming_sessions": len(server.streaming_sessions),
            "active_pcm_sessions": len(server.pcm_sessions),
            "active_opus_sessions": len(server.opus_decoder.get_active_sessions()),
            "ending_sessions": len(server.ending_sessions),
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
    site = web.TCPSite(runner, host, port)
    await site.start()
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
    site = web.UnixSite(runner, socket_path)
    await site.start()
    logger.info("HTTP health endpoint available at unix://%s/health", socket_path)
    return runner
