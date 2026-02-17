"""Audio conversion helpers for PCM scaling."""

from typing import cast

import numpy as np


def int16_to_float32(audio: np.ndarray) -> np.ndarray:
    """Convert int16 PCM to float32 in [-1.0, 1.0]."""
    if audio.dtype == np.int16:
        return audio.astype(np.float32) / 32768.0
    return audio.astype(np.float32)


def float32_to_int16(audio: np.ndarray) -> np.ndarray:
    """Convert float PCM in [-1.0, 1.0] to int16."""
    if audio.dtype == np.int16:
        return audio
    audio_f32 = audio.astype(np.float32)
    return cast("np.ndarray", np.clip(audio_f32 * 32768.0, -32768, 32767).astype(np.int16))
