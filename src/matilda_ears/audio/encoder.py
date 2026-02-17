"""Public audio encoder API.

This module intentionally re-exports a small, explicit surface from
`matilda_ears.audio.internal.encoder` to avoid leaking internal names.
"""

from .internal.encoder import OpusEncoder

__all__ = ["OpusEncoder"]
