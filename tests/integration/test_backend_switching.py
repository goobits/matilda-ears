#!/usr/bin/env python3
"""Integration tests for backend switching system.

These tests verify that the factory pattern, config loading, and
server integration all work together correctly.
"""

import pytest
import sys
import asyncio
from unittest.mock import Mock, patch, MagicMock
import tempfile
import json
import os


class TestBackendFactory:
    """Test the backend factory function."""

    def test_factory_creates_faster_whisper_backend(self):
        """Verify factory returns FasterWhisperBackend class for 'faster_whisper'."""
        from matilda_ears.transcription.backends import get_backend_class
        from matilda_ears.transcription.backends.faster_whisper_backend import FasterWhisperBackend
        
        backend_class = get_backend_class("faster_whisper")
        assert backend_class == FasterWhisperBackend

    def test_factory_creates_parakeet_backend_when_available(self):
        """Verify factory returns ParakeetBackend when dependencies are available."""
        # Mock parakeet availability
        with patch("matilda_ears.transcription.backends.PARAKEET_AVAILABLE", True):
            from matilda_ears.transcription.backends import get_backend_class
            from matilda_ears.transcription.backends.parakeet_backend import ParakeetBackend

            backend_class = get_backend_class("parakeet")
            assert backend_class == ParakeetBackend

    def test_factory_unknown_backend_raises_valueerror(self):
        """Verify factory raises ValueError with helpful message for unknown backend."""
        from matilda_ears.transcription.backends import get_backend_class
        
        with pytest.raises(ValueError) as exc_info:
            get_backend_class("unknown_backend")
        
        error_msg = str(exc_info.value)
        assert "Unknown backend: 'unknown_backend'" in error_msg
        assert "Available backends:" in error_msg
        assert "faster_whisper" in error_msg

    def test_factory_parakeet_unavailable_raises_valueerror(self):
        """Verify factory raises ValueError when Parakeet is requested but unavailable."""
        # Mock parakeet as unavailable
        with patch("matilda_ears.transcription.backends.PARAKEET_AVAILABLE", False):
            from matilda_ears.transcription.backends import get_backend_class

            with pytest.raises(ValueError) as exc_info:
                get_backend_class("parakeet")

            error_msg = str(exc_info.value)
            assert "Parakeet backend requested but dependencies are not installed" in error_msg
            assert "./setup.sh install --dev" in error_msg or "pip install" in error_msg

    def test_get_available_backends_includes_faster_whisper(self):
        """Verify get_available_backends always includes faster_whisper."""
        from matilda_ears.transcription.backends import get_available_backends
        
        backends = get_available_backends()
        assert "faster_whisper" in backends
        assert isinstance(backends, list)

    def test_get_available_backends_includes_parakeet_when_available(self):
        """Verify get_available_backends includes parakeet when available."""
        with patch("matilda_ears.transcription.backends.PARAKEET_AVAILABLE", True):
            # Need to reimport to pick up the mocked value
            import importlib
            import matilda_ears.transcription.backends as backends_module
            importlib.reload(backends_module)

            backends = backends_module.get_available_backends()
            assert "parakeet" in backends

    @pytest.mark.skip(reason="Conflicts with global parakeet mocking in conftest.py - parakeet is always available in integration tests")
    def test_get_available_backends_excludes_parakeet_when_unavailable(self):
        """Verify get_available_backends excludes parakeet when unavailable."""
        # NOTE: This test cannot work in integration tests because conftest.py
        # globally mocks mlx/parakeet_mlx to make all backend tests work.
        # The "unavailable" state is tested in unit tests instead.
        with patch("matilda_ears.transcription.backends.PARAKEET_AVAILABLE", False):
            import importlib
            import matilda_ears.transcription.backends as backends_module
            importlib.reload(backends_module)

            backends = backends_module.get_available_backends()
            assert "parakeet" not in backends


class TestConfigIntegration:
    """Test backend configuration integration."""

    def test_config_has_transcription_backend_property(self):
        """Verify config object has transcription_backend property."""
        from matilda_ears.core.config import get_config
        
        config = get_config()
        assert hasattr(config, "transcription_backend")
        
        # Should return a string
        backend = config.transcription_backend
        assert isinstance(backend, str)

    def test_config_defaults_to_faster_whisper(self):
        """Verify default config uses faster_whisper backend."""
        from matilda_ears.core.config import get_config
        
        config = get_config()
        assert config.transcription_backend == "faster_whisper"

    def test_config_custom_backend_selection(self):
        """Verify config can specify custom backend."""
        # Create a temporary config file with parakeet backend
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            config_data = {
                "transcription": {"backend": "parakeet"},
                "whisper": {"model": "base", "device": "cpu", "compute_type": "int8"},
                "parakeet": {"model": "mlx-community/parakeet-tdt-0.6b-v3"},
                "paths": {
                    "venv": {
                        "linux": "venv/bin/python",
                        "darwin": "venv/bin/python",
                        "windows": "venv\\Scripts\\python.exe"
                    },
                    "temp_dir": {
                        "linux": "/tmp/test-stt",
                        "darwin": "/tmp/test-stt",
                        "windows": "%TEMP%\\test-stt"
                    }
                },
                "tools": {
                    "audio": {
                        "linux": "arecord",
                        "darwin": "arecord",
                        "windows": "ffmpeg"
                    }
                }
            }
            json.dump(config_data, f)
            temp_config_path = f.name

        try:
            # Load custom config
            from matilda_ears.core.config import ConfigLoader
            config = ConfigLoader(config_path=temp_config_path)

            assert config.transcription_backend == "parakeet"
        finally:
            os.unlink(temp_config_path)


