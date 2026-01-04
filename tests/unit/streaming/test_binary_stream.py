import numpy as np
import pytest

from matilda_ears.audio.decoder import OpusStreamDecoder
from matilda_ears.audio.encoder import OpusEncoder
from matilda_ears.transcription.server import handlers


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
    server.opus_decoder = OpusStreamDecoder()
    server.opus_decoder.create_session(session_id, 16000, 1)
    server.session_chunk_counts = {}
    server.ending_sessions = set()
    server.streaming_sessions = {}
    server.binary_stream_sessions = {client_id: session_id}

    websocket = DummyWebSocket()

    await handlers.handle_binary_stream_chunk(
        server, websocket, encoded, "127.0.0.1", client_id
    )

    assert session_id in server.session_chunk_counts
    assert server.session_chunk_counts[session_id]["received"] == 1
