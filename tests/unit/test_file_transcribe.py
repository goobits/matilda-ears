import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch, AsyncMock

from matilda_ears.modes.file_transcribe import FileTranscribeMode
from matilda_ears.core.mode_config import FileTranscribeConfig
from matilda_ears.transcription.transcript import Transcript


@pytest.fixture
def mock_config():
    with patch("matilda_ears.modes.base_mode.get_config") as mock:
        config = MagicMock()
        config.whisper_model = "base"
        config.transcription_backend = "faster_whisper"
        config.ears_tuner = {"enabled": False}
        mock.return_value = config
        yield mock


@pytest.fixture
def mock_backend():
    with patch("matilda_ears.modes.base_mode.get_backend_class") as mock_get_cls:
        backend_cls = MagicMock()
        backend_instance = MagicMock()
        backend_instance.load = AsyncMock()
        backend_instance.is_ready = True
        backend_instance.transcribe = MagicMock(
            return_value=Transcript(
                text="Transcribed text",
                segments=(),
                language="en",
                duration=None,
                backend="faster_whisper",
            )
        )
        backend_cls.return_value = backend_instance
        mock_get_cls.return_value = backend_cls
        yield mock_get_cls, backend_instance


@pytest.mark.asyncio
async def test_file_not_found(mock_config):
    # Setup
    config = FileTranscribeConfig(file="non_existent_file.wav")
    mode = FileTranscribeMode(config)
    mode._send_error = AsyncMock()

    # Run
    await mode.run()

    # Verify
    mode._send_error.assert_called_once()
    args = mode._send_error.call_args[0]
    assert "File not found" in args[0]


@pytest.mark.asyncio
async def test_wrong_extension(mock_config):
    # Setup
    with patch("pathlib.Path.exists", return_value=True):
        config = FileTranscribeConfig(file="test.txt")
        mode = FileTranscribeMode(config)
        mode._send_error = AsyncMock()

        # Run
        await mode.run()

        # Verify
        mode._send_error.assert_called_once()
        args = mode._send_error.call_args[0]
        assert "Unsupported format" in args[0]


@pytest.mark.asyncio
async def test_successful_transcription(mock_config):
    # Setup
    with patch("pathlib.Path.exists", return_value=True):
        config = FileTranscribeConfig(file="test.wav")
        mode = FileTranscribeMode(config)
        mode._send_status = AsyncMock()
        mode._send_result = AsyncMock()
        mode._load_model = AsyncMock()
        mode._transcribe_file = AsyncMock(
            return_value={
                "success": True,
                "text": "Hello world",
                "is_final": True,
                "language": "en",
                "file": Path("test.wav"),
            }
        )

        # Run
        await mode.run()

        # Verify
        mode._load_model.assert_called_once()
        mode._transcribe_file.assert_called_once()
        mode._send_result.assert_called_once()


@pytest.mark.asyncio
async def test_load_model_uses_resolved_backend(mock_config, mock_backend):
    mock_config.return_value.transcription_backend = "parakeet"
    get_backend_class, backend = mock_backend
    mode = FileTranscribeMode(FileTranscribeConfig(file="test.wav"))

    await mode._load_model()

    get_backend_class.assert_called_once_with("parakeet")
    backend.load.assert_awaited_once()


@pytest.mark.asyncio
async def test_file_backend_override_is_resolved(mock_config, mock_backend):
    get_backend_class, backend = mock_backend
    mode = FileTranscribeMode(FileTranscribeConfig(file="test.wav", backend="huggingface"))

    await mode._load_model()

    get_backend_class.assert_called_once_with("huggingface")
    backend.load.assert_awaited_once()
