"""Type definitions for streaming transcription.

Provides:
- StreamingResult: Partial result with confirmed/tentative text
- StreamingMetrics: Performance and state metrics
- TimestampedWord: Word with timing information
- StreamingError: Base exception for streaming errors
"""

from dataclasses import dataclass
from enum import Enum


class StreamingState(Enum):
    """State of a streaming session."""

    IDLE = "idle"
    ACTIVE = "active"
    FINALIZING = "finalizing"
    COMPLETED = "completed"
    ERROR = "error"


@dataclass
class TimestampedWord:
    """A word with timing information.

    Used for LocalAgreement-2 algorithm and prompt continuity.
    """

    text: str
    start: float  # Start time in seconds (relative to stream start)
    end: float  # End time in seconds
    confidence: float = 1.0

    def shift(self, offset_seconds: float) -> "TimestampedWord":
        """Return a new word with timestamps shifted by offset.

        Used when buffer is trimmed to maintain absolute timestamps.
        """
        return TimestampedWord(
            text=self.text,
            start=self.start + offset_seconds,
            end=self.end + offset_seconds,
            confidence=self.confidence,
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, TimestampedWord):
            return False
        # Compare by text only for LocalAgreement matching
        return self.text.lower() == other.text.lower()

    def __hash__(self) -> int:
        return hash(self.text.lower())


@dataclass
class StreamingResult:
    """Result from processing a streaming audio chunk.

    Provides the client with:
    - confirmed_text: Text that has been confirmed via LocalAgreement
    - tentative_text: Current hypothesis that may change
    - is_final: True if this is the final result for the session
    """

    confirmed_text: str = ""
    tentative_text: str = ""
    is_final: bool = False

    # Metrics
    confirmed_word_count: int = 0
    tentative_word_count: int = 0

    # Timing
    audio_duration_seconds: float = 0.0
    processing_time_ms: float = 0.0

    @property
    def full_text(self) -> str:
        """Combined confirmed and tentative text."""
        if self.confirmed_text and self.tentative_text:
            return f"{self.confirmed_text} {self.tentative_text}"
        return self.confirmed_text or self.tentative_text

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "confirmed_text": self.confirmed_text,
            "tentative_text": self.tentative_text,
            "is_final": self.is_final,
            "confirmed_word_count": self.confirmed_word_count,
            "tentative_word_count": self.tentative_word_count,
            "audio_duration_seconds": self.audio_duration_seconds,
            "processing_time_ms": self.processing_time_ms,
        }


@dataclass
class StreamingMetrics:
    """Metrics for a streaming session.

    Used for monitoring and debugging streaming performance.
    """

    session_id: str
    state: StreamingState = StreamingState.IDLE

    # Audio stats
    total_audio_seconds: float = 0.0
    buffer_audio_seconds: float = 0.0
    chunks_received: int = 0

    # Transcription stats
    transcriptions_run: int = 0
    total_transcription_time_ms: float = 0.0

    # Hypothesis stats
    confirmed_words: int = 0
    words_in_buffer: int = 0

    # Timing
    session_start_time: float | None = None
    last_activity_time: float | None = None

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "session_id": self.session_id,
            "state": self.state.value,
            "total_audio_seconds": self.total_audio_seconds,
            "buffer_audio_seconds": self.buffer_audio_seconds,
            "chunks_received": self.chunks_received,
            "transcriptions_run": self.transcriptions_run,
            "avg_transcription_time_ms": (
                self.total_transcription_time_ms / self.transcriptions_run
                if self.transcriptions_run > 0
                else 0.0
            ),
            "confirmed_words": self.confirmed_words,
            "words_in_buffer": self.words_in_buffer,
        }


class StreamingError(Exception):
    """Base exception for streaming errors."""



class SessionNotFoundError(StreamingError):
    """Raised when a session ID is not found."""

    def __init__(self, session_id: str):
        self.session_id = session_id
        super().__init__(f"Session not found: {session_id}")


class SessionAlreadyExistsError(StreamingError):
    """Raised when trying to create a session that already exists."""

    def __init__(self, session_id: str):
        self.session_id = session_id
        super().__init__(f"Session already exists: {session_id}")


class SessionTimeoutError(StreamingError):
    """Raised when a session times out due to inactivity."""

    def __init__(self, session_id: str, timeout_seconds: float):
        self.session_id = session_id
        self.timeout_seconds = timeout_seconds
        super().__init__(f"Session {session_id} timed out after {timeout_seconds}s")


class TranscriptionError(StreamingError):
    """Raised when transcription fails."""

    def __init__(self, message: str, cause: Exception | None = None):
        self.cause = cause
        super().__init__(message)
