from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from matilda_ears.core.token_manager import TokenManager


class _Config:
    transcription_backend = "test"
    jwt_secret_key = "x" * 32
    websocket_bind_host = "127.0.0.1"
    websocket_port = 8773
    ssl_enabled = False
    whisper_model = "base"

    def __init__(self) -> None:
        self.websocket_trusted_proxies: list[str] = []

    @staticmethod
    def get(key, default=None):
        if key == "transcription.max_workers":
            return 1
        if key == "streaming":
            return {"enabled": False}
        return default


class _Backend:
    is_ready = True

    async def load(self) -> None:
        return None


def test_runtime_environment_overrides_inference_settings(monkeypatch, tmp_path):
    from matilda_ears.core.config import ConfigLoader

    monkeypatch.setenv("EARS_DEVICE", "cpu")
    monkeypatch.setenv("EARS_COMPUTE_TYPE", "int8")
    config = ConfigLoader(tmp_path / "missing.toml")

    assert config.whisper_device_auto == "cpu"
    assert config.whisper_compute_type_auto == "int8"


def test_websocket_server_accepts_shared_token_manager(monkeypatch, tmp_path):
    from matilda_ears.transcription import server as server_package
    from matilda_ears.transcription.server import core

    monkeypatch.setattr(server_package, "config", _Config())
    monkeypatch.setattr(core, "config", _Config())
    monkeypatch.setattr(core, "get_backend_class", lambda _name: _Backend)

    token_manager = TokenManager(data_dir=tmp_path)
    server = core.MatildaWebSocketServer(token_manager=token_manager)
    try:
        assert server.token_manager is token_manager
        assert server.auth.token_manager is token_manager
    finally:
        server.close()


@pytest.mark.asyncio
async def test_dashboard_uses_shared_runtime(tmp_path):
    pytest.importorskip("fastapi")
    pytest.importorskip("multipart")
    httpx = pytest.importorskip("httpx")

    from docker.src.api import DashboardAPI

    token_manager = TokenManager(data_dir=tmp_path)
    transcription_server = SimpleNamespace(
        backend=SimpleNamespace(is_ready=True),
        connected_clients=set(),
        model_size="base",
        port=8773,
        ssl_enabled=False,
        transcribe_audio_from_wav=AsyncMock(return_value=(True, "hello", {"confidence": 0.8})),
    )
    dashboard = DashboardAPI(token_manager, transcription_server, api_token="admin-token")
    headers = {"Authorization": "Bearer admin-token"}

    transport = httpx.ASGITransport(app=dashboard.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        status = await client.get("/api/status")
        assert status.status_code == 200
        assert status.json()["websocket_port"] == 8773

        assert (await client.get("/api/clients")).status_code == 401

        generated = await client.post(
            "/api/generate-token",
            headers=headers,
            json={"client_name": "integration", "expiration_days": 1, "one_time_use": False},
        )
        assert generated.status_code == 200
        token_id = generated.json()["token_id"]
        assert token_id in token_manager.active_tokens

        clients = await client.get("/api/clients", headers=headers)
        assert clients.status_code == 200
        assert clients.json()[0]["name"] == "integration"

        transcription = await client.post(
            "/api/transcribe",
            headers=headers,
            files={"audio": ("sample.wav", b"x" * 1200, "audio/wav")},
        )
        assert transcription.status_code == 200
        assert transcription.json()["text"] == "hello"

    transcription_server.transcribe_audio_from_wav.assert_awaited_once()
    token_manager.close()
