#!/usr/bin/env python3
"""Transcribe an audio file with the selected batch backend."""

import asyncio
import json
import sys
import time
from pathlib import Path
from typing import Any

from matilda_ears.modes.base_mode import BaseMode
from matilda_ears.transcription.backends import backend_supports, normalize_backend_name


class FileTranscribeMode(BaseMode):
    """Transcribe audio from a file."""

    async def run(self):
        file_path = Path(self.mode_config.file)
        if not await asyncio.to_thread(file_path.is_file):
            await self._send_error(f"File not found: {file_path}")
            return

        await self._send_status("initializing", "Loading model...")
        try:
            await self._load_model()
        except Exception as exc:
            await self._send_error(f"Model load failed: {exc}")
            return

        await self._send_status("transcribing", f"Transcribing {file_path.name}...")
        result = await self._transcribe_file(str(file_path))
        await self._send_result(result)

    def _resolve_backend_name(self) -> str:
        requested = normalize_backend_name(self.mode_config.backend)
        if self.mode_config.diarize:
            if requested not in {"auto", "moss"}:
                raise ValueError("--diarize requires --backend moss")
            requested = "moss"
        backend_name = requested if requested != "auto" else self.config.transcription_backend
        if not backend_supports(backend_name, "file"):
            raise ValueError(f"Backend '{backend_name}' does not support file transcription")
        return backend_name

    async def _transcribe_file(self, file_path: str) -> dict[str, Any]:
        try:
            if self.backend is None or not self.backend.is_ready:
                raise RuntimeError("Backend not loaded")

            transcript = await asyncio.to_thread(self.backend.transcribe, file_path, self.mode_config.language)
            text = transcript.text
            if self.mode_config.diarize and self.mode_config.format != "json":
                text = "\n".join(
                    f"[{_format_timestamp(segment.start)}] {segment.speaker}: {segment.text}"
                    for segment in transcript.segments
                )
            elif not self.mode_config.no_formatting:
                text = await self._format_text(text)
            self.logger.info("Transcribed %d characters with %s", len(text), transcript.backend)
            return {
                "success": True,
                "text": text,
                "is_final": True,
                "language": transcript.language or "en",
                "file": file_path,
                "duration": transcript.duration,
                "backend": transcript.backend,
                "segments": [
                    {
                        "start": segment.start,
                        "end": segment.end,
                        "speaker": segment.speaker,
                        "text": segment.text,
                    }
                    for segment in transcript.segments
                ],
            }
        except Exception as exc:
            self.logger.error("Transcription error: %s", exc)
            return {"success": False, "error": str(exc), "text": "", "is_final": True, "file": file_path}

    async def _format_text(self, text: str) -> str:
        if not text.strip() or not self.config.get("ears_tuner.enabled", False):
            return text

        formatter_name = self.config.get("ears_tuner.formatter", "noop")
        try:
            from matilda_ears_tuner import FormatterRequest, get_formatter

            formatter = get_formatter(formatter_name)
            formatting_config = self.config.get("ears_tuner.formatting", {})
            formatter_locale = (
                (formatting_config.get("locale") if isinstance(formatting_config, dict) else None)
                or self.config.get("ears_tuner.locale", None)
                or self.mode_config.language
            )
            filename_formats = self.config.get("ears_tuner.filename_formats", {})
            request_config = {
                "formatting": formatting_config if isinstance(formatting_config, dict) else {},
                "ears_tuner": {"filename_formats": filename_formats if isinstance(filename_formats, dict) else {}},
            }
            return formatter.format(FormatterRequest(text=text, language=formatter_locale, config=request_config)).text
        except ImportError:
            self.logger.warning("Ears Tuner formatting not available")
            return text
        except Exception as exc:
            self.logger.warning("Ears Tuner formatting failed: %s", exc)
            return text

    async def _send_status(self, status: str, message: str):
        if self.mode_config.format == "json":
            result = {"type": "status", "mode": "file", "status": status, "message": message, "timestamp": time.time()}
            print(json.dumps(result), flush=True)

    async def _send_result(self, result: dict[str, Any]):
        if self.mode_config.format == "json":
            output = {"type": "transcription", "mode": "file", **result, "timestamp": time.time()}
            print(json.dumps(output), flush=True)
        elif result.get("success") and result.get("text"):
            print(result["text"], flush=True)
        elif result.get("error"):
            print(f"Error: {result['error']}", file=sys.stderr)

    async def _send_error(self, message: str):
        if self.mode_config.format == "json":
            result = {"type": "error", "mode": "file", "error": message, "timestamp": time.time()}
            print(json.dumps(result), flush=True)
        else:
            print(f"Error: {message}", file=sys.stderr)


def _format_timestamp(seconds: float) -> str:
    milliseconds = max(0, round(seconds * 1000))
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    whole_seconds, milliseconds = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{whole_seconds:02d}.{milliseconds:03d}"
