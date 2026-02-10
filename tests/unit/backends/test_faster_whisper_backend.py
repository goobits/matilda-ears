#!/usr/bin/env python3
"""Unit tests for FasterWhisperBackend.

These tests mock the underlying faster-whisper library to verify
the backend wrapper logic works correctly.
"""

import pytest
import asyncio
import sys
from unittest.mock import Mock, patch, MagicMock


@pytest.fixture(autouse=True)
def isolate_faster_whisper_module():
    """Keep faster_whisper mocking scoped to each test."""
    with patch.dict(sys.modules, {"faster_whisper": MagicMock()}):
        yield


class TestFasterWhisperBackend:
    """Test suite for FasterWhisperBackend implementation."""

    @pytest.fixture
    def mock_config(self):
        """Mock configuration object."""
        config = Mock()
        config.whisper_model = "base"
        config.whisper_device_auto = "cpu"
        config.whisper_compute_type_auto = "int8"
        config.get = Mock(
            side_effect=lambda key, default=None: {
                "whisper.word_timestamps": True,
                "whisper.vad_filter": True,
                "whisper.vad_parameters": {
                    "threshold": 0.5,
                    "min_speech_duration_ms": 250,
                    "max_speech_duration_s": 30,
                    "min_silence_duration_ms": 200,
                },
                "whisper.no_speech_threshold": 0.6,
            }.get(key, default)
        )
        return config

    @pytest.fixture
    def mock_whisper_model(self):
        """Mock WhisperModel instance."""
        model = Mock()

        # Mock transcription output
        segment = Mock()
        segment.text = " Test transcription"
        segment.words = []

        info = Mock()
        info.duration = 2.5
        info.language = "en"

        model.transcribe.return_value = ([segment], info)
        return model

    def test_backend_initialization(self, mock_config):
        """Verify backend initializes with correct config values."""
        with patch("matilda_ears.transcription.backends.internal.faster_whisper.get_config", return_value=mock_config):
            from matilda_ears.transcription.backends.internal.faster_whisper import FasterWhisperBackend

            backend = FasterWhisperBackend()

            assert backend.model_size == "base"
            assert backend.device == "cpu"
            assert backend.compute_type == "int8"
            assert backend.model is None

    def test_backend_is_ready_before_load(self, mock_config):
        """Verify is_ready returns False before model is loaded."""
        with patch("matilda_ears.transcription.backends.internal.faster_whisper.get_config", return_value=mock_config):
            from matilda_ears.transcription.backends.internal.faster_whisper import FasterWhisperBackend

            backend = FasterWhisperBackend()
            assert backend.is_ready is False

    def test_backend_load_model_success(self, mock_config, mock_whisper_model):
        """Verify async model loading works correctly."""
        with patch("matilda_ears.transcription.backends.internal.faster_whisper.get_config", return_value=mock_config):
            # Patch at the source module where WhisperModel is imported from
            with patch("faster_whisper.WhisperModel", return_value=mock_whisper_model):
                from matilda_ears.transcription.backends.internal.faster_whisper import FasterWhisperBackend

                backend = FasterWhisperBackend()

                # Run async load
                loop = asyncio.new_event_loop()
                loop.run_until_complete(backend.load())
                loop.close()

                assert backend.model is not None
                assert backend.is_ready is True

    def test_backend_load_model_failure(self, mock_config):
        """Verify load() raises exception on model loading failure."""
        with patch("matilda_ears.transcription.backends.internal.faster_whisper.get_config", return_value=mock_config):
            # Patch at the source module where WhisperModel is imported from
            with patch("faster_whisper.WhisperModel", side_effect=RuntimeError("Model load failed")):
                from matilda_ears.transcription.backends.internal.faster_whisper import FasterWhisperBackend

                backend = FasterWhisperBackend()

                loop = asyncio.new_event_loop()
                with pytest.raises(RuntimeError, match="Model load failed"):
                    loop.run_until_complete(backend.load())
                loop.close()

    def test_backend_transcribe_success(self, mock_config, mock_whisper_model):
        """Verify transcription works and returns correct format."""
        with patch("matilda_ears.transcription.backends.internal.faster_whisper.get_config", return_value=mock_config):
            from matilda_ears.transcription.backends.internal.faster_whisper import FasterWhisperBackend

            backend = FasterWhisperBackend()
            backend.model = mock_whisper_model

            text, metadata = backend.transcribe("/fake/audio.wav", language="en")

            # Verify output format
            assert isinstance(text, str)
            assert isinstance(metadata, dict)

            # Verify content
            assert text == "Test transcription"
            assert metadata["duration"] == 2.5
            assert metadata["language"] == "en"

            # Verify model.transcribe was called correctly
            mock_whisper_model.transcribe.assert_called_once_with(
                "/fake/audio.wav",
                beam_size=5,
                language="en",
                word_timestamps=True,
                vad_filter=True,
                vad_parameters={
                    "threshold": 0.5,
                    "min_speech_duration_ms": 250,
                    "max_speech_duration_s": 30,
                    "min_silence_duration_ms": 200,
                },
                no_speech_threshold=0.6,
            )

    def test_backend_transcribe_not_loaded(self, mock_config):
        """Verify transcribe() raises RuntimeError if model not loaded."""
        with patch("matilda_ears.transcription.backends.internal.faster_whisper.get_config", return_value=mock_config):
            from matilda_ears.transcription.backends.internal.faster_whisper import FasterWhisperBackend

            backend = FasterWhisperBackend()

            with pytest.raises(RuntimeError, match="Model not loaded"):
                backend.transcribe("/fake/audio.wav")

    def test_backend_transcribe_multiple_segments(self, mock_config):
        """Verify transcription correctly joins multiple segments."""
        with patch("matilda_ears.transcription.backends.internal.faster_whisper.get_config", return_value=mock_config):
            from matilda_ears.transcription.backends.internal.faster_whisper import FasterWhisperBackend

            # Create mock with multiple segments
            model = Mock()
            seg1 = Mock()
            seg1.text = " Hello"
            seg1.words = []
            seg2 = Mock()
            seg2.text = " world"
            seg2.words = []
            seg3 = Mock()
            seg3.text = "!"
            seg3.words = []

            info = Mock()
            info.duration = 1.5
            info.language = "en"

            model.transcribe.return_value = ([seg1, seg2, seg3], info)

            backend = FasterWhisperBackend()
            backend.model = model

            text, metadata = backend.transcribe("/fake/audio.wav")

            assert text == "Hello world!"
            assert metadata["duration"] == 1.5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
