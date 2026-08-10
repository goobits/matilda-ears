#!/usr/bin/env python3
"""BaseMode - Abstract base class for all STT operation modes

This class provides common functionality shared across all operation modes:
- Whisper model loading and management
- Audio streaming setup
- Transcription processing
- Output formatting (JSON/text)
- Error handling and cleanup
"""

import asyncio
import json
import os
import re
import sys
import tempfile
import time
import wave
from abc import ABC, abstractmethod
from typing import Any

import numpy as np

from matilda_ears.core.config import get_config, setup_logging
from matilda_ears.core.mode_config import ModeConfig
from matilda_ears.audio.capture import PipeBasedAudioStreamer
from matilda_ears.transcription.backends import get_backend_class


class AudioCaptureEndedError(RuntimeError):
    pass


class BaseMode(ABC):
    """Abstract base class for all STT operation modes."""

    def __init__(self, mode_config: ModeConfig):
        """Initialize common mode components."""
        self.mode_config = mode_config
        self.config = get_config()
        if self.mode_config.sample_rate is None:
            self.mode_config.sample_rate = self.config.audio_sample_rate
        if self.mode_config.language is None:
            self.mode_config.language = "en"
        if self.mode_config.model is None:
            self.mode_config.model = self.config.whisper_model
        if not self.mode_config.format:
            self.mode_config.format = "text"
        self.logger = setup_logging(
            self.__class__.__name__,
            log_level="DEBUG" if self.mode_config.debug else "WARNING",
            include_console=self.mode_config.debug,  # Only show console logs in debug mode
            include_file=True,
        )

        # Audio processing
        self.audio_queue: asyncio.Queue[np.ndarray] | None = None
        self.audio_streamer: PipeBasedAudioStreamer | None = None

        # Transcription Backend
        self.backend = None

        # Recording state
        self.is_recording = False
        self._stop_requested = False

        # Check dependencies
        self.logger.info(f"{self.__class__.__name__} initialized")

    def _get_mode_config(self) -> dict[str, Any]:
        """Get mode-specific configuration from matilda config."""
        mode_name = self._get_mode_name()
        return self.config.get("modes", {}).get(mode_name, {})

    @abstractmethod
    async def run(self):
        """Main entry point for the mode. Must be implemented by subclasses."""

    async def _load_model(self):
        """Load transcription backend asynchronously."""
        try:
            backend_name = self.config.transcription_backend
            self.logger.info(f"Initializing backend: {backend_name}")

            # Get backend class
            BackendClass = get_backend_class(backend_name)
            self.backend = BackendClass()

            # Load backend
            await self.backend.load()

            self.logger.info(f"Backend {backend_name} loaded successfully")

        except Exception as e:
            self.logger.error(f"Failed to load transcription backend: {e}")
            raise

    async def _start_audio_capture(self, maxsize: int = 1000, chunk_duration_ms: int = 32) -> None:
        """Initialize and start the shared audio capture pipeline."""
        if self.is_recording:
            return

        try:
            self.audio_queue = asyncio.Queue(maxsize=maxsize)
            self.audio_streamer = PipeBasedAudioStreamer(
                loop=asyncio.get_running_loop(),
                queue=self.audio_queue,
                chunk_duration_ms=chunk_duration_ms,
                sample_rate=self.mode_config.sample_rate,
                audio_device=self.mode_config.device,
            )
            if not await asyncio.to_thread(self.audio_streamer.start_recording):
                raise RuntimeError("Failed to start audio recording")
            self.is_recording = True
            self._stop_requested = False
            self.logger.info("Audio capture started")
        except Exception:
            self.audio_queue = None
            self.audio_streamer = None
            self.is_recording = False
            raise

    async def _stop_audio_capture(self) -> dict[str, Any]:
        """Stop capture once and release all queue/process ownership."""
        streamer = self.audio_streamer
        self.audio_streamer = None
        self.audio_queue = None
        self.is_recording = False
        if streamer is None:
            return {}
        return await asyncio.to_thread(streamer.stop_recording)

    async def _read_audio_chunk(self, timeout_seconds: float = 0.1) -> np.ndarray:
        """Read one chunk and distinguish silence from a dead capture process."""
        if self.audio_queue is None:
            raise AudioCaptureEndedError("Audio capture is not initialized")
        try:
            return await asyncio.wait_for(self.audio_queue.get(), timeout=timeout_seconds)
        except TimeoutError:
            if self.audio_streamer is None or not self.audio_streamer.is_recording():
                raise AudioCaptureEndedError("Audio capture process stopped") from None
            raise

    def stop(self) -> None:
        """Request a graceful mode shutdown."""
        self._stop_requested = True

    def _transcribe_audio(self, audio_data: np.ndarray) -> dict[str, Any]:
        """Transcribe audio data using the loaded backend."""
        tmp_file_path = None
        try:
            if self.backend is None or not self.backend.is_ready:
                raise RuntimeError("Backend not loaded or not ready")

            # Save audio to temporary WAV file
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_file:
                tmp_file_path = tmp_file.name
                with wave.open(tmp_file.name, "wb") as wav_file:
                    wav_file.setnchannels(1)  # Mono
                    wav_file.setsampwidth(2)  # 16-bit
                    wav_file.setframerate(self.mode_config.sample_rate)
                    wav_file.writeframes(audio_data.astype(np.int16).tobytes())

            # Transcribe using backend
            text, info = self.backend.transcribe(tmp_file_path, language=self.mode_config.language)

            self.logger.info(f"Transcribed: '{text}' ({len(text)} chars)")

            return {
                "success": True,
                "text": text,
                "language": info.get("language", "en"),
                "duration": info.get("duration", 0.0),
                "confidence": info.get("confidence", 1.0),
            }

        except Exception as e:
            self.logger.error(f"Transcription error: {e}")
            return {"success": False, "error": str(e), "text": "", "duration": 0}
        finally:
            # Cleanup temp file
            if tmp_file_path and os.path.exists(tmp_file_path):
                try:
                    os.unlink(tmp_file_path)
                except Exception as e:
                    self.logger.warning(f"Failed to delete temp file {tmp_file_path}: {e}")

    async def _send_status(self, status: str, message: str, extra: dict | None = None):
        """Send status message."""
        result = {
            "type": "status",
            "mode": self._get_mode_name(),
            "status": status,
            "message": message,
            "timestamp": time.time(),
        }

        # Add any extra fields
        if extra:
            result.update(extra)

        if self.mode_config.format == "json":
            # Send status messages to stderr to avoid interfering with pipeline output
            print(json.dumps(result), file=sys.stderr)
        elif self.mode_config.debug:
            # Only show status messages in text mode when debug is enabled
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
            "timestamp": time.time(),
        }

        # Add any extra fields
        if extra:
            output.update(extra)

        if self.mode_config.format == "json":
            print(json.dumps(output))
        else:
            # Text mode - just print the transcribed text
            print(result["text"])

    async def _send_error(self, error_message: str, extra: dict | None = None):
        """Send error message."""
        result = {"type": "error", "mode": self._get_mode_name(), "error": error_message, "timestamp": time.time()}

        # Add any extra fields
        if extra:
            result.update(extra)

        if self.mode_config.format == "json":
            # Send errors to stderr to avoid interfering with pipeline output
            print(json.dumps(result), file=sys.stderr)
        elif self.mode_config.debug:
            # Only show errors in text mode when debug is enabled
            print(f"Error: {error_message}", file=sys.stderr)

    def _get_mode_name(self) -> str:
        """Get the mode name from the class name."""
        class_name = self.__class__.__name__
        class_name = class_name.removesuffix("Mode")  # Remove "Mode" suffix
        return re.sub("([A-Z]+)", r"_\1", class_name).lower().strip("_")

    async def _transcribe_async(self, audio_data: np.ndarray) -> dict[str, Any]:
        duration = len(audio_data) / self.mode_config.sample_rate
        self.logger.info(f"Transcribing {duration:.2f}s of audio ({len(audio_data)} samples)")
        return await asyncio.to_thread(self._transcribe_audio, audio_data)

    async def _transcribe_and_send(self, audio_data: np.ndarray, extra: dict | None = None) -> dict[str, Any]:
        """Transcribe one normalized utterance and emit the standard result."""
        if audio_data.size == 0:
            result = {"success": False, "error": "No audio data to transcribe"}
        else:
            result = await self._transcribe_async(audio_data)

        if result.get("success"):
            await self._send_transcription(result, extra)
        else:
            await self._send_error(f"Transcription failed: {result.get('error', 'Unknown error')}")
        return result

    async def _cleanup(self):
        """Stop capture and release mode resources once."""
        await self._stop_audio_capture()
        self.logger.info(f"{self.__class__.__name__} cleanup completed")
