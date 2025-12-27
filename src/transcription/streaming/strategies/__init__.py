"""Streaming strategies.

Available strategies:
- LocalAgreementStrategy: Uses LocalAgreement-2 with batch transcription (faster-whisper)
- ChunkedStrategy: Simple periodic batch transcription fallback
- NativeStrategy: Wraps native streaming APIs (Parakeet)
"""

from .protocol import StreamingStrategy
from .local_agreement import LocalAgreementStrategy
from .chunked import ChunkedStrategy
from .native import NativeStrategy

__all__ = [
    "StreamingStrategy",
    "LocalAgreementStrategy",
    "ChunkedStrategy",
    "NativeStrategy",
]
