from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TranscriptSegment:
    start: float
    end: float
    text: str
    speaker: str | None = None


@dataclass(frozen=True)
class Transcript:
    text: str
    segments: tuple[TranscriptSegment, ...]
    language: str | None
    duration: float | None
    backend: str
