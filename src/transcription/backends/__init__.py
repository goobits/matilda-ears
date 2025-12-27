"""
Transcription backends package.

Supported backends:
- faster_whisper: Cross-platform Whisper with CUDA support (default)
- parakeet: Apple Silicon MLX-optimized
- huggingface: Universal backend supporting 17,000+ HuggingFace ASR models
"""
import logging
from typing import Optional, Type, List, Dict
from .base import TranscriptionBackend
from .faster_whisper_backend import FasterWhisperBackend

logger = logging.getLogger(__name__)

PARAKEET_AVAILABLE: Optional[bool] = None
HUGGINGFACE_AVAILABLE: Optional[bool] = None


def _check_parakeet_available() -> bool:
    """Return whether the Parakeet backend can be imported."""
    global PARAKEET_AVAILABLE
    if PARAKEET_AVAILABLE is not None:
        return PARAKEET_AVAILABLE
    try:
        from . import parakeet_backend as _parakeet_backend
        PARAKEET_AVAILABLE = True
    except Exception as exc:
        logger.debug(f"Parakeet backend unavailable: {exc}")
        PARAKEET_AVAILABLE = False
    return PARAKEET_AVAILABLE


def _check_huggingface_available() -> bool:
    """Return whether the HuggingFace backend can be imported."""
    global HUGGINGFACE_AVAILABLE
    if HUGGINGFACE_AVAILABLE is not None:
        return HUGGINGFACE_AVAILABLE
    try:
        from . import huggingface_backend as _huggingface_backend
        HUGGINGFACE_AVAILABLE = True
    except Exception as exc:
        logger.debug(f"HuggingFace backend unavailable: {exc}")
        HUGGINGFACE_AVAILABLE = False
    return HUGGINGFACE_AVAILABLE


def get_available_backends() -> List[str]:
    """
    Return list of available backend names.

    Returns:
        List of backend names that are currently available.
    """
    backends = ["faster_whisper"]
    if _check_parakeet_available():
        backends.append("parakeet")
    if _check_huggingface_available():
        backends.append("huggingface")
    return backends


def get_backend_info() -> Dict[str, Dict]:
    """
    Return detailed info about all backends.

    Returns:
        Dict mapping backend name to info dict with 'available', 'description', 'install'.
    """
    return {
        "faster_whisper": {
            "available": True,
            "description": "Cross-platform Whisper with CUDA/CPU support",
            "models": "Whisper tiny/base/small/medium/large-v3",
            "install": "Included by default",
        },
        "parakeet": {
            "available": _check_parakeet_available(),
            "description": "Apple Silicon MLX-optimized (M1/M2/M3)",
            "models": "Parakeet TDT, RNNT, CTC variants",
            "install": "pip install goobits-stt[mac]",
        },
        "huggingface": {
            "available": _check_huggingface_available(),
            "description": "Universal backend for 17,000+ HuggingFace ASR models",
            "models": "Whisper, Wav2Vec2, Wav2Vec2-BERT, HuBERT, MMS, Canary, etc.",
            "install": "pip install goobits-stt[huggingface]",
        },
    }


def get_backend_class(backend_name: str) -> Type[TranscriptionBackend]:
    """
    Factory function to get the backend class based on name.

    Args:
        backend_name: 'faster_whisper', 'parakeet', or 'huggingface'

    Returns:
        The backend class.

    Raises:
        ValueError: If backend is unknown or unavailable.
    """
    if backend_name == "faster_whisper":
        return FasterWhisperBackend

    if backend_name == "parakeet":
        if not _check_parakeet_available():
            raise ValueError(
                "Parakeet backend requested but dependencies are not installed.\n"
                "To use Parakeet on macOS with Apple Silicon:\n"
                "  1. Install: ./setup.sh install --dev (includes [mac] extras)\n"
                "  2. Or: pip install goobits-stt[mac]\n"
                "Note: Parakeet requires macOS with Metal/MLX support (M1/M2/M3 chips)"
            )
        from .parakeet_backend import ParakeetBackend
        return ParakeetBackend

    if backend_name == "huggingface":
        if not _check_huggingface_available():
            raise ValueError(
                "HuggingFace backend requested but dependencies are not installed.\n"
                "To use HuggingFace Transformers ASR models:\n"
                "  1. Install: pip install goobits-stt[huggingface]\n"
                "  2. Or: pip install transformers torch\n"
                "This backend supports 17,000+ ASR models from HuggingFace Hub."
            )
        from .huggingface_backend import HuggingFaceBackend
        return HuggingFaceBackend

    # Unknown backend - provide helpful error
    available = get_available_backends()
    raise ValueError(
        f"Unknown backend: '{backend_name}'\n"
        f"Available backends: {', '.join(available)}\n"
        f"  - 'faster_whisper' (default): Cross-platform Whisper with CUDA support\n"
        f"  - 'parakeet': Apple Silicon MLX-optimized (requires [mac] extras)\n"
        f"  - 'huggingface': Universal HuggingFace ASR (requires [huggingface] extras)\n"
        f"Check your config.json: {{\"transcription\": {{\"backend\": \"{available[0]}\"}}}}"
    )
