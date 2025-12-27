#!/usr/bin/env python3
"""Transcription client module - Public API exports.

This module provides the public API for the transcription client package,
consolidating all transcription-related functionality.
"""

from .exceptions import (
    TranscriptionError,
    StreamingError,
    TranscriptionConnectionError,
)
from .circuit_breaker import (
    CircuitState,
    CircuitBreakerConfig,
    CircuitBreaker,
)
from .streaming import StreamingAudioClient, PartialResult, PartialResultCallback
from .batch import BatchTranscriber
from .unified import TranscriptionClient

__all__ = [
    # Exceptions
    "TranscriptionError",
    "StreamingError",
    "TranscriptionConnectionError",
    # Circuit breaker
    "CircuitState",
    "CircuitBreakerConfig",
    "CircuitBreaker",
    # Clients
    "StreamingAudioClient",
    "BatchTranscriber",
    "TranscriptionClient",
    # Streaming types
    "PartialResult",
    "PartialResultCallback",
]
