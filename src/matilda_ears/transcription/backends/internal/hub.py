from __future__ import annotations

import base64
from pathlib import Path

from ..base import BackendNotAvailableError, TranscriptionBackend
from ...transcript import Transcript, TranscriptSegment


class HubBackend(TranscriptionBackend):
    def __init__(self) -> None:
        self._ready = True

    async def load(self):
        self._ready = True

    def transcribe(self, audio_path: str, language: str = "en") -> Transcript:
        try:
            from matilda_transport import HubClient  # type: ignore[import-not-found]
        except Exception as exc:
            raise BackendNotAvailableError(
                "Hub backend requires matilda-transport.\n"
                "Install it or switch to a local backend (e.g. faster_whisper/parakeet).\n"
                'Hint: set [ears.transcription] backend = "faster_whisper"'
            ) from exc

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
            segments = tuple(
                TranscriptSegment(
                    start=float(segment["start"]),
                    end=float(segment["end"]),
                    text=str(segment.get("text", "")).strip(),
                    speaker=str(segment["speaker"]) if segment.get("speaker") else None,
                )
                for segment in result.get("segments", ())
                if isinstance(segment, dict) and "start" in segment and "end" in segment
            )
            return Transcript(
                text=str(result.get("text", "")),
                segments=segments,
                language=str(result["language"]) if result.get("language") else language,
                duration=float(result["audio_duration"]) if result.get("audio_duration") is not None else None,
                backend="hub",
            )
        return Transcript(text=str(result), segments=(), language=language, duration=None, backend="hub")

    @property
    def is_ready(self) -> bool:
        return self._ready