class TestServerIntegration:
    """Test backend integration with WebSocket server."""

    @pytest.fixture
    def mock_config(self):
        """Mock configuration for server."""
        config = Mock()
        config.transcription_backend = "faster_whisper"
        config.jwt_token = "test_token"
        config.jwt_secret_key = "test_secret_key"
        config.websocket_port = 8769
        config.websocket_host = "localhost"
        config.ssl_enabled = False
        config.whisper_model = "base"
        config.whisper_device_auto = "cpu"
        config.whisper_compute_type_auto = "int8"
        config.get = Mock(return_value="default_value")
        return config

    def test_server_initializes_backend_from_config(self, mock_config):
        """Verify server creates backend instance based on config."""
        with patch("matilda_ears.transcription.server.get_config", return_value=mock_config):
            with patch("matilda_ears.transcription.server.TokenManager"):
                from matilda_ears.transcription.server import MatildaWebSocketServer

                server = MatildaWebSocketServer()

                assert server.backend is not None
                assert server.backend_name == "faster_whisper"

    def test_server_exits_on_invalid_backend(self, mock_config):
        """Verify server exits gracefully on invalid backend configuration."""
        mock_config.transcription_backend = "invalid_backend"

        # Patch the module-level config variable, not get_config()
        with patch("matilda_ears.transcription.server.config", mock_config):
            with patch("matilda_ears.transcription.server.TokenManager"):
                with patch("matilda_ears.transcription.server.sys.exit") as mock_exit:
                    from matilda_ears.transcription.server import MatildaWebSocketServer

                    server = MatildaWebSocketServer()

                    # Should have called sys.exit(1)
                    mock_exit.assert_called_with(1)

    def test_server_load_model_delegates_to_backend(self, mock_config):
        """Verify server's load_model() delegates to backend.load()."""
        with patch("matilda_ears.transcription.server.get_config", return_value=mock_config):
            with patch("matilda_ears.transcription.server.TokenManager"):
                from matilda_ears.transcription.server import MatildaWebSocketServer

                server = MatildaWebSocketServer()

                # Mock backend's load method to set model (making is_ready True)
                async def mock_load():
                    server.backend.model = Mock()
                server.backend.load = mock_load

                # Verify backend not ready before load
                assert not server.backend.is_ready

                # Run async code synchronously using event loop (matches unit test pattern)
                loop = asyncio.new_event_loop()
                loop.run_until_complete(server.load_model())
                loop.close()

                # Verify backend is ready after load (is_ready is a property that checks if model is not None)
                assert server.backend.is_ready


class TestBackendOutputCompatibility:
    """Test that both backends produce compatible output formats."""

    @pytest.fixture
    def mock_audio_file(self):
        """Create a temporary empty audio file for testing."""
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            temp_path = f.name
        yield temp_path
        if os.path.exists(temp_path):
            os.unlink(temp_path)

    def test_faster_whisper_output_format(self, mock_audio_file):
        """Verify FasterWhisperBackend produces correct output format."""
        mock_config = Mock()
        mock_config.whisper_model = "base"
        mock_config.whisper_device_auto = "cpu"
        mock_config.whisper_compute_type_auto = "int8"

        with patch("matilda_ears.transcription.backends.faster_whisper_backend.get_config", return_value=mock_config):
            from matilda_ears.transcription.backends.faster_whisper_backend import FasterWhisperBackend
            
            backend = FasterWhisperBackend()
            
            # Mock the model
            segment = Mock()
            segment.text = " test"
            info = Mock()
            info.duration = 1.0
            info.language = "en"
            
            model = Mock()
            model.transcribe.return_value = ([segment], info)
            backend.model = model
            
            text, metadata = backend.transcribe(mock_audio_file)
            
            # Verify format
            assert isinstance(text, str)
            assert isinstance(metadata, dict)
            assert "duration" in metadata
            assert "language" in metadata
            assert isinstance(metadata["duration"], (int, float))
            assert isinstance(metadata["language"], str)

    def test_parakeet_output_format(self, mock_audio_file):
        """Verify ParakeetBackend produces compatible output format."""
        # Mock MLX imports
        sys.modules["mlx"] = MagicMock()
        sys.modules["mlx.core"] = MagicMock()
        sys.modules["parakeet_mlx"] = MagicMock()
        
        try:
            mock_config = Mock()
            mock_config.get = Mock(return_value="mlx-community/parakeet-tdt-0.6b-v3")
            
            with patch("matilda_ears.transcription.backends.parakeet_backend.get_config", return_value=mock_config):
                from matilda_ears.transcription.backends.parakeet_backend import ParakeetBackend
                
                backend = ParakeetBackend()
                
                # Mock the model
                result = Mock()
                result.text = "  test  "
                sentence = Mock()
                sentence.end = 1.5
                result.sentences = [sentence]
                
                model = Mock()
                model.transcribe.return_value = result
                backend.model = model
                
                text, metadata = backend.transcribe(mock_audio_file)
                
                # Verify format matches FasterWhisper
                assert isinstance(text, str)
                assert isinstance(metadata, dict)
                assert "duration" in metadata
                assert "language" in metadata
                assert isinstance(metadata["duration"], (int, float))
                assert isinstance(metadata["language"], str)
                
                # Parakeet adds extra backend field
                assert "backend" in metadata
                assert metadata["backend"] == "parakeet"
        finally:
            # Cleanup
            for module in ["mlx", "mlx.core", "parakeet_mlx"]:
                if module in sys.modules:
                    del sys.modules[module]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
