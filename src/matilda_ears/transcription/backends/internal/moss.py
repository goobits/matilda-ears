from __future__ import annotations

import json
import logging
import math
import os
import re
import shutil
import subprocess
import tempfile
import wave
from itertools import pairwise
from pathlib import Path

from ....core.config import get_config
from ...model_store import get_moss_model_path, get_moss_runtime_path
from ...transcript import Transcript, TranscriptSegment
from ..base import TranscriptionBackend

logger = logging.getLogger(__name__)

_SPEAKER_PATTERN = re.compile(r"^S\d{2,}$")


class MossBackend(TranscriptionBackend):
    def __init__(self) -> None:
        config = get_config()
        self.runtime = str(config.get("moss.runtime", "native"))
        self.binary_setting = os.environ.get("EARS_MOSS_BINARY") or str(
            config.get("moss.binary", get_moss_runtime_path())
        )
        self.model_setting = os.environ.get("EARS_MOSS_MODEL") or str(config.get("moss.model", "q8_0"))
        self.threads = int(config.get("moss.threads", 8))
        self.token_limit = int(config.get("moss.token_limit", 4096))
        self.chunk_seconds = float(config.get("moss.chunk_seconds", 150))
        self.reference_seconds = float(config.get("moss.reference_seconds", 10))
        self.overlap_seconds = float(config.get("moss.overlap_seconds", 12))
        self.temp_dir = Path(config.temp_dir)
        self.binary: Path | None = None
        self.model: Path | None = None

    async def load(self) -> None:
        if self.runtime != "native":
            raise RuntimeError("MOSS supports only the isolated native runtime; set [ears.moss].runtime to native")
        self.binary = _resolve_binary(self.binary_setting)
        if self.binary is None:
            raise RuntimeError(
                f"MOSS native runtime not found: {self.binary_setting}. "
                "Install it with: ears download --backend moss --model q8_0"
            )
        self.model = get_moss_model_path(self.model_setting)
        if self.model is None:
            raise RuntimeError(
                f"MOSS model not found: {self.model_setting}. "
                "Download it with: ears download --backend moss --model q8_0"
            )
        if self.threads < 1 or self.token_limit < 1:
            raise ValueError("MOSS threads and token_limit must be positive")
        target_seconds = self.chunk_seconds - self.reference_seconds
        if self.chunk_seconds <= 0 or not 0 < self.reference_seconds < self.chunk_seconds:
            raise ValueError("MOSS reference_seconds must be positive and smaller than chunk_seconds")
        if not 0 < self.overlap_seconds < target_seconds:
            raise ValueError("MOSS overlap_seconds must be positive and smaller than the unanchored chunk duration")

    def transcribe(self, audio_path: str, language: str = "en") -> Transcript:
        if not self.is_ready or self.binary is None or self.model is None:
            raise RuntimeError("MOSS backend not loaded")
        if shutil.which("ffmpeg") is None:
            raise RuntimeError("ffmpeg is required to normalize audio for MOSS")

        self.temp_dir.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="moss-", dir=self.temp_dir) as temporary:
            work_dir = Path(temporary)
            normalized = work_dir / "audio.wav"
            _normalize_audio(Path(audio_path), normalized)
            duration = _wav_duration(normalized)
            segments = self._transcribe_chunks(normalized, duration, work_dir)

        text = " ".join(segment.text for segment in segments).strip()
        return Transcript(
            text=text,
            segments=tuple(segments),
            language=language or None,
            duration=duration,
            backend="moss",
        )

    def _transcribe_chunks(self, normalized: Path, duration: float, work_dir: Path) -> list[TranscriptSegment]:
        first_end = min(self.chunk_seconds, duration)
        first_path = work_dir / "chunk-0000.wav"
        _write_wav_chunk(normalized, first_path, 0, first_end)
        logger.info("MOSS chunk 1: %.2f-%.2f", 0.0, first_end)
        first = self._run_chunk(first_path, first_end)
        stitched = _offset_segments(first, start=0, prefix_seconds=0, duration=duration)
        if first_end >= duration:
            return stitched

        reference_path = work_dir / "reference.wav"
        speaker_reference, prefix_seconds = _write_speaker_reference(
            normalized,
            reference_path,
            first,
            budget_seconds=self.reference_seconds,
        )
        if not speaker_reference or prefix_seconds <= 0:
            raise RuntimeError("MOSS could not build a speaker reference from the first chunk")

        starts = _chunk_starts(duration, self.chunk_seconds, prefix_seconds, self.overlap_seconds)
        known_speakers = {segment.speaker for segment in stitched if segment.speaker}
        for index, start in enumerate(starts[1:], 1):
            target_seconds = self.chunk_seconds - prefix_seconds
            end = min(start + target_seconds, duration)
            chunk_path = work_dir / f"chunk-{index:04d}.wav"
            _write_prefixed_wav_chunk(reference_path, normalized, chunk_path, start, end)
            logger.info("MOSS chunk %d/%d: %.2f-%.2f", index + 1, len(starts), start, end)
            local = self._run_chunk(chunk_path, prefix_seconds + end - start)
            timeline_local = _offset_segments(
                local,
                start=start,
                prefix_seconds=prefix_seconds,
                duration=duration,
            )
            local = _align_speakers(
                local,
                comparisons=[
                    (speaker_reference, local, 0, prefix_seconds),
                    (
                        stitched,
                        timeline_local,
                        start,
                        min(start + self.overlap_seconds, end),
                    ),
                ],
                known_speakers=known_speakers,
            )
            current = _offset_segments(local, start=start, prefix_seconds=prefix_seconds, duration=duration)
            known_speakers.update(segment.speaker for segment in current if segment.speaker)
            seam = _stitch_seam(
                stitched,
                current,
                start=start,
                end=min(start + self.overlap_seconds, end),
            )
            previous = [segment for segment in stitched if _midpoint(segment) < seam]
            following = [segment for segment in current if _midpoint(segment) >= seam]
            stitched = previous + _deduplicate_boundary(previous, following)

        return sorted(stitched, key=lambda segment: (segment.start, segment.end))

    def _run_chunk(self, chunk_path: Path, duration: float) -> list[TranscriptSegment]:
        if self.binary is None or self.model is None:
            raise RuntimeError("MOSS backend not loaded")
        environment = os.environ.copy()
        environment["MTD_THREADS"] = str(self.threads)
        result = subprocess.run(
            [
                str(self.binary),
                "transcribe",
                str(self.model),
                str(chunk_path),
                "--max-new",
                str(self.token_limit),
                "--format",
                "json",
            ],
            check=False,
            capture_output=True,
            text=True,
            env=environment,
        )
        if result.returncode != 0:
            detail = (result.stderr or result.stdout).strip().splitlines()
            message = detail[-1] if detail else f"exit code {result.returncode}"
            raise RuntimeError(f"MOSS transcription failed: {message}")
        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"MOSS returned invalid JSON: {exc}") from exc
        return _parse_segments(payload, duration)

    @property
    def is_ready(self) -> bool:
        return self.binary is not None and self.model is not None


