"""Parakeet MLX backend for Apple Silicon.

Provides batch transcription for macOS. Real-time streaming is handled
by the streaming framework using NativeStrategy, which calls the model's
transcribe_stream() method directly.
"""

import logging
import os

from ..base import TranscriptionBackend
from ...transcript import Transcript, TranscriptSegment
from ....core.config import get_config
from ....core.mlx_memory import clear_mlx_cache, mlx_memory_stats

logger = logging.getLogger(__name__)

# Enforce dependencies at module level so import fails if missing
try:
    import mlx.core  # noqa: F401
    import parakeet_mlx  # noqa: F401
except ImportError:
    raise ImportError("parakeet-mlx or mlx is not installed")


def _config_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return _config_bool(value)


class ParakeetBackend(TranscriptionBackend):
    """Backend implementation using parakeet-mlx for Apple Silicon.

    The model's native transcribe_stream() method can be accessed by the
    streaming framework's NativeStrategy for real-time transcription.
    """

    def __init__(self):
        config = get_config()
        self.model_name = config.get("parakeet.model", "mlx-community/parakeet-tdt-0.6b-v3")
        self.model = None
        self.processor = None
        self.clear_mlx_cache_after_transcribe = _env_bool(
            "MATILDA_EARS_MLX_CLEAR_CACHE",
            _config_bool(config.get("parakeet.clear_mlx_cache", True)),
        )

        # Configure chunk duration and overlap to reduce MPS pressure and prevent AGXG15X crashes
        # These settings trade slight performance for stability on macOS Metal/MPS
        self.chunk_duration = config.get("parakeet.chunk_duration", 120.0)
        self.overlap_duration = config.get("parakeet.overlap_duration", 15.0)

        logger.info(
            "Parakeet config: chunk_duration=%ss, overlap_duration=%ss, clear_mlx_cache=%s",
            self.chunk_duration,
            self.overlap_duration,
            self.clear_mlx_cache_after_transcribe,
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

    def transcribe(self, audio_path: str, language: str = "en") -> Transcript:
        """Transcribe audio using Parakeet with MPS-safe parameters."""
        if self.model is None:
            raise RuntimeError("Parakeet Model not loaded")

        try:
            mlx_before = mlx_memory_stats()
            # Use chunk_duration and overlap_duration parameters per parakeet-mlx API
            # This prevents Metal command buffer overflows (AGXG15X crashes)
            result = self.model.transcribe(
                audio_path, chunk_duration=self.chunk_duration, overlap_duration=self.overlap_duration
            )
            text = result.text.strip()
            sentences = getattr(result, "sentences", None) or ()
            segments = tuple(
                TranscriptSegment(
                    start=float(sentence.start),
                    end=float(sentence.end),
                    text=str(sentence.text).strip(),
                )
                for sentence in sentences
                if getattr(sentence, "text", "").strip()
            )
            audio_duration = float(sentences[-1].end) if sentences else None
            mlx_after = mlx_memory_stats()
            if mlx_before or mlx_after:
                logger.debug("Parakeet MLX memory before=%s after=%s", mlx_before, mlx_after)

            return Transcript(
                text=text,
                segments=segments,
                language="en",
                duration=audio_duration,
                backend="parakeet",
            )

        except Exception as e:
            logger.error(f"Parakeet transcription failed: {e}")
            raise
        finally:
            if self.clear_mlx_cache_after_transcribe:
                released = clear_mlx_cache()
                mlx_cleanup = mlx_memory_stats()
                logger.info("Parakeet MLX cache cleanup complete (released=%s, mlx=%s)", released, mlx_cleanup)

    @property
    def is_ready(self) -> bool:
        return self.model is not None

    def transcribe_stream(self, context_size=(128, 128), depth=1):
        """Access the model's native streaming API.

        This method is called by the streaming framework's NativeStrategy.

        Args:
            context_size: Tuple of (left_context, right_context) in frames
            depth: Streaming depth parameter

        Returns:
            Context manager for streaming transcription

        """
        if self.model is None:
            raise RuntimeError("Parakeet model not loaded. Call load() first.")

        return self.model.transcribe_stream(
            context_size=context_size,
            depth=depth,
            keep_original_attention=False,
        )
