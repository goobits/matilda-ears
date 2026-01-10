"""Audio buffer with sliding window and offset tracking.

Provides AudioBuffer that maintains a fixed-size audio window with:
- O(1) append using chunk-based storage
- Automatic trimming when max size exceeded
- Offset tracking for absolute timestamps
- Concatenation deferred to get_audio() call
"""

from collections import deque
import numpy as np
import logging

logger = logging.getLogger(__name__)


class AudioBuffer:
    """Sliding window audio buffer with offset tracking.

    Maintains a bounded audio buffer that automatically trims older audio
    when the maximum size is exceeded. Tracks the cumulative offset so that
    absolute timestamps can be maintained.

    Uses chunk-based storage for O(1) append operations, deferring
    concatenation to when audio is actually needed.

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

        # Chunk-based storage for O(1) append
        self._chunks: deque[np.ndarray] = deque()
        self._samples_in_buffer: int = 0
        self._offset_samples: int = 0  # Samples trimmed from start
        self._total_samples: int = 0  # Total samples ever received

        # Cache for concatenated audio (invalidated on append/trim)
        self._cached_audio: np.ndarray | None = None

    @property
    def offset_seconds(self) -> float:
        """Cumulative offset in seconds (audio trimmed from start)."""
        return self._offset_samples / self.sample_rate

    @property
    def duration_seconds(self) -> float:
        """Current buffer duration in seconds."""
        return self._samples_in_buffer / self.sample_rate

    @property
    def total_duration_seconds(self) -> float:
        """Total audio duration received (including trimmed)."""
        return self._total_samples / self.sample_rate

    @property
    def samples_in_buffer(self) -> int:
        """Number of samples currently in buffer."""
        return self._samples_in_buffer

    def append(self, audio_chunk: np.ndarray) -> int:
        """Append audio chunk to buffer.

        Automatically trims oldest audio if buffer exceeds max size.
        O(1) operation - concatenation deferred to get_audio().

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

        # Append chunk (O(1))
        self._chunks.append(audio_chunk)
        self._samples_in_buffer += len(audio_chunk)
        self._total_samples += len(audio_chunk)
        self._cached_audio = None  # Invalidate cache

        # Trim if exceeded max size
        trimmed = self._trim_to_max()

        return trimmed

    def _trim_to_max(self) -> int:
        """Trim oldest chunks to stay within max_samples."""
        if self._samples_in_buffer <= self.max_samples:
            return 0

        trimmed = 0
        while self._samples_in_buffer > self.max_samples and self._chunks:
            oldest = self._chunks[0]
            samples_to_remove = self._samples_in_buffer - self.max_samples

            if len(oldest) <= samples_to_remove:
                # Remove entire chunk
                self._chunks.popleft()
                self._samples_in_buffer -= len(oldest)
                self._offset_samples += len(oldest)
                trimmed += len(oldest)
            else:
                # Partial trim of first chunk
                keep_samples = len(oldest) - samples_to_remove
                self._chunks[0] = oldest[-keep_samples:]
                self._samples_in_buffer -= samples_to_remove
                self._offset_samples += samples_to_remove
                trimmed += samples_to_remove
                break

        if trimmed > 0:
            self._cached_audio = None  # Invalidate cache
            logger.debug(f"Buffer trimmed: {trimmed} samples, offset now {self.offset_seconds:.2f}s")

        return trimmed

    def get_audio(self) -> tuple[np.ndarray, float]:
        """Get current buffer audio and offset.

        Concatenates chunks if needed (cached for repeated calls).

        Returns:
            (audio_array, offset_seconds) tuple

        """
        if self._cached_audio is None:
            if not self._chunks:
                self._cached_audio = np.array([], dtype=np.float32)
            elif len(self._chunks) == 1:
                self._cached_audio = self._chunks[0].copy()
            else:
                self._cached_audio = np.concatenate(list(self._chunks))

        return self._cached_audio.copy(), self.offset_seconds

    def trim_to_seconds(self, keep_seconds: float) -> int:
        """Trim buffer to keep only the last N seconds.

        Args:
            keep_seconds: Duration to keep in seconds

        Returns:
            Number of samples trimmed

        """
        keep_samples = int(keep_seconds * self.sample_rate)
        if self._samples_in_buffer <= keep_samples:
            return 0

        target_trim = self._samples_in_buffer - keep_samples
        trimmed = 0

        while trimmed < target_trim and self._chunks:
            oldest = self._chunks[0]
            remaining_to_trim = target_trim - trimmed

            if len(oldest) <= remaining_to_trim:
                # Remove entire chunk
                self._chunks.popleft()
                self._samples_in_buffer -= len(oldest)
                self._offset_samples += len(oldest)
                trimmed += len(oldest)
            else:
                # Partial trim
                self._chunks[0] = oldest[remaining_to_trim:]
                self._samples_in_buffer -= remaining_to_trim
                self._offset_samples += remaining_to_trim
                trimmed += remaining_to_trim
                break

        if trimmed > 0:
            self._cached_audio = None
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
        if trim_samples >= self._samples_in_buffer:
            # Would trim everything - keep at least a small amount
            trim_samples = max(0, self._samples_in_buffer - self.sample_rate)  # Keep 1s minimum

        if trim_samples <= 0:
            return 0

        # Trim the calculated amount
        trimmed = 0
        while trimmed < trim_samples and self._chunks:
            oldest = self._chunks[0]
            remaining = trim_samples - trimmed

            if len(oldest) <= remaining:
                self._chunks.popleft()
                self._samples_in_buffer -= len(oldest)
                self._offset_samples += len(oldest)
                trimmed += len(oldest)
            else:
                self._chunks[0] = oldest[remaining:]
                self._samples_in_buffer -= remaining
                self._offset_samples += remaining
                trimmed += remaining
                break

        if trimmed > 0:
            self._cached_audio = None
            logger.debug(f"Trimmed to time {absolute_time:.2f}s: {trimmed} samples")

        return trimmed

    def clear(self) -> None:
        """Clear all buffered audio (keeps offset for continuity)."""
        self._offset_samples += self._samples_in_buffer
        self._chunks.clear()
        self._samples_in_buffer = 0
        self._cached_audio = None

    def reset(self) -> None:
        """Fully reset buffer including offset tracking."""
        self._chunks.clear()
        self._samples_in_buffer = 0
        self._offset_samples = 0
        self._total_samples = 0
        self._cached_audio = None

    def to_wav_bytes(self) -> bytes:
        """Convert current buffer to WAV format bytes.

        Useful for passing to batch transcription APIs.

        Returns:
            WAV file bytes

        """
        import io
        import wave

        audio, _ = self.get_audio()

        # Convert to int16 for WAV
        samples_int16 = (audio * 32768).astype(np.int16)

        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)  # 16-bit
            wav_file.setframerate(self.sample_rate)
            wav_file.writeframes(samples_int16.tobytes())

        return buffer.getvalue()
