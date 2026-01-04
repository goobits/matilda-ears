import asyncio
import json
import os

import numpy as np
import pytest
import websockets

from matilda_ears.audio.encoder import OpusEncoder


@pytest.mark.asyncio
async def test_streaming_e2e():
    ws_url = os.environ.get("MATILDA_E2E_WS_URL")
    if not ws_url:
        pytest.skip("MATILDA_E2E_WS_URL not set for live streaming test")

    async with websockets.connect(ws_url) as ws:
        welcome = await asyncio.wait_for(ws.recv(), timeout=5)
        assert "welcome" in welcome

        session_id = "e2e-session"
        start_msg = {
            "type": "start_stream",
            "session_id": session_id,
            "sample_rate": 16000,
            "channels": 1,
            "binary": True,
        }
        await ws.send(json.dumps(start_msg))

        started = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
        assert started.get("type") == "stream_started"
        assert started.get("session_id") == session_id

        encoder = OpusEncoder(sample_rate=16000, channels=1)
        frame = np.zeros(960, dtype=np.int16)
        opus_packet = encoder.encode_chunk(frame)
        assert opus_packet is not None
        await ws.send(opus_packet)

        await ws.send(
            json.dumps(
                {"type": "end_stream", "session_id": session_id, "expected_chunks": 1}
            )
        )

        result = json.loads(await asyncio.wait_for(ws.recv(), timeout=20))
        assert result.get("type") == "stream_transcription_complete"
