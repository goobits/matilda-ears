"""Audio buffer with sliding window and offset tracking.

Provides AudioBuffer that maintains a fixed-size audio window with:
- Automatic trimming when max size exceeded
- Offset tracking for absolute timestamps
- Efficient numpy-based operations
"""

import numpy as np
from typing import Tuple
import logging

logger = logging.getLogger(__name__)


class AudioBuffer:
    """Sliding window audio buffer with offset tracking.

    Maintains a bounded audio buffer that automatically trims older audio
    when the maximum size is exceeded. Tracks the cumulative offset so that
    absolute timestamps can be maintained.

    Example:
        buffer = AudioBuffer(max_seconds=30.0, sample_rate=16000)
        buffer.append(audio_chunk)  # Add audio

        # Get current buffer for transcription
        audio, offset = buffer.get_audio()

        # Trim to keep only last N seconds
        buffer.trim_to_seconds(20.0)

    """

    def __init__(self, max_seconds: float, sample_rate: int = 16000):
        """Initialize audio buffer.

        Args:
            max_seconds: Maximum buffer duration in seconds
            sample_rate: Audio sample rate in Hz

        """
        self.max_seconds = max_seconds
        self.sample_rate = sample_rate
        self.max_samples = int(max_seconds * sample_rate)

        # Buffer state
        self._buffer: np.ndarray = np.array([], dtype=np.float32)
        self._offset_samples: int = 0  # Samples trimmed from start
        self._total_samples: int = 0  # Total samples ever received

    @property
    def offset_seconds(self) -> float:
        """Cumulative offset in seconds (audio trimmed from start)."""
        return self._offset_samples / self.sample_rate

    @property
    def duration_seconds(self) -> float:
        """Current buffer duration in seconds."""
        return len(self._buffer) / self.sample_rate

    @property
    def total_duration_seconds(self) -> float:
        """Total audio duration received (including trimmed)."""
        return self._total_samples / self.sample_rate

    @property
    def samples_in_buffer(self) -> int:
        """Number of samples currently in buffer."""
        return len(self._buffer)

    def append(self, audio_chunk: np.ndarray) -> int:
        """Append audio chunk to buffer.

        Automatically trims oldest audio if buffer exceeds max size.

        Args:
            audio_chunk: Audio samples (float32 or int16)

        Returns:
            Number of samples trimmed (0 if no trimming occurred)

        """
        # Convert int16 to float32 if needed
        if audio_chunk.dtype == np.int16:
            audio_chunk = audio_chunk.astype(np.float32) / 32768.0
        elif audio_chunk.dtype != np.float32:
            audio_chunk = audio_chunk.astype(np.float32)

        # Append to buffer
        self._buffer = np.concatenate([self._buffer, audio_chunk])
        self._total_samples += len(audio_chunk)

        # Trim if exceeded max size
        trimmed = 0
        if len(self._buffer) > self.max_samples:
            trimmed = len(self._buffer) - self.max_samples
            self._buffer = self._buffer[-self.max_samples :]
            self._offset_samples += trimmed
            logger.debug(f"Buffer trimmed: {trimmed} samples, offset now {self.offset_seconds:.2f}s")

        return trimmed

    def get_audio(self) -> Tuple[np.ndarray, float]:
        """Get current buffer audio and offset.

        Returns:
            (audio_array, offset_seconds) tuple

        """
        return self._buffer.copy(), self.offset_seconds

    def trim_to_seconds(self, keep_seconds: float) -> int:
        """Trim buffer to keep only the last N seconds.

        Args:
            keep_seconds: Duration to keep in seconds

        Returns:
            Number of samples trimmed

        """
        keep_samples = int(keep_seconds * self.sample_rate)
        if len(self._buffer) <= keep_samples:
            return 0

        trimmed = len(self._buffer) - keep_samples
        self._buffer = self._buffer[-keep_samples:]
        self._offset_samples += trimmed

        logger.debug(f"Manually trimmed: {trimmed} samples, offset now {self.offset_seconds:.2f}s")
        return trimmed

    def trim_to_time(self, absolute_time: float) -> int:
        """Trim buffer up to an absolute timestamp.

        Removes all audio before the given absolute time.

        Args:
            absolute_time: Absolute time in seconds (relative to stream start)

        Returns:
            Number of samples trimmed

        """
        # Convert absolute time to buffer-relative position
        buffer_start_time = self.offset_seconds
        if absolute_time <= buffer_start_time:
            return 0  # Already trimmed past this point

        # How many seconds into the buffer?
        relative_time = absolute_time - buffer_start_time
        trim_samples = int(relative_time * self.sample_rate)

        if trim_samples <= 0:
            return 0
        if trim_samples >= len(self._buffer):
            # Would trim everything - keep at least a small amount
            trim_samples = max(0, len(self._buffer) - self.sample_rate)  # Keep 1s minimum

        if trim_samples > 0:
            self._buffer = self._buffer[trim_samples:]
            self._offset_samples += trim_samples
            logger.debug(f"Trimmed to time {absolute_time:.2f}s: {trim_samples} samples")

        return trim_samples

    def clear(self) -> None:
        """Clear all buffered audio (keeps offset for continuity)."""
        self._offset_samples += len(self._buffer)
        self._buffer = np.array([], dtype=np.float32)

    def reset(self) -> None:
        """Fully reset buffer including offset tracking."""
        self._buffer = np.array([], dtype=np.float32)
        self._offset_samples = 0
        self._total_samples = 0

    def to_wav_bytes(self) -> bytes:
        """Convert current buffer to WAV format bytes.

        Useful for passing to batch transcription APIs.

        Returns:
            WAV file bytes

        """
        import io
        import wave

        # Convert to int16 for WAV
        samples_int16 = (self._buffer * 32768).astype(np.int16)

        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)  # 16-bit
            wav_file.setframerate(self.sample_rate)
            wav_file.writeframes(samples_int16.tobytes())

        return buffer.getvalue()
