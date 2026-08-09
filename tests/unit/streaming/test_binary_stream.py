import numpy as np
import pytest

from matilda_ears.audio.decoder import OpusDecoder
from matilda_ears.audio.encoder import OpusEncoder
from matilda_ears.transcription.server import handlers
from matilda_ears.transcription.server.internal.session_registry import SessionRegistry


class DummyWebSocket:
    def __init__(self) -> None:
        self.sent = []

    async def send(self, message) -> None:
        self.sent.append(message)


@pytest.mark.asyncio
async def test_binary_stream_chunk_updates_session_counts():
    encoder = OpusEncoder(sample_rate=16000, channels=1)
    frame = np.zeros(960, dtype=np.int16)
    encoded = encoder.encode_chunk(frame)
    assert encoded is not None

    session_id = "test-session"
    client_id = "client-1"

    server = type("Server", (), {})()
    server.sessions = SessionRegistry()
    session = server.sessions.create(session_id, client_id, "binary")
    session.decoder = OpusDecoder(16000, 1)

    websocket = DummyWebSocket()

    await handlers.handle_binary_stream_chunk(server, websocket, encoded, "127.0.0.1", client_id)

    assert session.chunks_received == 1
