import asyncio
import base64
import json
import os
import re
import time
import wave
from pathlib import Path

import pytest
import numpy as np


# Known hallucination patterns (garbage Whisper produces on silence)
HALLUCINATION_PATTERNS = [
    r"sous.?titres",
    r"amara\.org",
    r"it'?s general",
    r"communaut",
    r"merci d'avoir regard",
    r"thank you for watching",
    r"please subscribe",
]


def _load_wav(path: Path) -> tuple[np.ndarray, int]:
    with wave.open(str(path), "rb") as wav_file:
        sample_rate = wav_file.getframerate()
        samples = wav_file.readframes(wav_file.getnframes())
    return np.frombuffer(samples, dtype=np.int16), sample_rate


def _check_hallucinations(text: str) -> list[str]:
    """Check for known hallucination patterns."""
    found = []
    lower = text.lower()
    for pattern in HALLUCINATION_PATTERNS:
        if re.search(pattern, lower):
            found.append(pattern)
    return found


@pytest.mark.asyncio
async def test_streaming_replay_like():
    ws_url = os.environ.get("MATILDA_E2E_WS_URL")
    if not ws_url:
        pytest.skip("MATILDA_E2E_WS_URL not set for live streaming test")

    import websockets

    wav_path = os.environ.get("MATILDA_E2E_WAV_PATH")
    if wav_path is None:
        wav_path = "/workspace/matilda/tauri/static/test-recordings/hey-jarvis-test.wav"

    wav_file = Path(wav_path)
    if not wav_file.exists():
        pytest.skip(f"WAV file not found: {wav_file}")

    audio, sample_rate = _load_wav(wav_file)
    if sample_rate != 16000:
        pytest.skip(f"Unsupported sample rate: {sample_rate}")

    max_seconds = float(os.environ.get("MATILDA_E2E_MAX_AUDIO_SECONDS", "10"))
    max_samples = int(max_seconds * sample_rate)
    if audio.size > max_samples:
        audio = audio[:max_samples]

    chunk_seconds = 0.1
    chunk_samples = int(sample_rate * chunk_seconds)
    max_factor = float(os.environ.get("MATILDA_E2E_MAX_REALTIME_FACTOR", "4.0"))
    max_first_partial_seconds = float(os.environ.get("MATILDA_E2E_MAX_FIRST_PARTIAL_SECONDS", "6.0"))

    async with websockets.connect(ws_url) as ws:
        welcome = await asyncio.wait_for(ws.recv(), timeout=5)
        assert "welcome" in welcome

        session_id = f"replay-like-{int(time.time() * 1000)}"
        await ws.send(
            json.dumps(
                {
                    "type": "start_stream",
                    "session_id": session_id,
                    "sample_rate": sample_rate,
                    "channels": 1,
                    "binary": False,
                }
            )
        )

        started = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
        assert started.get("type") == "stream_started"
        assert started.get("session_id") == session_id

        first_partial_time = None
        final_time = None
        final_text = ""
        all_partials = []
        start_time = time.monotonic()

        async def listen():
            nonlocal first_partial_time, final_time, final_text
            while True:
                message = await ws.recv()
                if not isinstance(message, str):
                    continue
                payload = json.loads(message)
                msg_type = payload.get("type")
                if msg_type == "partial_result":
                    if first_partial_time is None:
                        first_partial_time = time.monotonic()
                    confirmed = payload.get("confirmed_text", "")
                    tentative = payload.get("tentative_text", "")
                    full = f"{confirmed} {tentative}".strip()
                    if full:
                        all_partials.append(full)
                if msg_type == "stream_transcription_complete":
                    final_time = time.monotonic()
                    final_text = payload.get("confirmed_text", "")
                    break

        listener_task = asyncio.create_task(listen())

        for offset in range(0, audio.size, chunk_samples):
            chunk = audio[offset : offset + chunk_samples]
            if chunk.size == 0:
                break
            await ws.send(
                json.dumps(
                    {
                        "type": "pcm_chunk",
                        "session_id": session_id,
                        "audio_data": base64.b64encode(chunk.tobytes()).decode("ascii"),
                        "format": "pcm_s16le",
                        "sample_rate": sample_rate,
                        "channels": 1,
                    }
                )
            )
            await asyncio.sleep(chunk_seconds)

        await ws.send(json.dumps({"type": "end_stream", "session_id": session_id}))

        timeout_seconds = (audio.size / sample_rate) * max_factor + 10.0
        await asyncio.wait_for(listener_task, timeout=timeout_seconds)

        assert final_time is not None
        elapsed = final_time - start_time
        audio_duration = audio.size / sample_rate
        print(f"Replay-like streaming: audio={audio_duration:.2f}s elapsed={elapsed:.2f}s")

        assert elapsed <= audio_duration * max_factor
        if first_partial_time is not None:
            time_to_first = first_partial_time - start_time
            print(f"Time to first partial: {time_to_first:.2f}s")
            assert time_to_first <= max_first_partial_seconds

        # Check for hallucinations in partials (critical quality check)
        hallucination_count = 0
        for partial in all_partials:
            found = _check_hallucinations(partial)
            if found:
                hallucination_count += 1
                print(f"Hallucination detected: {found} in '{partial[:60]}...'")

        assert hallucination_count == 0, f"Found {hallucination_count} hallucinations in partials"

        # Check we got reasonable output
        word_count = len(final_text.split())
        print(f"Final text ({word_count} words): {final_text[:100]}...")
        assert word_count >= 5, f"Too few words in final output: {word_count}"
