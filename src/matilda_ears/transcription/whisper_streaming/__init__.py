"""WhisperStreaming adapter for real-time transcription.

This module wraps the whisper_streaming library (from UFAL) to provide
streaming transcription with LocalAgreement for stable partial results.

See: https://github.com/ufal/whisper_streaming
"""

from .adapter import WhisperStreamingAdapter, WhisperStreamingResult

__all__ = ["WhisperStreamingAdapter", "WhisperStreamingResult"]
