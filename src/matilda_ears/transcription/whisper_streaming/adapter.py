"""Adapter for whisper_streaming library.

Wraps OnlineASRProcessor to provide streaming transcription with
LocalAgreement-based confirmed/tentative text separation.
"""

import asyncio
import numpy as np
from dataclasses import dataclass, field
from typing import Optional
import logging

logger = logging.getLogger(__name__)


@dataclass
class WhisperStreamingResult:
    """Result from streaming transcription."""

    confirmed_text: str = ""
    tentative_text: str = ""
    is_final: bool = False
    audio_duration_seconds: float = 0.0


@dataclass
class WhisperStreamingConfig:
    """Configuration for WhisperStreaming adapter."""

    language: str = "en"
    model_size: str = "small"
    backend: str = "faster-whisper"  # faster-whisper, mlx-whisper
    use_vad: bool = False
    buffer_trimming: tuple = ("segment", 15)
    min_chunk_seconds: float = 1.0  # Minimum audio before processing


class WhisperStreamingAdapter:
    """Adapter that wraps whisper_streaming's OnlineASRProcessor.

    Provides streaming transcription with LocalAgreement for stable partial results.
    Converts our int16 PCM audio to float32 format expected by whisper_streaming.

    Usage:
        adapter = WhisperStreamingAdapter(config)
        await adapter.start()

        # Feed audio chunks
        result = await adapter.process_chunk(pcm_int16_array)
        print(f"Confirmed: {result.confirmed_text}")
        print(f"Tentative: {result.tentative_text}")

        # Finalize
        final = await adapter.finalize()
    """

    SAMPLE_RATE = 16000  # whisper_streaming expects 16kHz

    def __init__(self, config: Optional[WhisperStreamingConfig] = None):
        self.config = config or WhisperStreamingConfig()
        self._asr = None
        self._processor = None
        self._confirmed_text = ""
        self._audio_buffer = np.array([], dtype=np.float32)
        self._total_samples = 0
        self._initialized = False
        self._lock = asyncio.Lock()

    async def start(self) -> None:
        """Initialize the ASR and processor."""
        if self._initialized:
            return

        # Import from vendored whisper_streaming
        try:
            from .vendor import FasterWhisperASR, OnlineASRProcessor
        except ImportError as e:
            logger.error(f"Failed to import whisper_streaming vendor: {e}")
            raise

        logger.info(
            f"Initializing WhisperStreaming with {self.config.backend}, "
            f"model={self.config.model_size}, lang={self.config.language}"
        )

        # Create ASR backend
        if self.config.backend == "faster-whisper":
            self._asr = FasterWhisperASR(
                lan=self.config.language,
                modelsize=self.config.model_size,
            )
        elif self.config.backend == "mlx-whisper":
            from .vendor.whisper_online import MLXWhisper

            self._asr = MLXWhisper(
                lan=self.config.language,
                modelsize=self.config.model_size,
            )
        else:
            raise ValueError(f"Unknown backend: {self.config.backend}")

        # Load the model
        self._asr.load_model()

        # Create online processor with LocalAgreement
        self._processor = OnlineASRProcessor(
            self._asr,
            buffer_trimming=self.config.buffer_trimming,
        )

        self._initialized = True
        logger.info("WhisperStreaming initialized successfully")

    async def process_chunk(self, pcm_int16: np.ndarray) -> WhisperStreamingResult:
        """Process an audio chunk and return partial results.

        Args:
            pcm_int16: Audio samples as int16 numpy array (16kHz, mono)

        Returns:
            WhisperStreamingResult with confirmed and tentative text
        """
        if not self._initialized:
            raise RuntimeError("Adapter not started. Call start() first.")

        async with self._lock:
            # Convert int16 to float32 [-1.0, 1.0]
            audio_float32 = pcm_int16.astype(np.float32) / 32768.0

            # Accumulate audio
            self._audio_buffer = np.concatenate([self._audio_buffer, audio_float32])
            self._total_samples += len(pcm_int16)

            # Only process if we have enough audio (reduces CPU load)
            min_samples = int(self.config.min_chunk_seconds * self.SAMPLE_RATE)
            if len(self._audio_buffer) < min_samples:
                return WhisperStreamingResult(
                    confirmed_text=self._confirmed_text,
                    tentative_text="",
                    audio_duration_seconds=self._total_samples / self.SAMPLE_RATE,
                )

            # Feed audio to processor
            self._processor.insert_audio_chunk(self._audio_buffer)
            self._audio_buffer = np.array([], dtype=np.float32)

            # Get result - runs in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, self._processor.process_iter)

            # process_iter returns (start_ts, end_ts, confirmed_text)
            start_ts, end_ts, new_confirmed = result

            # Accumulate confirmed text
            if new_confirmed:
                if self._confirmed_text:
                    self._confirmed_text += " " + new_confirmed
                else:
                    self._confirmed_text = new_confirmed

            # Get tentative text from internal buffer
            tentative = self._get_tentative_text()

            return WhisperStreamingResult(
                confirmed_text=self._confirmed_text,
                tentative_text=tentative,
                audio_duration_seconds=self._total_samples / self.SAMPLE_RATE,
            )

    def _get_tentative_text(self) -> str:
        """Extract tentative (uncommitted) text from processor's internal buffer."""
        if not self._processor:
            return ""

        try:
            # Access the hypothesis buffer's uncommitted words
            # The buffer contains words that haven't been confirmed yet
            hyp_buffer = self._processor.transcript_buffer
            if hasattr(hyp_buffer, "buffer") and hyp_buffer.buffer:
                # buffer is a list of (start, end, word) tuples
                words = [w[2] for w in hyp_buffer.buffer if len(w) > 2]
                return " ".join(words)
        except (AttributeError, IndexError):
            pass

        return ""

    async def finalize(self) -> WhisperStreamingResult:
        """Finalize transcription and get remaining text.

        Call this when the audio stream ends to flush any remaining
        uncommitted text from the buffer.

        Returns:
            WhisperStreamingResult with final confirmed text
        """
        if not self._initialized:
            return WhisperStreamingResult(is_final=True)

        async with self._lock:
            # Process any remaining buffered audio
            if len(self._audio_buffer) > 0:
                self._processor.insert_audio_chunk(self._audio_buffer)
                self._audio_buffer = np.array([], dtype=np.float32)

                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(None, self._processor.process_iter)
                _, _, new_confirmed = result
                if new_confirmed:
                    if self._confirmed_text:
                        self._confirmed_text += " " + new_confirmed
                    else:
                        self._confirmed_text = new_confirmed

            # Flush remaining uncommitted text
            loop = asyncio.get_event_loop()
            final_text = await loop.run_in_executor(None, self._processor.finish)

            if final_text:
                if self._confirmed_text:
                    self._confirmed_text += " " + final_text
                else:
                    self._confirmed_text = final_text

            duration = self._total_samples / self.SAMPLE_RATE

            return WhisperStreamingResult(
                confirmed_text=self._confirmed_text.strip(),
                tentative_text="",
                is_final=True,
                audio_duration_seconds=duration,
            )

    async def reset(self) -> None:
        """Reset the processor for a new transcription session."""
        if self._processor:
            self._processor.init()
        self._confirmed_text = ""
        self._audio_buffer = np.array([], dtype=np.float32)
        self._total_samples = 0

    @property
    def is_initialized(self) -> bool:
        """Check if the adapter is initialized and ready."""
        return self._initialized


# Singleton for reusing the loaded model across sessions
_global_adapter: Optional[WhisperStreamingAdapter] = None


async def get_shared_adapter(
    config: Optional[WhisperStreamingConfig] = None,
) -> WhisperStreamingAdapter:
    """Get or create a shared adapter instance.

    Reuses the same model across multiple sessions to avoid
    repeated model loading.
    """
    global _global_adapter

    if _global_adapter is None:
        _global_adapter = WhisperStreamingAdapter(config)
        await _global_adapter.start()

    return _global_adapter
