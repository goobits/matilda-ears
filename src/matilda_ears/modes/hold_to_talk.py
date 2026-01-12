#!/usr/bin/env python3
"""Hold-to-Talk Mode - Push-to-talk recording

This mode offers a "walkie-talkie" style interaction:
- Press and hold a key to start recording
- Recording continues while key is held down
- Release key to stop recording and trigger transcription
- Global hotkey support (works without terminal focus)
"""

import asyncio
import threading
from typing import Any

from ._imports import Key, Listener, PYNPUT_AVAILABLE
from .base_mode import BaseMode
from matilda_ears.core.mode_config import HoldToTalkConfig


class HoldToTalkMode(BaseMode):
    """Hold-to-talk mode with global hotkey support."""

    def __init__(self, mode_config: HoldToTalkConfig):
        super().__init__(mode_config)
        self.hotkey = mode_config.hotkey

        # Keyboard listener
        self.keyboard_listener = None
        self.target_key = None
        self.stop_event = threading.Event()

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
            await self._setup_audio_streamer(maxsize=1000)  # Large buffer for recording

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

    def _start_keyboard_listener(self):
        """Start the keyboard listener for press/release events."""
        try:
            # Parse target key
            self.target_key = self._parse_key(self.hotkey)

            # Create and start listener
            self.keyboard_listener = Listener(on_press=self._on_key_press, on_release=self._on_key_release)

            self.keyboard_listener.start()
            self.logger.info(f"Keyboard listener started for: {self.hotkey}")

        except Exception as e:
            self.logger.error(f"Failed to start keyboard listener: {e}")
            raise

    def _parse_key(self, key_str: str):
        """Parse key string to pynput Key object."""
        # Convert common key names to pynput Key objects
        key_mapping = {
            "space": Key.space,
            "enter": Key.enter,
            "shift": Key.shift,
            "shift_l": Key.shift_l,
            "shift_r": Key.shift_r,
            "ctrl": Key.ctrl,
            "ctrl_l": Key.ctrl_l,
            "ctrl_r": Key.ctrl_r,
            "alt": Key.alt,
            "alt_l": Key.alt_l,
            "alt_r": Key.alt_r,
            "cmd": Key.cmd,
            "tab": Key.tab,
            "esc": Key.esc,
            "escape": Key.esc,
            "backspace": Key.backspace,
            "delete": Key.delete,
            "up": Key.up,
            "down": Key.down,
            "left": Key.left,
            "right": Key.right,
        }

        # Handle function keys
        if key_str.lower().startswith("f") and key_str[1:].isdigit():
            func_num = int(key_str[1:])
            if 1 <= func_num <= 12:
                return getattr(Key, f"f{func_num}")

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
            if hasattr(key, "name"):
                return bool(key == self.target_key or str(key) == str(self.target_key))

            # Handle character keys
            if hasattr(key, "char") and key.char:
                return bool(key.char.lower() == str(self.target_key).lower())

            # Direct comparison
            return bool(key == self.target_key)

        except Exception:
            self.logger.exception("Error in recording loop")
            return False

    # Recording methods inherited from BaseMode - just customize messages

    def _get_recording_start_message(self) -> str:
        """Get the status message shown when recording starts."""
        return f"Recording... (release {self.hotkey} to stop)"

    def _get_recording_ready_message(self) -> str:
        """Get the status message shown when ready to record."""
        return f"Ready - Hold {self.hotkey} to record"

    async def _transcribe_recording(self):
        """Transcribe the recorded audio."""
        await self._process_and_transcribe_collected_audio()

    async def _send_status(self, status: str, message: str):
        """Send status message with hotkey info."""
        await super()._send_status(status, message, {"hotkey": self.hotkey})

    async def _send_transcription(self, result: dict[str, Any]):
        """Send transcription result with hotkey info."""
        await super()._send_transcription(result, {"hotkey": self.hotkey})

    async def _send_error(self, error_message: str):
        """Send error message with hotkey info."""
        await super()._send_error(error_message, {"hotkey": self.hotkey})

    async def _cleanup(self):
        """Clean up resources."""
        self.stop_event.set()

        if self.keyboard_listener:
            self.keyboard_listener.stop()

        await super()._cleanup()
