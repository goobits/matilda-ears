"""Native streaming strategy for Parakeet.

Wraps the native transcribe_stream() API from Parakeet MLX:
- Uses native streaming context manager
- Emits confirmed + draft tokens from the API
- Provides consistent StreamingResult interface

This strategy is only available for backends that implement
a native streaming API (currently Parakeet MLX).
"""

import asyncio
import logging
from typing import TYPE_CHECKING, Optional, Any

import numpy as np

from ...config import StreamingConfig
from ...types import StreamingResult, StreamingError

if TYPE_CHECKING:
    from ....backends.base import TranscriptionBackend

logger = logging.getLogger(__name__)


class NativeStrategy:
    """Native streaming strategy using backend's streaming API.

    Wraps Parakeet's transcribe_stream() context manager:
    - Creates streaming context on first audio
    - Feeds audio chunks to context
    - Returns confirmed + draft text from context

    Best for:
    - Parakeet MLX backend on Apple Silicon
    - Lowest latency streaming with native support
    """

    def __init__(
        self,
        backend: "TranscriptionBackend",
        config: StreamingConfig,
    ):
        """Initialize native strategy.

        Args:
            backend: Backend with transcribe_stream() method
            config: Streaming configuration

        """
        self.backend = backend
        self.config = config

        # Streaming context (created on first audio)
        self._context: Optional[Any] = None
        self._context_entered = False

        # Current state
        self._confirmed_text = ""
        self._draft_text = ""
        self._finalized_tokens = 0
        self._draft_tokens = 0

        # Audio tracking
        self._total_samples = 0

    async def process_audio(self, audio_chunk: np.ndarray) -> StreamingResult:
        """Process audio chunk with native streaming API.

        Args:
            audio_chunk: Audio samples (float32 or int16)

        Returns:
            StreamingResult with confirmed/tentative text

        """
        # Convert to float32 if needed
        if audio_chunk.dtype == np.int16:
            audio_chunk = audio_chunk.astype(np.float32) / 32768.0

        self._total_samples += len(audio_chunk)

        # Create streaming context on first audio
        if not self._context_entered:
            try:
                await self._start_context()
            except Exception as e:
                logger.error(f"Failed to start native streaming context: {e}")
                raise StreamingError(f"Native streaming not available: {e}")

        # Feed audio to context
        loop = asyncio.get_event_loop()
        try:
            result = await loop.run_in_executor(
                None,
                lambda: self._process_in_context(audio_chunk),
            )

            if result:
                self._update_from_result(result)

        except Exception as e:
            logger.error(f"Native streaming error: {e}")
            # Continue with current state

        return StreamingResult(
            confirmed_text=self._confirmed_text,
            tentative_text=self._draft_text,
            confirmed_word_count=self._finalized_tokens,
            tentative_word_count=self._draft_tokens,
        )

    async def finalize(self) -> StreamingResult:
        """Finalize native streaming context.

        Exits the streaming context and returns final transcription.

        Returns:
            Final StreamingResult

        """
        if self._context_entered and self._context:
            loop = asyncio.get_event_loop()
            try:
                result = await loop.run_in_executor(
                    None,
                    self._finalize_context,
                )

                if result:
                    self._update_from_result(result)
                    # On finalize, move all draft to confirmed
                    if self._draft_text:
                        if self._confirmed_text:
                            self._confirmed_text += " " + self._draft_text
                        else:
                            self._confirmed_text = self._draft_text
                        self._finalized_tokens += self._draft_tokens
                        self._draft_text = ""
                        self._draft_tokens = 0

            except Exception as e:
                logger.error(f"Native streaming finalize error: {e}")

        return StreamingResult(
            confirmed_text=self._confirmed_text,
            tentative_text="",
            is_final=True,
            confirmed_word_count=self._finalized_tokens,
            tentative_word_count=0,
        )

    async def cleanup(self) -> None:
        """Clean up native streaming resources."""
        if self._context_entered and self._context:
            try:
                # Exit context if not already exited
                if hasattr(self._context, "__exit__"):
                    self._context.__exit__(None, None, None)
            except Exception as e:
                logger.warning(f"Error cleaning up native context: {e}")

        self._context = None
        self._context_entered = False
        self._confirmed_text = ""
        self._draft_text = ""

    async def _start_context(self) -> None:
        """Start the native streaming context."""
        if not hasattr(self.backend, "transcribe_stream"):
            raise StreamingError(
                f"Backend {self.backend.__class__.__name__} does not support native streaming"
            )

        loop = asyncio.get_event_loop()

        # Get streaming context
        # Parakeet's transcribe_stream() returns a context manager
        self._context = await loop.run_in_executor(
            None,
            lambda: self.backend.transcribe_stream(),
        )

        # Enter the context
        if hasattr(self._context, "__enter__"):
            self._context = self._context.__enter__()
            self._context_entered = True
            logger.info("Native streaming context started")

    def _process_in_context(self, audio_chunk: np.ndarray) -> Optional[dict]:
        """Process audio in the native context (runs in executor).

        Args:
            audio_chunk: Audio samples

        Returns:
            Result dict from context, or None

        """
        if not self._context:
            return None

        # Parakeet context expects add_audio() method
        if hasattr(self._context, "add_audio"):
            self._context.add_audio(audio_chunk)

            # Get current result
            if hasattr(self._context, "result"):
                return self._context.result
            if hasattr(self._context, "get_result"):
                return self._context.get_result()

        return None

    def _finalize_context(self) -> Optional[dict]:
        """Finalize the native context (runs in executor).

        Returns:
            Final result dict

        """
        if not self._context:
            return None

        result = None

        # Get final result
        if hasattr(self._context, "result"):
            result = self._context.result
        elif hasattr(self._context, "get_result"):
            result = self._context.get_result()

        # Exit context
        if hasattr(self._context, "__exit__"):
            self._context.__exit__(None, None, None)

        self._context_entered = False

        return result

    def _update_from_result(self, result: Any) -> None:
        """Update state from native context result.

        Args:
            result: Result from native streaming context

        """
        # Handle different result formats
        if isinstance(result, dict):
            # Dict format: {"finalized": "text", "draft": "text", ...}
            if "finalized" in result:
                self._confirmed_text = result.get("finalized", "")
                self._draft_text = result.get("draft", "")
                self._finalized_tokens = len(self._confirmed_text.split())
                self._draft_tokens = len(self._draft_text.split())
            elif "text" in result:
                # Simple format with just text
                self._confirmed_text = result.get("text", "")
                self._finalized_tokens = len(self._confirmed_text.split())

        elif isinstance(result, str):
            # Plain string result
            self._confirmed_text = result
            self._finalized_tokens = len(result.split())

        elif hasattr(result, "finalized") and hasattr(result, "draft"):
            # Object with attributes
            self._confirmed_text = getattr(result, "finalized", "")
            self._draft_text = getattr(result, "draft", "")
            self._finalized_tokens = len(self._confirmed_text.split())
            self._draft_tokens = len(self._draft_text.split())
