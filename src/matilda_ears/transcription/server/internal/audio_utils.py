"""Audio utilities for sample rate validation and resampling.

This module provides audio processing utilities for the WebSocket server:
- Sample rate validation (accepts 8000Hz and 16000Hz)
- Resampling to 16000Hz (required by Whisper models)
"""

import io
import wave
from typing import TYPE_CHECKING, cast

import numpy as np

from ....core.config import setup_logging
from ....audio.conversion import float32_to_int16, int16_to_float32

if TYPE_CHECKING:
    from .session_registry import ServerSession

logger = setup_logging(__name__, log_filename="transcription.txt")

# Supported sample rates
SUPPORTED_SAMPLE_RATES = {8000, 16000, 48000}
TARGET_SAMPLE_RATE = 16000


def downmix_to_mono(pcm_samples: np.ndarray, channels: int) -> np.ndarray:
    """Downmix interleaved PCM samples to mono."""
    if channels <= 1 or pcm_samples.size == 0:
        return pcm_samples

    frame_count = pcm_samples.size // channels
    if frame_count == 0:
        return np.array([], dtype=pcm_samples.dtype)

    frames = pcm_samples[: frame_count * channels].reshape(frame_count, channels).astype(np.int32)
    return np.clip(frames.mean(axis=1), -32768, 32767).astype(np.int16)


def validate_sample_rate(sample_rate: int) -> tuple[bool, str | None]:
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
        samples_float = int16_to_float32(pcm_samples)
    else:
        samples_float = pcm_samples.astype(np.float32)

    # Create output time indices
    output_indices = np.linspace(0, len(samples_float) - 1, output_length)

    # Interpolate
    resampled = np.interp(output_indices, np.arange(len(samples_float)), samples_float)

    # Convert back to original dtype
    if original_dtype == np.int16:
        # Clip to prevent overflow and convert back to int16
        resampled = float32_to_int16(resampled)
    else:
        resampled = resampled.astype(original_dtype)

    logger.debug(
        f"Resampled audio: {len(pcm_samples)} samples @ {source_rate}Hz -> {len(resampled)} samples @ {target_rate}Hz"
    )

    return cast("np.ndarray", resampled)


def resample_to_16k(pcm_samples: np.ndarray, source_rate: int) -> np.ndarray:
    """Convenience function to resample audio to 16kHz.

    Args:
        pcm_samples: Input PCM samples
        source_rate: Source sample rate in Hz

    Returns:
        Resampled PCM samples at 16kHz

    """
    return resample_audio(pcm_samples, source_rate, TARGET_SAMPLE_RATE)


def decode_opus_chunk(decoder, opus_data: bytes) -> np.ndarray:
    """Decode an Opus packet to 16 kHz mono PCM."""
    pcm_samples = downmix_to_mono(decoder.decode_chunk(opus_data), decoder.channels)
    if decoder.sample_rate != TARGET_SAMPLE_RATE:
        return resample_to_16k(pcm_samples, decoder.sample_rate)
    return pcm_samples


def pcm_to_wav(samples: np.ndarray, sample_rate: int, channels: int = 1) -> bytes:
    """Convert interleaved int16 PCM samples to WAV bytes."""
    if samples.dtype != np.int16:
        samples = samples.astype(np.int16)

    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(channels)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(samples.tobytes())
    return buffer.getvalue()


def session_audio_to_wav(session: "ServerSession") -> tuple[bytes, float] | None:
    """Return normalized WAV bytes and duration for a server session."""
    if session.pcm is not None:
        samples = session.pcm.as_array()
        sample_rate = TARGET_SAMPLE_RATE if session.pcm.needs_resampling else session.pcm.sample_rate
        return pcm_to_wav(samples, sample_rate, 1), len(samples) / sample_rate

    if session.decoder is not None:
        samples = downmix_to_mono(session.decoder.get_pcm_array(), session.decoder.channels)
        if session.decoder.sample_rate != TARGET_SAMPLE_RATE:
            samples = resample_to_16k(samples, session.decoder.sample_rate)
            sample_rate = TARGET_SAMPLE_RATE
        else:
            sample_rate = session.decoder.sample_rate
        return pcm_to_wav(samples, sample_rate, 1), len(samples) / sample_rate

    return None
