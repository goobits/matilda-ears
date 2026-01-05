import asyncio
import base64
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
            "binary": False,
        }
        await ws.send(json.dumps(start_msg))

        started = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
        assert started.get("type") == "stream_started"
        assert started.get("session_id") == session_id

        encoder = OpusEncoder(sample_rate=16000, channels=1)
        opus_packets = []
        for _ in range(3):
            frame = np.zeros(960, dtype=np.int16)
            opus_packet = encoder.encode_chunk(frame)
            assert opus_packet is not None
            opus_packets.append(opus_packet)

        for opus_packet in opus_packets:
            await ws.send(
                json.dumps(
                    {
                        "type": "audio_chunk",
                        "session_id": session_id,
                        "audio_data": base64.b64encode(opus_packet).decode("ascii"),
                        "ack_requested": True,
                    }
                )
            )

        await ws.send(
            json.dumps(
                {
                    "type": "end_stream",
                    "session_id": session_id,
                    "expected_chunks": len(opus_packets),
                }
            )
        )

        chunk_acks = 0
        message_types = []
        final_result = None
        deadline = asyncio.get_event_loop().time() + 20

        while final_result is None:
            timeout = max(0.1, deadline - asyncio.get_event_loop().time())
            if timeout <= 0:
                pytest.fail("Timed out waiting for stream_transcription_complete")

            message = json.loads(await asyncio.wait_for(ws.recv(), timeout=timeout))
            message_type = message.get("type")
            message_types.append(message_type)

            if message_type == "chunk_received":
                chunk_acks += 1
            elif message_type == "partial_result":
                continue
            elif message_type == "stream_transcription_complete":
                final_result = message
            elif message_type == "error":
                pytest.fail(f"Server error: {message}")

        assert chunk_acks == len(opus_packets)
        assert final_result.get("type") == "stream_transcription_complete"
        if "partial_result" in message_types:
            last_partial = max(
                idx for idx, mtype in enumerate(message_types) if mtype == "partial_result"
            )
            final_index = message_types.index("stream_transcription_complete")
            assert last_partial < final_index
