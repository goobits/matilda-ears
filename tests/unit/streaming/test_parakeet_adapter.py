from types import SimpleNamespace

import numpy as np
import pytest

from matilda_ears.transcription.streaming.internal.parakeet_adapter import ParakeetStreamingAdapter
from matilda_ears.transcription.streaming.types import StreamingConfig


class NativeTranscriber:
    def __init__(self) -> None:
        self.finalized_tokens = []
        self.draft_tokens = []
        self.exited = False

    def __enter__(self):
        return self

    def __exit__(self, _exc_type, _exc_val, _exc_tb) -> None:
        self.exited = True

    def add_audio(self, _audio) -> None:
        self.finalized_tokens = [SimpleNamespace(text="hello")]
        self.draft_tokens = [SimpleNamespace(text="world")]


@pytest.mark.asyncio
async def test_native_parakeet_streaming_reads_transcriber_state() -> None:
    transcriber = NativeTranscriber()
    backend = SimpleNamespace(is_ready=True, transcribe_stream=lambda **_kwargs: transcriber)
    config = StreamingConfig(backend="parakeet", vad_enabled=False)
    adapter = ParakeetStreamingAdapter(backend, config)

    await adapter.start()
    interim = await adapter.process_chunk(np.zeros(adapter.MIN_BUFFER_SAMPLES, dtype=np.int16))
    final = await adapter.finalize()

    assert interim.alpha_text == "hello"
    assert interim.omega_text == "world"
    assert final.alpha_text == "hello world"
    assert final.omega_text == ""
    assert transcriber.exited is True
