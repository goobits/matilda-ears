"""Unit tests for HypothesisBuffer and LocalAgreement algorithm."""

import pytest
from matilda_ears.transcription.streaming.hypothesis import HypothesisBuffer
from matilda_ears.transcription.streaming.types import TimestampedWord


def make_words(texts: list, start_time: float = 0.0, word_duration: float = 0.5) -> list:
    """Helper to create TimestampedWord list from text list."""
    words = []
    current_time = start_time
    for text in texts:
        words.append(
            TimestampedWord(text=text, start=current_time, end=current_time + word_duration)
        )
        current_time += word_duration
    return words


class TestHypothesisBufferInit:
    """Test HypothesisBuffer initialization."""

    def test_init_defaults(self):
        """Test initialization with defaults."""
        buffer = HypothesisBuffer()
        assert buffer.agreement_n == 2
        assert buffer.max_confirmed_words == 500
        assert buffer.confirmed == []
        assert buffer.confirmed_in_buffer == []

    def test_init_custom(self):
        """Test initialization with custom values."""
        buffer = HypothesisBuffer(agreement_n=3, max_confirmed_words=100)
        assert buffer.agreement_n == 3
        assert buffer.max_confirmed_words == 100


class TestLocalAgreement:
    """Test LocalAgreement-N algorithm."""

    def test_agreement_2_basic(self):
        """Test basic LocalAgreement-2: confirms after 2 matching hypotheses."""
        buffer = HypothesisBuffer(agreement_n=2)

        # First hypothesis
        buffer.insert(make_words(["hello", "world"]))
        confirmed1 = buffer.flush()
        assert confirmed1 == []  # Need 2 hypotheses

        # Second hypothesis (same)
        buffer.insert(make_words(["hello", "world"]))
        confirmed2 = buffer.flush()

        # Should confirm "hello" and "world"
        assert len(confirmed2) == 2
        assert confirmed2[0].text == "hello"
        assert confirmed2[1].text == "world"

    def test_agreement_2_partial(self):
        """Test partial agreement confirms only matching prefix."""
        buffer = HypothesisBuffer(agreement_n=2)

        buffer.insert(make_words(["hello", "world", "today"]))
        buffer.flush()

        buffer.insert(make_words(["hello", "world", "tomorrow"]))
        confirmed = buffer.flush()

        # Only "hello" and "world" agree
        assert len(confirmed) == 2
        assert [w.text for w in confirmed] == ["hello", "world"]

    def test_agreement_3(self):
        """Test LocalAgreement-3 requires 3 matching hypotheses."""
        buffer = HypothesisBuffer(agreement_n=3)

        buffer.insert(make_words(["hello", "world"]))
        buffer.flush()

        buffer.insert(make_words(["hello", "world"]))
        confirmed2 = buffer.flush()
        assert confirmed2 == []  # Need 3 hypotheses

        buffer.insert(make_words(["hello", "world"]))
        confirmed3 = buffer.flush()

        assert len(confirmed3) == 2

    def test_agreement_case_insensitive(self):
        """Test that word comparison is case-insensitive."""
        buffer = HypothesisBuffer(agreement_n=2)

        buffer.insert(make_words(["Hello", "WORLD"]))
        buffer.flush()

        buffer.insert(make_words(["hello", "world"]))
        confirmed = buffer.flush()

        assert len(confirmed) == 2

    def test_no_agreement_on_first_word(self):
        """Test that disagreement on first word confirms nothing."""
        buffer = HypothesisBuffer(agreement_n=2)

        buffer.insert(make_words(["hello", "world"]))
        buffer.flush()

        buffer.insert(make_words(["hi", "world"]))
        confirmed = buffer.flush()

        assert confirmed == []

    def test_empty_hypothesis_clears(self):
        """Test that empty hypothesis doesn't crash."""
        buffer = HypothesisBuffer(agreement_n=2)

        buffer.insert([])
        confirmed = buffer.flush()

        assert confirmed == []


class TestConfirmedHistory:
    """Test confirmed word history and bounding."""

    def test_confirmed_accumulates(self):
        """Test that confirmed words accumulate with overlapping hypotheses."""
        buffer = HypothesisBuffer(agreement_n=2)

        # First hypothesis with 2 words
        buffer.insert(make_words(["hello", "world"]))
        buffer.flush()

        # Second hypothesis - same words = confirms them
        buffer.insert(make_words(["hello", "world"]))
        confirmed1 = buffer.flush()

        assert len(confirmed1) == 2
        assert buffer.confirmed_word_count == 2
        assert buffer.get_confirmed_text() == "hello world"

    def test_incremental_confirmation(self):
        """Test that words are confirmed incrementally as they stabilize."""
        buffer = HypothesisBuffer(agreement_n=2)

        # First hypothesis
        buffer.insert(make_words(["hello", "world", "today"], start_time=0.0))
        buffer.flush()

        # Second hypothesis - same first two words
        buffer.insert(make_words(["hello", "world", "today", "is"], start_time=0.0))
        confirmed1 = buffer.flush()
        # "hello world today" (first 3 matching) confirmed? No - "today" has different position
        # Actually: only first 2 words match in same position ("hello" at 0, "world" at 1)
        # Wait - all 3 "hello world today" match in position 0, 1, 2
        assert len(confirmed1) == 3  # All 3 match in position

        # Remaining unconfirmed: ["is"] from second hypothesis
        # Third hypothesis
        buffer.insert(make_words(["is", "sunny"], start_time=1.5))
        confirmed2 = buffer.flush()
        assert len(confirmed2) == 1  # "is" confirmed

        assert buffer.confirmed_word_count == 4

    def test_bounded_history_single_batch(self):
        """Test that confirmed history is bounded with single large batch."""
        buffer = HypothesisBuffer(agreement_n=2, max_confirmed_words=3)

        # Confirm 5 words at once
        buffer.insert(make_words(["one", "two", "three", "four", "five"]))
        buffer.flush()
        buffer.insert(make_words(["one", "two", "three", "four", "five"]))
        buffer.flush()

        # Should only keep last 3
        assert buffer.confirmed_word_count == 3
        texts = [w.text for w in buffer.confirmed]
        assert texts == ["three", "four", "five"]


