#!/usr/bin/env python3
"""
BaseMode - Abstract base class for all STT operation modes

This class provides common functionality shared across all operation modes:
- Whisper model loading and management
- Audio streaming setup
- Transcription processing
- Output formatting (JSON/text)
- Error handling and cleanup
"""
from __future__ import annotations

import asyncio
import json
import sys
import tempfile
import time
import wave
from abc import ABC, abstractmethod
from typing import Any

from stt.audio.capture import PipeBasedAudioStreamer
from stt.core.config import get_config, setup_logging

try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False
    # Create dummy for type annotations
    class _DummyNumpy:
        class ndarray:
            pass
    np = _DummyNumpy()


class BaseMode(ABC):
    """Abstract base class for all STT operation modes."""

    def __init__(self, args):
        """Initialize common mode components."""
        self.args = args
        self.config = get_config()
        self.logger = setup_logging(
            self.__class__.__name__,
            log_level="DEBUG" if args.debug else "WARNING",
            include_console=False,  # Never show logger output to console - use _send_* methods
            include_file=True
        )

        # Audio processing
        self.loop = None
        self.audio_queue = None
        self.audio_streamer = None

        # Model
        self.model = None

        # Recording state
        self.is_recording = False
        self.audio_data = []

        # Check dependencies
        if not NUMPY_AVAILABLE:
            raise ImportError(
                f"NumPy is required for {self.__class__.__name__}. "
                "Install with: pip install numpy"
            )

        self.logger.info(f"{self.__class__.__name__} initialized")

    def _get_mode_config(self) -> dict[str, Any]:
        """Get mode-specific configuration from config.json."""
        mode_name = self._get_mode_name()
        result: dict[str, Any] = self.config.get("modes", {}).get(mode_name, {})
        return result

    @abstractmethod
    async def run(self):
        """Main entry point for the mode. Must be implemented by subclasses."""

    async def _load_model(self):
        """Load Whisper model asynchronously."""
        try:
            from faster_whisper import WhisperModel

            self.logger.info(f"Loading Whisper model: {self.args.model}")

            # Load in executor to avoid blocking
            loop = asyncio.get_event_loop()
            self.model = await loop.run_in_executor(
                None, lambda: WhisperModel(self.args.model, device="cpu", compute_type="int8")
            )

            self.logger.info(f"Whisper model {self.args.model} loaded successfully")

        except Exception as e:
            self.logger.error(f"Failed to load Whisper model: {e}")
            raise

    async def _setup_audio_streamer(self, maxsize: int = 1000, chunk_duration_ms: int = 32):
        """Initialize the PipeBasedAudioStreamer."""
        try:
            self.loop = asyncio.get_event_loop()
            self.audio_queue = asyncio.Queue(maxsize=maxsize)

            # Create audio streamer
            self.audio_streamer = PipeBasedAudioStreamer(
                loop=self.loop,
                queue=self.audio_queue,
                chunk_duration_ms=chunk_duration_ms,
                sample_rate=self.args.sample_rate,
                audio_device=self.args.device,
                debug=self.args.debug  # Pass debug flag to control logger output
            )

            self.logger.info("Audio streamer setup completed")

        except Exception as e:
            self.logger.error(f"Failed to setup audio streaming: {e}")
            raise

    def _transcribe_audio(self, audio_data: np.ndarray, prompt: str = "") -> dict[str, Any]:
        """Transcribe audio data using Whisper with optional context prompt."""
        try:
            # Save audio to temporary WAV file
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_file:
                with wave.open(tmp_file.name, "wb") as wav_file:
                    wav_file.setnchannels(1)  # Mono
                    wav_file.setsampwidth(2)  # 16-bit
                    wav_file.setframerate(self.args.sample_rate)
                    wav_file.writeframes(audio_data.astype(np.int16).tobytes())

                # Transcribe with optional prompt for context
                if self.model is None:
                    raise RuntimeError("Model not loaded")

                # Use prompt if provided to give Whisper context
                transcribe_kwargs = {"language": self.args.language}
                if prompt.strip():
                    # Limit prompt to ~200 words for optimal performance
                    prompt_words = prompt.split()[-200:]
                    transcribe_kwargs["initial_prompt"] = " ".join(prompt_words)
                    self.logger.debug(f"Using context prompt: '{transcribe_kwargs['initial_prompt'][:50]}...'")

                segments, info = self.model.transcribe(tmp_file.name, **transcribe_kwargs)
                text = "".join([segment.text for segment in segments]).strip()

                self.logger.info(f"Transcribed: '{text}' ({len(text)} chars)")

                return {
                    "success": True,
                    "text": text,
                    "language": info.language if hasattr(info, "language") else "en",
                    "duration": len(audio_data) / self.args.sample_rate,
                    "confidence": 0.95  # Placeholder - Whisper doesn't provide confidence
                }

        except Exception as e:
            self.logger.error(f"Transcription error: {e}")
            return {
                "success": False,
                "error": str(e),
                "text": "",
                "duration": 0
            }

    async def _send_status(self, status: str, message: str, extra: dict | None = None):
        """Send status message."""
        result = {
            "type": "status",
            "mode": self._get_mode_name(),
            "status": status,
            "message": message,
            "timestamp": time.time()
        }

        # Add any extra fields
        if extra:
            result.update(extra)

        if self.args.format == "json":
            # Send status messages to stderr to avoid interfering with pipeline output
            print(json.dumps(result), file=sys.stderr)
        elif self.args.debug:
            # Only show status messages in debug mode
            print(f"[{status.upper()}] {message}", file=sys.stderr)

    async def _send_transcription(self, result: dict[str, Any], extra: dict | None = None):
        """Send transcription result."""
        output = {
            "type": "transcription",
            "mode": self._get_mode_name(),
            "text": result["text"],
            "language": result["language"],
            "duration": result["duration"],
            "confidence": result["confidence"],
            "timestamp": time.time()
        }

        # Add any extra fields
        if extra:
            output.update(extra)

        if self.args.format == "json":
            print(json.dumps(output))
        # Text mode - just print the transcribed text
        # Skip partial results in non-debug mode to avoid clutter
        elif not result.get("is_partial", False) or self.args.debug:
            print(result["text"])

    async def _send_error(self, error_message: str, extra: dict | None = None):
        """Send error message."""
        result = {
            "type": "error",
            "mode": self._get_mode_name(),
            "error": error_message,
            "timestamp": time.time()
        }

        # Add any extra fields
        if extra:
            result.update(extra)

        if self.args.format == "json":
            # Send errors to stderr to avoid interfering with pipeline output
            print(json.dumps(result), file=sys.stderr)
        elif self.args.debug:
            # Only show errors in debug mode
            print(f"Error: {error_message}", file=sys.stderr)

    def _get_mode_name(self) -> str:
        """Get the mode name from the class name."""
        class_name = self.__class__.__name__
        if class_name.endswith("Mode"):
            class_name = class_name[:-4]  # Remove "Mode" suffix

        # Convert CamelCase to snake_case
        import re
        return re.sub("([A-Z]+)", r"_\1", class_name).lower().strip("_")

    async def _process_and_transcribe_collected_audio(self, audio_chunks: list | None = None):
        """
        A helper to process a list of audio chunks, transcribe it,
        and send the results. Uses self.audio_data by default.
        """
        # Use the provided chunks, or fall back to the instance's audio_data
        chunks_to_process = audio_chunks if audio_chunks is not None else self.audio_data

        if not chunks_to_process:
            await self._send_error("No audio data to transcribe")
            return

        try:
            # Combine all audio chunks
            audio_array = np.concatenate(chunks_to_process)
            duration = len(audio_array) / self.args.sample_rate
            self.logger.info(f"Transcribing {duration:.2f}s of audio ({len(audio_array)} samples)")

            # Transcribe in executor to avoid blocking
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, lambda: self._transcribe_audio(audio_array))

            if result.get("success"):
                await self._send_transcription(result)
            else:
                await self._send_error(f"Transcription failed: {result.get('error', 'Unknown error')}")

        except Exception as e:
            self.logger.exception(f"Error during transcription processing: {e}")
            await self._send_error(f"Transcription error: {e}")

    async def _cleanup(self):
        """Default cleanup behavior. Can be overridden by subclasses."""
        if self.is_recording and self.audio_streamer:
            self.audio_streamer.stop_recording()

        self.logger.info(f"{self.__class__.__name__} cleanup completed")
