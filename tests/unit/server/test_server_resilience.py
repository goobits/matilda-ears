import asyncio
import base64
import json
import sys
import time
import types
from types import SimpleNamespace
from unittest.mock import ANY, AsyncMock, Mock

import numpy as np
import pytest

from matilda_ears.core.auth import AuthResult
from matilda_ears.service.health import health_handler
from matilda_ears.transcription.server import stream_handlers
from matilda_ears.transcription.server.core import MatildaWebSocketServer
from matilda_ears.transcription.server.internal.session_registry import PcmBuffer, SessionRegistry, WakeWordState
from matilda_ears.transcription.server.internal.transcription import transcribe_audio_from_wav
from matilda_ears.transcription.transcript import Transcript


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
    detector = SimpleNamespace(CHUNK_SAMPLES=4, close=Mock(), reset=Mock())
    session_id = "s-1"
    client_id = "deadbeef"
    sessions = SessionRegistry()
    session = sessions.create(session_id, client_id, "opus")
    session.decoder = object()
    session.pcm = PcmBuffer(sample_rate=16000, channels=1, needs_resampling=False)
    session.streaming = object()
    session.ending = True
    session.wake_word = WakeWordState(detector)

    async def cleanup_server_session(orphaned_session):
        await MatildaWebSocketServer._cleanup_server_session(server, orphaned_session)

    server = SimpleNamespace(
        auth=SimpleNamespace(check=lambda _token, _ip: AuthResult(authorized=True, method="localhost")),
        authenticated_clients={},
        trusted_proxies=[],
        connected_clients=set(),
        sessions=sessions,
        process_message=AsyncMock(),
        _cleanup_streaming_session=cleanup_mock,
        _cleanup_server_session=cleanup_server_session,
        backend=SimpleNamespace(is_ready=True),
    )

    monkeypatch.setattr("matilda_ears.transcription.server.core.uuid.uuid4", lambda: "deadbeef-0000-0000-0000")

    ws = _SilentWebSocket()
    await MatildaWebSocketServer.handle_client(server, ws)

    cleanup_mock.assert_awaited_once()
    detector.close.assert_called_once()
    assert len(sessions) == 0


@pytest.mark.asyncio
async def test_handle_client_disconnect_cleans_binary_session_not_in_client_sessions(monkeypatch):
    session_id = "binary-only"
    client_id = "deadbeef"
    sessions = SessionRegistry()
    session = sessions.create(session_id, client_id, "binary")
    session.decoder = object()
    session.wake_word = WakeWordState(SimpleNamespace(CHUNK_SAMPLES=4, close=Mock(), reset=Mock()))

    cleanup_server_session = AsyncMock()

    server = SimpleNamespace(
        auth=SimpleNamespace(check=lambda _token, _ip: AuthResult(authorized=True, method="localhost")),
        authenticated_clients={},
        trusted_proxies=[],
        connected_clients=set(),
        sessions=sessions,
        process_message=AsyncMock(),
        _cleanup_server_session=cleanup_server_session,
        backend=SimpleNamespace(is_ready=True),
    )

    monkeypatch.setattr("matilda_ears.transcription.server.core.uuid.uuid4", lambda: "deadbeef-0000-0000-0000")

    ws = _SilentWebSocket()
    await MatildaWebSocketServer.handle_client(server, ws)

    cleanup_server_session.assert_awaited_once_with(session)
    assert len(sessions) == 0


