from __future__ import annotations

import asyncio
import struct
import subprocess
import threading
import wave
from pathlib import Path
from types import SimpleNamespace

import pytest

from matilda_ears.transcription.backends.internal import moss
from matilda_ears.transcription.backends.internal.moss import (
    MossBackend,
    _align_speakers,
    _chunk_starts,
    _parse_segments,
    _stitch_seam,
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
        "moss.anchor_seconds": 15,
        "moss.overlap_seconds": 15,
        **overrides,
    }
    return SimpleNamespace(temp_dir=str(tmp_path), get=lambda key, default=None: values.get(key, default))


def test_chunk_starts_stop_when_the_last_chunk_reaches_the_end() -> None:
    assert _chunk_starts(4028.288, 150, 15, 15)[-1] == 3975
    assert len(_chunk_starts(4028.288, 150, 15, 15)) == 34


def test_anchored_chunk_prepends_reference_audio(tmp_path: Path) -> None:
    source = tmp_path / "source.wav"
    output = tmp_path / "anchored.wav"
    with wave.open(str(source), "wb") as audio:
        audio.setparams((1, 2, 10, 0, "NONE", "not compressed"))
        audio.writeframes(struct.pack("<100h", *range(100)))

    moss._write_anchored_wav_chunk(source, output, anchor_seconds=2, start=5, end=7)

    with wave.open(str(output), "rb") as audio:
        samples = struct.unpack("<40h", audio.readframes(40))
    assert samples == (*range(20), *range(50, 70))


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


def test_align_speakers_handles_chunk_local_label_swap() -> None:
    previous = [
        TranscriptSegment(0.2, 9.69, "Your mission is helping people rebuild their lives.", "S02"),
        TranscriptSegment(9.72, 10.0, "Back.", "S01"),
    ]
    current = [
        TranscriptSegment(0.12, 9.63, "Different words do not affect alignment.", "S01"),
        TranscriptSegment(9.64, 10.14, "Also different.", "S02"),
        TranscriptSegment(20.14, 21.0, "Directed.", "S01"),
    ]

    reconciled = _align_speakers(
        current,
        comparisons=[(previous, current, 0, 15)],
        known_speakers={"S01", "S02"},
    )

    assert [segment.speaker for segment in reconciled] == ["S02", "S01", "S02"]


def test_align_speakers_combines_reference_and_timeline_overlap() -> None:
    reference = [
        TranscriptSegment(0, 4, "Reference A.", "S01"),
        TranscriptSegment(4, 8, "Reference B.", "S02"),
    ]
    local = [
        TranscriptSegment(4, 8, "Reference B.", "S01"),
        TranscriptSegment(0, 4, "Reference A.", "S02"),
        TranscriptSegment(12, 16, "Timeline B.", "S01"),
        TranscriptSegment(16, 20, "Timeline A.", "S02"),
    ]
    previous_timeline = [
        TranscriptSegment(100, 104, "Timeline B.", "S02"),
        TranscriptSegment(104, 108, "Timeline A.", "S01"),
    ]
    current_timeline = [
        TranscriptSegment(100, 104, "Timeline B.", "S01"),
        TranscriptSegment(104, 108, "Timeline A.", "S02"),
    ]

    reconciled = _align_speakers(
        local,
        comparisons=[
            (reference, local, 0, 8),
            (previous_timeline, current_timeline, 100, 108),
        ],
        known_speakers={"S01", "S02"},
    )

    assert [segment.speaker for segment in reconciled] == ["S02", "S01", "S02", "S01"]


def test_stitch_seam_prefers_shared_silence_near_midpoint() -> None:
    previous = [
        TranscriptSegment(100, 103.5, "Before.", "S01"),
        TranscriptSegment(106.5, 110, "After.", "S02"),
    ]
    current = [
        TranscriptSegment(100.1, 104, "Before.", "S01"),
        TranscriptSegment(106, 109.9, "After.", "S02"),
    ]

    assert _stitch_seam(previous, current, start=100, end=110) == 105


def test_stitch_seam_falls_back_to_midpoint_without_shared_silence() -> None:
    previous = [TranscriptSegment(100, 110, "Continuous.", "S01")]
    current = [TranscriptSegment(100, 110, "Continuous.", "S01")]

    assert _stitch_seam(previous, current, start=100, end=110) == 105


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
    monkeypatch.setattr(moss, "_write_anchored_wav_chunk", lambda *args: None)
    barrier = threading.Barrier(2)
    backend = MossBackend()

    def run_chunk(_path, _duration):
        barrier.wait(timeout=2)
        return [TranscriptSegment(30, 31, "Concurrent.", "S01")]

    monkeypatch.setattr(backend, "_run_chunk", run_chunk)

    segments = backend._transcribe_chunks(Path("audio.wav"), 270, tmp_path)

    assert [segment.start for segment in segments] == [30, 150]
