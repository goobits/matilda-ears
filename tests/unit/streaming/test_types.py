"""Unit tests for streaming types."""

from matilda_ears.transcription.streaming.types import (
    TimestampedWord,
    StreamingResult,
    StreamingMetrics,
    StreamingError,
    StreamingState,
)


class TestTimestampedWord:
    """Test TimestampedWord dataclass."""

    def test_creation(self):
        """Test basic creation."""
        word = TimestampedWord(text="hello", start=1.0, end=1.5)
        assert word.text == "hello"
        assert word.start == 1.0
        assert word.end == 1.5
        assert word.confidence == 1.0  # Default confidence

    def test_with_confidence(self):
        """Test creation with confidence."""
        word = TimestampedWord(text="hello", start=1.0, end=1.5, confidence=0.95)
        assert word.confidence == 0.95

    def test_shift(self):
        """Test timestamp shifting."""
        word = TimestampedWord(text="hello", start=1.0, end=1.5, confidence=0.9)
        shifted = word.shift(5.0)

        assert shifted.text == "hello"
        assert shifted.start == 6.0
        assert shifted.end == 6.5
        assert shifted.confidence == 0.9

    def test_shift_negative(self):
        """Test negative shifting."""
        word = TimestampedWord(text="hello", start=5.0, end=5.5)
        shifted = word.shift(-2.0)

        assert shifted.start == 3.0
        assert shifted.end == 3.5

    def test_equality_case_insensitive(self):
        """Test that equality is case-insensitive."""
        word1 = TimestampedWord(text="Hello", start=1.0, end=1.5)
        word2 = TimestampedWord(text="hello", start=2.0, end=2.5)
        assert word1 == word2

    def test_hash(self):
        """Test that hash is case-insensitive."""
        word1 = TimestampedWord(text="Hello", start=1.0, end=1.5)
        word2 = TimestampedWord(text="hello", start=2.0, end=2.5)
        assert hash(word1) == hash(word2)


class TestStreamingResult:
    """Test StreamingResult dataclass."""

    def test_creation_defaults(self):
        """Test creation with defaults."""
        result = StreamingResult()
        assert result.confirmed_text == ""
        assert result.tentative_text == ""
        assert result.is_final == False
        assert result.confirmed_word_count == 0
        assert result.tentative_word_count == 0

    def test_creation_with_values(self):
        """Test creation with values."""
        result = StreamingResult(
            confirmed_text="hello world",
            tentative_text="today",
            is_final=False,
            confirmed_word_count=2,
            tentative_word_count=1,
        )
        assert result.confirmed_text == "hello world"
        assert result.tentative_text == "today"
        assert result.confirmed_word_count == 2

    def test_full_text(self):
        """Test full_text property."""
        result = StreamingResult(
            confirmed_text="hello world",
            tentative_text="today",
        )
        assert result.full_text == "hello world today"

    def test_full_text_only_confirmed(self):
        """Test full_text with only confirmed text."""
        result = StreamingResult(confirmed_text="hello world")
        assert result.full_text == "hello world"

    def test_full_text_only_tentative(self):
        """Test full_text with only tentative text."""
        result = StreamingResult(tentative_text="today")
        assert result.full_text == "today"

    def test_full_text_empty(self):
        """Test full_text when empty."""
        result = StreamingResult()
        assert result.full_text == ""

    def test_to_dict(self):
        """Test serialization to dict."""
        result = StreamingResult(
            confirmed_text="hello",
            tentative_text="world",
            is_final=True,
        )
        d = result.to_dict()

        assert d["confirmed_text"] == "hello"
        assert d["tentative_text"] == "world"
        assert d["is_final"] == True
        assert "confirmed_word_count" in d


class TestStreamingMetrics:
    """Test StreamingMetrics dataclass."""

    def test_creation_with_session_id(self):
        """Test creation with required session_id."""
        metrics = StreamingMetrics(session_id="test-session")
        assert metrics.session_id == "test-session"
        assert metrics.total_audio_seconds == 0.0
        assert metrics.transcriptions_run == 0
        assert metrics.confirmed_words == 0
        assert metrics.state == StreamingState.IDLE

    def test_creation_with_values(self):
        """Test creation with values."""
        metrics = StreamingMetrics(
            session_id="test-session",
            total_audio_seconds=30.5,
            transcriptions_run=15,
            confirmed_words=50,
            total_transcription_time_ms=1500.0,
        )
        assert metrics.total_audio_seconds == 30.5
        assert metrics.transcriptions_run == 15
        assert metrics.confirmed_words == 50


class TestStreamingErrors:
    """Test streaming error classes."""

    def test_streaming_error(self):
        """Test base StreamingError."""
        error = StreamingError("Test error")
        assert str(error) == "Test error"
        assert isinstance(error, Exception)


class TestStreamingState:
    """Test StreamingState enum."""

    def test_states(self):
        """Test all states exist."""
        assert StreamingState.IDLE.value == "idle"
        assert StreamingState.ACTIVE.value == "active"
        assert StreamingState.FINALIZING.value == "finalizing"
        assert StreamingState.COMPLETED.value == "completed"
        assert StreamingState.ERROR.value == "error"
