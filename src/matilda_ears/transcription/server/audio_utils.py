"""Audio utilities for sample rate validation and resampling.

This module provides audio processing utilities for the WebSocket server:
- Sample rate validation (accepts 8000Hz and 16000Hz)
- Resampling to 16000Hz (required by Whisper models)
"""

import numpy as np
from typing import Tuple, Optional

from ...core.config import setup_logging

logger = setup_logging(__name__, log_filename="transcription.txt")

# Supported sample rates
SUPPORTED_SAMPLE_RATES = {8000, 16000}
TARGET_SAMPLE_RATE = 16000


def validate_sample_rate(sample_rate: int) -> Tuple[bool, Optional[str]]:
    """Validate that the sample rate is supported.

    Args:
        sample_rate: The sample rate in Hz

    Returns:
        Tuple of (is_valid, error_message)
        - If valid: (True, None)
        - If invalid: (False, error_message)
    """
    if sample_rate not in SUPPORTED_SAMPLE_RATES:
        supported_str = ", ".join(f"{r}Hz" for r in sorted(SUPPORTED_SAMPLE_RATES))
        return False, f"Unsupported sample rate: {sample_rate}Hz. Supported rates: {supported_str}"
    return True, None


def needs_resampling(sample_rate: int) -> bool:
    """Check if audio at this sample rate needs resampling to 16kHz."""
    return sample_rate != TARGET_SAMPLE_RATE


def resample_audio(pcm_samples: np.ndarray, source_rate: int, target_rate: int = TARGET_SAMPLE_RATE) -> np.ndarray:
    """Resample PCM audio from source_rate to target_rate.

    Uses linear interpolation for simple resampling. For production use with
    quality-critical applications, consider using scipy.signal.resample or
    librosa.resample.

    Args:
        pcm_samples: Input PCM samples as numpy array (int16 or float32)
        source_rate: Source sample rate in Hz
        target_rate: Target sample rate in Hz (default: 16000)

    Returns:
        Resampled PCM samples as numpy array (same dtype as input)
    """
    if source_rate == target_rate:
        return pcm_samples

    if len(pcm_samples) == 0:
        return pcm_samples

    # Calculate resampling ratio
    ratio = target_rate / source_rate

    # Calculate output length
    output_length = int(len(pcm_samples) * ratio)

    if output_length == 0:
        return np.array([], dtype=pcm_samples.dtype)

    # Store original dtype for conversion back
    original_dtype = pcm_samples.dtype

    # Convert to float for interpolation
    if pcm_samples.dtype == np.int16:
        samples_float = pcm_samples.astype(np.float32) / 32768.0
    else:
        samples_float = pcm_samples.astype(np.float32)

    # Create output time indices
    output_indices = np.linspace(0, len(samples_float) - 1, output_length)

    # Interpolate
    resampled = np.interp(output_indices, np.arange(len(samples_float)), samples_float)

    # Convert back to original dtype
    if original_dtype == np.int16:
        # Clip to prevent overflow and convert back to int16
        resampled = np.clip(resampled * 32768.0, -32768, 32767).astype(np.int16)
    else:
        resampled = resampled.astype(original_dtype)

    logger.debug(
        f"Resampled audio: {len(pcm_samples)} samples @ {source_rate}Hz -> "
        f"{len(resampled)} samples @ {target_rate}Hz"
    )

    return resampled


def resample_to_16k(pcm_samples: np.ndarray, source_rate: int) -> np.ndarray:
    """Convenience function to resample audio to 16kHz.

    Args:
        pcm_samples: Input PCM samples
        source_rate: Source sample rate in Hz

    Returns:
        Resampled PCM samples at 16kHz
    """
    return resample_audio(pcm_samples, source_rate, TARGET_SAMPLE_RATE)
