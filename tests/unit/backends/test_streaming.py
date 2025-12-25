"""
Unit tests for streaming transcription functionality across all backends.

Tests the streaming interface defined in TranscriptionBackend base class.
"""

import asyncio
import pytest
import numpy as np
from unittest.mock import Mock, MagicMock, patch, AsyncMock


class TestTranscriptionBackendStreamingInterface:
    """Test the streaming interface in the base TranscriptionBackend class."""

    def test_base_class_supports_streaming_default_false(self):
        """Base class should default supports_streaming to False."""
        from src.transcription.backends.base import TranscriptionBackend

        # Create a minimal concrete implementation
        class MinimalBackend(TranscriptionBackend):
            async def load(self):
                pass

            def transcribe(self, audio_path, language="en"):
                return "", {}

            @property
            def is_ready(self):
                return True

        backend = MinimalBackend()
        assert backend.supports_streaming is False

    @pytest.mark.asyncio
    async def test_base_class_streaming_methods_raise_not_implemented(self):
        """Base class streaming methods should raise NotImplementedError."""
        from src.transcription.backends.base import TranscriptionBackend

        class MinimalBackend(TranscriptionBackend):
            async def load(self):
                pass

            def transcribe(self, audio_path, language="en"):
                return "", {}

            @property
            def is_ready(self):
                return True

        backend = MinimalBackend()

        with pytest.raises(NotImplementedError):
            await backend.start_streaming("test-session")

        with pytest.raises(NotImplementedError):
            await backend.process_chunk("test-session", np.zeros(1600, dtype=np.int16))

        with pytest.raises(NotImplementedError):
            await backend.end_streaming("test-session")


class TestFasterWhisperBackendStreaming:
    """Test streaming functionality in FasterWhisperBackend."""

    @pytest.fixture
    def mock_config(self, monkeypatch):
        """Mock the config module."""
        mock_cfg = Mock()
        mock_cfg.whisper_model = "base"
        mock_cfg.whisper_device_auto = "cpu"
        mock_cfg.whisper_compute_type_auto = "int8"
        mock_cfg.get = Mock(return_value=None)
        monkeypatch.setattr("src.transcription.backends.faster_whisper_backend.config", mock_cfg)
        return mock_cfg

    def test_supports_streaming_is_true(self, mock_config):
        """FasterWhisperBackend should support streaming."""
        from src.transcription.backends.faster_whisper_backend import FasterWhisperBackend

        backend = FasterWhisperBackend()
        assert backend.supports_streaming is True

    @pytest.mark.asyncio
    async def test_start_streaming_without_model_raises_error(self, mock_config):
        """Starting streaming without loaded model should raise RuntimeError."""
        from src.transcription.backends.faster_whisper_backend import FasterWhisperBackend

        backend = FasterWhisperBackend()
        # Model not loaded

        with pytest.raises(RuntimeError, match="Model not loaded"):
            await backend.start_streaming("test-session")

    @pytest.mark.asyncio
    async def test_start_streaming_creates_session(self, mock_config):
        """Starting streaming should create a session and return info."""
        from src.transcription.backends.faster_whisper_backend import FasterWhisperBackend

        backend = FasterWhisperBackend()
        backend.model = Mock()  # Pretend model is loaded

        result = await backend.start_streaming("test-session-123")

        assert result["session_id"] == "test-session-123"
        assert result["ready"] is True
        assert result["backend"] == "faster_whisper"
        assert "test-session-123" in backend._streaming_buffers or "test-session-123" in backend._streaming_processors

    @pytest.mark.asyncio
    async def test_process_chunk_accumulates_audio(self, mock_config):
        """Processing chunks should accumulate audio in buffer."""
        from src.transcription.backends.faster_whisper_backend import FasterWhisperBackend

        backend = FasterWhisperBackend()
        backend.model = Mock()

        await backend.start_streaming("test-session")

        # Send a 100ms chunk (1600 samples at 16kHz)
        chunk = np.random.randint(-32768, 32767, 1600, dtype=np.int16)
        result = await backend.process_chunk("test-session", chunk)

        assert "text" in result
        assert result["is_final"] is False
        assert backend._streaming_sample_counts["test-session"] == 1600

    @pytest.mark.asyncio
    async def test_end_streaming_returns_final_result(self, mock_config):
        """Ending streaming should return final transcription."""
        from src.transcription.backends.faster_whisper_backend import FasterWhisperBackend

        backend = FasterWhisperBackend()
        backend.model = Mock()

        # Mock the transcribe method to return test text
        backend.transcribe = Mock(return_value=("Hello world", {"duration": 1.0}))

        await backend.start_streaming("test-session")

        # Send some audio
        chunk = np.random.randint(-32768, 32767, 16000, dtype=np.int16)
        await backend.process_chunk("test-session", chunk)

        result = await backend.end_streaming("test-session")

        assert result["is_final"] is True
        assert result["backend"] == "faster_whisper"
        assert "duration" in result
        # Session should be cleaned up
        assert "test-session" not in backend._streaming_buffers
        assert "test-session" not in backend._streaming_sample_counts

    @pytest.mark.asyncio
    async def test_duplicate_session_raises_error(self, mock_config):
        """Starting a session with existing ID should raise error."""
        from src.transcription.backends.faster_whisper_backend import FasterWhisperBackend

        backend = FasterWhisperBackend()
        backend.model = Mock()

        await backend.start_streaming("test-session")

        with pytest.raises(RuntimeError, match="already exists"):
            await backend.start_streaming("test-session")


