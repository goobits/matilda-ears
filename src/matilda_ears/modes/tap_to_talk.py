#!/usr/bin/env python3
"""Tap-to-Talk Mode - Hotkey toggle recording

This mode provides a simple toggle-based recording mechanism:
- First key press starts recording
- Second key press stops recording and triggers transcription
- Global hotkey support (works without terminal focus)
"""

import asyncio
import threading
from typing import Dict, Any

from ._imports import keyboard, PYNPUT_AVAILABLE
from .base_mode import BaseMode


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
            "space": "<space>",
            "enter": "<enter>",
            "shift": "<shift>",
            "ctrl": "<ctrl>",
            "alt": "<alt>",
            "cmd": "<cmd>",
            "tab": "<tab>",
            "esc": "<esc>",
            "escape": "<esc>",
        }

        # Handle function keys
        if hotkey_str.lower().startswith("f") and hotkey_str[1:].isdigit():
            return f"<{hotkey_str.lower()}>"

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
            # Stop recording and transcribe
            elif self.loop is not None:
                asyncio.run_coroutine_threadsafe(self._stop_recording(), self.loop)

        except Exception as e:
            self.logger.error(f"Error handling hotkey press: {e}")

    # Recording methods inherited from BaseMode - just customize messages

    def _get_recording_start_message(self) -> str:
        """Get the status message shown when recording starts."""
        return f"Recording started - Press {self.hotkey} again to stop"

    def _get_recording_ready_message(self) -> str:
        """Get the status message shown when ready to record."""
        return f"Ready - Press {self.hotkey} to start recording"

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
