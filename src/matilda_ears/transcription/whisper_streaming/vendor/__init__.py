"""Vendored whisper_streaming from UFAL.

Source: https://github.com/ufal/whisper_streaming
"""

from .whisper_online import (
    FasterWhisperASR,
    OnlineASRProcessor,
    HypothesisBuffer,
)

__all__ = ["FasterWhisperASR", "OnlineASRProcessor", "HypothesisBuffer"]
