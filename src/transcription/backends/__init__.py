"""
Transcription backends package.
"""
import logging
from typing import Optional, Type
from .base import TranscriptionBackend
from .faster_whisper_backend import FasterWhisperBackend

logger = logging.getLogger(__name__)

# Conditionally import Parakeet backend
try:
    from .parakeet_backend import ParakeetBackend
    PARAKEET_AVAILABLE = True
except ImportError:
    PARAKEET_AVAILABLE = False


def get_available_backends() -> list:
    """
    Return list of available backend names.

    Returns:
        List of backend names that are currently available.
    """
    backends = ["faster_whisper"]
    if PARAKEET_AVAILABLE:
        backends.append("parakeet")
    return backends


def get_backend_class(backend_name: str) -> Type[TranscriptionBackend]:
    """
    Factory function to get the backend class based on name.

    Args:
        backend_name: 'faster_whisper' or 'parakeet'

    Returns:
        The backend class.

    Raises:
        ValueError: If backend is unknown or unavailable.
    """
    if backend_name == "faster_whisper":
        return FasterWhisperBackend

    if backend_name == "parakeet":
        if not PARAKEET_AVAILABLE:
            raise ValueError(
                "Parakeet backend requested but dependencies are not installed.\n"
                "To use Parakeet on macOS with Apple Silicon:\n"
                "  1. Install: ./setup.sh install --dev (includes [mac] extras)\n"
                "  2. Or: pip install goobits-stt[mac]\n"
                "Note: Parakeet requires macOS with Metal/MLX support (M1/M2/M3 chips)"
            )
        return ParakeetBackend

    raise ValueError(
        f"Unknown backend: '{backend_name}'\n"
        f"Available backends:\n"
        f"  - 'faster_whisper' (default): Cross-platform Whisper with CUDA support\n"
        f"  - 'parakeet': Apple Silicon MLX-optimized (requires [mac] extras)\n"
        f"Check your config.json: {{\"transcription\": {{\"backend\": \"faster_whisper\"}}}}"
    )
