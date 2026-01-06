"""Opus audio encoder for streaming audio to server."""

import numpy as np
import opuslib
from typing import Optional

# Setup standardized logging
try:
    from ...core.config import setup_logging

    logger = setup_logging(__name__, log_filename="audio_encoder.txt")
except ImportError:
    # Fallback for standalone usage
    import logging
    logger = logging.getLogger(__name__)


class OpusEncoder:
    """Handles Opus encoding for streaming audio."""

    def __init__(self, sample_rate: int = 16000, channels: int = 1, bitrate: int = 24000):
        """Initialize Opus encoder.

        Args:
            sample_rate: Audio sample rate (default: 16000 for Whisper)
            channels: Number of audio channels (default: 1 for mono)
            bitrate: Opus bitrate in bits per second (default: 24000)

        """
        self.sample_rate = sample_rate
        self.channels = channels
        self.bitrate = bitrate
        self.frame_size = 960  # 60ms at 16kHz

        # Initialize Opus encoder
        self.encoder = opuslib.Encoder(sample_rate, channels, opuslib.APPLICATION_AUDIO)

        # Audio buffer for accumulating samples
        self.audio_buffer: list[int] = []
        self.buffer_size = 0

        logger.info(f"Opus encoder initialized: {sample_rate}Hz, {channels} channel(s), {bitrate}bps")

    def encode_chunk(self, audio_data: np.ndarray) -> Optional[bytes]:
        """Encode audio chunk to Opus format.

        Args:
            audio_data: Audio samples as numpy array (float32 or int16)

        Returns:
            Opus-encoded data if frame is complete, None if buffering

        """
        # Convert to int16 if needed
        if audio_data.dtype == np.float32:
            audio_data = (audio_data * 32767).astype(np.int16)

        # Add to buffer
        self.audio_buffer.extend(audio_data)
        self.buffer_size += len(audio_data)

        # Check if we have enough samples for a frame
        if self.buffer_size >= self.frame_size:
            # Extract frame
            frame = np.array(self.audio_buffer[: self.frame_size], dtype=np.int16)

            # Remove from buffer
            self.audio_buffer = self.audio_buffer[self.frame_size :]
            self.buffer_size -= self.frame_size

            # Encode with Opus
            try:
                encoded = self.encoder.encode(frame.tobytes(), self.frame_size)
                logger.debug(f"Encoded frame: {self.frame_size} samples → {len(encoded)} bytes")
                return bytes(encoded)
            except Exception as e:
                logger.error(f"Opus encoding error: {e}")
                return None

        return None

    def flush(self) -> Optional[bytes]:
        """Encode any remaining samples in buffer with padding."""
        if self.buffer_size == 0:
            return None

        # Pad to frame size
        padding_needed = self.frame_size - self.buffer_size
        frame = np.array(self.audio_buffer + [0] * padding_needed, dtype=np.int16)

        # Clear buffer
        self.audio_buffer = []
        self.buffer_size = 0

        # Encode
        try:
            encoded = self.encoder.encode(frame.tobytes(), self.frame_size)
            logger.debug(f"Encoded final frame with {padding_needed} padding samples")
            return bytes(encoded)
        except Exception as e:
            logger.error(f"Opus encoding error on flush: {e}")
            return None

    def reset(self):
        """Reset encoder and clear buffers."""
        self.audio_buffer = []
        self.buffer_size = 0
        logger.debug("Encoder reset")


# All streaming functionality has been moved to core/transcription_client.py
# Use TranscriptionClient.create_streaming_session() for streaming transcription.
