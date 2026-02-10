import asyncio
import json
import sys
import time
import types
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from matilda_ears.transcription.server.core import MatildaWebSocketServer
from matilda_ears.transcription.server.internal.health import health_handler
from matilda_ears.transcription.server.internal.transcription import transcribe_audio_from_wav
import matilda_ears.transcription.server.stream_handlers as stream_handlers


class _SilentWebSocket:
    def __init__(self):
        self.remote_address = ("127.0.0.1", 9999)
        self.request_headers = {}
        self.messages = []

    async def send(self, message):
        self.messages.append(message)

    def __aiter__(self):
        return self

    async def __anext__(self):
        raise StopAsyncIteration


@pytest.mark.asyncio
async def test_handle_client_disconnect_cleans_orphaned_streaming_sessions(monkeypatch):
    cleanup_mock = AsyncMock()
    opus_decoder = SimpleNamespace(remove_session=Mock())

    session_id = "s-1"
    client_id = "deadbeef"
    server = SimpleNamespace(
        connected_clients=set(),
        binary_stream_sessions={},
        client_sessions={client_id: {session_id}},
        pcm_sessions={session_id: object()},
        opus_decoder=opus_decoder,
        session_chunk_counts={session_id: {"received": 1}},
        ending_sessions={session_id},
        streaming_sessions={session_id: object()},
        process_message=AsyncMock(),
        _cleanup_streaming_session=cleanup_mock,
        backend=SimpleNamespace(is_ready=True),
    )

    monkeypatch.setattr("matilda_ears.transcription.server.core.uuid.uuid4", lambda: "deadbeef-0000-0000-0000")

    ws = _SilentWebSocket()
    await MatildaWebSocketServer.handle_client(server, ws)

    cleanup_mock.assert_awaited_once()
    opus_decoder.remove_session.assert_called_once_with(session_id)
    assert client_id not in server.client_sessions
    assert session_id not in server.streaming_sessions
    assert session_id not in server.pcm_sessions
    assert session_id not in server.session_chunk_counts
    assert session_id not in server.ending_sessions


@pytest.mark.asyncio
async def test_cleanup_streaming_session_falls_back_to_reset():
    session = SimpleNamespace(reset=AsyncMock())
    server = SimpleNamespace()

    await MatildaWebSocketServer._cleanup_streaming_session(server, session)
    session.reset.assert_awaited_once()


@pytest.mark.asyncio
async def test_start_server_delegates_via_lazy_import(monkeypatch):
    start_mock = AsyncMock()
    fake_module = types.ModuleType("matilda_ears.transcription.server.main")
    fake_module.start_server = start_mock
    monkeypatch.setitem(sys.modules, "matilda_ears.transcription.server.main", fake_module)

    server = SimpleNamespace()
    await MatildaWebSocketServer.start_server(server, "127.0.0.1", 9999)

    start_mock.assert_awaited_once_with(server, "127.0.0.1", 9999)


@pytest.mark.asyncio
async def test_transcribe_audio_timeout_does_not_lock_serialization_semaphore(monkeypatch):
    class _Config:
        def get(self, key, default=None):
            if key == "transcription.timeout_seconds":
                return 0.01
            return default

    class _StuckBackend:
        is_ready = True

        def transcribe(self, _path, language="en"):
            time.sleep(0.1)
            return "ignored", {"duration": 1.0, "language": language}

    server = SimpleNamespace(
        backend=_StuckBackend(),
        transcription_semaphore=asyncio.Semaphore(1),
    )
    monkeypatch.setattr("matilda_ears.transcription.server.internal.transcription.get_config", lambda: _Config())

    # Size > MIN_AUDIO_SIZE so function reaches backend path.
    wav_data = b"RIFF" + b"\x00" * 2000
    success, text, info = await transcribe_audio_from_wav(server, wav_data, "client-timeout")

    assert success is False
    assert text == ""
    assert "timed out" in info["error"].lower()
    assert server.transcription_semaphore.locked() is False


@pytest.mark.asyncio
async def test_health_handler_reports_session_counters():
    server = SimpleNamespace(
        backend_name="parakeet",
        backend=SimpleNamespace(is_ready=True),
        connected_clients={object(), object()},
        streaming_sessions={"a": object()},
        pcm_sessions={"b": object(), "c": object()},
        opus_decoder=SimpleNamespace(get_active_sessions=lambda: ["x", "y", "z"]),
        ending_sessions={"done"},
    )

    response = await health_handler(server, request=None)
    payload = json.loads(response.text)

    assert payload["status"] == "healthy"
    assert payload["connected_clients"] == 2
    assert payload["active_streaming_sessions"] == 1
    assert payload["active_pcm_sessions"] == 2
    assert payload["active_opus_sessions"] == 3
    assert payload["ending_sessions"] == 1


@pytest.mark.asyncio
async def test_end_stream_removes_empty_client_session_bucket(monkeypatch):
    session_id = "s-final"
    client_id = "client-1"
    ws = _SilentWebSocket()

    finalize_result = SimpleNamespace(confirmed_text="ok", audio_duration_seconds=1.0)
    streaming_session = SimpleNamespace(finalize=AsyncMock(return_value=finalize_result))

    send_envelope = AsyncMock()
    send_error = AsyncMock()
    monkeypatch.setattr(stream_handlers, "send_envelope", send_envelope)
    monkeypatch.setattr(stream_handlers, "send_error", send_error)

    server = SimpleNamespace(
        ending_sessions=set(),
        check_rate_limit=lambda _ip: True,
        session_chunk_counts={},
        pcm_sessions={},
        opus_decoder=SimpleNamespace(remove_session=lambda _sid: None),
        streaming_sessions={session_id: streaming_session},
        client_sessions={client_id: {session_id}},
        binary_stream_sessions={client_id: session_id},
        wake_word_sessions={session_id: True},
        wake_word_buffers={session_id: object()},
        wake_word_debug_sessions={session_id: {"last_sent": 0}},
        backend_name="parakeet",
    )

    await stream_handlers.handle_end_stream(
        server=server,
        websocket=ws,
        data={"session_id": session_id},
        client_ip="127.0.0.1",
        client_id=client_id,
    )

    assert client_id not in server.client_sessions
    assert session_id not in server.wake_word_sessions
    assert session_id not in server.wake_word_buffers
    assert session_id not in server.wake_word_debug_sessions
    assert client_id not in server.binary_stream_sessions
    send_error.assert_not_awaited()
