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
import time
import tempfile
import wave
import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any
import sys

# Shared imports and fallbacks
from ._imports import np, NUMPY_AVAILABLE

# Add project root to path for local imports (also done in _imports.py)
sys.path.insert(0, str(Path(__file__).parent.parent.parent.absolute()))

from matilda_ears.core.config import get_config, setup_logging
from matilda_ears.core.mode_config import ModeConfig
from matilda_ears.audio.capture import PipeBasedAudioStreamer
from matilda_ears.transcription.backends import get_backend_class


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
        self.loop = None
        self.audio_queue = None
        self.audio_streamer = None

        # Transcription Backend
        self.backend = None

        # Recording state
        self.is_recording = False
        self.audio_data = []

        # Check dependencies
        if not NUMPY_AVAILABLE:
            raise ImportError(f"NumPy is required for {self.__class__.__name__}. " "Install with: pip install numpy")

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
            # Determine backend from config
            backend_name = self.config.get("transcription", {}).get("backend", "faster_whisper")
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
                sample_rate=self.mode_config.sample_rate,
                audio_device=self.mode_config.device,
            )

            self.logger.info("Audio streamer setup completed")

        except Exception as e:
            self.logger.error(f"Failed to setup audio streaming: {e}")
            raise

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

        # Convert CamelCase to snake_case
        import re

        return re.sub("([A-Z]+)", r"_\1", class_name).lower().strip("_")

    async def _process_and_transcribe_collected_audio(self, audio_chunks: list | None = None):
        """A helper to process a list of audio chunks, transcribe it,
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
            duration = len(audio_array) / self.mode_config.sample_rate
            self.logger.info(f"Transcribing {duration:.2f}s of audio ({len(audio_array)} samples)")

            # Transcribe in executor to avoid blocking
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, self._transcribe_audio, audio_array)

            if result.get("success"):
                await self._send_transcription(result)
            else:
                await self._send_error(f"Transcription failed: {result.get('error', 'Unknown error')}")

        except Exception as e:
            self.logger.exception(f"Error during transcription processing: {e}")
            await self._send_error(f"Transcription error: {e}")

    async def _collect_audio(self):
        """Collect audio chunks while recording.

        This shared method accumulates audio data into self.audio_data while
        self.is_recording is True.
        """
        while self.is_recording:
            try:
                if self.audio_queue is None:
                    break
                audio_chunk = await asyncio.wait_for(self.audio_queue.get(), timeout=0.1)
                self.audio_data.append(audio_chunk)
            except TimeoutError:
                # No audio data available - continue if still recording
                continue
            except Exception as e:
                self.logger.error(f"Error collecting audio: {e}")
                break

    # =========================================================================
    # Recording control methods shared by explicit recording workflows
    # =========================================================================

    def _get_recording_start_message(self) -> str:
        """Get the status message shown when recording starts.

        Override in subclasses to customize the message.
        """
        return "Recording..."

    def _get_recording_ready_message(self) -> str:
        """Get the status message shown when ready to record.

        Override in subclasses to customize the message.
        """
        return "Ready to record"

    async def _start_recording(self):
        """Start audio recording.

        Shared implementation for explicit recording workflows.
        Override _get_recording_start_message() to customize the status message.
        """
        try:
            if self.is_recording:
                return

            self.is_recording = True
            self.audio_data = []

            # Start audio streamer
            if self.audio_streamer is None or not self.audio_streamer.start_recording():
                raise RuntimeError("Failed to start audio recording")

            # Start collecting audio in background
            asyncio.create_task(self._collect_audio())

            await self._send_status("recording", self._get_recording_start_message())
            self.logger.info("Recording started")

        except Exception as e:
            self.logger.error(f"Error starting recording: {e}")
            await self._send_error(f"Failed to start recording: {e}")
            self.is_recording = False

    async def _stop_recording(self):
        """Stop recording and transcribe.

        Shared implementation for explicit recording workflows.
        Override _get_recording_ready_message() to customize the status message.
        """
        try:
            if not self.is_recording:
                return

            self.is_recording = False

            # Stop audio streamer
            stats = {}
            if self.audio_streamer is not None:
                stats = self.audio_streamer.stop_recording()

            await self._send_status("processing", "Recording stopped - Transcribing...")
            self.logger.info(f"Recording stopped. Stats: {stats}")

            # Process the recorded audio
            if self.audio_data:
                await self._transcribe_recording()
            else:
                await self._send_error("No audio data recorded")

            await self._send_status("ready", self._get_recording_ready_message())

        except Exception as e:
            self.logger.exception(f"Error stopping recording: {e}")
            await self._send_error(f"Failed to stop recording: {e}")

    async def _cleanup(self):
        """Default cleanup behavior. Can be overridden by subclasses."""
        if self.is_recording and self.audio_streamer:
            self.audio_streamer.stop_recording()

        self.logger.info(f"{self.__class__.__name__} cleanup completed")
