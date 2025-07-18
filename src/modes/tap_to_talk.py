#!/usr/bin/env python3
"""
Tap-to-Talk Mode - Hotkey toggle recording

This mode provides a simple toggle-based recording mechanism:
- First key press starts recording
- Second key press stops recording and triggers transcription
- Global hotkey support (works without terminal focus)
"""

import asyncio
import threading
import time
import json
from typing import Dict, Any
from pathlib import Path
import sys

# Add project root to path for local imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.absolute()))

from src.core.config import get_config, setup_logging
from src.audio.capture import PipeBasedAudioStreamer

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

try:
    from pynput import keyboard
    PYNPUT_AVAILABLE = True
except ImportError:
    PYNPUT_AVAILABLE = False


class TapToTalkMode:
    """Tap-to-talk mode with global hotkey support."""

    def __init__(self, args):
        self.args = args
        self.hotkey = args.tap_to_talk
        self.config = get_config()
        self.logger = setup_logging(__name__,
                                  log_level="DEBUG" if args.debug else "INFO",
                                  include_console=args.format != "json",
                                  include_file=True)

        # Recording state
        self.is_recording = False
        self.audio_data = []

        # Audio processing
        self.audio_queue = None
        self.audio_streamer = None
        self.loop = None

        # Whisper model
        self.model = None

        # Hotkey listener
        self.hotkey_listener = None
        self.stop_event = threading.Event()

        # Check dependencies
        if not NUMPY_AVAILABLE:
            raise ImportError(
                "NumPy is required for tap-to-talk mode. "
                "Install with: pip install numpy"
            )

        self.logger.info(f"Tap-to-talk mode initialized with hotkey: {self.hotkey}")

    async def run(self):
        """Main tap-to-talk mode loop."""
        try:
            # Check if pynput is available
            if not PYNPUT_AVAILABLE:
                await self._send_error("pynput is required for tap-to-talk mode")
                return

            # Initialize Whisper model
            await self._load_model()

            # Setup audio streaming
            await self._setup_audio()

            # Start hotkey listener
            self._start_hotkey_listener()

            # Send initial status
            await self._send_status("ready", f"Tap-to-talk ready - Press {self.hotkey} to toggle recording")

            # Keep running until stopped
            while not self.stop_event.is_set():
                await asyncio.sleep(0.1)

        except KeyboardInterrupt:
            await self._send_status("interrupted", "Tap-to-talk mode stopped by user")
        except Exception as e:
            self.logger.exception(f"Tap-to-talk mode error: {e}")
            await self._send_error(f"Tap-to-talk mode failed: {e}")
        finally:
            await self._cleanup()

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

    async def _setup_audio(self):
        """Setup audio streaming (but don't start recording yet)."""
        try:
            self.loop = asyncio.get_event_loop()
            self.audio_queue = asyncio.Queue(maxsize=1000)  # Large buffer for recording

            # Create audio streamer (but don't start yet)
            self.audio_streamer = PipeBasedAudioStreamer(
                loop=self.loop,
                queue=self.audio_queue,
                chunk_duration_ms=32,  # 32ms chunks for VAD compatibility (512 samples at 16kHz)
                sample_rate=self.args.sample_rate,
                audio_device=self.args.device
            )

            self.logger.info("Audio streaming setup completed")

        except Exception as e:
            self.logger.error(f"Failed to setup audio streaming: {e}")
            raise

    def _start_hotkey_listener(self):
        """Start the global hotkey listener."""
        try:
            # Parse hotkey
            parsed_hotkey = self._parse_hotkey(self.hotkey)

            # Create and start listener
            self.hotkey_listener = keyboard.GlobalHotKeys({
                parsed_hotkey: self._on_hotkey_pressed
            })

            self.hotkey_listener.start()
            self.logger.info(f"Global hotkey listener started for: {self.hotkey}")

        except Exception as e:
            self.logger.error(f"Failed to start hotkey listener: {e}")
            raise

    def _parse_hotkey(self, hotkey_str: str) -> str:
        """Parse hotkey string to pynput format."""
        # Convert common key names to pynput format
        key_mapping = {
            'space': '<space>',
            'enter': '<enter>',
            'shift': '<shift>',
            'ctrl': '<ctrl>',
            'alt': '<alt>',
            'cmd': '<cmd>',
            'tab': '<tab>',
            'esc': '<esc>',
            'escape': '<esc>',
        }

        # Handle function keys
        if hotkey_str.lower().startswith('f') and hotkey_str[1:].isdigit():
            return f'<{hotkey_str.lower()}>'

        # Check if it's a special key
        if hotkey_str.lower() in key_mapping:
            return key_mapping[hotkey_str.lower()]

        # For single characters, return as-is
        if len(hotkey_str) == 1:
            return hotkey_str.lower()

        # Default: return as-is and hope pynput understands it
        return hotkey_str

    def _on_hotkey_pressed(self):
        """Handle hotkey press - toggle recording state."""
        try:
            if not self.is_recording:
                # Start recording
                if self.loop is not None:
                    asyncio.run_coroutine_threadsafe(self._start_recording(), self.loop)
            else:
                # Stop recording and transcribe
                if self.loop is not None:
                    asyncio.run_coroutine_threadsafe(self._stop_recording(), self.loop)

        except Exception as e:
            self.logger.error(f"Error handling hotkey press: {e}")

    async def _start_recording(self):
        """Start audio recording."""
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

            await self._send_status("recording", f"Recording started - Press {self.hotkey} again to stop")
            self.logger.info("Recording started")

        except Exception as e:
            self.logger.error(f"Error starting recording: {e}")
            await self._send_error(f"Failed to start recording: {e}")
            self.is_recording = False

    async def _stop_recording(self):
        """Stop recording and transcribe."""
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

            await self._send_status("ready", f"Ready - Press {self.hotkey} to start recording")

        except Exception as e:
            self.logger.error(f"Error stopping recording: {e}")
            await self._send_error(f"Failed to stop recording: {e}")

    async def _collect_audio(self):
        """Collect audio chunks while recording."""
        while self.is_recording:
            try:
                # Get audio chunk with timeout
                if self.audio_queue is None:
                    break
                audio_chunk = await asyncio.wait_for(self.audio_queue.get(), timeout=0.1)
                self.audio_data.append(audio_chunk)

            except asyncio.TimeoutError:
                # No audio data - continue if still recording
                continue
            except Exception as e:
                self.logger.error(f"Error collecting audio: {e}")
                break

    async def _transcribe_recording(self):
        """Transcribe the recorded audio."""
        try:
            # Combine all audio chunks
            if not self.audio_data:
                await self._send_error("No audio data to transcribe")
                return

            audio_array = np.concatenate(self.audio_data)
            duration = len(audio_array) / self.args.sample_rate

            self.logger.info(f"Transcribing {duration:.2f}s of audio ({len(audio_array)} samples)")

            # Transcribe in executor to avoid blocking
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, self._transcribe_audio, audio_array)

            if result["success"]:
                await self._send_transcription(result)
            else:
                await self._send_error(f"Transcription failed: {result.get('error', 'Unknown error')}")

        except Exception as e:
            self.logger.exception(f"Error transcribing recording: {e}")
            await self._send_error(f"Transcription error: {e}")

    def _transcribe_audio(self, audio_data: np.ndarray) -> Dict[str, Any]:
        """Transcribe audio data using Whisper."""
        try:
            import tempfile
            import wave

            # Save audio to temporary WAV file
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_file:
                with wave.open(tmp_file.name, 'wb') as wav_file:
                    wav_file.setnchannels(1)  # Mono
                    wav_file.setsampwidth(2)  # 16-bit
                    wav_file.setframerate(self.args.sample_rate)
                    wav_file.writeframes(audio_data.astype(np.int16).tobytes())

                # Transcribe
                if self.model is None:
                    raise RuntimeError("Model not loaded")
                segments, info = self.model.transcribe(tmp_file.name, language=self.args.language)
                text = "".join([segment.text for segment in segments]).strip()

                self.logger.info(f"Transcribed: '{text}' ({len(text)} chars)")

                return {
                    "success": True,
                    "text": text,
                    "language": info.language if hasattr(info, 'language') else 'en',
                    "duration": len(audio_data) / self.args.sample_rate,
                    "confidence": 0.95  # Placeholder
                }

        except Exception as e:
            self.logger.error(f"Transcription error: {e}")
            return {
                "success": False,
                "error": str(e),
                "text": "",
                "duration": 0
            }

    async def _send_status(self, status: str, message: str):
        """Send status message."""
        result = {
            "type": "status",
            "mode": "tap_to_talk",
            "status": status,
            "message": message,
            "hotkey": self.hotkey,
            "timestamp": time.time()
        }

        if self.args.format == "json":
            print(json.dumps(result))
        else:
            print(f"[{status.upper()}] {message}", file=sys.stderr)

    async def _send_transcription(self, result: Dict[str, Any]):
        """Send transcription result."""
        output = {
            "type": "transcription",
            "mode": "tap_to_talk",
            "text": result["text"],
            "language": result["language"],
            "duration": result["duration"],
            "confidence": result["confidence"],
            "hotkey": self.hotkey,
            "timestamp": time.time()
        }

        if self.args.format == "json":
            print(json.dumps(output))
        else:
            print(result["text"])

    async def _send_error(self, error_message: str):
        """Send error message."""
        result = {
            "type": "error",
            "mode": "tap_to_talk",
            "error": error_message,
            "hotkey": self.hotkey,
            "timestamp": time.time()
        }

        if self.args.format == "json":
            print(json.dumps(result))
        else:
            print(f"Error: {error_message}", file=sys.stderr)

    async def _cleanup(self):
        """Clean up resources."""
        self.stop_event.set()

        if self.is_recording and self.audio_streamer:
            self.audio_streamer.stop_recording()

        if self.hotkey_listener:
            self.hotkey_listener.stop()

        self.logger.info("Tap-to-talk mode cleanup completed")
