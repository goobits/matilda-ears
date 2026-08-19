from __future__ import annotations

import subprocess
from unittest.mock import patch

from matilda_ears.transcription.backends import registry


def test_check_parakeet_available_returns_false_when_probe_crashes() -> None:
    registry.PARAKEET_AVAILABLE = None
    failed = subprocess.CompletedProcess(
        args=["python", "-c", "import parakeet"],
        returncode=-6,
        stdout="",
        stderr="libc++abi: terminating due to uncaught exception",
    )

    with patch("matilda_ears.transcription.backends.registry.subprocess.run", return_value=failed):
        assert registry._check_parakeet_available() is False

    registry.PARAKEET_AVAILABLE = None


def test_backend_names_are_normalized_once() -> None:
    assert registry.normalize_backend_name(" faster-whisper ") == "faster_whisper"
    assert registry.normalize_backend_name("WHISPER") == "faster_whisper"
    assert registry.normalize_backend_name("hf") == "huggingface"
    assert registry.normalize_backend_name("") == "auto"


def test_moss_is_file_only_and_diarized() -> None:
    spec = registry.get_backend_spec("moss")

    assert spec.capabilities == frozenset({"file", "diarization"})
    assert registry.backend_supports("moss", "server") is False