def test_rate_limit_prunes_inactive_ip_buckets():
    server = SimpleNamespace(
        rate_limits={
            "203.0.113.10": [100.0],
            "203.0.113.11": [195.0],
        },
        _last_rate_limit_cleanup=0.0,
    )

    MatildaWebSocketServer._cleanup_rate_limits(server, now=200.0)

    assert "203.0.113.10" not in server.rate_limits
    assert server.rate_limits["203.0.113.11"] == [195.0]


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
async def test_transcribe_audio_timeout_holds_serialization_until_worker_finishes(monkeypatch):
    class _Config:
        def get(self, key, default=None):
            if key == "transcription.timeout_seconds":
                return 0.01
            return default

    class _StuckBackend:
        is_ready = True

        def transcribe(self, _path, language="en"):
            time.sleep(0.05)
            return Transcript(text="ignored", segments=(), language=language, duration=1.0, backend="test")

    server = SimpleNamespace(
        backend=_StuckBackend(),
        transcription_semaphore=asyncio.Semaphore(1),
        transcription_executor=None,
        transcription_executor_semaphore=asyncio.Semaphore(1),
        transcriptions_started=0,
        transcriptions_completed=0,
        transcriptions_failed=0,
        transcriptions_timed_out=0,
        transcriptions_inflight=0,
    )

    def _get_config() -> _Config:
        return _Config()

    monkeypatch.setattr("matilda_ears.transcription.server.internal.transcription.get_config", _get_config)

    # Size > MIN_AUDIO_SIZE so function reaches backend path.
    wav_data = b"RIFF" + b"\x00" * 2000
    success, text, info = await transcribe_audio_from_wav(server, wav_data, "client-timeout")

    assert success is False
    assert text == ""
    assert "timed out" in info["error"].lower()
    assert server.transcription_semaphore.locked() is True
    await asyncio.sleep(0.06)
    assert server.transcription_semaphore.locked() is False


