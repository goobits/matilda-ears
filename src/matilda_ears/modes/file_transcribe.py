#!/usr/bin/env python3
"""FileTranscribeMode - Transcribe audio from a file

Simple mode that loads a WAV/audio file and transcribes it using Whisper.
No audio capture, no VAD - just direct file-to-text transcription.
"""

import asyncio
import json
import sys
import time
from pathlib import Path
from typing import Any, ClassVar

from matilda_ears.modes.base_mode import BaseMode


class FileTranscribeMode(BaseMode):
    """Transcribe audio from a file."""

    SUPPORTED_EXTENSIONS: ClassVar[set[str]] = {".wav", ".mp3", ".m4a", ".flac", ".ogg", ".webm"}

    async def run(self):
        """Main entry point - transcribe the file."""
        file_path = Path(self.mode_config.file)

        # Validate file exists
        # Use to_thread to prevent blocking the event loop with I/O
        file_exists = await asyncio.to_thread(file_path.exists)
        if not file_exists:
            await self._send_error(f"File not found: {file_path}")
            return

        # Check file extension
        if file_path.suffix.lower() not in self.SUPPORTED_EXTENSIONS:
            await self._send_error(f"Unsupported format: {file_path.suffix}. Supported: {self.SUPPORTED_EXTENSIONS}")
            return

        # Send initializing status
        await self._send_status("initializing", "Loading model...")

        # Load model
        try:
            await self._load_model()
        except Exception as e:
            await self._send_error(f"Model load failed: {e}")
            return

        # Send transcribing status
        await self._send_status("transcribing", f"Transcribing {file_path.name}...")

        # Transcribe
        result = await self._transcribe_file(str(file_path))

        # Output result
        await self._send_result(result)

    async def _transcribe_file(self, file_path: str) -> dict[str, Any]:
        """Transcribe audio file using backend."""
        try:
            if self.backend is None or not self.backend.is_ready:
                raise RuntimeError("Backend not loaded")

            loop = asyncio.get_event_loop()

            def do_transcribe():
                return self.backend.transcribe(file_path, language=self.mode_config.language)

            text, info = await loop.run_in_executor(None, do_transcribe)

            # Apply Ears Tuner formatting if enabled
            if not self.mode_config.no_formatting:
                text = await self._format_text(text)

            self.logger.info(f"Transcribed: '{text[:50]}...' ({len(text)} chars)")

            return {
                "success": True,
                "text": text,
                "is_final": True,
                "language": info.get("language", "en"),
                "file": file_path,
            }

        except Exception as e:
            self.logger.error(f"Transcription error: {e}")
            return {"success": False, "error": str(e), "text": "", "is_final": True, "file": file_path}

    async def _format_text(self, text: str) -> str:
        """Apply Ears Tuner formatting pipeline."""
        if not text.strip():
            return text

        if not self.config.get("ears_tuner.enabled", False):
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
        except Exception as e:
            self.logger.warning(f"Ears Tuner formatting failed: {e}")
            return text

    async def _send_status(self, status: str, message: str):
        """Send status message."""
        if self.mode_config.format == "json":
            result = {"type": "status", "mode": "file", "status": status, "message": message, "timestamp": time.time()}
            print(json.dumps(result), flush=True)

    async def _send_result(self, result: dict[str, Any]):
        """Send transcription result."""
        if self.mode_config.format == "json":
            output = {"type": "transcription", "mode": "file", **result, "timestamp": time.time()}
            print(json.dumps(output), flush=True)
        # Plain text mode - just print the text
        elif result.get("success") and result.get("text"):
            print(result["text"], flush=True)
        elif result.get("error"):
            print(f"Error: {result['error']}", file=sys.stderr)

    async def _send_error(self, message: str):
        """Send error message."""
        if self.mode_config.format == "json":
            result = {"type": "error", "mode": "file", "error": message, "timestamp": time.time()}
            print(json.dumps(result), flush=True)
        else:
            print(f"Error: {message}", file=sys.stderr)
