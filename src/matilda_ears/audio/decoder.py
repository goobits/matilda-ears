"""Public audio decoder API.

This module intentionally re-exports a small, explicit surface from
`matilda_ears.audio.internal.decoder` to avoid leaking internal names.
"""

from .internal.decoder import OpusDecoder, OpusStreamDecoder

__all__ = ["OpusDecoder", "OpusStreamDecoder"]
