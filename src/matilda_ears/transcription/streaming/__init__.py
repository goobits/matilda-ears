"""Streaming transcription using SimulStreaming.

Provides real-time streaming transcription with alpha (stable) and
omega (unstable) text separation using AlignAtt attention-guided decoding.
"""

from .adapter import (
    StreamingAdapter,
    StreamingConfig,
    StreamingResult,
    AlphaOmegaWrapper,
    get_shared_adapter,
)
from .parakeet_adapter import ParakeetStreamingAdapter
from .session import StreamingSession, SessionResult

__all__ = [
    "StreamingAdapter",
    "StreamingConfig",
    "StreamingResult",
    "StreamingSession",
    "SessionResult",
    "AlphaOmegaWrapper",
    "get_shared_adapter",
    "ParakeetStreamingAdapter",
]
