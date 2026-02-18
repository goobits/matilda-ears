from __future__ import annotations

from ..base import TranscriptionBackend


class DummyBackend(TranscriptionBackend):
    """Deterministic backend for tests and local development.

    This backend does not load models and returns a fixed transcription.
    """

    def __init__(self, *, text: str = "Hello world") -> None:
        self._ready = False
        self._text = text

    async def load(self):
        self._ready = True

    def transcribe(self, audio_path: str, language: str = "en") -> tuple[str, dict]:
        # Keep output deterministic and cheap; ignore audio_path contents.
        return self._text, {"duration": 0.0, "language": language}

    @property
    def is_ready(self) -> bool:
        return self._ready