@pytest.mark.asyncio
async def test_health_handler_reports_session_counters():
    sessions = SessionRegistry()
    streaming = sessions.create("a", "client-a", "opus")
    streaming.streaming = object()
    streaming.decoder = SimpleNamespace(get_stats=lambda: {"buffer_size_bytes": 0})
    pcm_b = sessions.create("b", "client-b", "pcm")
    pcm_b.pcm = PcmBuffer(sample_rate=16000, channels=1, needs_resampling=False)
    pcm_c = sessions.create("c", "client-c", "pcm")
    pcm_c.pcm = PcmBuffer(sample_rate=16000, channels=1, needs_resampling=False)
    pcm_c.decoder = SimpleNamespace(get_stats=lambda: {"buffer_size_bytes": 0})
    ending = sessions.create("done", "client-d", "opus")
    ending.decoder = SimpleNamespace(get_stats=lambda: {"buffer_size_bytes": 0})
    ending.ending = True

    server = SimpleNamespace(
        backend_name="parakeet",
        backend=SimpleNamespace(is_ready=True),
        connected_clients={object(), object()},
        sessions=sessions,
        transcriptions_started=4,
        transcriptions_completed=3,
        transcriptions_failed=1,
        transcriptions_timed_out=0,
        transcriptions_inflight=0,
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

    sessions = SessionRegistry()
    session = sessions.create(session_id, client_id, "binary")
    session.streaming = streaming_session
    server = SimpleNamespace(sessions=sessions, check_rate_limit=lambda _ip: True, backend_name="parakeet")

    await stream_handlers.handle_end_stream(
        server=server,
        websocket=ws,
        data={"session_id": session_id},
        client_ip="127.0.0.1",
        client_id=client_id,
    )

    assert sessions.get(session_id) is None
    send_error.assert_not_awaited()


@pytest.mark.asyncio
async def test_end_stream_falls_back_to_batch_when_streaming_finalize_empty(monkeypatch):
    session_id = "s-empty"
    client_id = "client-empty"
    ws = _SilentWebSocket()

    finalize_result = SimpleNamespace(confirmed_text="", audio_duration_seconds=1.0)
    streaming_session = SimpleNamespace(finalize=AsyncMock(return_value=finalize_result))

    class _Decoder:
        sample_rate = 16000
        channels = 1

        @staticmethod
        def get_pcm_array():
            # 1 second of non-silent mono PCM
            return np.full(16000, 1000, dtype=np.int16)

    send_envelope = AsyncMock()
    send_error = AsyncMock()
    transcribe_audio_from_wav = AsyncMock(return_value=(True, "fallback transcription", {"language": "en"}))

    monkeypatch.setattr(stream_handlers, "send_envelope", send_envelope)
    monkeypatch.setattr(stream_handlers, "send_error", send_error)
    monkeypatch.setattr(stream_handlers, "transcribe_audio_from_wav", transcribe_audio_from_wav)

    sessions = SessionRegistry()
    session = sessions.create(session_id, client_id, "binary")
    session.streaming = streaming_session
    session.decoder = _Decoder()
    server = SimpleNamespace(sessions=sessions, check_rate_limit=lambda _ip: True, backend_name="parakeet")

    await stream_handlers.handle_end_stream(
        server=server,
        websocket=ws,
        data={"session_id": session_id},
        client_ip="127.0.0.1",
        client_id=client_id,
    )

    transcribe_audio_from_wav.assert_awaited_once()
    send_error.assert_not_awaited()
    # First envelope may be a final partial from streaming, second is the final batch result.
    assert send_envelope.await_count >= 1
    final_payload = send_envelope.await_args_list[-1].args[2]
    assert final_payload["type"] == "stream_transcription_complete"
    assert final_payload["confirmed_text"] == "fallback transcription"
    assert final_payload["streaming_mode"] is False


@pytest.mark.asyncio
async def test_stream_handlers_reject_cross_client_session_access(monkeypatch):
    sessions = SessionRegistry()
    sessions.create("owned-session", "owner", "opus")
    send_error = AsyncMock()
    monkeypatch.setattr(stream_handlers, "send_error", send_error)

    server = SimpleNamespace(sessions=sessions)
    await stream_handlers.handle_audio_chunk(
        server,
        _SilentWebSocket(),
        {"session_id": "owned-session", "audio_data": "unused"},
        "127.0.0.1",
        "attacker",
    )

    send_error.assert_awaited_once()
    assert sessions.get_owned("owned-session", "owner") is not None


@pytest.mark.asyncio
async def test_start_stream_rejects_duplicate_session_id(monkeypatch):
    sessions = SessionRegistry()
    existing = sessions.create("duplicate", "owner", "opus")
    send_error = AsyncMock()
    monkeypatch.setattr(stream_handlers, "send_error", send_error)

    server = SimpleNamespace(backend=SimpleNamespace(is_ready=True), sessions=sessions)
    await stream_handlers.handle_start_stream(
        server,
        _SilentWebSocket(),
        {"session_id": "duplicate", "sample_rate": 16000},
        "127.0.0.1",
        "other-client",
    )

    send_error.assert_awaited_once_with(
        ANY,
        "Session ID is already active",
        code="session_conflict",
    )
    assert sessions.get("duplicate") is existing


def test_streaming_session_keeps_vad_enabled_and_forwards_inference_gate(monkeypatch):
    captured = {}
    sentinel = object()
    semaphore = asyncio.Semaphore(1)

    def fake_session(**kwargs):
        captured.update(kwargs)
        return sentinel

    monkeypatch.setattr("matilda_ears.transcription.streaming.StreamingSession", fake_session)
    monkeypatch.setattr(
        stream_handlers,
        "get_config",
        lambda: {
            "streaming": {
                "simul_streaming": {"vad_enabled": True},
                "parakeet": {},
            }
        },
    )

    result = stream_handlers._create_streaming_session(
        "session",
        backend=object(),
        backend_name="parakeet",
        transcription_semaphore=semaphore,
    )

    assert result is sentinel
    assert captured["config"].vad_enabled is True
    assert captured["config"].backend == "parakeet"
    assert captured["vad"] is None
    assert captured["inference_semaphore"] is semaphore


def test_streaming_rejects_parakeet_without_matching_loaded_backend(monkeypatch):
    monkeypatch.setattr(
        stream_handlers,
        "get_config",
        lambda: {"streaming": {"backend": "parakeet", "simul_streaming": {}, "parakeet": {}}},
    )

    with pytest.raises(ValueError, match="loaded transcription backend"):
        stream_handlers._create_streaming_session(
            "session",
            backend=object(),
            backend_name="faster_whisper",
            transcription_semaphore=None,
        )


@pytest.mark.asyncio
async def test_json_and_binary_opus_use_the_same_partial_result_path(monkeypatch):
    class Decoder:
        sample_rate = 16000
        channels = 1

        @staticmethod
        def decode_chunk(_packet):
            return np.full(320, 100, dtype=np.int16)

        @staticmethod
        def get_duration():
            return 0.02

    result = SimpleNamespace(confirmed_text="hello", tentative_text="world")
    sessions = SessionRegistry()
    json_session = sessions.create("json", "json-client", "opus")
    json_session.decoder = Decoder()
    json_session.streaming = SimpleNamespace(process_chunk=AsyncMock(return_value=result))
    binary_session = sessions.create("binary", "binary-client", "binary")
    binary_session.decoder = Decoder()
    binary_session.streaming = SimpleNamespace(process_chunk=AsyncMock(return_value=result))
    server = SimpleNamespace(sessions=sessions)
    send_envelope = AsyncMock()
    send_error = AsyncMock()
    monkeypatch.setattr(stream_handlers, "send_envelope", send_envelope)
    monkeypatch.setattr(stream_handlers, "send_error", send_error)

    packet = b"encoded-opus"
    await stream_handlers.handle_audio_chunk(
        server,
        _SilentWebSocket(),
        {"session_id": "json", "audio_data": base64.b64encode(packet).decode()},
        "127.0.0.1",
        "json-client",
    )
    await stream_handlers.handle_binary_stream_chunk(
        server,
        _SilentWebSocket(),
        packet,
        "127.0.0.1",
        "binary-client",
    )

    json_session.streaming.process_chunk.assert_awaited_once()
    binary_session.streaming.process_chunk.assert_awaited_once()
    assert send_envelope.await_count == 2
    assert all(call.args[1] == "partial_result" for call in send_envelope.await_args_list)
    send_error.assert_not_awaited()


@pytest.mark.asyncio
async def test_wake_word_state_is_created_per_stream(monkeypatch):
    detectors = [
        SimpleNamespace(CHUNK_SAMPLES=4, close=Mock(), reset=Mock()),
        SimpleNamespace(CHUNK_SAMPLES=4, close=Mock(), reset=Mock()),
    ]
    factory = Mock(side_effect=detectors)
    server = SimpleNamespace(wake_word_available=None)
    monkeypatch.setattr(stream_handlers.WakeWordDetector, "from_config", factory)
    monkeypatch.setattr(stream_handlers, "get_config", lambda: {"modes": {"wake_word": {}}})

    first = await stream_handlers._create_wake_word_state(server, debug_enabled=False)
    second = await stream_handlers._create_wake_word_state(server, debug_enabled=True)

    assert first is not None
    assert first.detector is detectors[0]
    assert second is not None
    assert second.detector is detectors[1]
    assert first.debug_last_sent is None
    assert second.debug_last_sent == 0.0
    assert factory.call_count == 2


@pytest.mark.asyncio
async def test_wake_word_frame_uses_one_model_evaluation(monkeypatch):
    detection = ("Matilda", "hey_matilda", 0.9)
    detector = SimpleNamespace(
        CHUNK_SAMPLES=4,
        evaluate=Mock(return_value=(detection, "hey_matilda", 0.9)),
        reset=Mock(),
        close=Mock(),
    )
    session = SessionRegistry().create("wake", "client", "opus")
    session.wake_word = WakeWordState(detector)
    send_envelope = AsyncMock()
    monkeypatch.setattr(stream_handlers, "send_envelope", send_envelope)

    await stream_handlers._process_wake_word_chunk(
        _SilentWebSocket(),
        session,
        np.arange(4, dtype=np.int16),
    )

    detector.evaluate.assert_called_once()
    detector.reset.assert_called_once()
    payload = send_envelope.await_args.args[2]
    assert payload["type"] == "wake_word_detected"
    assert payload["agent"] == "Matilda"
