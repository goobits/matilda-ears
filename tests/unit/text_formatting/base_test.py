#!/usr/bin/env python3
"""Base test class with common assertion helpers for text formatting tests."""

from stt.text_formatting.formatter import format_transcription


class BaseFormattingTest:
    """Base class with common test utilities for text formatting tests."""
    
    def assert_formatting(self, input_text, expected, formatter=None):
        """Helper to reduce repetitive assertion patterns."""
        fmt = formatter or format_transcription
        result = fmt(input_text)
        assert result == expected, f"Input '{input_text}' should format to '{expected}', got '{result}'"

    def assert_formatting_options(self, input_text, expected_options, formatter=None):
        """Helper for tests with multiple valid outcomes."""
        fmt = formatter or format_transcription
        result = fmt(input_text)
        assert result in expected_options, f"Input '{input_text}' should format to one of {expected_options}, got '{result}'"
        
    def assert_formatting_contains(self, input_text, expected_substring, formatter=None):
        """Helper to check if result contains expected substring."""
        fmt = formatter or format_transcription
        result = fmt(input_text)
        assert expected_substring in result, f"Expected '{expected_substring}' in result '{result}' for input '{input_text}'"