def _resolve_binary(setting: str) -> Path | None:
    if setting == "auto":
        setting = str(get_moss_runtime_path())
    expanded = Path(setting).expanduser()
    if expanded.is_file() and os.access(expanded, os.X_OK):
        return expanded.resolve()
    resolved = shutil.which(setting)
    return Path(resolved).resolve() if resolved else None


def _normalize_audio(source: Path, output: Path) -> None:
    result = subprocess.run(
        [
            "ffmpeg",
            "-nostdin",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(source),
            "-vn",
            "-ac",
            "1",
            "-ar",
            "16000",
            "-c:a",
            "pcm_s16le",
            str(output),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg audio normalization failed: {result.stderr.strip()}")


def _wav_duration(path: Path) -> float:
    with wave.open(str(path), "rb") as source:
        return source.getnframes() / source.getframerate()


def _write_wav_chunk(source_path: Path, output_path: Path, start: float, end: float) -> None:
    with wave.open(str(source_path), "rb") as source:
        frame_rate = source.getframerate()
        source.setpos(min(round(start * frame_rate), source.getnframes()))
        frames = source.readframes(max(0, round((end - start) * frame_rate)))
        with wave.open(str(output_path), "wb") as output:
            output.setparams(source.getparams())
            output.writeframes(frames)


def _write_speaker_reference(
    source_path: Path,
    output_path: Path,
    segments: list[TranscriptSegment],
    *,
    budget_seconds: float,
) -> tuple[list[TranscriptSegment], float]:
    speakers = _speakers_in_order(segments)
    silence_seconds = 0.2
    speech_budget = budget_seconds - silence_seconds * max(0, len(speakers) - 1)
    if not speakers or speech_budget <= 0:
        return [], 0
    per_speaker = speech_budget / len(speakers)
    excerpts: list[TranscriptSegment] = []
    for speaker in speakers:
        candidates = [segment for segment in segments if segment.speaker == speaker and segment.end > segment.start]
        if not candidates:
            continue
        complete = [segment for segment in candidates if 0.5 <= segment.end - segment.start <= per_speaker]
        selected = max(complete or candidates, key=lambda segment: segment.end - segment.start)
        excerpts.append(
            TranscriptSegment(
                start=selected.start,
                end=min(selected.end, selected.start + per_speaker),
                speaker=selected.speaker,
                text=selected.text,
            )
        )

    reference: list[TranscriptSegment] = []
    with wave.open(str(source_path), "rb") as source:
        frame_rate = source.getframerate()
        bytes_per_frame = source.getnchannels() * source.getsampwidth()
        silence = b"\0" * (round(silence_seconds * frame_rate) * bytes_per_frame)
        cursor = 0.0
        with wave.open(str(output_path), "wb") as output:
            output.setparams(source.getparams())
            for index, excerpt in enumerate(excerpts):
                if index:
                    output.writeframes(silence)
                    cursor += len(silence) / bytes_per_frame / frame_rate
                source.setpos(min(round(excerpt.start * frame_rate), source.getnframes()))
                frames = source.readframes(max(0, round((excerpt.end - excerpt.start) * frame_rate)))
                frame_count = len(frames) / bytes_per_frame
                if frame_count <= 0:
                    continue
                output.writeframes(frames)
                end = cursor + frame_count / frame_rate
                reference.append(TranscriptSegment(cursor, end, excerpt.text, excerpt.speaker))
                cursor = end
    return reference, cursor


def _write_prefixed_wav_chunk(
    reference_path: Path,
    source_path: Path,
    output_path: Path,
    start: float,
    end: float,
) -> None:
    with wave.open(str(reference_path), "rb") as reference, wave.open(str(source_path), "rb") as source:
        frame_rate = source.getframerate()
        source.setpos(min(round(start * frame_rate), source.getnframes()))
        target_frames = source.readframes(max(0, round((end - start) * frame_rate)))
        with wave.open(str(output_path), "wb") as output:
            output.setparams(source.getparams())
            output.writeframes(reference.readframes(reference.getnframes()))
            output.writeframes(target_frames)


def _chunk_starts(
    duration: float,
    chunk_seconds: float,
    reference_seconds: float,
    overlap_seconds: float,
) -> list[float]:
    starts = [0.0]
    target_seconds = chunk_seconds - reference_seconds
    while starts[-1] + (chunk_seconds if len(starts) == 1 else target_seconds) < duration:
        if len(starts) == 1:
            starts.append(chunk_seconds - overlap_seconds)
        else:
            starts.append(starts[-1] + target_seconds - overlap_seconds)
    return starts


def _parse_segments(payload: object, duration: float) -> list[TranscriptSegment]:
    if not isinstance(payload, list):
        raise TypeError("MOSS JSON output must be a segment list")
    segments: list[TranscriptSegment] = []
    previous_start = -1.0
    for item in payload:
        if not isinstance(item, dict):
            raise TypeError("MOSS JSON output contains a non-object segment")
        try:
            start = float(item["start"])
            end = float(item["end"])
            speaker = str(item["speaker"])
            text = str(item["text"]).strip()
        except (KeyError, TypeError, ValueError) as exc:
            raise RuntimeError(f"Invalid MOSS segment: {item}") from exc
        if not math.isfinite(start) or not math.isfinite(end) or start < previous_start or start < 0 or end < start:
            raise RuntimeError(f"Invalid MOSS segment timestamps: {item}")
        if not _SPEAKER_PATTERN.fullmatch(speaker):
            raise RuntimeError(f"Invalid MOSS speaker label: {speaker}")
        previous_start = start
        if text and start < duration:
            segments.append(TranscriptSegment(start=start, end=min(end, duration), speaker=speaker, text=text))
    return segments


def _offset_segments(
    segments: list[TranscriptSegment],
    *,
    start: float,
    prefix_seconds: float,
    duration: float,
) -> list[TranscriptSegment]:
    return [
        TranscriptSegment(
            start=min(start + max(0, segment.start - prefix_seconds), duration),
            end=min(start + max(0, segment.end - prefix_seconds), duration),
            speaker=segment.speaker,
            text=segment.text,
        )
        for segment in segments
        if segment.end > prefix_seconds and start + max(0, segment.start - prefix_seconds) < duration
    ]


def _align_speakers(
    current: list[TranscriptSegment],
    *,
    comparisons: list[tuple[list[TranscriptSegment], list[TranscriptSegment], float, float]],
    known_speakers: set[str],
) -> list[TranscriptSegment]:
    local_speakers = _speakers_in_order(current)
    mapping: dict[str, str] = {}
    global_speakers = list(
        dict.fromkeys(
            speaker
            for previous, _, overlap_start, overlap_end in comparisons
            for speaker in _speakers_in_window(previous, overlap_start, overlap_end)
        )
    )
    candidates = sorted(
        (
            sum(
                _speaker_time_overlap(
                    previous,
                    compared,
                    global_label,
                    local,
                    overlap_start,
                    overlap_end,
                )
                for previous, compared, overlap_start, overlap_end in comparisons
            ),
            local,
            global_label,
        )
        for local in local_speakers
        for global_label in global_speakers
    )
    used_global: set[str] = set()
    for score, local, global_label in reversed(candidates):
        if score <= 0 or local in mapping or global_label in used_global:
            continue
        mapping[local] = global_label
        used_global.add(global_label)

    for local in local_speakers:
        if local in mapping:
            continue
        if local not in used_global:
            mapping[local] = local
            used_global.add(local)
        else:
            global_label = _next_speaker(known_speakers | used_global)
            mapping[local] = global_label
            used_global.add(global_label)

    return [
        TranscriptSegment(
            start=segment.start,
            end=segment.end,
            speaker=mapping.get(segment.speaker or ""),
            text=segment.text,
        )
        for segment in current
    ]


def _stitch_seam(
    previous: list[TranscriptSegment],
    current: list[TranscriptSegment],
    *,
    start: float,
    end: float,
) -> float:
    midpoint = (start + end) / 2
    intervals = sorted(
        (max(segment.start, start), min(segment.end, end))
        for segment in (*previous, *current)
        if segment.end > start and segment.start < end
    )
    if not intervals:
        return midpoint

    merged: list[tuple[float, float]] = []
    for left, right in intervals:
        if not merged or left > merged[-1][1]:
            merged.append((left, right))
        else:
            merged[-1] = (merged[-1][0], max(merged[-1][1], right))
    gaps = [(left[1], right[0]) for left, right in pairwise(merged) if right[0] - left[1] >= 0.2]
    if gaps:
        return min(
            ((left + right) / 2 for left, right in gaps),
            key=lambda candidate: abs(candidate - midpoint),
        )
    current_midpoints = [
        _midpoint(segment)
        for segment in current
        if segment.end > start and segment.start < end and start <= _midpoint(segment) <= end
    ]
    return min(current_midpoints, key=lambda candidate: abs(candidate - midpoint)) if current_midpoints else midpoint


def _deduplicate_boundary(
    previous: list[TranscriptSegment],
    current: list[TranscriptSegment],
) -> list[TranscriptSegment]:
    if not previous or not current:
        return current
    left = previous[-1]
    right = current[0]
    if left.speaker != right.speaker or right.start > left.end + 1:
        return current

    left_words = [match.group().lower() for match in re.finditer(r"\b[\w']+\b", left.text)]
    right_matches = list(re.finditer(r"\b[\w']+\b", right.text))
    right_words = [match.group().lower() for match in right_matches]
    overlap = next(
        (
            size
            for size in range(min(len(left_words), len(right_words)), 3, -1)
            if left_words[-size:] == right_words[:size]
        ),
        0,
    )
    if not overlap:
        return current
    if overlap == len(right_words):
        return current[1:]

    text = right.text[right_matches[overlap - 1].end() :].lstrip(" \t,.;:!?-—")
    start = right.start + (right.end - right.start) * overlap / len(right_words)
    trimmed = TranscriptSegment(start=start, end=right.end, speaker=right.speaker, text=text)
    return [trimmed, *current[1:]]


def _speakers_in_window(segments: list[TranscriptSegment], start: float, end: float) -> list[str]:
    return list(
        dict.fromkeys(
            segment.speaker for segment in segments if segment.speaker and segment.end > start and segment.start < end
        )
    )


def _speaker_time_overlap(
    previous: list[TranscriptSegment],
    current: list[TranscriptSegment],
    global_label: str,
    local_label: str,
    overlap_start: float,
    overlap_end: float,
) -> float:
    total = 0.0
    for left in previous:
        if left.speaker != global_label:
            continue
        left_start = max(left.start, overlap_start)
        left_end = min(left.end, overlap_end)
        for right in current:
            if right.speaker != local_label:
                continue
            intersection_start = max(left_start, right.start, overlap_start)
            intersection_end = min(left_end, right.end, overlap_end)
            total += max(0.0, intersection_end - intersection_start)
    return total


def _speakers_in_order(segments: list[TranscriptSegment]) -> list[str]:
    return list(dict.fromkeys(segment.speaker for segment in segments if segment.speaker))


def _speaker_number(speaker: str) -> int:
    return int(speaker[1:])


def _next_speaker(speakers: set[str]) -> str:
    return f"S{max((_speaker_number(speaker) for speaker in speakers), default=0) + 1:02d}"


def _midpoint(segment: TranscriptSegment) -> float:
    return (segment.start + segment.end) / 2
