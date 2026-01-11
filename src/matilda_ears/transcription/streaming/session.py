"""Streaming session for WebSocket integration.

Wraps StreamingAdapter to provide the session interface expected by
stream_handlers.py.
"""

import numpy as np
from dataclasses import dataclass

from .adapter import StreamingAdapter, StreamingConfig


@dataclass
class SessionResult:
    """Result compatible with stream_handlers.py expectations."""

    confirmed_text: str = ""  # Maps to alpha_text
    tentative_text: str = ""  # Maps to omega_text
    is_final: bool = False
    audio_duration_seconds: float = 0.0


class StreamingSession:
    """Streaming session for WebSocket server integration.

    Provides the interface expected by stream_handlers.py:
    - start() -> None
    - process_chunk(pcm_samples) -> SessionResult
    - finalize() -> SessionResult
    """

    def __init__(
        self,
        session_id: str,
        config: StreamingConfig | None = None,
    ):
        self.session_id = session_id
        self.config = config or StreamingConfig()
        self._adapter = StreamingAdapter(self.config)

    async def start(self) -> None:
        """Initialize the streaming session."""
        await self._adapter.start()

    async def process_chunk(self, pcm_samples: np.ndarray) -> SessionResult:
        """Process an audio chunk and return partial results.

        Args:
            pcm_samples: Audio samples as int16 numpy array (16kHz, mono)

        Returns:
            SessionResult with confirmed (alpha) and tentative (omega) text

        """
        result = await self._adapter.process_chunk(pcm_samples)
        return SessionResult(
            confirmed_text=result.alpha_text,
            tentative_text=result.omega_text,
            is_final=result.is_final,
            audio_duration_seconds=result.audio_duration_seconds,
        )

    async def finalize(self) -> SessionResult:
        """Finalize the session and get remaining text."""
        result = await self._adapter.finalize()
        return SessionResult(
            confirmed_text=result.alpha_text,
            tentative_text=result.omega_text,
            is_final=True,
            audio_duration_seconds=result.audio_duration_seconds,
        )

    async def reset(self) -> None:
        """Reset for a new session."""
        await self._adapter.reset()


# Backwards compatibility aliases
StreamingSessionConfig = StreamingConfig
