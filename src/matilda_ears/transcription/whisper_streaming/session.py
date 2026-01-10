"""Streaming session using WhisperStreaming.

Drop-in replacement for our custom streaming session that uses
whisper_streaming's OnlineASRProcessor with LocalAgreement.
"""

import asyncio
import numpy as np
from dataclasses import dataclass
from typing import Optional
import logging

from .adapter import (
    WhisperStreamingAdapter,
    WhisperStreamingConfig,
    WhisperStreamingResult,
    get_shared_adapter,
)

logger = logging.getLogger(__name__)


@dataclass
class StreamingResult:
    """Compatible result format for our WebSocket protocol."""

    confirmed_text: str = ""
    tentative_text: str = ""
    is_final: bool = False
    audio_duration_seconds: float = 0.0


class WhisperStreamingSession:
    """Streaming session that wraps WhisperStreamingAdapter.

    Provides the same interface as our legacy StreamingSession but uses
    whisper_streaming under the hood.

    Usage:
        session = WhisperStreamingSession(session_id="abc123")
        await session.start()

        # Process audio chunks
        result = await session.process_chunk(pcm_int16_array)

        # Finalize
        final = await session.finalize()
    """

    def __init__(
        self,
        session_id: str,
        config: Optional[WhisperStreamingConfig] = None,
        use_shared_adapter: bool = True,
    ):
        """Initialize streaming session.

        Args:
            session_id: Unique session identifier
            config: Optional configuration (uses defaults if not provided)
            use_shared_adapter: If True, reuse model across sessions (recommended)
        """
        self.session_id = session_id
        self.config = config
        self._use_shared = use_shared_adapter
        self._adapter: Optional[WhisperStreamingAdapter] = None
        self._started = False

    async def start(self) -> None:
        """Start the streaming session."""
        if self._started:
            return

        if self._use_shared:
            self._adapter = await get_shared_adapter(self.config)
            # Reset for new session
            await self._adapter.reset()
        else:
            self._adapter = WhisperStreamingAdapter(self.config)
            await self._adapter.start()

        self._started = True
        logger.debug(f"WhisperStreamingSession {self.session_id} started")

    async def process_chunk(self, pcm_int16: np.ndarray) -> StreamingResult:
        """Process an audio chunk.

        Args:
            pcm_int16: Audio samples as int16 numpy array (16kHz, mono)

        Returns:
            StreamingResult with confirmed and tentative text
        """
        if not self._started or not self._adapter:
            raise RuntimeError("Session not started")

        result = await self._adapter.process_chunk(pcm_int16)

        return StreamingResult(
            confirmed_text=result.confirmed_text,
            tentative_text=result.tentative_text,
            is_final=result.is_final,
            audio_duration_seconds=result.audio_duration_seconds,
        )

    async def finalize(self) -> StreamingResult:
        """Finalize the session and get final transcription.

        Returns:
            StreamingResult with final confirmed text
        """
        if not self._adapter:
            return StreamingResult(is_final=True)

        result = await self._adapter.finalize()

        logger.debug(
            f"WhisperStreamingSession {self.session_id} finalized: "
            f"{len(result.confirmed_text)} chars, {result.audio_duration_seconds:.2f}s"
        )

        return StreamingResult(
            confirmed_text=result.confirmed_text,
            tentative_text="",
            is_final=True,
            audio_duration_seconds=result.audio_duration_seconds,
        )


def create_whisper_streaming_session(
    session_id: str,
    language: str = "en",
    model_size: str = "small",
    backend: str = "faster-whisper",
    use_vad: bool = False,
) -> WhisperStreamingSession:
    """Factory function to create a WhisperStreamingSession.

    This provides a similar interface to our legacy create_streaming_session().

    Args:
        session_id: Unique session identifier
        language: Language code (default: "en")
        model_size: Whisper model size (default: "small")
        backend: ASR backend ("faster-whisper" or "mlx-whisper")
        use_vad: Whether to use voice activity detection

    Returns:
        Configured WhisperStreamingSession
    """
    config = WhisperStreamingConfig(
        language=language,
        model_size=model_size,
        backend=backend,
        use_vad=use_vad,
    )

    return WhisperStreamingSession(
        session_id=session_id,
        config=config,
        use_shared_adapter=True,
    )
