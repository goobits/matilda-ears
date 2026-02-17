"""Streaming transcription types.

Kept separate from implementation to reduce import graph complexity.
"""

from __future__ import annotations

import os
from pathlib import Path
from dataclasses import dataclass


def _get_model_cache_dir() -> str:
    """Get XDG-compliant cache directory for whisper models."""
    xdg_cache = os.environ.get("XDG_CACHE_HOME", str(Path("~/.cache").expanduser()))
    return str(Path(xdg_cache) / "matilda-ears" / "whisper")


@dataclass
class StreamingResult:
    """Result from streaming transcription."""

    alpha_text: str = ""  # Stable/confirmed text (blue)
    omega_text: str = ""  # Unstable/tentative text (grey)
    is_final: bool = False
    audio_duration_seconds: float = 0.0


@dataclass
class StreamingConfig:
    """Configuration for streaming adapter."""

    backend: str = "whisper"  # whisper or parakeet
    language: str = "en"
    model_size: str = "tiny"  # tiny (fast), small, medium, large-v3
    model_cache_dir: str = ""  # Cache dir for models (default: ~/.cache/matilda-ears/whisper)
    frame_threshold: int = 25  # AlignAtt threshold (frames from end)
    audio_max_len: float = 30.0  # Max buffer length in seconds
    audio_min_len: float = 0.0  # Min buffer before processing
    segment_length: float = 1.0  # Chunk size for processing
    beams: int = 1  # Beam search (1 = greedy)
    task: str = "transcribe"  # transcribe or translate
    never_fire: bool = True  # Always show omega (unstable last word)
    vad_enabled: bool = True  # Skip silence with VAD gating
    vad_threshold: float = 0.5  # Speech probability threshold
    parakeet_context_size: tuple[int, int] = (128, 128)
    parakeet_depth: int = 1

    def __post_init__(self) -> None:
        if not self.model_cache_dir:
            self.model_cache_dir = _get_model_cache_dir()
