#!/usr/bin/env python3
"""Custom exceptions for transcription client operations.

This module defines the exception hierarchy for transcription-related errors.
"""


class TranscriptionError(Exception):
    """Base exception for transcription-related errors."""


class StreamingError(TranscriptionError):
    """Exception for streaming-related errors."""


class TranscriptionConnectionError(TranscriptionError):
    """Exception for connection-related errors."""
