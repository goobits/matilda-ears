"""Unit tests for AudioBuffer."""

import pytest
import numpy as np
from matilda_ears.transcription.streaming.buffer import AudioBuffer


class TestAudioBufferInit:
    """Test AudioBuffer initialization."""

    def test_init_default_sample_rate(self):
        """Test initialization with default sample rate."""
        buffer = AudioBuffer(max_seconds=30.0)
        assert buffer.max_seconds == 30.0
        assert buffer.sample_rate == 16000
        assert buffer.max_samples == 30 * 16000

    def test_init_custom_sample_rate(self):
        """Test initialization with custom sample rate."""
        buffer = AudioBuffer(max_seconds=10.0, sample_rate=48000)
        assert buffer.sample_rate == 48000
        assert buffer.max_samples == 10 * 48000

    def test_init_empty_buffer(self):
        """Test buffer starts empty."""
        buffer = AudioBuffer(max_seconds=30.0)
        assert buffer.samples_in_buffer == 0
        assert buffer.duration_seconds == 0.0
        assert buffer.offset_seconds == 0.0


class TestAudioBufferAppend:
    """Test AudioBuffer.append() method."""

    def test_append_float32(self):
        """Test appending float32 audio."""
        buffer = AudioBuffer(max_seconds=30.0, sample_rate=16000)
        audio = np.random.randn(16000).astype(np.float32)

        trimmed = buffer.append(audio)

        assert trimmed == 0
        assert buffer.samples_in_buffer == 16000
        assert buffer.duration_seconds == pytest.approx(1.0)

    def test_append_int16_conversion(self):
        """Test appending int16 audio is converted to float32."""
        buffer = AudioBuffer(max_seconds=30.0, sample_rate=16000)
        audio = (np.random.randn(16000) * 32768).astype(np.int16)

        buffer.append(audio)

        result, _ = buffer.get_audio()
        assert result.dtype == np.float32
        # Check values are normalized to [-1, 1] range
        assert result.max() <= 1.0
        assert result.min() >= -1.0

    def test_append_multiple_chunks(self):
        """Test appending multiple chunks."""
        buffer = AudioBuffer(max_seconds=30.0, sample_rate=16000)

        for _ in range(5):
            audio = np.random.randn(16000).astype(np.float32)
            buffer.append(audio)

        assert buffer.samples_in_buffer == 5 * 16000
        assert buffer.duration_seconds == pytest.approx(5.0)

    def test_append_auto_trim(self):
        """Test auto-trimming when max size exceeded."""
        buffer = AudioBuffer(max_seconds=2.0, sample_rate=16000)

        # Add 3 seconds of audio (exceeds 2 second max)
        audio = np.random.randn(3 * 16000).astype(np.float32)
        trimmed = buffer.append(audio)

        assert trimmed == 16000  # 1 second trimmed
        assert buffer.samples_in_buffer == 2 * 16000
        assert buffer.offset_seconds == pytest.approx(1.0)

    def test_append_incremental_trim(self):
        """Test incremental trimming over multiple appends."""
        buffer = AudioBuffer(max_seconds=2.0, sample_rate=16000)

        # Add 1 second chunks until we exceed
        for i in range(3):
            audio = np.random.randn(16000).astype(np.float32)
            buffer.append(audio)

        # After 3 seconds, should have 2 seconds buffered
        assert buffer.samples_in_buffer == 2 * 16000
        assert buffer.offset_seconds == pytest.approx(1.0)
        assert buffer.total_duration_seconds == pytest.approx(3.0)


