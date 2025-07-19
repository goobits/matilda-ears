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
from typing import Dict, Any
from pathlib import Path
import sys

# Add project root to path for local imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.absolute()))

from .base_mode import BaseMode

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


class TapToTalkMode(BaseMode):
    """Tap-to-talk mode with global hotkey support."""

    def __init__(self, args):
        super().__init__(args)
        self.hotkey = args.tap_to_talk
        
        # Hotkey listener
        self.hotkey_listener = None
        self.stop_event = threading.Event()
        
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
            await self._setup_audio_streamer(maxsize=1000)  # Large buffer for recording

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
        await self._process_and_transcribe_collected_audio()


    async def _send_status(self, status: str, message: str):
        """Send status message with hotkey info."""
        await super()._send_status(status, message, {"hotkey": self.hotkey})

    async def _send_transcription(self, result: Dict[str, Any]):
        """Send transcription result with hotkey info."""
        await super()._send_transcription(result, {"hotkey": self.hotkey})

    async def _send_error(self, error_message: str):
        """Send error message with hotkey info."""
        await super()._send_error(error_message, {"hotkey": self.hotkey})

    async def _cleanup(self):
        """Clean up resources."""
        self.stop_event.set()

        if self.hotkey_listener:
            self.hotkey_listener.stop()

        await super()._cleanup()
