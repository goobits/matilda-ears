import sys
from types import SimpleNamespace
from unittest.mock import Mock

from matilda_ears.transcription import model_store


def test_download_faster_whisper_uses_matching_repository(monkeypatch):
    snapshot_download = Mock()
    monkeypatch.setitem(sys.modules, "huggingface_hub", SimpleNamespace(snapshot_download=snapshot_download))
    events = []

    assert model_store.download_model("base", progress_callback=events.append, force=True) is True
    snapshot_download.assert_called_once_with(
        repo_id="Systran/faster-whisper-base",
        repo_type="model",
        local_files_only=False,
        force_download=True,
    )
    assert events[0]["repo_id"] == "Systran/faster-whisper-base"
    assert events[-1]["status"] == "complete"


def test_unknown_faster_whisper_model_returns_error():
    events = []

    assert model_store.download_model("missing", progress_callback=events.append) is False
    assert events == [
        {
            "status": "error",
            "error": "Unknown faster-whisper model: missing. Available: " + ", ".join(model_store.WHISPER_MODELS),
        }
    ]


def test_model_catalogs_cover_local_backends(monkeypatch):
    monkeypatch.setattr(model_store, "is_model_cached", lambda _name, backend="faster_whisper": False)

    catalogs = model_store.list_available_models()

    assert "base" in catalogs["faster_whisper"]
    assert "tdt-0.6b-v3" in catalogs["parakeet"]
