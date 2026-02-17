"""Public batch Opus encode/decode API.

This module intentionally re-exports a small, explicit surface from
`matilda_ears.audio.internal.opus_batch` to avoid leaking internal names.
"""

from .internal.opus_batch import OpusBatchDecoder, OpusBatchEncoder

__all__ = ["OpusBatchDecoder", "OpusBatchEncoder"]
