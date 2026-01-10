"""LocalAgreement-2 strategy for faster-whisper.

Uses batch transcription with sliding window and LocalAgreement-2 algorithm
for stable partial results:
- Maintains sliding audio window (default 30s)
- Uses prompt suffix from confirmed history for continuity
- Calls batch transcribe at fixed intervals
- Applies LocalAgreement-2 on word-aligned output
- Returns confirmed + tentative text for display
"""

import time
import logging
from collections.abc import Callable, Awaitable

import numpy as np

from ...config import StreamingConfig
from ...buffer import AudioBuffer
from ...hypothesis import HypothesisBuffer
from ...types import StreamingResult, TimestampedWord

logger = logging.getLogger(__name__)

# Type alias for batch transcribe function
BatchTranscribeFn = Callable[[bytes, str], Awaitable[tuple]]


class LocalAgreementStrategy:
    """Streaming strategy using LocalAgreement-2 with batch transcription.

    This strategy:
    1. Accumulates audio in a sliding window buffer
    2. Periodically calls batch transcription on the window
    3. Extracts word timestamps and applies LocalAgreement-2
    4. Returns confirmed + tentative text

    Best for:
    - faster-whisper backend with word timestamps
    - Low-latency streaming with stability guarantees
    """

    def __init__(
        self,
        batch_transcribe: BatchTranscribeFn,
        config: StreamingConfig,
        *,
        audio_buffer_factory: type[AudioBuffer] | None = None,
        hypothesis_buffer_factory: type[HypothesisBuffer] | None = None,
    ):
        """Initialize LocalAgreement strategy.

        Args:
            batch_transcribe: Async function (wav_bytes, prompt) -> (text, info)
            config: Streaming configuration
            audio_buffer_factory: Optional factory for AudioBuffer (for testing)
            hypothesis_buffer_factory: Optional factory for HypothesisBuffer (for testing)

        """
        self.transcribe = batch_transcribe
        self.config = config

        # Use provided factories or defaults
        audio_buffer_cls = audio_buffer_factory or AudioBuffer
        hypothesis_buffer_cls = hypothesis_buffer_factory or HypothesisBuffer

        # Audio buffer with sliding window
        self.buffer = audio_buffer_cls(
            max_seconds=config.max_buffer_seconds,
            sample_rate=config.sample_rate,
        )

        # Hypothesis tracking with LocalAgreement
        self.hypothesis = hypothesis_buffer_cls(
            agreement_n=config.local_agreement_n,
            max_confirmed_words=config.max_confirmed_words,
        )

        # Timing for transcription interval
        self._last_transcribe_samples = 0
        self._transcribe_count = 0

    async def process_audio(self, audio_chunk: np.ndarray) -> StreamingResult:
        """Process audio chunk with LocalAgreement-2.

        Args:
            audio_chunk: Audio samples (float32 or int16)

        Returns:
            StreamingResult with confirmed/tentative text

        """
        # Append to buffer (auto-trims if needed)
        self.buffer.append(audio_chunk)

        # Check if we should transcribe
        samples_since_transcribe = self.buffer.samples_in_buffer + (
            self.buffer._offset_samples - self._last_transcribe_samples
        )

        if samples_since_transcribe < self.config.transcribe_interval_samples:
            # Not time to transcribe yet - return current state
            return StreamingResult(
                confirmed_text=self.hypothesis.get_confirmed_text(),
                tentative_text=self.hypothesis.get_tentative_text(),
                confirmed_word_count=self.hypothesis.confirmed_word_count,
                tentative_word_count=self.hypothesis.tentative_word_count,
            )

        # Time to transcribe
        self._last_transcribe_samples = self.buffer._offset_samples + self.buffer.samples_in_buffer

        # Get prompt suffix for continuity
        prompt = self.hypothesis.get_prompt_suffix(self.config.prompt_suffix_chars)

        # Convert buffer to WAV and transcribe
        wav_bytes = self.buffer.to_wav_bytes()
        start_time = time.time()

        try:
            text, info = await self.transcribe(wav_bytes, prompt)
            transcribe_time = (time.time() - start_time) * 1000

            logger.debug(f"Transcribed in {transcribe_time:.0f}ms: " f"'{text[:50]}...' ({len(text)} chars)")

            self._transcribe_count += 1

            # Extract word timestamps and apply LocalAgreement
            words = self._extract_words(text, info)

            if words:
                # Insert into hypothesis buffer with offset
                self.hypothesis.insert(words, self.buffer.offset_seconds)

                # Flush to confirm stable words
                newly_confirmed = self.hypothesis.flush()

                if newly_confirmed:
                    # Trim buffer to remove confirmed audio
                    last_confirmed_time = newly_confirmed[-1].end
                    self._maybe_trim_buffer(last_confirmed_time)

        except Exception as e:
            logger.error(f"Transcription failed: {e}")
            # Return current state on error

        return StreamingResult(
            confirmed_text=self.hypothesis.get_confirmed_text(),
            tentative_text=self.hypothesis.get_tentative_text(),
            confirmed_word_count=self.hypothesis.confirmed_word_count,
            tentative_word_count=self.hypothesis.tentative_word_count,
        )

    async def finalize(self) -> StreamingResult:
        """Finalize transcription with remaining audio.

        Transcribes any remaining audio and confirms all pending words.

        Returns:
            Final StreamingResult

        """
        # Final transcription of remaining buffer
        if self.buffer.samples_in_buffer > 0:
            prompt = self.hypothesis.get_prompt_suffix(self.config.prompt_suffix_chars)
            wav_bytes = self.buffer.to_wav_bytes()

            try:
                text, info = await self.transcribe(wav_bytes, prompt)

                # Extract and add final words
                words = self._extract_words(text, info)
                if words:
                    self.hypothesis.insert(words, self.buffer.offset_seconds)
                    # Do one more flush to confirm any matching words
                    self.hypothesis.flush()

            except Exception as e:
                logger.error(f"Final transcription failed: {e}")

        # Force-confirm all remaining tentative words
        self.hypothesis.force_confirm_all()

        return StreamingResult(
            confirmed_text=self.hypothesis.get_confirmed_text(),
            tentative_text="",  # No tentative on final
            is_final=True,
            confirmed_word_count=self.hypothesis.confirmed_word_count,
            tentative_word_count=0,
        )

    async def cleanup(self) -> None:
        """Clean up strategy resources."""
        self.buffer.reset()
        self.hypothesis.clear()

    def _extract_words(self, text: str, info: dict) -> list[TimestampedWord]:
        """Extract word timestamps from transcription result.

        Falls back to simple splitting if word timestamps not available.

        Args:
            text: Transcribed text
            info: Info dict from transcriber (may contain word_timestamps)

        Returns:
            List of TimestampedWord

        """
        # Check for word timestamps in info
        if "words" in info:
            # faster-whisper with word_timestamps=True
            return [
                TimestampedWord(
                    text=w.get("word", w.get("text", "")),
                    start=w.get("start", 0.0),
                    end=w.get("end", 0.0),
                    confidence=w.get("probability", 1.0),
                )
                for w in info["words"]
                if w.get("word", w.get("text", "")).strip()
            ]

        # Fallback: create words with estimated timestamps
        words = text.split()
        if not words:
            return []

        # Estimate duration based on audio length
        audio_duration = self.buffer.duration_seconds
        if audio_duration <= 0:
            audio_duration = len(words) * 0.3  # Rough estimate: 0.3s per word

        word_duration = audio_duration / len(words)

        return [
            TimestampedWord(
                text=word,
                start=i * word_duration,
                end=(i + 1) * word_duration,
                confidence=0.8,  # Lower confidence for estimated timestamps
            )
            for i, word in enumerate(words)
        ]

    def _maybe_trim_buffer(self, confirmed_end_time: float) -> None:
        """Trim buffer to remove audio before confirmed words.

        Keeps a small overlap to ensure word boundaries aren't cut.

        Args:
            confirmed_end_time: End time of last confirmed word

        """
        # Keep some overlap (1 second) for safety
        trim_to_time = max(0, confirmed_end_time - 1.0)

        if trim_to_time > self.buffer.offset_seconds:
            self.buffer.trim_to_time(trim_to_time)
            self.hypothesis.trim_to_time(trim_to_time)
