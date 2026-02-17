"""Backend registry and availability checks.

Keep backend selection logic centralized here so other modules don't need to do
import-probing or platform checks.
"""

from __future__ import annotations

import logging
import platform
import subprocess

from .base import BackendNotAvailableError, TranscriptionBackend

logger = logging.getLogger(__name__)

PARAKEET_AVAILABLE: bool | None = None
HUGGINGFACE_AVAILABLE: bool | None = None
HUB_AVAILABLE: bool | None = None
IS_APPLE_SILICON: bool | None = None


def _is_apple_silicon() -> bool:
    """Detect if running on Apple Silicon (M1/M2/M3/M4 chips)."""
    global IS_APPLE_SILICON
    if IS_APPLE_SILICON is not None:
        return IS_APPLE_SILICON

    # Must be macOS
    if platform.system() != "Darwin":
        IS_APPLE_SILICON = False
        return False

    # Check for ARM architecture (Apple Silicon)
    machine = platform.machine().lower()
    if machine in ("arm64", "aarch64"):
        IS_APPLE_SILICON = True
        logger.debug("Detected Apple Silicon (ARM64)")
        return True

    # Fallback: check via sysctl (handles Rosetta translation)
    try:
        result = subprocess.run(
            ["sysctl", "-n", "machdep.cpu.brand_string"],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0 and "Apple" in result.stdout:
            IS_APPLE_SILICON = True
            logger.debug("Detected Apple Silicon via sysctl: %s", result.stdout.strip())
            return True
    except Exception:
        pass

    IS_APPLE_SILICON = False
    return False


def get_recommended_backend() -> str:
    """Get the recommended backend for the current platform.

    Returns:
        'parakeet' on Apple Silicon if available, otherwise 'faster_whisper'.

    """
    if _is_apple_silicon() and _check_parakeet_available():
        logger.info("Recommending parakeet backend for Apple Silicon")
        return "parakeet"
    return "faster_whisper"


def _check_parakeet_available() -> bool:
    """Return whether the Parakeet backend can be imported."""
    global PARAKEET_AVAILABLE
    if PARAKEET_AVAILABLE is not None:
        return PARAKEET_AVAILABLE
    try:
        from .internal import parakeet as _parakeet_backend  # noqa: F401

        PARAKEET_AVAILABLE = True
    except Exception as exc:
        logger.debug("Parakeet backend unavailable: %s", exc)
        PARAKEET_AVAILABLE = False
    return PARAKEET_AVAILABLE


def _check_huggingface_available() -> bool:
    """Return whether the HuggingFace backend can be imported."""
    global HUGGINGFACE_AVAILABLE
    if HUGGINGFACE_AVAILABLE is not None:
        return HUGGINGFACE_AVAILABLE
    try:
        from .internal import huggingface as _huggingface_backend  # noqa: F401

        HUGGINGFACE_AVAILABLE = True
    except Exception as exc:
        logger.debug("HuggingFace backend unavailable: %s", exc)
        HUGGINGFACE_AVAILABLE = False
    return HUGGINGFACE_AVAILABLE


def _check_hub_available() -> bool:
    """Return whether the Hub backend can be used (matilda-transport installed)."""
    global HUB_AVAILABLE
    if HUB_AVAILABLE is not None:
        return HUB_AVAILABLE
    try:
        from matilda_transport import HubClient  # noqa: F401

        HUB_AVAILABLE = True
    except Exception as exc:
        logger.debug("Hub backend unavailable: %s", exc)
        HUB_AVAILABLE = False
    return HUB_AVAILABLE


def get_available_backends() -> list[str]:
    """Return list of available backend names."""
    backends = ["dummy", "faster_whisper"]
    if _check_hub_available():
        backends.append("hub")
    if _check_parakeet_available():
        backends.append("parakeet")
    if _check_huggingface_available():
        backends.append("huggingface")
    return backends


def get_backend_info() -> dict[str, dict]:
    """Return detailed info about all backends."""
    return {
        "dummy": {
            "available": True,
            "description": "Deterministic test backend (no model downloads)",
            "models": "N/A",
            "install": "Included by default",
        },
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
            "install": "pip install goobits-matilda-ears[mac]",
        },
        "huggingface": {
            "available": _check_huggingface_available(),
            "description": "Universal backend for 17,000+ HuggingFace ASR models",
            "models": "Whisper, Wav2Vec2, Wav2Vec2-BERT, HuBERT, MMS, Canary, etc.",
            "install": "pip install goobits-matilda-ears[huggingface]",
        },
        "hub": {
            "available": _check_hub_available(),
            "description": "Hub-backed transcription via matilda-api gateway",
            "models": "Configured by hub",
            "install": "Requires matilda-transport",
        },
    }


def get_backend_class(backend_name: str) -> type[TranscriptionBackend]:
    """Factory function to get the backend class based on name."""
    if backend_name == "dummy":
        from .internal.dummy import DummyBackend

        return DummyBackend

    if backend_name == "faster_whisper":
        from .internal.faster_whisper import FasterWhisperBackend

        return FasterWhisperBackend

    if backend_name == "parakeet":
        if not _check_parakeet_available():
            raise BackendNotAvailableError(
                "Parakeet backend requested but dependencies are not installed.\n"
                "To use Parakeet on macOS with Apple Silicon:\n"
                "  1. Install: ./setup.sh install --dev (includes [mac] extras)\n"
                "  2. Or: pip install goobits-matilda-ears[mac]\n"
                "Note: Parakeet requires macOS with Metal/MLX support (M1/M2/M3 chips)"
            )
        from .internal.parakeet import ParakeetBackend

        return ParakeetBackend

    if backend_name == "huggingface":
        if not _check_huggingface_available():
            raise BackendNotAvailableError(
                "HuggingFace backend requested but dependencies are not installed.\n"
                "To use HuggingFace Transformers ASR models:\n"
                "  1. Install: pip install goobits-matilda-ears[huggingface]\n"
                "  2. Or: pip install transformers torch\n"
                "This backend supports 17,000+ ASR models from HuggingFace Hub."
            )
        from .internal.huggingface import HuggingFaceBackend

        return HuggingFaceBackend

    if backend_name == "hub":
        if not _check_hub_available():
            raise BackendNotAvailableError(
                "Hub backend requested but matilda-transport is not installed.\n"
                "Install matilda-transport or choose a local backend.\n"
                'Hint: set [ears.transcription] backend = "faster_whisper"'
            )
        from .internal.hub import HubBackend

        return HubBackend

    available = get_available_backends()
    raise ValueError(
        f"Unknown backend: '{backend_name}'\n"
        f"Available backends: {', '.join(available)}\n"
        f"  - 'dummy': Deterministic test backend (no model)\n"
        f"  - 'faster_whisper' (default): Cross-platform Whisper with CUDA support\n"
        f"  - 'parakeet': Apple Silicon MLX-optimized (requires [mac] extras)\n"
        f"  - 'huggingface': Universal HuggingFace ASR (requires [huggingface] extras)\n"
        f"  - 'hub': Hub-backed transcription via matilda-api\n"
        f'Check your matilda config: [ears.transcription] backend = "{available[0]}"'
    )
