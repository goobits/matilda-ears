from __future__ import annotations

import asyncio
import os
from pathlib import Path

import pytest


def test_real_moss_runtime_when_requested(monkeypatch) -> None:
    binary = os.environ.get("EARS_MOSS_TEST_BINARY")
    model = os.environ.get("EARS_MOSS_TEST_MODEL")
    audio = os.environ.get("EARS_MOSS_TEST_AUDIO")
    if not all((binary, model, audio)):
        pytest.skip("set EARS_MOSS_TEST_BINARY, EARS_MOSS_TEST_MODEL, and EARS_MOSS_TEST_AUDIO")
    monkeypatch.setenv("EARS_MOSS_BINARY", binary)
    monkeypatch.setenv("EARS_MOSS_MODEL", model)

    from matilda_ears.transcription.backends.internal.moss import MossBackend

    backend = MossBackend()
    asyncio.run(backend.load())
    transcript = backend.transcribe(str(Path(audio)))

    assert transcript.backend == "moss"
    assert transcript.text
    assert transcript.segments
    assert all(segment.speaker for segment in transcript.segments)
