#!/usr/bin/env python3
"""
FileTranscribeMode - Transcribe audio from a file

Simple mode that loads a WAV/audio file and transcribes it using Whisper.
No audio capture, no VAD - just direct file-to-text transcription.
"""

import asyncio
import json
import time
from pathlib import Path
from typing import Dict, Any
import sys

# Add project root to path for local imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.absolute()))

from src.core.config import get_config, setup_logging


class FileTranscribeMode:
    """Transcribe audio from a file."""

    def __init__(self, args):
        """Initialize file transcription mode."""
        self.args = args
        self.config = get_config()
        self.logger = setup_logging(
            "FileTranscribeMode",
            log_level="DEBUG" if args.debug else "WARNING",
            include_console=args.debug,
            include_file=True
        )
        self.model = None
        self.logger.info("FileTranscribeMode initialized")

    async def run(self):
        """Main entry point - transcribe the file."""
        file_path = Path(self.args.file)

        # Validate file exists
        if not file_path.exists():
            await self._send_error(f"File not found: {file_path}")
            return

        # Check file extension
        supported = {'.wav', '.mp3', '.m4a', '.flac', '.ogg', '.webm'}
        if file_path.suffix.lower() not in supported:
            await self._send_error(f"Unsupported format: {file_path.suffix}. Supported: {supported}")
            return

        # Send initializing status
        await self._send_status("initializing", "Loading model...")

        # Load model
        await self._load_model()

        # Send transcribing status
        await self._send_status("transcribing", f"Transcribing {file_path.name}...")

        # Transcribe
        result = await self._transcribe_file(str(file_path))

        # Output result
        await self._send_result(result)

    async def _load_model(self):
        """Load Whisper model."""
        try:
            from faster_whisper import WhisperModel

            self.logger.info(f"Loading Whisper model: {self.args.model}")

            loop = asyncio.get_event_loop()
            self.model = await loop.run_in_executor(
                None, lambda: WhisperModel(self.args.model, device="cpu", compute_type="int8")
            )

            self.logger.info(f"Model {self.args.model} loaded")

        except ImportError as e:
            raise ImportError(f"faster-whisper required: {e}")

    async def _transcribe_file(self, file_path: str) -> Dict[str, Any]:
        """Transcribe audio file using Whisper."""
        try:
            if self.model is None:
                raise RuntimeError("Model not loaded")

            loop = asyncio.get_event_loop()

            def do_transcribe():
                segments, info = self.model.transcribe(
                    file_path,
                    language=self.args.language
                )
                text = "".join([segment.text for segment in segments]).strip()
                return text, info

            text, info = await loop.run_in_executor(None, do_transcribe)

            # Apply text formatting if enabled
            if not self.args.no_formatting:
                text = await self._format_text(text)

            self.logger.info(f"Transcribed: '{text[:50]}...' ({len(text)} chars)")

            return {
                "success": True,
                "text": text,
                "is_final": True,
                "language": info.language if hasattr(info, 'language') else 'en',
                "file": file_path
            }

        except Exception as e:
            self.logger.error(f"Transcription error: {e}")
            return {
                "success": False,
                "error": str(e),
                "text": "",
                "is_final": True,
                "file": file_path
            }

    async def _format_text(self, text: str) -> str:
        """Apply text formatting pipeline."""
        try:
            from src.text_formatting.formatter import TextFormatter
            formatter = TextFormatter()
            return formatter.format(text)
        except ImportError:
            self.logger.warning("Text formatting not available")
            return text
        except Exception as e:
            self.logger.warning(f"Text formatting failed: {e}")
            return text

    async def _send_status(self, status: str, message: str):
        """Send status message."""
        if self.args.format == "json":
            result = {
                "type": "status",
                "mode": "file",
                "status": status,
                "message": message,
                "timestamp": time.time()
            }
            print(json.dumps(result), flush=True)

    async def _send_result(self, result: Dict[str, Any]):
        """Send transcription result."""
        if self.args.format == "json":
            output = {
                "type": "transcription",
                "mode": "file",
                **result,
                "timestamp": time.time()
            }
            print(json.dumps(output), flush=True)
        else:
            # Plain text mode - just print the text
            if result.get("success") and result.get("text"):
                print(result["text"], flush=True)
            elif result.get("error"):
                print(f"Error: {result['error']}", file=sys.stderr)

    async def _send_error(self, message: str):
        """Send error message."""
        if self.args.format == "json":
            result = {
                "type": "error",
                "mode": "file",
                "error": message,
                "timestamp": time.time()
            }
            print(json.dumps(result), flush=True)
        else:
            print(f"Error: {message}", file=sys.stderr)
