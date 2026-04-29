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
