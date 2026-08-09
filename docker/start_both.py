#!/usr/bin/env python3
import asyncio
import logging
import os
from pathlib import Path

import uvicorn

from docker.src.api import DashboardAPI
from matilda_ears.core.token_manager import TokenManager
from matilda_ears.transcription.server.core import MatildaWebSocketServer

logger = logging.getLogger(__name__)


def build_runtime() -> tuple[MatildaWebSocketServer, DashboardAPI]:
    os.environ.setdefault("EARS_MODEL", os.getenv("WHISPER_MODEL", "base"))

    data_dir = Path(os.getenv("MATILDA_DATA_DIR", "/app/data"))
    token_manager = TokenManager(secret_key=os.getenv("STT_JWT_SECRET"), data_dir=data_dir)

    websocket_server = MatildaWebSocketServer(token_manager=token_manager)
    websocket_server.host = os.getenv("WEBSOCKET_BIND_HOST", "0.0.0.0")
    websocket_server.port = int(os.getenv("WEBSOCKET_PORT", "8773"))

    dashboard_api = DashboardAPI(token_manager, websocket_server)
    return websocket_server, dashboard_api


async def run() -> None:
    websocket_server, dashboard_api = build_runtime()
    web_host = os.getenv("WEB_BIND_HOST", "0.0.0.0")
    web_port = int(os.getenv("WEB_PORT", "8080"))
    log_level = os.getenv("LOG_LEVEL", "info").lower()

    api_server = uvicorn.Server(
        uvicorn.Config(
            dashboard_api.app,
            host=web_host,
            port=web_port,
            log_level=log_level,
            access_log=True,
        )
    )

    logger.info("Dashboard: http://%s:%s", web_host, web_port)
    logger.info(
        "WebSocket: %s://%s:%s",
        "wss" if websocket_server.ssl_enabled else "ws",
        websocket_server.host,
        websocket_server.port,
    )

    websocket_task = asyncio.create_task(
        websocket_server.start_server(websocket_server.host, websocket_server.port),
        name="matilda-websocket",
    )
    dashboard_task = asyncio.create_task(api_server.serve(), name="matilda-dashboard")
    done, pending = await asyncio.wait({websocket_task, dashboard_task}, return_when=asyncio.FIRST_COMPLETED)

    api_server.should_exit = True
    for task in pending:
        task.cancel()
    await asyncio.gather(*pending, return_exceptions=True)
    for task in done:
        task.result()


def main() -> None:
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO").upper())
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        logger.info("Shutdown requested")


if __name__ == "__main__":
    main()
