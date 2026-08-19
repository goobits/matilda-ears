from __future__ import annotations

import asyncio
import subprocess
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest

from matilda_ears.transcription.backends.internal import moss
from matilda_ears.transcription.backends.internal.moss import (
    MossBackend,
    _chunk_starts,
    _parse_segments,
    _reconcile_speakers,
)
from matilda_ears.transcription.transcript import TranscriptSegment


def _config(tmp_path: Path, **overrides):
    values = {
        "moss.runtime": "native",
        "moss.binary": "missing-moss-transcribe",
        "moss.model": "q8_0",
        "moss.threads": 8,
        "moss.workers": 1,
        "moss.token_limit": 4096,
        "moss.chunk_seconds": 150,
        "moss.overlap_seconds": 30,
        **overrides,
    }
    return SimpleNamespace(temp_dir=str(tmp_path), get=lambda key, default=None: values.get(key, default))


def test_chunk_starts_stop_when_the_last_chunk_reaches_the_end() -> None:
    assert _chunk_starts(4028.288, 150, 30)[-1] == 3960
    assert len(_chunk_starts(4028.288, 150, 30)) == 34


def test_parse_segments_validates_and_clamps_native_output() -> None:
    segments = _parse_segments(
        [{"start": 149.72, "end": 150.22, "speaker": "S01", "text": "Back."}],
        150,
    )

    assert segments == [TranscriptSegment(149.72, 150, "Back.", "S01")]
    with pytest.raises(RuntimeError, match="speaker label"):
        _parse_segments([{"start": 0, "end": 1, "speaker": "person", "text": "Hi"}], 10)
    with pytest.raises(RuntimeError, match="timestamps"):
        _parse_segments([{"start": "nan", "end": 1, "speaker": "S01", "text": "Hi"}], 10)


def test_reconcile_speakers_handles_chunk_local_label_swap() -> None:
    previous = [
        TranscriptSegment(120.2, 149.69, "Your mission is helping people rebuild their lives.", "S02"),
        TranscriptSegment(149.72, 150.0, "Back.", "S01"),
    ]
    current = [
        TranscriptSegment(120.12, 149.63, "Your mission is helping people rebuild their lives.", "S01"),
        TranscriptSegment(149.64, 150.14, "Back.", "S02"),
        TranscriptSegment(150.14, 151.0, "Directed.", "S01"),
    ]

    reconciled = _reconcile_speakers(
        previous,
        current,
        overlap_start=120,
        overlap_end=150,
        known_speakers={"S01", "S02"},
    )

    assert [segment.speaker for segment in reconciled] == ["S02", "S01", "S02"]


def test_load_reports_exact_runtime_recovery_command(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(moss, "get_config", lambda: _config(tmp_path))
    backend = MossBackend()

    with pytest.raises(RuntimeError, match="ears download --backend moss --model q8_0"):
        asyncio.run(backend.load())


def test_load_reports_exact_model_recovery_command(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(moss, "get_config", lambda: _config(tmp_path))
    monkeypatch.setattr(moss, "_resolve_binary", lambda _setting: Path("/bin/true"))
    monkeypatch.setattr(moss, "get_moss_model_path", lambda _model: None)
    backend = MossBackend()

    with pytest.raises(RuntimeError, match="ears download --backend moss --model q8_0"):
        asyncio.run(backend.load())


def test_native_process_failure_is_not_hidden(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(moss, "get_config", lambda: _config(tmp_path))
    monkeypatch.setattr(
        moss.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args=[], returncode=137, stdout="", stderr="killed"),
    )
    backend = MossBackend()
    backend.binary = Path("/bin/true")
    backend.model = Path("model.gguf")

    with pytest.raises(RuntimeError, match="MOSS transcription failed: killed"):
        backend._run_chunk(Path("audio.wav"), 30)


def test_chunk_workers_are_bounded_and_results_stay_ordered(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(moss, "get_config", lambda: _config(tmp_path, **{"moss.workers": 2}))
    monkeypatch.setattr(moss, "_write_wav_chunk", lambda *args: None)
    barrier = threading.Barrier(2)
    backend = MossBackend()

    def run_chunk(_path, _duration):
        barrier.wait(timeout=2)
        return [TranscriptSegment(20, 21, "Concurrent.", "S01")]

    monkeypatch.setattr(backend, "_run_chunk", run_chunk)

    segments = backend._transcribe_chunks(Path("audio.wav"), 270, tmp_path)

    assert [segment.start for segment in segments] == [20, 140]
