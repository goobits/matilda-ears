#!/usr/bin/env python3
"""Audio APIs for Matilda Ears.

Public surface is kept explicit to reduce accidental coupling to internals.
"""

from .capture import PipeBasedAudioStreamer, StreamingStats
from .conversion import float32_to_int16, int16_to_float32
from .decoder import OpusDecoder, OpusStreamDecoder
from .encoder import OpusEncoder
from .opus_batch import OpusBatchDecoder, OpusBatchEncoder
from .vad import SileroVAD, VADProbSmoother

__all__ = [
    "OpusBatchDecoder",
    "OpusBatchEncoder",
    "OpusDecoder",
    "OpusEncoder",
    "OpusStreamDecoder",
    "PipeBasedAudioStreamer",
    "SileroVAD",
    "StreamingStats",
    "VADProbSmoother",
    "float32_to_int16",
    "int16_to_float32",
]
