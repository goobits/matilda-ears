from __future__ import annotations

import base64
from pathlib import Path

from matilda_transport import HubClient

from ..base import TranscriptionBackend


class HubBackend(TranscriptionBackend):
    def __init__(self) -> None:
        self._ready = True

    async def load(self):
        self._ready = True

    def transcribe(self, audio_path: str, language: str = "en") -> tuple[str, dict]:
        audio_bytes = Path(audio_path).read_bytes()
        audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")
        payload = {
            "input": audio_b64,
            "format": Path(audio_path).suffix.lstrip(".") or "wav",
            "options": {"language": language},
        }
        client = HubClient()
        response = client.post_capability("transcribe-audio", payload)
        error = response.get("error")
        if error:
            message = error.get("message") if isinstance(error, dict) else str(error)
            raise RuntimeError(message or "hub request failed")
        result = response.get("result") or {}
        if isinstance(result, dict):
            text = result.get("text", "")
            return text, {
                "duration": result.get("audio_duration", 0),
                "language": result.get("language", language),
            }
        return str(result), {"duration": 0, "language": language}

    @property
    def is_ready(self) -> bool:
        return self._ready
