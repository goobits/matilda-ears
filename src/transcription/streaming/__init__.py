"""Streaming transcription framework.

This package provides a centralized streaming framework for real-time speech-to-text,
replacing backend-embedded streaming logic with a strategy-based approach.

Public API:
- StreamingSession: Main orchestrator for streaming sessions
- create_streaming_session(): Factory function to create sessions
- StreamingConfig: Configuration from config.json
- StreamingResult: Result type with confirmed/tentative text
- StreamingStrategy: Protocol for pluggable strategies
"""

from .config import StreamingConfig
from .types import StreamingResult, StreamingMetrics, StreamingError, StreamingState, TimestampedWord
from .buffer import AudioBuffer
from .hypothesis import HypothesisBuffer
from .session import StreamingSession
from .factory import create_streaming_session

__all__ = [
    # Main API
    "StreamingSession",
    "create_streaming_session",
    # Configuration
    "StreamingConfig",
    # Types
    "StreamingResult",
    "StreamingMetrics",
    "StreamingError",
    "StreamingState",
    "TimestampedWord",
    # Internal (for testing/extension)
    "AudioBuffer",
    "HypothesisBuffer",
]
