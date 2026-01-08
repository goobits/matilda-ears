"""Chunked strategy - simple periodic batch transcription fallback.

A simple strategy for backends that don't support word timestamps:
- Accumulates audio chunks
- Periodically transcribes the full buffer
- Returns only confirmed text (no tentative)

Use this as a fallback when LocalAgreement can't be used due to
lack of word timestamp support.
"""

import time
import logging
from collections.abc import Callable, Awaitable

import numpy as np

from ...config import StreamingConfig
from ...buffer import AudioBuffer
from ...types import StreamingResult

logger = logging.getLogger(__name__)

# Type alias for batch transcribe function
BatchTranscribeFn = Callable[[bytes, str], Awaitable[tuple]]


class ChunkedStrategy:
    """Simple periodic batch transcription strategy.

    This strategy:
    1. Accumulates audio in a buffer
    2. Periodically transcribes the full buffer
    3. Returns the transcription as confirmed text

    Unlike LocalAgreement, this provides no tentative text and
    may have less stable partial results. Use when word timestamps
    are not available.

    Best for:
    - Backends without word timestamp support
    - Simple fallback when stability isn't critical
    """

    def __init__(
        self,
        batch_transcribe: BatchTranscribeFn,
        config: StreamingConfig,
    ):
        """Initialize chunked strategy.

        Args:
            batch_transcribe: Async function (wav_bytes, prompt) -> (text, info)
            config: Streaming configuration

        """
        self.transcribe = batch_transcribe
        self.config = config

        # Audio buffer (no sliding window needed - we keep everything)
        self.buffer = AudioBuffer(
            max_seconds=config.max_buffer_seconds,
            sample_rate=config.sample_rate,
        )

        # Current transcription
        self._current_text = ""
        self._word_count = 0

        # Timing
        self._last_transcribe_samples = 0
        self._transcribe_count = 0

    async def process_audio(self, audio_chunk: np.ndarray) -> StreamingResult:
        """Process audio chunk with periodic batch transcription.

        Args:
            audio_chunk: Audio samples (float32 or int16)

        Returns:
            StreamingResult with confirmed text only

        """
        # Append to buffer
        self.buffer.append(audio_chunk)

        # Check if we should transcribe
        samples_since_transcribe = self.buffer.samples_in_buffer - self._last_transcribe_samples

        if samples_since_transcribe < self.config.transcribe_interval_samples:
            # Not time to transcribe yet
            return StreamingResult(
                confirmed_text=self._current_text,
                tentative_text="",  # Chunked doesn't provide tentative
                confirmed_word_count=self._word_count,
                tentative_word_count=0,
            )

        # Time to transcribe
        self._last_transcribe_samples = self.buffer.samples_in_buffer

        # Transcribe full buffer
        wav_bytes = self.buffer.to_wav_bytes()
        start_time = time.time()

        try:
            text, info = await self.transcribe(wav_bytes, "")
            transcribe_time = (time.time() - start_time) * 1000

            logger.debug(
                f"Chunked transcription in {transcribe_time:.0f}ms: "
                f"'{text[:50]}...' ({len(text)} chars)"
            )

            self._current_text = text.strip()
            self._word_count = len(self._current_text.split())
            self._transcribe_count += 1

        except Exception as e:
            logger.error(f"Chunked transcription failed: {e}")
            # Keep previous text on error

        return StreamingResult(
            confirmed_text=self._current_text,
            tentative_text="",
            confirmed_word_count=self._word_count,
            tentative_word_count=0,
        )

    async def finalize(self) -> StreamingResult:
        """Finalize with final transcription of full buffer.

        Returns:
            Final StreamingResult

        """
        # Final transcription of complete buffer
        if self.buffer.samples_in_buffer > 0:
            wav_bytes = self.buffer.to_wav_bytes()

            try:
                text, info = await self.transcribe(wav_bytes, "")
                self._current_text = text.strip()
                self._word_count = len(self._current_text.split())
            except Exception as e:
                logger.error(f"Final chunked transcription failed: {e}")

        return StreamingResult(
            confirmed_text=self._current_text,
            tentative_text="",
            is_final=True,
            confirmed_word_count=self._word_count,
            tentative_word_count=0,
        )

    async def cleanup(self) -> None:
        """Clean up strategy resources."""
        self.buffer.reset()
        self._current_text = ""
        self._word_count = 0
