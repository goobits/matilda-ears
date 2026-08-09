import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from matilda_ears.core.auth import AuthPolicy, AuthResult
from matilda_ears.transcription.server.core import (
    MatildaWebSocketServer,
    _client_ip,
    _connection_token,
)
from matilda_ears.transcription.server.internal.session_registry import SessionRegistry


class StubTokenManager:
    def validate_token(self, token: str):
        if token == "valid":
            return {"token_id": "token-1", "client_name": "desktop"}
        return None


class StubWebSocket:
    def __init__(self, messages=(), *, headers=None, path="/", peer="203.0.113.10"):
        self._messages = iter(messages)
        self.remote_address = (peer, 1234)
        self.request_headers = headers or {}
        self.path = path
        self.sent = []

    def __aiter__(self):
        return self

    async def __anext__(self):
        try:
            return next(self._messages)
        except StopIteration as error:
            raise StopAsyncIteration from error

    async def send(self, message):
        self.sent.append(json.loads(message))


def test_origin_is_not_an_authentication_credential(monkeypatch):
    monkeypatch.delenv("STT_DEV_MODE", raising=False)
    policy = AuthPolicy(StubTokenManager())

    result = policy.check(None, "203.0.113.10")

    assert result.authorized is False


def test_valid_token_uses_client_name(monkeypatch):
    monkeypatch.delenv("STT_DEV_MODE", raising=False)
    result = AuthPolicy(StubTokenManager()).check("valid", "203.0.113.10")

    assert result == AuthResult(authorized=True, client_id="desktop", method="jwt")


def test_untrusted_peer_cannot_spoof_forwarded_loopback():
    websocket = StubWebSocket(headers={"X-Forwarded-For": "127.0.0.1"})

    assert _client_ip(websocket, []) == "203.0.113.10"


def test_trusted_proxy_can_forward_valid_client_address():
    websocket = StubWebSocket(headers={"X-Forwarded-For": "198.51.100.7"}, peer="10.0.0.4")

    assert _client_ip(websocket, ["10.0.0.0/8"]) == "198.51.100.7"


@pytest.mark.parametrize(
    ("headers", "path", "expected"),
    [
        ({"Authorization": "Bearer header-token"}, "/", "header-token"),
        ({}, "/socket?api_token=query-token", "query-token"),
        ({}, "/socket?token=legacy-token", "legacy-token"),
    ],
)
def test_connection_token_sources(headers, path, expected):
    assert _connection_token(StubWebSocket(headers=headers, path=path)) == expected


@pytest.mark.asyncio
async def test_work_message_authenticates_once_and_binds_connection():
    server = MatildaWebSocketServer.__new__(MatildaWebSocketServer)
    server.authenticated_clients = {}
    server.auth = SimpleNamespace(check=AsyncMock())
    server.auth.check = lambda token, client_ip: AuthResult(
        authorized=token == "valid",
        client_id="desktop" if token == "valid" else None,
        method="jwt" if token == "valid" else None,
    )
    handler = AsyncMock()
    server.message_handlers = {"transcribe": handler}
    websocket = StubWebSocket()

    await server.process_message(websocket, {"type": "transcribe", "token": "valid"}, "203.0.113.10", "c1")
    await server.process_message(websocket, {"type": "transcribe"}, "203.0.113.10", "c1")

    assert handler.await_count == 2
    assert server.authenticated_clients["c1"].client_id == "desktop"


@pytest.mark.asyncio
async def test_unauthenticated_binary_audio_is_rejected():
    server = MatildaWebSocketServer.__new__(MatildaWebSocketServer)
    server.auth = SimpleNamespace(check=lambda token, ip: AuthResult(authorized=False))
    server.authenticated_clients = {}
    server.trusted_proxies = []
    server.connected_clients = set()
    server.sessions = SessionRegistry()
    server.backend = SimpleNamespace(is_ready=True)
    websocket = StubWebSocket(messages=[b"RIFF" + b"\x00" * 2000])

    await server.handle_client(websocket)

    errors = [message for message in websocket.sent if message.get("error")]
    assert errors
    assert errors[-1]["error"]["code"] == "unauthorized"