class TestAudioBufferTrim:
    """Test AudioBuffer trimming methods."""

    def test_trim_to_seconds(self):
        """Test trim_to_seconds method."""
        buffer = AudioBuffer(max_seconds=30.0, sample_rate=16000)
        audio = np.random.randn(5 * 16000).astype(np.float32)
        buffer.append(audio)

        trimmed = buffer.trim_to_seconds(2.0)

        assert trimmed == 3 * 16000
        assert buffer.duration_seconds == pytest.approx(2.0)
        assert buffer.offset_seconds == pytest.approx(3.0)

    def test_trim_to_seconds_no_op(self):
        """Test trim_to_seconds when already smaller."""
        buffer = AudioBuffer(max_seconds=30.0, sample_rate=16000)
        audio = np.random.randn(16000).astype(np.float32)
        buffer.append(audio)

        trimmed = buffer.trim_to_seconds(5.0)

        assert trimmed == 0
        assert buffer.duration_seconds == pytest.approx(1.0)

    def test_trim_to_time(self):
        """Test trim_to_time with absolute timestamp."""
        buffer = AudioBuffer(max_seconds=30.0, sample_rate=16000)
        audio = np.random.randn(5 * 16000).astype(np.float32)
        buffer.append(audio)

        # Trim up to 2 seconds absolute
        trimmed = buffer.trim_to_time(2.0)

        assert trimmed == 2 * 16000
        assert buffer.offset_seconds == pytest.approx(2.0)
        assert buffer.duration_seconds == pytest.approx(3.0)

    def test_trim_to_time_already_past(self):
        """Test trim_to_time when already past that point."""
        buffer = AudioBuffer(max_seconds=2.0, sample_rate=16000)

        # Add 5 seconds, auto-trims to 2 seconds with 3s offset
        audio = np.random.randn(5 * 16000).astype(np.float32)
        buffer.append(audio)

        # Try to trim to 2 seconds, but we're already at offset 3
        trimmed = buffer.trim_to_time(2.0)
        assert trimmed == 0

    def test_trim_preserves_offset_continuity(self):
        """Test that offset is maintained correctly through trims."""
        buffer = AudioBuffer(max_seconds=30.0, sample_rate=16000)

        # Add 10 seconds
        for i in range(10):
            audio = np.random.randn(16000).astype(np.float32)
            buffer.append(audio)

        initial_total = buffer.total_duration_seconds

        # Trim to 5 seconds
        buffer.trim_to_seconds(5.0)

        # Total should still be 10
        assert buffer.total_duration_seconds == pytest.approx(initial_total)
        # Offset + current = total
        assert buffer.offset_seconds + buffer.duration_seconds == pytest.approx(initial_total)


class TestAudioBufferGetAudio:
    """Test AudioBuffer.get_audio() method."""

    def test_get_audio_returns_copy(self):
        """Test get_audio returns a copy, not reference."""
        buffer = AudioBuffer(max_seconds=30.0, sample_rate=16000)
        audio = np.random.randn(16000).astype(np.float32)
        buffer.append(audio)

        result1, _ = buffer.get_audio()
        result2, _ = buffer.get_audio()

        # Modify result1
        result1[0] = 999.0

        # result2 should be unchanged
        assert result2[0] != 999.0

    def test_get_audio_with_offset(self):
        """Test get_audio returns correct offset after trimming."""
        buffer = AudioBuffer(max_seconds=2.0, sample_rate=16000)

        # Add 3 seconds, auto-trims 1 second
        audio = np.random.randn(3 * 16000).astype(np.float32)
        buffer.append(audio)

        result, offset = buffer.get_audio()

        assert len(result) == 2 * 16000
        assert offset == pytest.approx(1.0)


class TestAudioBufferClear:
    """Test AudioBuffer clear and reset methods."""

    def test_clear_preserves_offset(self):
        """Test clear() keeps offset for continuity."""
        buffer = AudioBuffer(max_seconds=30.0, sample_rate=16000)
        audio = np.random.randn(5 * 16000).astype(np.float32)
        buffer.append(audio)

        buffer.clear()

        assert buffer.samples_in_buffer == 0
        assert buffer.duration_seconds == 0.0
        assert buffer.offset_seconds == pytest.approx(5.0)

    def test_reset_clears_everything(self):
        """Test reset() clears all state including offset."""
        buffer = AudioBuffer(max_seconds=30.0, sample_rate=16000)
        audio = np.random.randn(5 * 16000).astype(np.float32)
        buffer.append(audio)
        buffer.trim_to_seconds(2.0)

        buffer.reset()

        assert buffer.samples_in_buffer == 0
        assert buffer.offset_seconds == 0.0
        assert buffer.total_duration_seconds == 0.0


class TestAudioBufferWav:
    """Test AudioBuffer WAV conversion."""

    def test_to_wav_bytes(self):
        """Test conversion to WAV bytes."""
        buffer = AudioBuffer(max_seconds=30.0, sample_rate=16000)
        audio = np.random.randn(16000).astype(np.float32)
        buffer.append(audio)

        wav_bytes = buffer.to_wav_bytes()

        # Check WAV header magic bytes
        assert wav_bytes[:4] == b"RIFF"
        assert wav_bytes[8:12] == b"WAVE"

    def test_to_wav_bytes_empty(self):
        """Test WAV conversion of empty buffer."""
        buffer = AudioBuffer(max_seconds=30.0, sample_rate=16000)
        wav_bytes = buffer.to_wav_bytes()

        # Should still produce valid WAV header
        assert wav_bytes[:4] == b"RIFF"
