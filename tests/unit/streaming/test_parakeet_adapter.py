import asyncio
import threading
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


@pytest.mark.asyncio
async def test_parakeet_streaming_holds_shared_inference_gate_until_worker_finishes() -> None:
    started = threading.Event()
    release = threading.Event()

    class BlockingTranscriber(NativeTranscriber):
        def add_audio(self, _audio) -> None:
            started.set()
            release.wait(timeout=1)
            super().add_audio(_audio)

    transcriber = BlockingTranscriber()
    backend = SimpleNamespace(is_ready=True, transcribe_stream=lambda **_kwargs: transcriber)
    semaphore = asyncio.Semaphore(1)
    adapter = ParakeetStreamingAdapter(
        backend,
        StreamingConfig(backend="parakeet", vad_enabled=False),
        inference_semaphore=semaphore,
    )

    await adapter.start()
    inference = asyncio.create_task(adapter.process_chunk(np.zeros(adapter.MIN_BUFFER_SAMPLES, dtype=np.int16)))
    assert await asyncio.to_thread(started.wait, 1)
    assert semaphore.locked()

    contender = asyncio.create_task(semaphore.acquire())
    await asyncio.sleep(0)
    assert not contender.done()

    release.set()
    await inference
    await contender
    semaphore.release()
    await adapter.finalize()