class TestHuggingFaceBackendStreaming:
    """Test streaming functionality in HuggingFaceBackend."""

    @pytest.fixture
    def mock_hf_imports(self, monkeypatch):
        """Mock HuggingFace imports."""
        # Mock transformers availability
        monkeypatch.setattr(
            "src.transcription.backends.huggingface_backend.TRANSFORMERS_AVAILABLE",
            True
        )
        monkeypatch.setattr(
            "src.transcription.backends.huggingface_backend.TORCH_AVAILABLE",
            True
        )

        # Mock config
        mock_cfg = Mock()
        mock_cfg.get = Mock(return_value={})
        monkeypatch.setattr("src.transcription.backends.huggingface_backend.config", mock_cfg)

    def test_supports_streaming_is_true(self, mock_hf_imports):
        """HuggingFaceBackend should support streaming."""
        from src.transcription.backends.huggingface_backend import HuggingFaceBackend

        backend = HuggingFaceBackend()
        assert backend.supports_streaming is True

    @pytest.mark.asyncio
    async def test_start_streaming_without_model_raises_error(self, mock_hf_imports):
        """Starting streaming without loaded model should raise RuntimeError."""
        from src.transcription.backends.huggingface_backend import HuggingFaceBackend

        backend = HuggingFaceBackend()
        # Model not loaded (pipe is None)

        with pytest.raises(RuntimeError, match="Model not loaded"):
            await backend.start_streaming("test-session")

    @pytest.mark.asyncio
    async def test_streaming_session_lifecycle(self, mock_hf_imports):
        """Test full streaming session lifecycle."""
        from src.transcription.backends.huggingface_backend import HuggingFaceBackend

        backend = HuggingFaceBackend()
        backend.pipe = Mock()  # Pretend model is loaded
        backend.transcribe = Mock(return_value=("Test transcription", {"duration": 1.0}))

        # Start session
        start_result = await backend.start_streaming("lifecycle-test")
        assert start_result["ready"] is True
        assert "lifecycle-test" in backend._streaming_buffers

        # Process chunks
        for _ in range(5):
            chunk = np.random.randint(-32768, 32767, 1600, dtype=np.int16)
            await backend.process_chunk("lifecycle-test", chunk)

        # End session
        end_result = await backend.end_streaming("lifecycle-test")
        assert end_result["is_final"] is True
        assert "lifecycle-test" not in backend._streaming_buffers


class TestStreamingAudioFormat:
    """Test that streaming handles different audio formats correctly."""

    @pytest.fixture
    def mock_config(self, monkeypatch):
        """Mock config for backends."""
        mock_cfg = Mock()
        mock_cfg.whisper_model = "base"
        mock_cfg.whisper_device_auto = "cpu"
        mock_cfg.whisper_compute_type_auto = "int8"
        mock_cfg.get = Mock(return_value=None)
        monkeypatch.setattr("src.transcription.backends.faster_whisper_backend.config", mock_cfg)
        return mock_cfg

    @pytest.mark.asyncio
    async def test_process_chunk_accepts_int16(self, mock_config):
        """process_chunk should accept int16 audio data."""
        from src.transcription.backends.faster_whisper_backend import FasterWhisperBackend

        backend = FasterWhisperBackend()
        backend.model = Mock()

        await backend.start_streaming("test")
        chunk = np.zeros(1600, dtype=np.int16)
        result = await backend.process_chunk("test", chunk)

        assert "text" in result

    @pytest.mark.asyncio
    async def test_process_chunk_accepts_float32(self, mock_config):
        """process_chunk should accept float32 audio data."""
        from src.transcription.backends.faster_whisper_backend import FasterWhisperBackend

        backend = FasterWhisperBackend()
        backend.model = Mock()

        await backend.start_streaming("test")
        chunk = np.zeros(1600, dtype=np.float32)
        result = await backend.process_chunk("test", chunk)

        assert "text" in result


class TestStreamingConcurrency:
    """Test concurrent streaming sessions."""

    @pytest.fixture
    def mock_config(self, monkeypatch):
        """Mock config."""
        mock_cfg = Mock()
        mock_cfg.whisper_model = "base"
        mock_cfg.whisper_device_auto = "cpu"
        mock_cfg.whisper_compute_type_auto = "int8"
        mock_cfg.get = Mock(return_value=None)
        monkeypatch.setattr("src.transcription.backends.faster_whisper_backend.config", mock_cfg)
        return mock_cfg

    @pytest.mark.asyncio
    async def test_multiple_concurrent_sessions(self, mock_config):
        """Backend should handle multiple concurrent streaming sessions."""
        from src.transcription.backends.faster_whisper_backend import FasterWhisperBackend

        backend = FasterWhisperBackend()
        backend.model = Mock()
        backend.transcribe = Mock(return_value=("text", {"duration": 1.0}))

        # Start multiple sessions
        sessions = ["session-1", "session-2", "session-3"]
        for session_id in sessions:
            await backend.start_streaming(session_id)

        # Process chunks for each session
        for session_id in sessions:
            chunk = np.random.randint(-32768, 32767, 1600, dtype=np.int16)
            await backend.process_chunk(session_id, chunk)

        # End sessions
        for session_id in sessions:
            result = await backend.end_streaming(session_id)
            assert result["is_final"] is True

        # All sessions should be cleaned up
        assert len(backend._streaming_buffers) == 0
        assert len(backend._streaming_sample_counts) == 0
