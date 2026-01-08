#!/usr/bin/env python3
"""Unit tests for ParakeetBackend.

These tests mock the underlying parakeet-mlx library to verify
the backend wrapper logic works correctly.
"""

import pytest
import asyncio
from unittest.mock import Mock, patch


try:
    import mlx.core  # noqa: F401
    import parakeet_mlx  # noqa: F401
except Exception as exc:
    pytest.skip(f"Parakeet MLX backend not available: {exc}", allow_module_level=True)


class TestParakeetBackend:
    """Test suite for ParakeetBackend implementation."""

    @pytest.fixture
    def mock_config(self):
        """Mock configuration object."""
        config = Mock()
        config.get = Mock(return_value="mlx-community/parakeet-tdt-0.6b-v3")
        return config

    @pytest.fixture
    def mock_parakeet_model(self):
        """Mock Parakeet model instance."""
        model = Mock()

        # Mock transcription result
        result = Mock()
        result.text = "  Test parakeet transcription  "

        # Mock sentences for duration calculation
        sentence = Mock()
        sentence.end = 3.2
        result.sentences = [sentence]

        model.transcribe.return_value = result
        return model

    def test_backend_initialization(self, mock_config):
        """Verify backend initializes correctly."""
        from matilda_ears.transcription.backends.parakeet_backend import ParakeetBackend

        backend = ParakeetBackend()

        # Verify basic initialization
        assert backend.model_name is not None  # Will use default from config
        assert backend.model is None
        assert backend.processor is None

    def test_backend_is_ready_before_load(self, mock_config):
        """Verify is_ready returns False before model is loaded."""
        with patch("matilda_ears.core.config.get_config", return_value=mock_config):
            from matilda_ears.transcription.backends.parakeet_backend import ParakeetBackend

            backend = ParakeetBackend()
            assert backend.is_ready is False

    def test_backend_load_model_success(self, mock_config, mock_parakeet_model):
        """Verify async model loading works correctly."""
        with patch("matilda_ears.core.config.get_config", return_value=mock_config):
            with patch("parakeet_mlx.from_pretrained", return_value=mock_parakeet_model):
                from matilda_ears.transcription.backends.parakeet_backend import ParakeetBackend

                backend = ParakeetBackend()

                # Run async load
                loop = asyncio.new_event_loop()
                loop.run_until_complete(backend.load())
                loop.close()

                assert backend.model is not None
                assert backend.is_ready is True

    def test_backend_load_model_failure(self, mock_config):
        """Verify load() raises exception on model loading failure."""
        with patch("matilda_ears.core.config.get_config", return_value=mock_config):
            with patch("parakeet_mlx.from_pretrained", side_effect=RuntimeError("MLX model load failed")):
                from matilda_ears.transcription.backends.parakeet_backend import ParakeetBackend

                backend = ParakeetBackend()

                loop = asyncio.new_event_loop()
                with pytest.raises(RuntimeError, match="MLX model load failed"):
                    loop.run_until_complete(backend.load())
                loop.close()

    def test_backend_transcribe_success(self, mock_config, mock_parakeet_model):
        """Verify transcription works and returns correct format."""
        with patch("matilda_ears.core.config.get_config", return_value=mock_config):
            from matilda_ears.transcription.backends.parakeet_backend import ParakeetBackend

            backend = ParakeetBackend()
            backend.model = mock_parakeet_model

            text, metadata = backend.transcribe("/fake/audio.wav", language="en")

            # Verify output format
            assert isinstance(text, str)
            assert isinstance(metadata, dict)

            # Verify content (should be stripped)
            assert text == "Test parakeet transcription"
            assert metadata["duration"] == 3.2
            assert metadata["language"] == "en"
            assert metadata["backend"] == "parakeet"

            # Verify model.transcribe was called with correct parameters
            # Backend should pass chunk_duration and overlap_duration from config
            mock_parakeet_model.transcribe.assert_called_once()

    def test_backend_transcribe_not_loaded(self, mock_config):
        """Verify transcribe() raises RuntimeError if model not loaded."""
        with patch("matilda_ears.core.config.get_config", return_value=mock_config):
            from matilda_ears.transcription.backends.parakeet_backend import ParakeetBackend

            backend = ParakeetBackend()

            with pytest.raises(RuntimeError, match="Parakeet Model not loaded"):
                backend.transcribe("/fake/audio.wav")

    def test_backend_transcribe_no_sentences(self, mock_config):
        """Verify transcription works when result has no sentences (duration fallback)."""
        with patch("matilda_ears.core.config.get_config", return_value=mock_config):
            from matilda_ears.transcription.backends.parakeet_backend import ParakeetBackend

            # Mock model with empty sentences
            model = Mock()
            result = Mock()
            result.text = "Fallback test"
            result.sentences = []
            model.transcribe.return_value = result

            backend = ParakeetBackend()
            backend.model = model

            text, metadata = backend.transcribe("/fake/audio.wav")

            assert text == "Fallback test"
            # Duration should be > 0 (processing time)
            assert metadata["duration"] >= 0
            assert metadata["language"] == "en"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
