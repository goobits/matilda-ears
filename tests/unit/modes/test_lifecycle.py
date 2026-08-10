import asyncio
from unittest.mock import AsyncMock

import numpy as np
import pytest

from matilda_ears.core.mode_config import ModeConfig
from matilda_ears.modes import base_mode
from matilda_ears.modes.base_mode import AudioCaptureEndedError, BaseMode


class _Mode(BaseMode):
    async def run(self) -> None:
        pass


class FakeStreamer:
    def __init__(self, *, starts: bool = True) -> None:
        self.starts = starts
        self.recording = False
        self.stop_calls = 0

    def start_recording(self) -> bool:
        self.recording = self.starts
        return self.starts

    def stop_recording(self) -> dict:
        self.recording = False
        self.stop_calls += 1
        return {"chunks_sent": 2}

    def is_recording(self) -> bool:
        return self.recording


def _mode() -> _Mode:
    return _Mode(ModeConfig(sample_rate=16000, language="en", model="base"))


@pytest.mark.asyncio
async def test_capture_owner_starts_and_stops_once(monkeypatch) -> None:
    streamer = FakeStreamer()
    monkeypatch.setattr(base_mode, "PipeBasedAudioStreamer", lambda **_kwargs: streamer)
    mode = _mode()

    await mode._start_audio_capture(maxsize=4)
    mode.stop()
    stats = await mode._stop_audio_capture()
    await mode._cleanup()

    assert mode._stop_requested is True
    assert mode.is_recording is False
    assert mode.audio_streamer is None
    assert mode.audio_queue is None
    assert streamer.stop_calls == 1
    assert stats == {"chunks_sent": 2}


@pytest.mark.asyncio
async def test_failed_capture_start_releases_partial_state(monkeypatch) -> None:
    monkeypatch.setattr(base_mode, "PipeBasedAudioStreamer", lambda **_kwargs: FakeStreamer(starts=False))
    mode = _mode()

    with pytest.raises(RuntimeError, match="Failed to start"):
        await mode._start_audio_capture()

    assert mode.is_recording is False
    assert mode.audio_streamer is None
    assert mode.audio_queue is None


@pytest.mark.asyncio
async def test_audio_reader_distinguishes_dead_capture_from_idle_queue() -> None:
    mode = _mode()
    mode.audio_queue = asyncio.Queue()
    mode.audio_streamer = FakeStreamer()

    with pytest.raises(AudioCaptureEndedError, match="process stopped"):
        await mode._read_audio_chunk(timeout_seconds=0.001)


@pytest.mark.asyncio
async def test_transcribe_and_send_uses_one_shared_result_path() -> None:
    mode = _mode()
    result = {"success": True, "text": "hello", "language": "en", "duration": 1.0, "confidence": 1.0}
    mode._transcribe_async = AsyncMock(return_value=result)
    mode._send_transcription = AsyncMock()

    returned = await mode._transcribe_and_send(np.ones(160, dtype=np.int16), {"agent": "Matilda"})

    assert returned is result
    mode._send_transcription.assert_awaited_once_with(result, {"agent": "Matilda"})
