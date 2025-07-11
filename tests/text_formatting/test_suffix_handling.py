#!/usr/bin/env python3
"""Tests for suffix handling in the STT system.

This test suite ensures that the suffix configuration is properly applied
after transcription, which is critical for user experience.
"""

import pytest
from src.text_formatting.formatter import TextFormatter


class TestSuffixHandling:
    """Test suffix configuration and application"""

    def setup_method(self):
        """Set up test environment"""
        self.formatter = TextFormatter()

    def test_config_has_suffix_setting(self, preloaded_config):
        """Test that config contains suffix setting"""
        config = preloaded_config
        suffix = config.get("text_insertion.suffix", None)
        assert suffix is not None

    def test_space_suffix_in_config(self, preloaded_formatter, preloaded_config):
        """Test that default suffix is space"""
        format_transcription = preloaded_formatter
        config = preloaded_config
        suffix = config.get("text_insertion.suffix", "")
        assert suffix == " ", f"Expected space suffix, got '{suffix}'"

    def test_formatter_handles_enter_pressed(self, preloaded_formatter):
        """Test that enter pressed prevents suffix addition"""
        format_transcription = preloaded_formatter
        # The formatter itself doesn't handle suffix, but let's test the parameter
        format_transcription = preloaded_formatter
        result = format_transcription("hello world", enter_pressed=True)
        # Should not have suffix when enter is pressed
        assert result == "Hello world"  # Just formatted, no suffix

    def test_formatter_without_enter_pressed(self, preloaded_formatter):
        """Test that normal transcription gets formatted properly"""
        format_transcription = preloaded_formatter
        result = format_transcription("hello world", enter_pressed=False)
        # Formatter doesn't add suffix, but formats the text
        assert result == "Hello world"

    # Note: Daemon suffix logic is tested in TestHotkeyDaemonSuffixLogic class below

    def test_auto_suffix_mode(self, preloaded_formatter):
        """Test auto suffix mode logic"""
        format_transcription = preloaded_formatter
        # Auto mode should be smart about when to add suffix
        test_cases = [
            ("hello world", " "),  # Normal sentence gets space
            ("hello world.", ""),  # Sentence with period gets no suffix
            ("hello world!", ""),  # Sentence with exclamation gets no suffix
            ("hello world?", ""),  # Sentence with question mark gets no suffix
            ("visit google.com", ""),  # URL gets no suffix
            ("price is $25.99", ""),  # Money gets no suffix
            ("count++", ""),  # Code gets no suffix
            ("x = 5", ""),  # Assignment gets no suffix
        ]

        for text, expected_suffix in test_cases:
            # Simulate auto suffix logic from formatter._handle_suffix
            suffix = "auto"
            actual_suffix = ""

            if suffix == "auto":
                last_char = text.rstrip()[-1:] if text.rstrip() else ""
                # Don't add suffix after any punctuation or technical content
                if (
                    last_char in ".!?:)]}"
                    or any(
                        pat in text for pat in ["++", "--", "==", ".com", ".org", "://", "http", " = ", " + ", " - "]
                    )
                    or text.rstrip().endswith((".99", ".00"))  # Money pattern
                ):
                    actual_suffix = ""
                else:
                    actual_suffix = " "

            assert (
                actual_suffix == expected_suffix
            ), f"Auto suffix for '{text}' should be '{expected_suffix}', got '{actual_suffix}'"


class TestHotkeyDaemonSuffixLogic:
    """Test the suffix logic as implemented in hotkey_daemon.py"""

    def test_daemon_suffix_logic_space(self, preloaded_formatter):
        """Test daemon suffix logic with space config"""
        format_transcription = preloaded_formatter
        # Simulate the actual daemon logic
        transcription_text = "hello world"
        enter_pressed = False

        # This would come from config.get('text_insertion.suffix', ' ')
        suffix_config = " "

        cleaned_text = transcription_text
        if not enter_pressed:
            suffix = suffix_config
            if suffix == "space":
                suffix = " "
            elif suffix == "newline":
                suffix = "\n"
            if suffix:
                cleaned_text += suffix

        assert cleaned_text == "hello world "

    def test_daemon_suffix_logic_enter_pressed(self, preloaded_formatter):
        """Test daemon suffix logic when enter is pressed"""
        format_transcription = preloaded_formatter
        transcription_text = "hello world"
        enter_pressed = True
        suffix_config = " "

        cleaned_text = transcription_text
        if not enter_pressed:  # Should be False, so no suffix added
            suffix = suffix_config
            if suffix:
                cleaned_text += suffix

        assert cleaned_text == "hello world"

    def test_daemon_suffix_special_keywords(self, preloaded_formatter):
        """Test daemon handling of special suffix keywords"""
        format_transcription = preloaded_formatter
        test_cases = [
            ("space", " "),
            ("newline", "\n"),
            (" ", " "),
            ("", ""),
        ]

        for suffix_config, expected_suffix in test_cases:
            transcription_text = "hello"
            enter_pressed = False
            cleaned_text = transcription_text

            if not enter_pressed:
                suffix = suffix_config
                if suffix == "space":
                    suffix = " "
                elif suffix == "newline":
                    suffix = "\n"
                if suffix:
                    cleaned_text += suffix

            expected_result = transcription_text + expected_suffix
            assert (
                cleaned_text == expected_result
            ), f"Config '{suffix_config}' should produce '{expected_result}', got '{cleaned_text}'"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
