import json
from types import SimpleNamespace

import pytest
from matilda_transport import build_envelope

from matilda_ears.transcription.client.internal import streaming
from matilda_ears.transcription.client.internal.streaming import StreamingAudioClient


class FakeEncoder:
    sample_rate = 16000
    channels = 1

    def __init__(self, final_chunk: bytes | None = None) -> None:
        self.final_chunk = final_chunk
        self.reset_count = 0

    def flush(self):
        chunk, self.final_chunk = self.final_chunk, None
        return chunk

    def reset(self):
        self.reset_count += 1


class FakeWebSocket:
    def __init__(self, responses=()) -> None:
        self.responses = list(responses)
        self.sent = []
        self.closed = False

    async def recv(self):
        return self.responses.pop(0)

    async def send(self, message):
        self.sent.append(json.loads(message))

    async def close(self):
        self.closed = True


def _envelope(task: str, result: dict) -> str:
    return json.dumps(build_envelope(request_id="request-1", service="ears", task=task, result=result))


@pytest.mark.asyncio
async def test_wss_connect_uses_central_ssl_context(monkeypatch):
    context = object()
    websocket = FakeWebSocket([_envelope("welcome", {"type": "welcome", "server_ready": True})])
    calls = SimpleNamespace(url=None, ssl=None)

    async def fake_connect(url, *, ssl):
        calls.url = url
        calls.ssl = ssl
        return websocket

    monkeypatch.setattr(streaming, "create_ssl_context", lambda **_kwargs: context)
    monkeypatch.setattr(streaming.websockets, "connect", fake_connect)
    client = StreamingAudioClient("wss://localhost:3211", "token")

    await client.connect()

    assert calls.url == "wss://localhost:3211"
    assert calls.ssl is context


@pytest.mark.asyncio
async def test_end_stream_flushes_and_resets_state():
    response = {
        "type": "stream_transcription_complete",
        "confirmed_text": "hello",
        "tentative_text": "",
        "success": True,
    }
    websocket = FakeWebSocket([_envelope("stream_transcription_complete", response)])
    client = StreamingAudioClient("ws://localhost:3211", "token")
    client.websocket = websocket
    client.session_id = "session-1"
    client.encoder = FakeEncoder(b"final-opus")

    result = await client.end_stream()

    assert result == {**response, "is_final": True}
    assert websocket.sent[0]["type"] == "audio_chunk"
    assert websocket.sent[1] == {
        "type": "end_stream",
        "session_id": "session-1",
        "expected_chunks": 1,
        "final_chunk": True,
    }
    assert client.session_id is None
    assert client.sent_opus_packets == 0
    assert client.encoder.reset_count == 1
    assert not websocket.closed


@pytest.mark.asyncio
async def test_end_stream_connection_loss_keeps_error_contract_and_resets():
    client = StreamingAudioClient("ws://localhost:3211", "token")
    client.websocket = FakeWebSocket()
    client.websocket.closed = True
    client.session_id = "session-1"
    client.encoder = FakeEncoder()

    result = await client.end_stream()

    assert result == {
        "success": False,
        "text": "",
        "confirmed_text": "",
        "tentative_text": "",
        "is_final": True,
        "message": "WebSocket connection lost",
    }
    assert client.session_id is None
    assert client.encoder.reset_count == 1
