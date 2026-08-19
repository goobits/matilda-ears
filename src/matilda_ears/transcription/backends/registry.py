from __future__ import annotations

import importlib
import logging
import platform
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass

from .base import BackendNotAvailableError, TranscriptionBackend

logger = logging.getLogger(__name__)

PARAKEET_AVAILABLE: bool | None = None
HUGGINGFACE_AVAILABLE: bool | None = None
HUB_AVAILABLE: bool | None = None
IS_APPLE_SILICON: bool | None = None


def _always_available() -> bool:
    return True


def _is_apple_silicon() -> bool:
    global IS_APPLE_SILICON
    if IS_APPLE_SILICON is not None:
        return IS_APPLE_SILICON
    if platform.system() != "Darwin":
        IS_APPLE_SILICON = False
        return False
    if platform.machine().lower() in ("arm64", "aarch64"):
        IS_APPLE_SILICON = True
        return True
    try:
        result = subprocess.run(
            ["sysctl", "-n", "machdep.cpu.brand_string"],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
        IS_APPLE_SILICON = result.returncode == 0 and "Apple" in result.stdout
    except Exception:
        IS_APPLE_SILICON = False
    return IS_APPLE_SILICON


def _check_parakeet_available() -> bool:
    global PARAKEET_AVAILABLE
    if PARAKEET_AVAILABLE is not None:
        return PARAKEET_AVAILABLE
    try:
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                "import importlib; importlib.import_module('matilda_ears.transcription.backends.internal.parakeet')",
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
        PARAKEET_AVAILABLE = result.returncode == 0
        if not PARAKEET_AVAILABLE:
            logger.debug("Parakeet backend unavailable: %s", (result.stderr or result.stdout).strip())
    except Exception as exc:
        logger.debug("Parakeet backend unavailable: %s", exc)
        PARAKEET_AVAILABLE = False
    return PARAKEET_AVAILABLE


def _check_huggingface_available() -> bool:
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


@dataclass(frozen=True)
class BackendSpec:
    name: str
    module: str
    class_name: str
    description: str
    models: str
    install: str
    capabilities: frozenset[str]
    availability: Callable[[], bool] = _always_available
    aliases: tuple[str, ...] = ()
    unavailable_message: str = ""


BACKEND_SPECS = {
    spec.name: spec
    for spec in (
        BackendSpec(
            name="dummy",
            module=".internal.dummy",
            class_name="DummyBackend",
            description="Deterministic test backend (no model downloads)",
            models="N/A",
            install="Included by default",
            capabilities=frozenset({"file", "server"}),
        ),
        BackendSpec(
            name="faster_whisper",
            module=".internal.faster_whisper",
            class_name="FasterWhisperBackend",
            description="Cross-platform Whisper with CUDA/CPU support",
            models="Whisper tiny/base/small/medium/large-v3",
            install="Included by default",
            capabilities=frozenset({"file", "server"}),
            aliases=("faster-whisper", "whisper"),
        ),
        BackendSpec(
            name="parakeet",
            module=".internal.parakeet",
            class_name="ParakeetBackend",
            description="Apple Silicon MLX-optimized transcription",
            models="Parakeet TDT, RNNT, CTC variants",
            install="pip install goobits-matilda-ears[mac]",
            capabilities=frozenset({"file", "server", "mlx", "serialized"}),
            availability=_check_parakeet_available,
            unavailable_message=(
                "Parakeet backend requested but dependencies are not installed.\n"
                "Install with: pip install goobits-matilda-ears[mac]\n"
                "Parakeet requires macOS with Metal/MLX support."
            ),
        ),
        BackendSpec(
            name="huggingface",
            module=".internal.huggingface",
            class_name="HuggingFaceBackend",
            description="Universal backend for 17,000+ HuggingFace ASR models",
            models="Whisper, Wav2Vec2, HuBERT, MMS, Canary, and others",
            install="pip install goobits-matilda-ears[huggingface]",
            capabilities=frozenset({"file", "server"}),
            availability=_check_huggingface_available,
            aliases=("hf",),
            unavailable_message=(
                "HuggingFace backend requested but dependencies are not installed.\n"
                "Install with: pip install goobits-matilda-ears[huggingface]"
            ),
        ),
        BackendSpec(
            name="moss",
            module=".internal.moss",
            class_name="MossBackend",
            description="Native offline transcription with speaker diarization",
            models="MOSS-Transcribe-Diarize q8_0/q5_k GGUF",
            install="ears download --backend moss --model q8_0",
            capabilities=frozenset({"file", "diarization"}),
        ),
        BackendSpec(
            name="hub",
            module=".internal.hub",
            class_name="HubBackend",
            description="Hub-backed transcription via matilda-api gateway",
            models="Configured by hub",
            install="Requires matilda-transport",
            capabilities=frozenset({"file", "server"}),
            availability=_check_hub_available,
            unavailable_message="Hub backend requires matilda-transport. Install it or choose a local backend.",
        ),
    )
}

BACKEND_ALIASES = {alias: spec.name for spec in BACKEND_SPECS.values() for alias in spec.aliases}


def normalize_backend_name(backend_name: object) -> str:
    if backend_name is None:
        return "auto"
    name = str(backend_name).strip().lower()
    return BACKEND_ALIASES.get(name, name) if name else "auto"


def get_recommended_backend() -> str:
    if _is_apple_silicon() and _check_parakeet_available():
        return "parakeet"
    return "faster_whisper"


def get_backend_spec(backend_name: str) -> BackendSpec:
    name = normalize_backend_name(backend_name)
    spec = BACKEND_SPECS.get(name)
    if spec is None:
        available = get_available_backends()
        raise ValueError(f"Unknown backend: '{name}'\nAvailable backends: {', '.join(available)}")
    return spec


def backend_supports(backend_name: str, capability: str) -> bool:
    return capability in get_backend_spec(backend_name).capabilities


def get_available_backends() -> list[str]:
    return [name for name, spec in BACKEND_SPECS.items() if spec.availability()]


def get_backend_info() -> dict[str, dict]:
    return {
        name: {
            "available": spec.availability(),
            "description": spec.description,
            "models": spec.models,
            "install": spec.install,
            "capabilities": sorted(spec.capabilities),
        }
        for name, spec in BACKEND_SPECS.items()
    }


def get_backend_class(backend_name: str) -> type[TranscriptionBackend]:
    spec = get_backend_spec(backend_name)
    if not spec.availability():
        raise BackendNotAvailableError(spec.unavailable_message or f"Backend unavailable: {spec.name}")
    module = importlib.import_module(spec.module, package=__package__)
    backend_class = getattr(module, spec.class_name)
    if not isinstance(backend_class, type) or not issubclass(backend_class, TranscriptionBackend):
        raise TypeError(f"Registered backend is not a TranscriptionBackend: {spec.name}")
    return backend_class
