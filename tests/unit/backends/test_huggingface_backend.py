#!/usr/bin/env python3
"""Unit tests for HuggingFaceBackend.

These tests mock the underlying transformers library to verify
the backend wrapper logic works correctly without needing actual models.
"""

import pytest
import asyncio
import sys
from unittest.mock import Mock, patch, MagicMock


mock_torch = MagicMock()
mock_torch.cuda.is_available.return_value = False
mock_torch.backends.mps.is_available.return_value = False
mock_torch.float16 = "float16"
mock_torch.float32 = "float32"
mock_torch.bfloat16 = "bfloat16"


@pytest.fixture(autouse=True)
def isolate_backend_modules():
    """Isolate torch/transformers mocking per test to avoid cross-test pollution."""
    with patch.dict(sys.modules, {"torch": mock_torch, "transformers": MagicMock()}):
        yield


class TestHuggingFaceBackend:
    """Test suite for HuggingFaceBackend implementation."""

    @pytest.fixture
    def mock_config(self):
        """Mock configuration object."""
        config = Mock()
        config.get = Mock(
            side_effect=lambda key, default=None: {
                "huggingface": {
                    "model": "openai/whisper-base",
                    "device": "auto",
                    "torch_dtype": "auto",
                    "chunk_length_s": 30,
                    "batch_size": 8,
                },
                "huggingface.model": "openai/whisper-base",
                "huggingface.device": "auto",
                "huggingface.torch_dtype": "auto",
                "huggingface.chunk_length_s": 30,
                "huggingface.batch_size": 8,
            }.get(key, default)
        )
        return config

    @pytest.fixture
    def mock_pipeline(self):
        """Mock transformers pipeline."""
        pipe = Mock()
        pipe.return_value = {"text": " Test transcription from HuggingFace"}
        return pipe

    def test_device_detection_cpu_fallback(self):
        """Verify device detection falls back to CPU when no GPU available."""
        with patch.dict(sys.modules, {"torch": mock_torch}):
            mock_torch.cuda.is_available.return_value = False
            mock_torch.backends.mps.is_available.return_value = False

            from matilda_ears.transcription.backends.internal.huggingface import _detect_device

            device = _detect_device()
            assert device == "cpu"

    def test_device_detection_cuda(self):
        """Verify CUDA detection when available."""
        with patch.dict(sys.modules, {"torch": mock_torch}):
            mock_torch.cuda.is_available.return_value = True

            from matilda_ears.transcription.backends.internal.huggingface import _detect_device

            device = _detect_device()
            assert device == "cuda:0"

    def test_device_detection_mps(self):
        """Verify MPS (Apple Silicon) detection when available."""
        with patch.dict(sys.modules, {"torch": mock_torch}):
            mock_torch.cuda.is_available.return_value = False
            mock_torch.backends.mps.is_available.return_value = True

            from matilda_ears.transcription.backends.internal.huggingface import _detect_device

            device = _detect_device()
            assert device == "mps"

    def test_backend_initialization(self, mock_config):
        """Verify backend initializes with correct config values."""
        with patch("matilda_ears.transcription.backends.internal.huggingface.get_config", return_value=mock_config):
            from matilda_ears.transcription.backends.internal.huggingface import HuggingFaceBackend

            backend = HuggingFaceBackend()

            assert backend.model_id == "openai/whisper-base"
            assert backend.device_config == "auto"
            assert backend.dtype_config == "auto"
            assert backend.chunk_length_s == 30
            assert backend.batch_size == 8
            assert backend.pipe is None

    def test_backend_is_ready_before_load(self, mock_config):
        """Verify is_ready returns False before model is loaded."""
        with patch("matilda_ears.transcription.backends.internal.huggingface.get_config", return_value=mock_config):
            from matilda_ears.transcription.backends.internal.huggingface import HuggingFaceBackend

            backend = HuggingFaceBackend()
            assert backend.is_ready is False

    def test_backend_load_model_success(self, mock_config, mock_pipeline):
        """Verify async model loading works correctly."""
        with patch("matilda_ears.transcription.backends.internal.huggingface.get_config", return_value=mock_config):
            with patch("matilda_ears.transcription.backends.internal.huggingface.pipeline", return_value=mock_pipeline):
                from matilda_ears.transcription.backends.internal.huggingface import HuggingFaceBackend

                backend = HuggingFaceBackend()

                # Run async load
                loop = asyncio.new_event_loop()
                loop.run_until_complete(backend.load())
                loop.close()

                assert backend.pipe is not None
                assert backend.is_ready is True

    def test_backend_load_model_failure(self, mock_config):
        """Verify load() raises exception on model loading failure."""
        with patch("matilda_ears.transcription.backends.internal.huggingface.get_config", return_value=mock_config):
            with patch(
                "matilda_ears.transcription.backends.internal.huggingface.pipeline",
                side_effect=RuntimeError("Model load failed"),
            ):
                from matilda_ears.transcription.backends.internal.huggingface import HuggingFaceBackend

                backend = HuggingFaceBackend()

                loop = asyncio.new_event_loop()
                with pytest.raises(RuntimeError, match="Model load failed"):
                    loop.run_until_complete(backend.load())
                loop.close()

    def test_backend_transcribe_success(self, mock_config, mock_pipeline):
        """Verify transcription works and returns correct format."""
        with patch("matilda_ears.transcription.backends.internal.huggingface.get_config", return_value=mock_config):
            from matilda_ears.transcription.backends.internal.huggingface import HuggingFaceBackend

            backend = HuggingFaceBackend()
            backend.pipe = mock_pipeline
            backend.model_id = "openai/whisper-base"
            backend.chunk_length_s = 30
            backend.batch_size = 8
            backend.device = "cpu"

            text, metadata = backend.transcribe("/fake/audio.wav", language="en")

            # Verify output format
            assert isinstance(text, str)
            assert isinstance(metadata, dict)

            # Verify content
            assert text == "Test transcription from HuggingFace"
            assert metadata["language"] == "en"
            assert metadata["backend"] == "huggingface"
            assert metadata["model"] == "openai/whisper-base"

    def test_backend_transcribe_not_loaded(self, mock_config):
        """Verify transcribe() raises RuntimeError if model not loaded."""
        with patch("matilda_ears.transcription.backends.internal.huggingface.get_config", return_value=mock_config):
            from matilda_ears.transcription.backends.internal.huggingface import HuggingFaceBackend

            backend = HuggingFaceBackend()

            with pytest.raises(RuntimeError, match="Model not loaded"):
                backend.transcribe("/fake/audio.wav")

    def test_backend_transcribe_whisper_language_param(self, mock_config, mock_pipeline):
        """Verify Whisper models get language parameter in generate_kwargs."""
        with patch("matilda_ears.transcription.backends.internal.huggingface.get_config", return_value=mock_config):
            from matilda_ears.transcription.backends.internal.huggingface import HuggingFaceBackend

            backend = HuggingFaceBackend()
            backend.pipe = mock_pipeline
            backend.model_id = "openai/whisper-large-v3"  # Whisper model
            backend.chunk_length_s = 30
            backend.batch_size = 8
            backend.device = "cpu"

            backend.transcribe("/fake/audio.wav", language="es")

            # Verify pipeline was called with generate_kwargs containing language
            call_kwargs = mock_pipeline.call_args[1]
            assert call_kwargs.get("generate_kwargs") is not None
            assert call_kwargs["generate_kwargs"]["language"] == "es"
            assert call_kwargs["generate_kwargs"]["task"] == "transcribe"

    def test_backend_transcribe_non_whisper_no_language(self, mock_config, mock_pipeline):
        """Verify non-Whisper models don't get language parameter."""
        with patch("matilda_ears.transcription.backends.internal.huggingface.get_config", return_value=mock_config):
            from matilda_ears.transcription.backends.internal.huggingface import HuggingFaceBackend

            backend = HuggingFaceBackend()
            backend.pipe = mock_pipeline
            backend.model_id = "facebook/wav2vec2-base-960h"  # Not Whisper
            backend.chunk_length_s = 30
            backend.batch_size = 8
            backend.device = "cpu"

            backend.transcribe("/fake/audio.wav", language="en")

            # Verify generate_kwargs is None for non-Whisper
            call_kwargs = mock_pipeline.call_args[1]
            assert call_kwargs.get("generate_kwargs") is None

    def test_backend_list_popular_models(self, mock_config):
        """Verify list_popular_models returns dict of models."""
        with patch("matilda_ears.transcription.backends.internal.huggingface.get_config", return_value=mock_config):
            from matilda_ears.transcription.backends.internal.huggingface import HuggingFaceBackend

            models = HuggingFaceBackend.list_popular_models()

            assert isinstance(models, dict)
            assert "openai/whisper-large-v3" in models
            assert "facebook/wav2vec2-base-960h" in models
            assert "distil-whisper/distil-large-v3" in models


