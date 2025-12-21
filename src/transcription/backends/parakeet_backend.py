import logging
import os
import time
from typing import Tuple, Optional, Dict

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

        # Configure smaller chunk sizes to reduce MPS pressure and prevent AGXG15X crashes
        # These settings trade slight performance for stability on macOS Metal/MPS
        self.chunk_length = config.get("parakeet.chunk_length", 15)  # Smaller chunks (default: 30s)
        self.batch_size = config.get("parakeet.batch_size", 1)  # Force batch_size=1 for MPS
        logger.info(f"Parakeet MPS-optimized config: chunk_length={self.chunk_length}s, batch_size={self.batch_size}")

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
            # Use smaller chunk_length and batch_size to reduce MPS pressure
            # This prevents Metal command buffer overflows (AGXG15X crashes)
            result = self.model.transcribe(
                audio_path,
                chunk_length=self.chunk_length,
                batch_size=self.batch_size
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
