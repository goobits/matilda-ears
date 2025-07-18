#!/usr/bin/env python3
"""
Hold-to-Talk Mode - Push-to-talk recording

This mode offers a "walkie-talkie" style interaction:
- Press and hold a key to start recording
- Recording continues while key is held down
- Release key to stop recording and trigger transcription
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
    from pynput.keyboard import Key, Listener
    PYNPUT_AVAILABLE = True
except ImportError:
    PYNPUT_AVAILABLE = False


class HoldToTalkMode:
    """Hold-to-talk mode with global hotkey support."""

    def __init__(self, args):
        self.args = args
        self.hotkey = args.hold_to_talk
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

        # Keyboard listener
        self.keyboard_listener = None
        self.target_key = None
        self.stop_event = threading.Event()

        # Check dependencies
        if not NUMPY_AVAILABLE:
            raise ImportError(
                "NumPy is required for hold-to-talk mode. "
                "Install with: pip install numpy"
            )

        self.logger.info(f"Hold-to-talk mode initialized with hotkey: {self.hotkey}")

    async def run(self):
        """Main hold-to-talk mode loop."""
        try:
            # Check if pynput is available
            if not PYNPUT_AVAILABLE:
                await self._send_error("pynput is required for hold-to-talk mode")
                return

            # Initialize Whisper model
            await self._load_model()

            # Setup audio streaming
            await self._setup_audio()

            # Start keyboard listener
            self._start_keyboard_listener()

            # Send initial status
            await self._send_status("ready", f"Hold-to-talk ready - Hold {self.hotkey} to record")

            # Keep running until stopped
            while not self.stop_event.is_set():
                await asyncio.sleep(0.1)

        except KeyboardInterrupt:
            await self._send_status("interrupted", "Hold-to-talk mode stopped by user")
        except Exception as e:
            self.logger.exception(f"Hold-to-talk mode error: {e}")
            await self._send_error(f"Hold-to-talk mode failed: {e}")
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

    def _start_keyboard_listener(self):
        """Start the keyboard listener for press/release events."""
        try:
            # Parse target key
            self.target_key = self._parse_key(self.hotkey)

            # Create and start listener
            self.keyboard_listener = Listener(
                on_press=self._on_key_press,
                on_release=self._on_key_release
            )

            self.keyboard_listener.start()
            self.logger.info(f"Keyboard listener started for: {self.hotkey}")

        except Exception as e:
            self.logger.error(f"Failed to start keyboard listener: {e}")
            raise

    def _parse_key(self, key_str: str):
        """Parse key string to pynput Key object."""
        # Convert common key names to pynput Key objects
        key_mapping = {
            'space': Key.space,
            'enter': Key.enter,
            'shift': Key.shift,
            'shift_l': Key.shift_l,
            'shift_r': Key.shift_r,
            'ctrl': Key.ctrl,
            'ctrl_l': Key.ctrl_l,
            'ctrl_r': Key.ctrl_r,
            'alt': Key.alt,
            'alt_l': Key.alt_l,
            'alt_r': Key.alt_r,
            'cmd': Key.cmd,
            'tab': Key.tab,
            'esc': Key.esc,
            'escape': Key.esc,
            'backspace': Key.backspace,
            'delete': Key.delete,
            'up': Key.up,
            'down': Key.down,
            'left': Key.left,
            'right': Key.right,
        }

        # Handle function keys
        if key_str.lower().startswith('f') and key_str[1:].isdigit():
            func_num = int(key_str[1:])
            if 1 <= func_num <= 12:
                return getattr(Key, f'f{func_num}')

        # Check if it's a special key
        if key_str.lower() in key_mapping:
            return key_mapping[key_str.lower()]

        # For single characters, return the character itself
        if len(key_str) == 1:
            return key_str.lower()

        # Default: try to create Key from string
        try:
            return Key[key_str.lower()]
        except (KeyError, AttributeError):
            # Fallback: return the string and hope it works
            return key_str.lower()

    def _on_key_press(self, key):
        """Handle key press events."""
        try:
            # Check if this is our target key
            if self._is_target_key(key):
                if not self.is_recording:
                    # Start recording
                    if self.loop is not None:
                        asyncio.run_coroutine_threadsafe(self._start_recording(), self.loop)

        except Exception as e:
            self.logger.error(f"Error handling key press: {e}")

    def _on_key_release(self, key):
        """Handle key release events."""
        try:
            # Check if this is our target key
            if self._is_target_key(key):
                if self.is_recording:
                    # Stop recording and transcribe
                    if self.loop is not None:
                        asyncio.run_coroutine_threadsafe(self._stop_recording(), self.loop)

        except Exception as e:
            self.logger.error(f"Error handling key release: {e}")

    def _is_target_key(self, key) -> bool:
        """Check if the pressed/released key matches our target key."""
        try:
            # Handle special keys
            if hasattr(key, 'name'):
                return bool(key == self.target_key or str(key) == str(self.target_key))

            # Handle character keys
            if hasattr(key, 'char') and key.char:
                return bool(key.char.lower() == str(self.target_key).lower())

            # Direct comparison
            return bool(key == self.target_key)

        except Exception:
            return False

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

            await self._send_status("recording", f"Recording... (release {self.hotkey} to stop)")
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

            await self._send_status("ready", f"Ready - Hold {self.hotkey} to record")

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
            "mode": "hold_to_talk",
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
            "mode": "hold_to_talk",
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
            "mode": "hold_to_talk",
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

        if self.keyboard_listener:
            self.keyboard_listener.stop()

        self.logger.info("Hold-to-talk mode cleanup completed")
