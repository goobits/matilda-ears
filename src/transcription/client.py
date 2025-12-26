#!/usr/bin/env python3
"""Unified Transcription Client - Thin re-export facade.

This module provides backward-compatible imports for all transcription client
functionality. All implementations have been moved to the client/ subpackage.

Usage:
    from transcription.client import TranscriptionClient
    from transcription.client import StreamingAudioClient
    from transcription.client import TranscriptionError
"""

from .client import (
    # Exceptions
    TranscriptionError,
    StreamingError,
    TranscriptionConnectionError,
    # Circuit breaker
    CircuitState,
    CircuitBreakerConfig,
    CircuitBreaker,
    # Clients
    StreamingAudioClient,
    BatchTranscriber,
    TranscriptionClient,
)

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
]
