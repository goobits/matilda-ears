import logging
import os
import time
from typing import Tuple, Optional, Dict, Any

import numpy as np

from .base import TranscriptionBackend
from ...core.config import get_config

logger = logging.getLogger(__name__)
config = get_config()

# Enforce dependencies at module level so import fails if missing
try:
    import mlx.core
    import parakeet_mlx
except ImportError:
    raise ImportError("parakeet-mlx or mlx is not installed")

class ParakeetBackend(TranscriptionBackend):
    """Backend implementation using parakeet-mlx for Apple Silicon."""

    def __init__(self):
        self.model_name = config.get("parakeet.model", "mlx-community/parakeet-tdt-0.6b-v3")
        self.model = None
        self.processor = None

        # Configure chunk duration and overlap to reduce MPS pressure and prevent AGXG15X crashes
        # These settings trade slight performance for stability on macOS Metal/MPS
        self.chunk_duration = config.get("parakeet.chunk_duration", 120.0)  # Duration in seconds for each chunk
        self.overlap_duration = config.get("parakeet.overlap_duration", 15.0)  # Overlap between chunks for continuity

        # Streaming configuration
        self._streaming_context_size = tuple(
            config.get("parakeet.streaming.context_size", [128, 128])
        )
        self._streaming_depth = config.get("parakeet.streaming.depth", 1)

        # Streaming state - maps session_id to streaming context
        self._streaming_contexts: Dict[str, Any] = {}
        self._streaming_start_times: Dict[str, float] = {}
        self._streaming_sample_counts: Dict[str, int] = {}

        logger.info(
            f"Parakeet config: chunk_duration={self.chunk_duration}s, "
            f"overlap_duration={self.overlap_duration}s, "
            f"streaming_context_size={self._streaming_context_size}"
        )

    async def load(self):
        """Load Parakeet model."""
        try:
            from parakeet_mlx import from_pretrained

            # Set MPS fallback environment variable before loading model
            os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")

            logger.info(f"Loading Parakeet model: {self.model_name}")
            # parakeet loading might be blocking, so we should consider running it in executor if it takes time
            # However, MLX lazy loading might make it fast.
            self.model = from_pretrained(self.model_name)
            logger.info(f"Parakeet model {self.model_name} loaded successfully")

        except Exception as e:
            logger.exception(f"Failed to load Parakeet model: {e}")
            raise

    def transcribe(self, audio_path: str, language: str = "en") -> Tuple[str, dict]:
        """Transcribe audio using Parakeet with MPS-safe parameters."""
        if self.model is None:
            raise RuntimeError("Parakeet Model not loaded")

        start_time = time.time()

        try:
            # Use chunk_duration and overlap_duration parameters per parakeet-mlx API
            # This prevents Metal command buffer overflows (AGXG15X crashes)
            result = self.model.transcribe(
                audio_path,
                chunk_duration=self.chunk_duration,
                overlap_duration=self.overlap_duration
            )
            text = result.text.strip()

            # Calculate duration (approximate if not available)
            duration = time.time() - start_time

            # Attempt to get accurate duration from result if available
            audio_duration = 0.0
            if hasattr(result, 'sentences') and result.sentences:
                audio_duration = result.sentences[-1].end

            # Use processing time if we couldn't get duration from audio
            if audio_duration == 0.0:
                audio_duration = duration

            return text, {
                "duration": audio_duration,
                "language": "en", # Parakeet is primarily English AFAIK
                "backend": "parakeet"
            }

        except Exception as e:
            logger.error(f"Parakeet transcription failed: {e}")
            raise

    @property
    def is_ready(self) -> bool:
        return self.model is not None

    # ==================== STREAMING IMPLEMENTATION ====================

    @property
    def supports_streaming(self) -> bool:
        """Parakeet MLX supports native streaming via transcribe_stream()."""
        return True

    async def start_streaming(self, session_id: str, **config) -> Dict[str, Any]:
        """
        Start a streaming transcription session using Parakeet's native streaming.

        Args:
            session_id: Unique identifier for this streaming session.
            **config: Optional overrides for context_size, depth.

        Returns:
            Dict with session info.
        """
        if session_id in self._streaming_contexts:
            raise RuntimeError(f"Streaming session {session_id} already exists")

        if self.model is None:
            raise RuntimeError("Parakeet model not loaded. Call load() first.")

        # Get config with optional overrides
        context_size = tuple(config.get("context_size", self._streaming_context_size))
        depth = config.get("depth", self._streaming_depth)

        logger.info(
            f"Starting Parakeet streaming session {session_id} "
            f"(context_size={context_size}, depth={depth})"
        )

        try:
            # Create streaming context using Parakeet's native API
            # transcribe_stream() returns a context manager
            stream_ctx = self.model.transcribe_stream(
                context_size=context_size,
                depth=depth,
                keep_original_attention=False  # Use local attention for streaming
            )

            # Enter the context manager
            transcriber = stream_ctx.__enter__()

            # Store the context and transcriber
            self._streaming_contexts[session_id] = {
                "context_manager": stream_ctx,
                "transcriber": transcriber,
                "context_size": context_size,
                "depth": depth,
            }
            self._streaming_start_times[session_id] = time.time()
            self._streaming_sample_counts[session_id] = 0

            return {
                "session_id": session_id,
                "ready": True,
                "context_size": context_size,
                "depth": depth,
                "backend": "parakeet",
            }

        except Exception as e:
            logger.error(f"Failed to start streaming session {session_id}: {e}")
            raise RuntimeError(f"Failed to start streaming: {e}")

    async def process_chunk(self, session_id: str, audio_chunk: np.ndarray) -> Dict[str, Any]:
        """
        Process an audio chunk and return partial transcription.

        Args:
            session_id: Session ID from start_streaming().
            audio_chunk: Audio data as numpy array (int16 or float32, 16kHz mono).

        Returns:
            Dict with partial transcription result.
        """
        if session_id not in self._streaming_contexts:
            raise RuntimeError(f"No streaming session with ID: {session_id}")

        ctx = self._streaming_contexts[session_id]
        transcriber = ctx["transcriber"]

        # Track sample count for duration calculation
        self._streaming_sample_counts[session_id] += len(audio_chunk)

        try:
            # Add audio chunk to the streaming transcriber
            # Parakeet expects int16 or float32 numpy array at 16kHz
            transcriber.add_audio(audio_chunk)

            # Get current result
            result = transcriber.result

            # Extract token info if available
            finalized_count = 0
            draft_count = 0
            if hasattr(transcriber, "finalized_tokens"):
                finalized_count = len(transcriber.finalized_tokens)
            if hasattr(transcriber, "draft_tokens"):
                draft_count = len(transcriber.draft_tokens)

            return {
                "text": result.text if result else "",
                "is_final": False,
                "tokens": {
                    "finalized": finalized_count,
                    "draft": draft_count,
                },
            }

        except Exception as e:
            logger.error(f"Error processing chunk for session {session_id}: {e}")
            return {
                "text": "",
                "is_final": False,
                "error": str(e),
            }

    async def end_streaming(self, session_id: str) -> Dict[str, Any]:
        """
        End a streaming session and return the final transcription.

        Args:
            session_id: Session ID from start_streaming().

        Returns:
            Dict with final transcription result.
        """
        if session_id not in self._streaming_contexts:
            raise RuntimeError(f"No streaming session with ID: {session_id}")

        ctx = self._streaming_contexts[session_id]
        transcriber = ctx["transcriber"]
        stream_ctx = ctx["context_manager"]

        try:
            # Get final result before exiting context
            result = transcriber.result
            text = result.text.strip() if result else ""

            # Calculate duration from sample count (16kHz sample rate)
            sample_count = self._streaming_sample_counts.get(session_id, 0)
            audio_duration = sample_count / 16000.0

            # Exit the context manager properly
            stream_ctx.__exit__(None, None, None)

            logger.info(
                f"Ended Parakeet streaming session {session_id}: "
                f"{len(text)} chars, {audio_duration:.2f}s audio"
            )

            return {
                "text": text,
                "is_final": True,
                "duration": audio_duration,
                "language": "en",  # Parakeet is English-focused
                "backend": "parakeet",
            }

        except Exception as e:
            logger.error(f"Error ending streaming session {session_id}: {e}")
            # Try to clean up even on error
            try:
                stream_ctx.__exit__(None, None, None)
            except Exception:
                pass
            raise RuntimeError(f"Failed to end streaming: {e}")

        finally:
            # Clean up session state
            self._streaming_contexts.pop(session_id, None)
            self._streaming_start_times.pop(session_id, None)
            self._streaming_sample_counts.pop(session_id, None)
