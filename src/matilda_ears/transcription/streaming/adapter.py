"""Adapter for SimulStreaming library.

Wraps SimulWhisperASR/SimulWhisperOnline to provide streaming transcription
with alpha (stable) and omega (unstable) text separation using AlignAtt.
"""

import asyncio
import numpy as np
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class StreamingResult:
    """Result from streaming transcription."""

    alpha_text: str = ""  # Stable/confirmed text (blue)
    omega_text: str = ""  # Unstable/tentative text (grey)
    is_final: bool = False
    audio_duration_seconds: float = 0.0


@dataclass
class StreamingConfig:
    """Configuration for streaming adapter."""

    language: str = "en"
    model_size: str = "small"  # small, medium, large-v3
    frame_threshold: int = 25  # AlignAtt threshold (frames from end)
    audio_max_len: float = 30.0  # Max buffer length in seconds
    audio_min_len: float = 0.0  # Min buffer before processing
    segment_length: float = 1.0  # Chunk size for processing
    beams: int = 1  # Beam search (1 = greedy)
    task: str = "transcribe"  # transcribe or translate
    never_fire: bool = True  # Always show omega (unstable last word)


class AlphaOmegaWrapper:
    """Wraps SimulWhisperOnline to expose alpha (stable) and omega (unstable) text.

    The omega text comes from generation["result_truncated"] which contains
    the last word that was truncated because it may be incomplete.
    """

    SAMPLING_RATE = 16000

    def __init__(self, online):
        self.online = online
        self.model = online.model
        self._original_infer = self.model.infer
        self._last_generation = None
        # Patch infer to capture generation data
        self.model.infer = self._patched_infer

    def _patched_infer(self, is_last=False):
        tokens, generation = self._original_infer(is_last=is_last)
        self._last_generation = generation
        return tokens, generation

    def insert_audio_chunk(self, audio: np.ndarray):
        """Insert audio chunk (float32, 16kHz)."""
        self.online.insert_audio_chunk(audio)

    def process_iter(self) -> dict:
        """Process buffered audio and return alpha/omega text."""
        result = self.online.process_iter()
        if not result:
            return {"alpha": "", "omega": ""}

        alpha_text = result.get("text", "").strip()
        omega_text = ""

        if self._last_generation:
            truncated = self._last_generation.get("result_truncated", {})
            omega_words = truncated.get("split_words", [])
            if omega_words:
                omega_text = "".join(["".join(w) for w in omega_words]).strip()

        return {"alpha": alpha_text, "omega": omega_text}

    def finish(self) -> dict:
        """Finalize and get remaining text."""
        result = self.online.finish()
        if not result:
            return {"alpha": "", "omega": ""}
        return {"alpha": result.get("text", "").strip(), "omega": ""}

    def init(self, offset=None):
        """Reset for new session."""
        self.online.init(offset)
        self._last_generation = None


class StreamingAdapter:
    """Adapter that wraps SimulStreaming for async streaming transcription.

    Provides alpha/omega text separation using AlignAtt attention-guided decoding.

    Usage:
        adapter = StreamingAdapter(config)
        await adapter.start()

        # Feed audio chunks
        result = await adapter.process_chunk(pcm_int16_array)
        print(f"Alpha (stable): {result.alpha_text}")
        print(f"Omega (unstable): {result.omega_text}")

        # Finalize
        final = await adapter.finalize()
    """

    SAMPLE_RATE = 16000

    def __init__(self, config: StreamingConfig | None = None):
        self.config = config or StreamingConfig()
        self._wrapper: AlphaOmegaWrapper | None = None
        self._alpha_text = ""
        self._total_samples = 0
        self._initialized = False
        self._lock = asyncio.Lock()

    async def start(self) -> None:
        """Initialize the ASR and processor."""
        if self._initialized:
            return

        from .vendor import SimulWhisperASR, SimulWhisperOnline

        logger.info(
            f"Initializing SimulStreaming with model={self.config.model_size}, "
            f"lang={self.config.language}, threshold={self.config.frame_threshold}"
        )

        asr = SimulWhisperASR(
            language=self.config.language,
            model_path=self.config.model_size,
            cif_ckpt_path=None,  # No CIF model needed with never_fire=True
            frame_threshold=self.config.frame_threshold,
            audio_max_len=self.config.audio_max_len,
            audio_min_len=self.config.audio_min_len,
            segment_length=self.config.segment_length,
            beams=self.config.beams,
            task=self.config.task,
            decoder_type="greedy" if self.config.beams == 1 else "beam",
            never_fire=self.config.never_fire,
            init_prompt=None,
            static_init_prompt=None,
            max_context_tokens=None,
            logdir=None,
        )

        online = SimulWhisperOnline(asr)
        self._wrapper = AlphaOmegaWrapper(online)

        self._initialized = True
        logger.info("SimulStreaming initialized successfully")

    async def process_chunk(self, pcm_int16: np.ndarray) -> StreamingResult:
        """Process an audio chunk and return partial results.

        Args:
            pcm_int16: Audio samples as int16 numpy array (16kHz, mono)

        Returns:
            StreamingResult with alpha (stable) and omega (unstable) text

        """
        if not self._initialized:
            raise RuntimeError("Adapter not started. Call start() first.")

        async with self._lock:
            # Convert int16 to float32 [-1.0, 1.0]
            audio_float32 = pcm_int16.astype(np.float32) / 32768.0
            self._total_samples += len(pcm_int16)

            # Feed audio to processor
            self._wrapper.insert_audio_chunk(audio_float32)

            # Get result - runs in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, self._wrapper.process_iter)

            alpha = result.get("alpha", "")
            omega = result.get("omega", "")

            # Accumulate alpha text
            if alpha:
                if self._alpha_text:
                    self._alpha_text += " " + alpha
                else:
                    self._alpha_text = alpha

            return StreamingResult(
                alpha_text=self._alpha_text,
                omega_text=omega,
                audio_duration_seconds=self._total_samples / self.SAMPLE_RATE,
            )

    async def finalize(self) -> StreamingResult:
        """Finalize transcription and get remaining text.

        Call this when the audio stream ends to flush any remaining
        uncommitted text from the buffer.

        Returns:
            StreamingResult with final alpha text

        """
        if not self._initialized:
            return StreamingResult(is_final=True)

        async with self._lock:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, self._wrapper.finish)

            final_alpha = result.get("alpha", "")
            if final_alpha:
                if self._alpha_text:
                    self._alpha_text += " " + final_alpha
                else:
                    self._alpha_text = final_alpha

            duration = self._total_samples / self.SAMPLE_RATE

            return StreamingResult(
                alpha_text=self._alpha_text.strip(),
                omega_text="",
                is_final=True,
                audio_duration_seconds=duration,
            )

    async def reset(self) -> None:
        """Reset the processor for a new transcription session."""
        if self._wrapper:
            self._wrapper.init()
        self._alpha_text = ""
        self._total_samples = 0

    @property
    def is_initialized(self) -> bool:
        """Check if the adapter is initialized and ready."""
        return self._initialized


# Singleton for reusing the loaded model across sessions
_global_adapter: StreamingAdapter | None = None


async def get_shared_adapter(
    config: StreamingConfig | None = None,
) -> StreamingAdapter:
    """Get or create a shared adapter instance.

    Reuses the same model across multiple sessions to avoid
    repeated model loading.
    """
    global _global_adapter

    if _global_adapter is None:
        _global_adapter = StreamingAdapter(config)
        await _global_adapter.start()

    return _global_adapter
