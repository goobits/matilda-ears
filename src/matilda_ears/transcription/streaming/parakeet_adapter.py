"""Adapter for Parakeet MLX streaming transcription."""

import asyncio
import logging
from typing import Any

import numpy as np

from .adapter import StreamingConfig, StreamingResult

logger = logging.getLogger(__name__)


class ParakeetStreamingAdapter:
    """Adapter that wraps parakeet-mlx streaming for async transcription."""

    SAMPLE_RATE = 16000

    def __init__(self, backend, config: StreamingConfig | None = None):
        self.config = config or StreamingConfig(backend="parakeet")
        self._backend = backend
        self._initialized = False
        self._transcriber_cm = None
        self._transcriber = None
        self._lock = asyncio.Lock()
        self._alpha_text = ""
        self._total_samples = 0
        self._vad = None
        self._dirty = False
        self._inference_running = False
        self._pending_audio: list[np.ndarray] = []
        self._last_result = StreamingResult()

    async def start(self) -> None:
        if self._initialized:
            return

        if not getattr(self._backend, "is_ready", False):
            if hasattr(self._backend, "load"):
                await self._backend.load()
            else:
                raise RuntimeError("Parakeet backend is not ready")

        self._transcriber_cm = self._backend.transcribe_stream(
            context_size=self.config.parakeet_context_size,
            depth=self.config.parakeet_depth,
        )
        self._transcriber = self._transcriber_cm.__enter__()

        if self.config.vad_enabled:
            try:
                from ...audio.vad import SileroVAD

                self._vad = SileroVAD(threshold=self.config.vad_threshold)
                logger.info(f"SileroVAD enabled with threshold={self.config.vad_threshold}")
            except Exception as e:
                logger.warning(f"SileroVAD unavailable ({e}), continuing without VAD gating")

        self._initialized = True
        logger.info("Parakeet streaming initialized successfully")

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
            logger.debug(f"Coalescing: inference busy, buffered {len(self._pending_audio)} chunks")
            return self._last_result

        logger.debug(f"Starting inference with {len(self._pending_audio)} pending chunks")
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

                alpha, omega = self._extract_text(result)
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

    def _add_audio_chunks(self, chunks: list[np.ndarray]) -> Any:
        last_result = None
        for chunk in chunks:
            audio_f32 = chunk.astype(np.float32) / 32768.0
            last_result = self._transcriber.add_audio(audio_f32)
        return last_result

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

    def _extract_text(self, result: Any) -> tuple[str, str]:
        if result is None:
            return "", ""

        if isinstance(result, dict):
            finalized = result.get("finalized_tokens") or result.get("finalized_text") or result.get("text")
            draft = result.get("draft_tokens") or result.get("draft_text")
        else:
            finalized = getattr(result, "finalized_tokens", None)
            draft = getattr(result, "draft_tokens", None)
            if finalized is None:
                finalized = getattr(result, "finalized_text", None) or getattr(result, "text", None)
            if draft is None:
                draft = getattr(result, "draft_text", None)

        return self._tokens_to_text(finalized), self._tokens_to_text(draft)

    @staticmethod
    def _tokens_to_text(tokens: Any) -> str:
        if tokens is None:
            return ""
        if isinstance(tokens, str):
            return tokens.strip()
        if isinstance(tokens, (list, tuple)):
            parts = []
            for token in tokens:
                if isinstance(token, str):
                    parts.append(token)
                elif isinstance(token, dict) and "text" in token:
                    parts.append(str(token["text"]))
                elif hasattr(token, "text"):
                    parts.append(str(token.text))
                else:
                    parts.append(str(token))
            return "".join(parts).strip()
        if hasattr(tokens, "text"):
            return str(tokens.text).strip()
        return str(tokens).strip()

    async def finalize(self) -> StreamingResult:
        if not self._initialized:
            return StreamingResult(is_final=True)

        try:
            final_result = None
            if self._transcriber and hasattr(self._transcriber, "finish"):
                loop = asyncio.get_event_loop()
                final_result = await loop.run_in_executor(None, self._transcriber.finish)
            alpha, _ = self._extract_text(final_result)
            self._merge_alpha(alpha)
        finally:
            if self._transcriber_cm:
                self._transcriber_cm.__exit__(None, None, None)

        duration = self._total_samples / self.SAMPLE_RATE
        return StreamingResult(
            alpha_text=self._alpha_text.strip(),
            omega_text="",
            is_final=True,
            audio_duration_seconds=duration,
        )

    async def reset(self) -> None:
        if self._transcriber_cm:
            self._transcriber_cm.__exit__(None, None, None)
        if self._vad:
            self._vad.reset_states()
        self._transcriber_cm = None
        self._transcriber = None
        self._alpha_text = ""
        self._total_samples = 0
        self._dirty = False
        self._inference_running = False
        self._pending_audio.clear()
        self._last_result = StreamingResult()
        self._initialized = False

    @property
    def is_initialized(self) -> bool:
        return self._initialized