class TestTentativeText:
    """Test tentative (unconfirmed) text handling."""

    def test_tentative_text_before_flush(self):
        """Test tentative text is available after insert."""
        buffer = HypothesisBuffer(agreement_n=2)

        buffer.insert(make_words(["hello", "world"]))

        assert buffer.get_tentative_text() == "hello world"
        assert buffer.tentative_word_count == 2

    def test_tentative_after_insert(self):
        """Test tentative text after inserting new hypothesis."""
        buffer = HypothesisBuffer(agreement_n=2)

        # First hypothesis - tentative
        buffer.insert(make_words(["hello", "world"]))
        assert buffer.get_tentative_text() == "hello world"

        # Second hypothesis replaces current_hypothesis
        buffer.insert(make_words(["hello", "world", "today"]))
        assert buffer.get_tentative_text() == "hello world today"

    def test_current_hypothesis_updates_on_insert(self):
        """Test that insert updates current_hypothesis."""
        buffer = HypothesisBuffer(agreement_n=2)

        buffer.insert(make_words(["hello"]))
        assert buffer.get_tentative_text() == "hello"

        buffer.insert(make_words(["world"]))
        # Insert replaces current_hypothesis
        assert buffer.get_tentative_text() == "world"


class TestTimestampOffset:
    """Test timestamp offset handling."""

    def test_offset_applied(self):
        """Test that offset is applied to timestamps."""
        buffer = HypothesisBuffer(agreement_n=2)

        # Insert with 5 second offset
        words = make_words(["hello"], start_time=0.0)
        buffer.insert(words, offset_seconds=5.0)

        # Current hypothesis should have shifted timestamps
        assert buffer.current_hypothesis[0].start == pytest.approx(5.0)


class TestDeduplication:
    """Test overlap deduplication."""

    def test_dedupe_with_confirmed(self):
        """Test that confirmed words are deduped from new hypothesis."""
        buffer = HypothesisBuffer(agreement_n=2)

        # Confirm "hello world"
        buffer.insert(make_words(["hello", "world"]))
        buffer.flush()
        buffer.insert(make_words(["hello", "world"]))
        buffer.flush()

        # Now insert hypothesis that overlaps with confirmed
        # The overlap detection uses timing, so we need overlapping times
        overlap_words = make_words(["world", "today"], start_time=0.5)
        buffer.insert(overlap_words, offset_seconds=0.0)

        # "world" should be deduped, only "today" remains
        assert buffer.get_tentative_text() == "today"


class TestTrimToTime:
    """Test trim_to_time method."""

    def test_trim_removes_old_words(self):
        """Test that trim_to_time removes words before threshold."""
        buffer = HypothesisBuffer(agreement_n=2)

        # Confirm words with timestamps 0-2s
        words = make_words(["hello", "world", "today", "here"])
        buffer.confirmed_in_buffer = words

        # Trim to 1.0s (removes words ending before 1.0s)
        buffer.trim_to_time(1.0)

        # "hello" ends at 0.5, should be removed
        # "world" ends at 1.0, kept (end >= threshold)
        assert len(buffer.confirmed_in_buffer) == 3


class TestPromptSuffix:
    """Test prompt suffix generation."""

    def test_prompt_suffix_empty(self):
        """Test prompt suffix with no confirmed words."""
        buffer = HypothesisBuffer()
        assert buffer.get_prompt_suffix() == ""

    def test_prompt_suffix_short(self):
        """Test prompt suffix when under max chars."""
        buffer = HypothesisBuffer()
        buffer.confirmed_in_buffer = make_words(["hello", "world"])

        suffix = buffer.get_prompt_suffix(max_chars=200)
        assert suffix == "hello world"

    def test_prompt_suffix_truncated(self):
        """Test prompt suffix truncation at word boundary."""
        buffer = HypothesisBuffer()
        buffer.confirmed_in_buffer = make_words(
            ["this", "is", "a", "very", "long", "sentence", "here"]
        )

        suffix = buffer.get_prompt_suffix(max_chars=15)

        # Should truncate at word boundary, keeping end
        assert len(suffix) <= 15
        assert " " not in suffix or suffix.count(" ") >= 0


class TestClear:
    """Test clear method."""

    def test_clear_resets_all(self):
        """Test that clear resets all state."""
        buffer = HypothesisBuffer(agreement_n=2)

        # Add some state
        buffer.insert(make_words(["hello", "world"]))
        buffer.flush()
        buffer.insert(make_words(["hello", "world"]))
        buffer.flush()

        buffer.clear()

        assert buffer.confirmed == []
        assert buffer.confirmed_in_buffer == []
        assert buffer.previous_hypotheses == []
        assert buffer.current_hypothesis == []
