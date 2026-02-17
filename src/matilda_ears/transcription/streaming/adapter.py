"""Streaming transcription adapter.

This is the only non-vendored module allowed to import `streaming.vendor`.
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

import numpy as np

from ...audio.conversion import int16_to_float32
from .types import StreamingConfig, StreamingResult

logger = logging.getLogger(__name__)


class AlphaOmegaWrapper:
    """Wraps SimulWhisperOnline to expose alpha (stable) and omega (unstable) text."""

    SAMPLING_RATE = 16000

    def __init__(self, online: Any):
        self.online: Any = online
        self.model: Any = online.model
        self._original_infer = self.model.infer
        self._last_generation: dict[str, Any] | None = None
        # Patch infer to capture generation data
        self.model.infer = self._patched_infer

    def _patched_infer(self, is_last: bool = False):
        tokens, generation = self._original_infer(is_last=is_last)
        self._last_generation = generation
        return tokens, generation

    def insert_audio_chunk(self, audio: np.ndarray) -> None:
        self.online.insert_audio_chunk(audio)

    def process_iter(self) -> dict:
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
        result = self.online.finish()
        if not result:
            return {"alpha": "", "omega": ""}
        return {"alpha": result.get("text", "").strip(), "omega": ""}

    def init(self, offset: object | None = None) -> None:
        self.online.init(offset)
        self._last_generation = None


class StreamingAdapter:
    """Adapter that wraps vendored SimulStreaming for async streaming transcription."""

    SAMPLE_RATE = 16000

    def __init__(self, config: StreamingConfig | None = None, vad: Any | None = None):
        self.config = config or StreamingConfig()
        self._wrapper: AlphaOmegaWrapper | None = None
        self._alpha_text = ""
        self._total_samples = 0
        self._initialized = False
        self._lock = asyncio.Lock()
        # VAD and coalescing state
        self._vad: Any | None = vad if self.config.vad_enabled else None
        self._dirty = False
        self._inference_running = False
        self._pending_audio: list[np.ndarray] = []
        self._last_result = StreamingResult()

    @property
    def is_initialized(self) -> bool:
        return self._initialized

    async def start(self) -> None:
        """Initialize the ASR and processor."""
        if self._initialized:
            return

        # Import vendored modules here to keep the rest of the package vendor-free.
        from .vendor import SimulWhisperASR, SimulWhisperOnline

        model_path = os.path.join(self.config.model_cache_dir, self.config.model_size)
        os.makedirs(self.config.model_cache_dir, exist_ok=True)

        logger.info(
            "Initializing SimulStreaming with model=%s, lang=%s, cache=%s",
            self.config.model_size,
            self.config.language,
            self.config.model_cache_dir,
        )

        asr = SimulWhisperASR(
            language=self.config.language,
            model_path=model_path,
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

        if self.config.vad_enabled and self._vad is None:
            try:
                from ...audio.vad import SileroVAD

                self._vad = SileroVAD(threshold=self.config.vad_threshold)
                logger.info("SileroVAD enabled with threshold=%s", self.config.vad_threshold)
            except Exception as e:
                logger.warning("SileroVAD unavailable (%s), continuing without VAD gating", e)

        self._initialized = True
        logger.info("SimulStreaming initialized successfully")

    async def process_chunk(self, pcm_int16: np.ndarray) -> StreamingResult:
        if not self._initialized:
            raise RuntimeError("Adapter not started. Call start() first.")

        self._total_samples += len(pcm_int16)

        if self._vad:
            speech_prob = self._vad.process_chunk(pcm_int16)
            if speech_prob < self._vad.threshold:
                return self._last_result

        self._pending_audio.append(pcm_int16)

        if self._inference_running:
            self._dirty = True
            return self._last_result

        return await self._run_inference_loop()

    async def _run_inference_loop(self) -> StreamingResult:
        while True:
            self._dirty = False
            self._inference_running = True

            try:
                async with self._lock:
                    pending = self._pending_audio
                    self._pending_audio = []

                    loop = asyncio.get_event_loop()
                    result = await loop.run_in_executor(None, self._add_audio_chunks, pending)

                alpha, omega = self._extract_alpha_omega(result)
                self._merge_alpha(alpha)

                self._last_result = StreamingResult(
                    alpha_text=self._alpha_text,
                    omega_text=omega,
                    audio_duration_seconds=self._total_samples / self.SAMPLE_RATE,
                )
            finally:
                self._inference_running = False

            if not self._dirty:
                return self._last_result

    def _add_audio_chunks(self, chunks: list[np.ndarray]) -> dict:
        if self._wrapper is None:
            raise RuntimeError("Adapter not started. Call start() first.")

        last = {"alpha": "", "omega": ""}
        for chunk in chunks:
            audio_f32 = int16_to_float32(chunk)
            self._wrapper.insert_audio_chunk(audio_f32)
            last = self._wrapper.process_iter()
        return last

    def _extract_alpha_omega(self, result: dict) -> tuple[str, str]:
        return (result.get("alpha", "") or "").strip(), (result.get("omega", "") or "").strip()

    def _merge_alpha(self, alpha: str) -> None:
        if not alpha:
            return
        if self._alpha_text and alpha.startswith(self._alpha_text):
            self._alpha_text = alpha
            return
        if self._alpha_text:
            self._alpha_text = f"{self._alpha_text} {alpha}".strip()
        else:
            self._alpha_text = alpha

    async def finalize(self) -> StreamingResult:
        if not self._initialized:
            return StreamingResult(is_final=True)

        wrapper = self._wrapper
        if wrapper is None:
            return StreamingResult(is_final=True)

        try:
            loop = asyncio.get_event_loop()
            final_result = await loop.run_in_executor(None, wrapper.finish)
            alpha, _ = self._extract_alpha_omega(final_result)
            self._merge_alpha(alpha)
        finally:
            self._initialized = False

        duration = self._total_samples / self.SAMPLE_RATE
        return StreamingResult(
            alpha_text=self._alpha_text.strip(),
            omega_text="",
            is_final=True,
            audio_duration_seconds=duration,
        )

    async def reset(self) -> None:
        if self._wrapper is not None:
            self._wrapper.init(None)
        self._alpha_text = ""
        self._total_samples = 0
        self._pending_audio = []
        self._dirty = False
        self._inference_running = False
        self._last_result = StreamingResult()
