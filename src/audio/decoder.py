"""Opus audio decoder for streaming audio processing."""

import io
import wave
import numpy as np
import opuslib
from typing import Optional

# Setup standardized logging
try:
    from ..config import setup_logging

    logger = setup_logging(__name__, log_filename="audio_decoder.txt")
except ImportError:
    # Fallback for standalone usage
    import logging

    logging.basicConfig()
    logger = logging.getLogger(__name__)


class OpusDecoder:
    """Handles Opus decoding and PCM audio accumulation for streaming."""

    def __init__(self, sample_rate: int = 16000, channels: int = 1):
        """Initialize Opus decoder.

        Args:
            sample_rate: Audio sample rate (default: 16000 for Whisper)
            channels: Number of audio channels (default: 1 for mono)

        """
        self.sample_rate = sample_rate
        self.channels = channels
        self.frame_size = 960  # 60ms at 16kHz

        # Initialize Opus decoder
        self.decoder = opuslib.Decoder(sample_rate, channels)

        # PCM audio buffer (accumulates decoded audio)
        self.pcm_buffer = io.BytesIO()
        self.sample_count = 0

        logger.info(f"Opus decoder initialized: {sample_rate}Hz, {channels} channel(s)")

    def decode_chunk(self, opus_data: bytes) -> int:
        """Decode an Opus chunk and append to PCM buffer.

        Args:
            opus_data: Opus-encoded audio data

        Returns:
            Number of samples decoded

        """
        try:
            # Decode Opus to PCM, explicitly providing the frame size
            pcm_data = self.decoder.decode(opus_data, self.frame_size)

            # Write decoded PCM to buffer
            self.pcm_buffer.write(pcm_data)

            # Track sample count (2 bytes per sample for 16-bit audio)
            samples_decoded = len(pcm_data) // 2
            self.sample_count += samples_decoded

            logger.debug(f"Decoded {len(opus_data)} bytes Opus → {len(pcm_data)} bytes PCM ({samples_decoded} samples)")
            return samples_decoded

        except Exception as e:
            logger.error(f"Opus decoding error: {e}")
            raise

    def get_wav_data(self) -> bytes:
        """Get accumulated audio as WAV format data.

        Returns:
            Complete WAV file data ready for Whisper

        """
        # Get PCM data from buffer
        self.pcm_buffer.seek(0)
        pcm_data = self.pcm_buffer.read()

        # Create WAV file in memory
        wav_buffer = io.BytesIO()

        with wave.open(wav_buffer, "wb") as wav_file:
            wav_file.setnchannels(self.channels)
            wav_file.setsampwidth(2)  # 16-bit audio
            wav_file.setframerate(self.sample_rate)
            wav_file.writeframes(pcm_data)

        # Return complete WAV data
        wav_buffer.seek(0)
        wav_data = wav_buffer.read()

        logger.info(
            f"Generated WAV: {len(wav_data)} bytes, {self.sample_count} samples, {self.sample_count/self.sample_rate:.2f}s duration"
        )
        return wav_data

    def get_pcm_array(self) -> np.ndarray:
        """Get accumulated audio as numpy array.

        Returns:
            PCM audio data as int16 numpy array

        """
        # Get PCM data
        self.pcm_buffer.seek(0)
        pcm_data = self.pcm_buffer.read()

        # Convert to numpy array
        audio_array = np.frombuffer(pcm_data, dtype=np.int16)

        return audio_array

    def reset(self):
        """Reset decoder and clear buffers."""
        self.pcm_buffer = io.BytesIO()
        self.sample_count = 0
        logger.debug("Decoder reset")

    def get_duration(self) -> float:
        """Get duration of accumulated audio in seconds."""
        return self.sample_count / self.sample_rate if self.sample_rate > 0 else 0.0

    def get_stats(self) -> dict:
        """Get decoder statistics."""
        return {
            "sample_rate": self.sample_rate,
            "channels": self.channels,
            "frame_size": self.frame_size,
            "samples_accumulated": self.sample_count,
            "duration_seconds": self.get_duration(),
            "buffer_size_bytes": self.pcm_buffer.tell(),
        }


class OpusStreamDecoder:
    """Manages multiple Opus decoding sessions for concurrent streams."""

    def __init__(self):
        """Initialize stream decoder manager."""
        self.sessions = {}
        logger.info("Opus stream decoder initialized")

    def create_session(self, session_id: str, sample_rate: int = 16000, channels: int = 1) -> OpusDecoder:
        """Create a new decoding session.

        Args:
            session_id: Unique identifier for the session
            sample_rate: Audio sample rate
            channels: Number of channels

        Returns:
            OpusDecoder instance for the session

        """
        if session_id in self.sessions:
            logger.warning(f"Session {session_id} already exists, replacing")

        decoder = OpusDecoder(sample_rate, channels)
        self.sessions[session_id] = decoder

        logger.info(f"Created decoding session: {session_id}")
        return decoder

    def get_session(self, session_id: str) -> Optional[OpusDecoder]:
        """Get an existing session decoder."""
        return self.sessions.get(session_id)

    def remove_session(self, session_id: str) -> Optional[OpusDecoder]:
        """Remove and return a session decoder."""
        decoder = self.sessions.pop(session_id, None)
        if decoder:
            logger.info(f"Removed decoding session: {session_id}")
        return decoder

    def get_active_sessions(self) -> list:
        """Get list of active session IDs."""
        return list(self.sessions.keys())
