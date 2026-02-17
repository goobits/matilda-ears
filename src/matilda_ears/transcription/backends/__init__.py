"""Transcription backends package.

Public API surface for backend selection lives here; the implementation details
and import-probing live in :mod:`matilda_ears.transcription.backends.registry`.

Supported backends:
- dummy: Deterministic test backend (no model)
- faster_whisper: Cross-platform Whisper with CUDA support (default)
- parakeet: Apple Silicon MLX-optimized (optional)
- huggingface: Universal backend supporting many HuggingFace ASR models (optional)
- hub: Hub-backed transcription via matilda-api gateway
"""

from .base import TranscriptionBackend
from .registry import get_available_backends, get_backend_class, get_backend_info, get_recommended_backend

__all__ = [
    "TranscriptionBackend",
    "get_available_backends",
    "get_backend_class",
    "get_backend_info",
    "get_recommended_backend",
]

