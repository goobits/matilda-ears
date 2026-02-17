"""Public audio capture API.

This module intentionally re-exports a small, explicit surface from
`matilda_ears.audio.internal.capture` to avoid leaking internal names.
"""

from .internal.capture import PipeBasedAudioStreamer, StreamingStats

__all__ = ["PipeBasedAudioStreamer", "StreamingStats"]
