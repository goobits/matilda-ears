"""Hypothesis buffer with LocalAgreement-2 algorithm.

Implements the core streaming stability algorithm:
- Maintains confirmed words (agreed upon in N consecutive hypotheses)
- Tracks words still in the audio buffer for overlap handling
- Provides prompt suffix for continuity
"""

from typing import List
import logging

from .types import TimestampedWord

logger = logging.getLogger(__name__)


class HypothesisBuffer:
    """Buffer for managing hypotheses with LocalAgreement-2 confirmation.

    The LocalAgreement-N algorithm confirms words only when they appear in
    the same position across N consecutive transcription hypotheses. This
    provides stability while maintaining low latency.

    Key concepts:
    - confirmed: All confirmed words (capped by max_confirmed_words)
    - confirmed_in_buffer: Subset of confirmed words still in audio window
    - previous_hypothesis: Last transcription for comparison
    - current_hypothesis: Current transcription being processed

    Example:
        buffer = HypothesisBuffer(agreement_n=2, max_confirmed_words=500)

        # Process each transcription result
        buffer.insert(words, offset_seconds=5.0)
        newly_confirmed = buffer.flush()

        # Get text for display
        confirmed_text = buffer.get_confirmed_text()
        tentative_text = buffer.get_tentative_text()

    """

    def __init__(self, agreement_n: int = 2, max_confirmed_words: int = 500):
        """Initialize hypothesis buffer.

        Args:
            agreement_n: Number of consecutive agreements required to confirm
            max_confirmed_words: Maximum confirmed words to retain (bounded history)

        """
        self.agreement_n = agreement_n
        self.max_confirmed_words = max_confirmed_words

        # Confirmed words (full history, bounded)
        self.confirmed: List[TimestampedWord] = []

        # Confirmed words still in current audio buffer
        # Used for prompt continuity and overlap deduplication
        self.confirmed_in_buffer: List[TimestampedWord] = []

        # Hypothesis tracking for LocalAgreement
        self.previous_hypotheses: List[List[TimestampedWord]] = []
        self.current_hypothesis: List[TimestampedWord] = []

    def insert(self, words: List[TimestampedWord], offset_seconds: float = 0.0) -> None:
        """Insert a new transcription hypothesis.

        Words are shifted by offset_seconds to maintain absolute timestamps.
        Overlap with confirmed_in_buffer is detected and handled.

        Args:
            words: Timestamped words from transcription
            offset_seconds: Buffer offset to add to timestamps

        """
        # Shift timestamps to absolute time
        shifted = [w.shift(offset_seconds) for w in words]

        # Remove overlap with already-confirmed words in buffer
        self.current_hypothesis = self._dedupe_overlap(shifted)

        logger.debug(
            f"Inserted hypothesis: {len(words)} words, "
            f"{len(self.current_hypothesis)} after dedup"
        )

    def flush(self) -> List[TimestampedWord]:
        """Apply LocalAgreement and confirm stable words.

        Compares current hypothesis with previous hypotheses to find words
        that appear in the same position across agreement_n hypotheses.

        Returns:
            List of newly confirmed words

        """
        if not self.current_hypothesis:
            return []

        # Add current to hypothesis history
        self.previous_hypotheses.append(self.current_hypothesis)

        # Keep only the last agreement_n hypotheses
        if len(self.previous_hypotheses) > self.agreement_n:
            self.previous_hypotheses = self.previous_hypotheses[-self.agreement_n :]

        # Need at least agreement_n hypotheses to confirm
        if len(self.previous_hypotheses) < self.agreement_n:
            logger.debug(
                f"Not enough hypotheses yet: {len(self.previous_hypotheses)}/{self.agreement_n}"
            )
            return []

        # Find agreed-upon words
        newly_confirmed = self._local_agreement()

        if newly_confirmed:
            # Add to confirmed lists
            self.confirmed.extend(newly_confirmed)
            self.confirmed_in_buffer.extend(newly_confirmed)

            # Enforce bounded history
            if len(self.confirmed) > self.max_confirmed_words:
                overflow = len(self.confirmed) - self.max_confirmed_words
                self.confirmed = self.confirmed[-self.max_confirmed_words :]
                logger.debug(f"Trimmed confirmed history: removed {overflow} oldest words")

            logger.info(
                f"Confirmed {len(newly_confirmed)} words, "
                f"total confirmed: {len(self.confirmed)}"
            )

        return newly_confirmed

    def _local_agreement(self) -> List[TimestampedWord]:
        """Apply LocalAgreement-N algorithm.

        Words are confirmed when they appear in the same position (relative to
        confirmed_in_buffer) across all recent hypotheses.

        Returns:
            List of newly confirmed words

        """
        if len(self.previous_hypotheses) < self.agreement_n:
            return []

        # Get the relevant hypotheses
        hypotheses = self.previous_hypotheses[-self.agreement_n :]

        # Find minimum length
        min_len = min(len(h) for h in hypotheses)
        if min_len == 0:
            return []

        # Find agreed words from the start
        agreed_count = 0
        for i in range(min_len):
            # Check if all hypotheses agree on word at position i
            reference_word = hypotheses[0][i]
            all_agree = all(
                h[i].text.lower() == reference_word.text.lower()
                for h in hypotheses[1:]
            )

            if all_agree:
                agreed_count += 1
            else:
                # Stop at first disagreement
                break

        if agreed_count == 0:
            return []

        # Get newly confirmed words (from the oldest hypothesis for best timestamps)
        newly_confirmed = hypotheses[0][:agreed_count]

        # Remove confirmed words from all hypothesis histories
        self.previous_hypotheses = [h[agreed_count:] for h in self.previous_hypotheses]

        return newly_confirmed

    def _dedupe_overlap(self, words: List[TimestampedWord]) -> List[TimestampedWord]:
        """Remove words that overlap with confirmed_in_buffer.

        Uses timing to detect overlap: if a word's start time is before
        the end of the last confirmed word, it's likely a duplicate.

        Args:
            words: Words to deduplicate

        Returns:
            Words with overlap removed

        """
        if not self.confirmed_in_buffer or not words:
            return words

        # Find where new words start (after confirmed words)
        last_confirmed_end = self.confirmed_in_buffer[-1].end

        # Skip words that overlap with confirmed
        result = []
        for word in words:
            # Word starts after last confirmed ends
            if word.start >= last_confirmed_end - 0.1:  # 100ms tolerance
                result.append(word)
            elif word.end > last_confirmed_end:
                # Partial overlap - check if it's a new word
                # by comparing text with recent confirmed
                recent_texts = {w.text.lower() for w in self.confirmed_in_buffer[-5:]}
                if word.text.lower() not in recent_texts:
                    result.append(word)

        return result

    def trim_to_time(self, absolute_time: float) -> None:
        """Remove words from confirmed_in_buffer before given time.

        Called when the audio buffer is trimmed to keep confirmed_in_buffer
        in sync with the audio window.

        Args:
            absolute_time: Absolute time in seconds

        """
        self.confirmed_in_buffer = [
            w for w in self.confirmed_in_buffer if w.end >= absolute_time
        ]

    def get_confirmed_text(self) -> str:
        """Get confirmed text as a string."""
        return " ".join(w.text for w in self.confirmed)

    def get_tentative_text(self) -> str:
        """Get current tentative (unconfirmed) text."""
        return " ".join(w.text for w in self.current_hypothesis)

    def get_prompt_suffix(self, max_chars: int = 200) -> str:
        """Get suffix of confirmed text for prompt continuity.

        Returns the last max_chars characters of confirmed text,
        broken at word boundaries.

        Args:
            max_chars: Maximum characters to return

        Returns:
            Suffix string for prompt

        """
        if not self.confirmed_in_buffer:
            return ""

        # Build from recent confirmed words
        words = [w.text for w in self.confirmed_in_buffer]
        text = " ".join(words)

        if len(text) <= max_chars:
            return text

        # Truncate at word boundary
        truncated = text[-max_chars:]
        first_space = truncated.find(" ")
        if first_space > 0:
            truncated = truncated[first_space + 1 :]

        return truncated

    def clear(self) -> None:
        """Clear all hypothesis state."""
        self.confirmed.clear()
        self.confirmed_in_buffer.clear()
        self.previous_hypotheses.clear()
        self.current_hypothesis.clear()

    @property
    def confirmed_word_count(self) -> int:
        """Number of confirmed words."""
        return len(self.confirmed)

    @property
    def tentative_word_count(self) -> int:
        """Number of tentative (unconfirmed) words."""
        return len(self.current_hypothesis)
