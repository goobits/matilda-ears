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
from typing import Any

# Import shared path setup (also adds project root to sys.path)
from ._imports import *  # noqa: F403

from matilda_ears.core.config import get_config, setup_logging
from matilda_ears.core.mode_config import FileTranscribeConfig
from matilda_ears.transcription.backends import get_backend_class


class FileTranscribeMode:
    """Transcribe audio from a file."""

    def __init__(self, mode_config: FileTranscribeConfig):
        """Initialize file transcription mode."""
        self.mode_config = mode_config
        self.config = get_config()
        if self.mode_config.language is None:
            self.mode_config.language = "en"
        if self.mode_config.model is None:
            self.mode_config.model = self.config.whisper_model
        if not self.mode_config.format:
            self.mode_config.format = "text"
        self.logger = setup_logging(
            "FileTranscribeMode",
            log_level="DEBUG" if self.mode_config.debug else "WARNING",
            include_console=self.mode_config.debug,
            include_file=True,
        )
        self.backend = None
        self.logger.info("FileTranscribeMode initialized")

    async def run(self):
        """Main entry point - transcribe the file."""
        file_path = Path(self.mode_config.file)

        # Validate file exists
        if not file_path.exists():
            await self._send_error(f"File not found: {file_path}")
            return

        # Check file extension
        supported = {".wav", ".mp3", ".m4a", ".flac", ".ogg", ".webm"}
        if file_path.suffix.lower() not in supported:
            await self._send_error(f"Unsupported format: {file_path.suffix}. Supported: {supported}")
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

    async def _load_model(self):
        """Load transcription backend."""
        try:
            # Determine backend from config
            backend_name = self.config.get("transcription", {}).get("backend", "faster_whisper")
            self.logger.info(f"Initializing backend: {backend_name}")

            # Get backend class
            BackendClass = get_backend_class(backend_name)
            self.backend = BackendClass()

            self.logger.info(f"Loading backend: {backend_name}")

            await self.backend.load()

            self.logger.info(f"Backend {backend_name} loaded")

        except Exception as e:
            raise RuntimeError(f"Failed to load backend: {e}")

    async def _transcribe_file(self, file_path: str) -> dict[str, Any]:
        """Transcribe audio file using backend."""
        try:
            if self.backend is None or not self.backend.is_ready:
                raise RuntimeError("Backend not loaded")

            loop = asyncio.get_event_loop()

            def do_transcribe():
                return self.backend.transcribe(file_path, language=self.mode_config.language)

            text, info = await loop.run_in_executor(None, do_transcribe)

            # Apply text formatting if enabled
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
        """Apply text formatting pipeline."""
        if not text.strip():
            return text

        if not self.config.get("text_formatting.enabled", False):
            return text

        formatter_name = self.config.get("text_formatting.formatter", "noop")
        try:
            from matilda_text_formatting import FormatterRequest, get_formatter

            formatter = get_formatter(formatter_name)
            return formatter.format(FormatterRequest(text=text, language=self.mode_config.language)).text
        except ImportError:
            self.logger.warning("Text formatting not available")
            return text
        except Exception as e:
            self.logger.warning(f"Text formatting failed: {e}")
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
