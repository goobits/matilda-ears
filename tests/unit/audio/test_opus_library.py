import ctypes.util
from types import ModuleType

import pytest

from matilda_ears.audio.internal import opus_library


def test_explicit_opus_library_is_used_only_for_opus(tmp_path, monkeypatch: pytest.MonkeyPatch):
    library = tmp_path / "libopus.dylib"
    library.touch()
    imported = ModuleType("opuslib")
    resolved = []

    def import_module(name: str) -> ModuleType:
        assert name == "opuslib"
        resolved.extend((ctypes.util.find_library("opus"), ctypes.util.find_library("other")))
        return imported

    original_find_library = ctypes.util.find_library
    monkeypatch.setenv("MATILDA_OPUS_LIBRARY", str(library))
    monkeypatch.setattr(opus_library.importlib, "import_module", import_module)

    assert opus_library._load_opuslib() is imported
    assert resolved == [str(library), original_find_library("other")]
    assert ctypes.util.find_library is original_find_library


def test_missing_explicit_opus_library_fails_fast(tmp_path, monkeypatch: pytest.MonkeyPatch):
    missing = tmp_path / "missing.dylib"
    monkeypatch.setenv("MATILDA_OPUS_LIBRARY", str(missing))

    with pytest.raises(RuntimeError, match="MATILDA_OPUS_LIBRARY does not exist"):
        opus_library._load_opuslib()
