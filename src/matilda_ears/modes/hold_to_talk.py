#!/usr/bin/env python3
"""Hold-to-Talk Mode - Push-to-talk recording

This mode offers a "walkie-talkie" style interaction:
- Press and hold a key to start recording
- Recording continues while key is held down
- Release key to stop recording and trigger transcription
- Global hotkey support (works without terminal focus)
"""

import asyncio
import platform
import threading
from typing import Any

from ._imports import Controller, Key, Listener, PYNPUT_AVAILABLE
from .base_mode import BaseMode
from matilda_ears.core.mode_config import HoldToTalkConfig


class HoldToTalkMode(BaseMode):
    """Hold-to-talk mode with global hotkey support."""

    def __init__(self, mode_config: HoldToTalkConfig):
        super().__init__(mode_config)
        self.hotkey = mode_config.hotkey

        # Keyboard listener
        self.keyboard_listener = None
        self._key_controller = Controller() if Controller else None
        self.stop_event = threading.Event()
        self._required_modifiers: set[str] = set()
        self._pressed_modifiers: set[str] = set()
        self._trigger_key = None
        self._trigger_char: str | None = None
        self._suppress_chars: set[str] = set()
        self._recording_started_by_trigger = False

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
            self._required_modifiers, self._trigger_key, self._trigger_char = self._parse_hotkey_combo(self.hotkey)
            if self._trigger_char:
                self._suppress_chars.add(self._trigger_char)

            # Create and start listener
            listener_kwargs = {
                "on_press": self._on_key_press,
                "on_release": self._on_key_release,
            }
            if platform.system() == "Darwin":
                listener_kwargs["darwin_intercept"] = self._darwin_intercept
            self.keyboard_listener = Listener(**listener_kwargs)

            self.keyboard_listener.start()
            self.logger.info(f"Keyboard listener started for: {self.hotkey}")

        except Exception as e:
            self.logger.error(f"Failed to start keyboard listener: {e}")
            raise

    def _parse_key(self, key_str: str):
        """Parse key string to pynput Key object or character."""
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
            "command": Key.cmd,
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

    def _parse_hotkey_combo(self, hotkey_str: str) -> tuple[set[str], Any, str | None]:
        """Parse combos like 'cmd+/' into required modifiers + trigger key."""
        if "+" not in hotkey_str:
            key = self._parse_key(hotkey_str)
            trigger_char = key if isinstance(key, str) and len(key) == 1 else None
            return set(), key, trigger_char

        parts = [p.strip().lower() for p in hotkey_str.split("+") if p.strip()]
        if not parts:
            return set(), self._parse_key("space"), None

        modifiers: set[str] = set()
        trigger_part = parts[-1]
        for part in parts[:-1]:
            normalized = {
                "cmd": "cmd",
                "command": "cmd",
                "ctrl": "ctrl",
                "control": "ctrl",
                "alt": "alt",
                "option": "alt",
                "shift": "shift",
            }.get(part)
            if normalized:
                modifiers.add(normalized)
        trigger_key = self._parse_key(trigger_part)
        trigger_char = trigger_key if isinstance(trigger_key, str) and len(trigger_key) == 1 else None
        return modifiers, trigger_key, trigger_char

    def _get_modifier_name(self, key) -> str | None:
        if key is None:
            return None
        key_name = None
        if hasattr(key, "name"):
            key_name = str(getattr(key, "name", "")).lower()
        else:
            key_name = str(key).lower()

        if "cmd" in key_name:
            return "cmd"
        if "ctrl" in key_name or "control" in key_name:
            return "ctrl"
        if "alt" in key_name or "option" in key_name:
            return "alt"
        if "shift" in key_name:
            return "shift"
        return None

    def _on_key_press(self, key):
        """Handle key press events."""
        try:
            modifier = self._get_modifier_name(key)
            if modifier:
                self._pressed_modifiers.add(modifier)
                return

            if self._should_suppress_character(key):
                self._erase_last_character()

            if self._is_trigger_key(key) and self._combo_is_satisfied() and not self.is_recording:
                if self.loop is not None:
                    asyncio.run_coroutine_threadsafe(self._start_recording(), self.loop)
                    self._recording_started_by_trigger = True

        except Exception as e:
            self.logger.error(f"Error handling key press: {e}")

    def _on_key_release(self, key):
        """Handle key release events."""
        try:
            modifier = self._get_modifier_name(key)
            if modifier:
                self._pressed_modifiers.discard(modifier)
                if self.is_recording and modifier in self._required_modifiers and self._recording_started_by_trigger:
                    if self.loop is not None:
                        asyncio.run_coroutine_threadsafe(self._stop_recording(), self.loop)
                        self._recording_started_by_trigger = False
                return

            if self._is_trigger_key(key):
                if self.is_recording and self._recording_started_by_trigger:
                    if self.loop is not None:
                        asyncio.run_coroutine_threadsafe(self._stop_recording(), self.loop)
                        self._recording_started_by_trigger = False

        except Exception as e:
            self.logger.error(f"Error handling key release: {e}")

    def _is_trigger_key(self, key) -> bool:
        """Check if key matches trigger key for hold-to-talk."""
        try:
            if hasattr(key, "name"):
                return bool(key == self._trigger_key or str(key) == str(self._trigger_key))

            if hasattr(key, "char") and key.char:
                return bool(key.char.lower() == str(self._trigger_key).lower())

            return bool(key == self._trigger_key)

        except Exception:
            self.logger.exception("Error in recording loop")
            return False

    def _combo_is_satisfied(self) -> bool:
        return not self._required_modifiers or self._required_modifiers.issubset(self._pressed_modifiers)

    def _should_suppress_character(self, key) -> bool:
        if not self._combo_is_satisfied():
            return False
        if not hasattr(key, "char") or not key.char:
            return False
        return key.char.lower() in self._suppress_chars

    def _erase_last_character(self) -> None:
        if not self._key_controller:
            return
        try:
            self._key_controller.press(Key.backspace)
            self._key_controller.release(Key.backspace)
        except Exception:
            pass

    def _darwin_intercept(self, event_type, event):
        # Lightweight interception on macOS to avoid printable trigger chars leaking through.
        # We keep this defensive: if Quartz isn't available or parsing fails, pass event through.
        try:
            if platform.system() != "Darwin":
                return event
            if not self._trigger_char or not self._combo_is_satisfied():
                return event
            import Quartz  # type: ignore

            if event_type not in (Quartz.kCGEventKeyDown, Quartz.kCGEventKeyUp):
                return event

            _, event_chars = Quartz.CGEventKeyboardGetUnicodeString(event, 4, None, None)
            if event_chars and str(event_chars).lower() in self._suppress_chars:
                return None
            return event
        except Exception:
            return event

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
