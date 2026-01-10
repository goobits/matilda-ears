"""Hypothesis buffer with LocalAgreement algorithm.

Based on whisper_streaming's approach:
- Compare consecutive hypotheses to find stable words
- Use n-gram matching for deduplication
- Track committed vs uncommitted words with timestamps
"""

import logging

from .types import TimestampedWord

logger = logging.getLogger(__name__)


class HypothesisBuffer:
    """Buffer for managing hypotheses with LocalAgreement confirmation.

    The LocalAgreement algorithm confirms words only when they appear in
    the same position across consecutive transcription hypotheses. This
    provides stability while maintaining low latency.

    Based on whisper_streaming implementation:
    - commited_in_buffer: All confirmed words
    - buffer: Previous hypothesis (unconfirmed words from last iteration)
    - new: Current hypothesis (unconfirmed words from this iteration)

    Words are confirmed when they match between buffer and new.
    """

    def __init__(self, agreement_n: int = 2, max_confirmed_words: int = 500):
        """Initialize hypothesis buffer.

        Args:
            agreement_n: Number of consecutive agreements required (default 2)
            max_confirmed_words: Maximum confirmed words to retain

        """
        self.agreement_n = agreement_n
        self.max_confirmed_words = max_confirmed_words

        # Confirmed words (permanently committed)
        self.commited_in_buffer: list[TimestampedWord] = []

        # Previous iteration's unconfirmed words
        self.buffer: list[TimestampedWord] = []

        # Current iteration's unconfirmed words
        self.new: list[TimestampedWord] = []

        # Timestamp of last confirmed word (for filtering)
        self.last_commited_time: float = 0.0

    def insert(self, words: list[TimestampedWord], offset_seconds: float = 0.0) -> None:
        """Insert a new transcription hypothesis.

        Filters words by timestamp and deduplicates against committed words.

        Args:
            words: Timestamped words from transcription
            offset_seconds: Buffer offset to add to timestamps

        """
        # Shift timestamps to absolute time
        shifted = [w.shift(offset_seconds) for w in words]

        # Filter to only words after last committed time (with 100ms tolerance)
        cutoff_time = self.last_commited_time - 0.1
        self.new = [w for w in shifted if w.end > cutoff_time]

        # Deduplicate: remove n-grams that match the tail of committed words
        self._dedupe_ngrams()

        logger.debug(
            f"Inserted hypothesis: {len(words)} words -> {len(self.new)} after filter/dedup"
        )

    @staticmethod
    def _normalize_word(text: str) -> str:
        """Normalize word for comparison (lowercase, strip, remove punctuation)."""
        import re
        # Lowercase, strip whitespace, remove punctuation
        return re.sub(r'[^\w\s]', '', text.lower().strip())

    def _dedupe_ngrams(self) -> None:
        """Remove matching n-grams between committed tail and new head.

        Searches for matching sequences of 1-5 words and removes them from new.
        """
        if not self.commited_in_buffer or not self.new:
            return

        # Get normalized text for comparison (no punctuation)
        committed_texts = [self._normalize_word(w.text) for w in self.commited_in_buffer]
        new_texts = [self._normalize_word(w.text) for w in self.new]

        # Try n-grams from 5 down to 1
        for n in range(min(5, len(committed_texts), len(new_texts)), 0, -1):
            # Get last n words of committed
            committed_ngram = committed_texts[-n:]
            # Get first n words of new
            new_ngram = new_texts[:n]

            if committed_ngram == new_ngram:
                # Found match - remove these words from new
                logger.debug(f"Dedup: removing {n} matching words from start of new")
                self.new = self.new[n:]
                return

    def flush(self) -> list[TimestampedWord]:
        """Apply LocalAgreement and confirm stable words.

        Compares current hypothesis (new) with previous hypothesis (buffer).
        Words that match in both get confirmed.

        Returns:
            List of newly confirmed words

        """
        if not self.new:
            self.buffer = []
            return []

        # Find words that match between buffer and new (LocalAgreement)
        newly_confirmed = []

        buffer_idx = 0
        new_idx = 0

        while buffer_idx < len(self.buffer) and new_idx < len(self.new):
            buffer_word = self.buffer[buffer_idx]
            new_word = self.new[new_idx]

            # Compare word text (normalized - no punctuation)
            if self._normalize_word(buffer_word.text) == self._normalize_word(new_word.text):
                # Match! This word is confirmed
                newly_confirmed.append(new_word)
                buffer_idx += 1
                new_idx += 1
            else:
                # Mismatch - stop confirming
                break

        # Add confirmed words to committed buffer
        if newly_confirmed:
            self.commited_in_buffer.extend(newly_confirmed)
            self.last_commited_time = newly_confirmed[-1].end

            # Enforce bounded history
            if len(self.commited_in_buffer) > self.max_confirmed_words:
                overflow = len(self.commited_in_buffer) - self.max_confirmed_words
                self.commited_in_buffer = self.commited_in_buffer[-self.max_confirmed_words:]
                logger.debug(f"Trimmed committed history: removed {overflow} oldest words")

            logger.info(
                f"Confirmed {len(newly_confirmed)} words, "
                f"total committed: {len(self.commited_in_buffer)}"
            )

        # Move remaining new words to buffer for next comparison
        self.buffer = self.new[new_idx:] if new_idx < len(self.new) else []
        self.new = []

        return newly_confirmed

    def get_confirmed_text(self) -> str:
        """Get confirmed text as a string."""
        return " ".join(w.text for w in self.commited_in_buffer)

    def get_tentative_text(self) -> str:
        """Get current tentative (unconfirmed) text."""
        return " ".join(w.text for w in self.buffer)

    def get_prompt_suffix(self, max_chars: int = 200) -> str:
        """Get suffix of confirmed text for prompt continuity.

        Returns the last max_chars characters of confirmed text,
        broken at word boundaries.

        Args:
            max_chars: Maximum characters to return

        Returns:
            Suffix string for prompt

        """
        if not self.commited_in_buffer:
            return ""

        # Build from recent confirmed words
        words = [w.text for w in self.commited_in_buffer]
        text = " ".join(words)

        if len(text) <= max_chars:
            return text

        # Truncate at word boundary
        truncated = text[-max_chars:]
        first_space = truncated.find(" ")
        if first_space > 0:
            truncated = truncated[first_space + 1:]

        return truncated

    def trim_to_time(self, absolute_time: float) -> None:
        """Remove words from buffer before given time.

        Called when the audio buffer is trimmed.

        Args:
            absolute_time: Absolute time in seconds

        """
        # Keep committed words (they're permanent)
        # Only trim from current buffer if needed
        self.buffer = [w for w in self.buffer if w.end >= absolute_time]

    def clear(self) -> None:
        """Clear all hypothesis state."""
        self.commited_in_buffer.clear()
        self.buffer.clear()
        self.new.clear()
        self.last_commited_time = 0.0

    @property
    def confirmed_word_count(self) -> int:
        """Number of confirmed words."""
        return len(self.commited_in_buffer)

    @property
    def tentative_word_count(self) -> int:
        """Number of tentative (unconfirmed) words."""
        return len(self.buffer)

    # Aliases for compatibility with existing code
    @property
    def confirmed(self) -> list[TimestampedWord]:
        """Alias for commited_in_buffer."""
        return self.commited_in_buffer

    @property
    def confirmed_in_buffer(self) -> list[TimestampedWord]:
        """Alias for commited_in_buffer (compatibility)."""
        return self.commited_in_buffer

    @property
    def current_hypothesis(self) -> list[TimestampedWord]:
        """Alias for buffer (compatibility)."""
        return self.buffer

    @current_hypothesis.setter
    def current_hypothesis(self, value: list[TimestampedWord]) -> None:
        """Setter for buffer (compatibility)."""
        self.buffer = value

    @property
    def previous_hypotheses(self) -> list[list[TimestampedWord]]:
        """Compatibility property - returns buffer wrapped in list."""
        return [self.buffer] if self.buffer else []

    @previous_hypotheses.setter
    def previous_hypotheses(self, value: list[list[TimestampedWord]]) -> None:
        """Compatibility setter - sets buffer from last item."""
        if value:
            self.buffer = value[-1] if value else []

    def force_confirm_all(self) -> None:
        """Force-confirm all tentative words (for finalize)."""
        if self.buffer:
            self.commited_in_buffer.extend(self.buffer)
            if self.buffer:
                self.last_commited_time = self.buffer[-1].end
            self.buffer = []
        if self.new:
            self.commited_in_buffer.extend(self.new)
            if self.new:
                self.last_commited_time = self.new[-1].end
            self.new = []