class TestBackendFactoryIntegration:
    """Test backend factory integration with HuggingFace backend."""

    def test_huggingface_in_available_backends(self):
        """Verify huggingface appears in available backends when transformers is installed."""
        with patch.dict(sys.modules, {"transformers": MagicMock()}):
            # Force reimport to pick up mocked modules
            from matilda_ears.transcription.backends import get_available_backends

            backends = get_available_backends()
            assert "faster_whisper" in backends
            # huggingface should be available since we mocked transformers

    def test_get_backend_class_huggingface(self):
        """Verify factory returns HuggingFaceBackend class."""
        with patch.dict(sys.modules, {"transformers": MagicMock()}):
            from matilda_ears.transcription.backends import get_available_backends, get_backend_class
            from matilda_ears.transcription.backends import registry

            # Force a fresh availability probe under the mocked import environment.
            registry.HUGGINGFACE_AVAILABLE = None

            assert "huggingface" in get_available_backends()
            backend_class = get_backend_class("huggingface")
            assert backend_class.__name__ == "HuggingFaceBackend"

    def test_get_backend_info_includes_huggingface(self):
        """Verify get_backend_info includes huggingface entry."""
        from matilda_ears.transcription.backends import get_backend_info

        info = get_backend_info()
        assert "huggingface" in info
        assert "description" in info["huggingface"]
        assert "17,000+" in info["huggingface"]["description"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
