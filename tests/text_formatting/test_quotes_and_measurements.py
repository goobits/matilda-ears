#!/usr/bin/env python3
"""Test cases for proper quote formatting and measurement conversions."""

import pytest
from stt_hotkeys.text_formatting.formatter import format_transcription


class TestQuoteFormatting:
    """Test proper smart quote conversion."""

    def test_double_quotes(self):
        """Test double quote conversion to curly quotes."""
        assert format_transcription('he said "hello"') == 'He said "hello".'
        assert format_transcription('the book "war and peace" is long') == 'The book "war and peace" is long.'
        assert format_transcription('she said "I am tired"') == 'She said: "I am tired".'

    def test_single_quotes(self):
        """Test single quote conversion to curly quotes."""
        assert format_transcription("he said 'hello'") == "He said 'hello'."
        assert format_transcription("the word 'cat' has three letters") == "The word 'cat' has 3 letters."

    def test_apostrophes_preserved(self):
        """Test that apostrophes in contractions remain curly."""
        assert format_transcription("it's raining") == "It's raining."
        assert format_transcription("the dog's bone") == "The dog's bone."
        assert format_transcription("I can't go") == "I can't go."
        assert format_transcription("they're here") == "They're here."

    def test_nested_quotes(self):
        """Test nested quote handling."""
        assert format_transcription("he said \"she told me 'hello'\"") == "He said: \"she told me 'hello'\"."

    def test_quotes_with_punctuation(self):
        """Test quotes with adjacent punctuation."""
        assert format_transcription('did he say "hello"?') == 'Did he say "hello"?'
        assert format_transcription('she yelled "stop!"') == 'She yelled: "stop".'


class TestMeasurementConversion:
    """Test measurement to proper symbol conversion."""

    def test_feet_conversion(self):
        """Test feet measurements get prime symbol."""
        assert format_transcription("six feet") == "6′"
        assert format_transcription("the board is eight feet long") == "The board is 8′ long."
        assert format_transcription("twelve feet") == "12′"

    def test_inches_conversion(self):
        """Test inches measurements get double prime symbol."""
        assert format_transcription("twelve inches") == "12″"
        assert format_transcription("four inches wide") == "4″ wide."

    def test_height_measurements(self):
        """Test height format like 5'10"."""
        assert format_transcription("five foot ten") == "5′10″"
        assert format_transcription("six foot two") == "6′2″"
        assert format_transcription("five foot ten inches") == "5′10″"

    def test_fractional_measurements(self):
        """Test measurements with fractions."""
        assert format_transcription("three and a half feet") == "3.5′"
        assert format_transcription("two and a half inches") == "2.5″"

    def test_measurements_vs_possessives(self):
        """Test that measurements don't interfere with possessives."""
        assert format_transcription("John's height is six feet") == "John's height is 6′."
        assert format_transcription("the tree's height") == "The tree's height."


class TestEdgeCases:
    """Test edge cases combining quotes and measurements."""

    def test_quotes_with_measurements(self):
        """Test quotes containing measurements."""
        assert format_transcription('he said "I am six feet tall"') == 'He said: "I am 6′ tall".'
        assert (
            format_transcription('the sign reads "maximum height twelve feet"')
            == 'The sign reads: "maximum height: 12′".'
        )

    def test_technical_content_with_quotes(self):
        """Test technical content doesn't get wrong quotes."""
        # URLs should remain standalone
        assert format_transcription("example dot com") == "example.com"
        # But URLs in sentences get quotes
        assert format_transcription('visit "example dot com" today') == 'Visit "example.com" today.'

    def test_measurements_as_standalone(self):
        """Test standalone measurements."""
        # Standalone measurements should not get extra punctuation
        assert format_transcription("six feet") == "6′"
        # But measurements in sentences should work normally
        assert format_transcription("the height is six feet exactly") == "The height is 6′ exactly."

    def test_mixed_quote_types(self):
        """Test mixing straight and curly quotes doesn't break."""
        # Even if input has mixed quotes, output should be consistent
        text = "he said \"hello\" and she said 'goodbye'"
        result = format_transcription(text)
        assert '"' in result  # Should have left double quote
        assert '"' in result  # Should have right double quote
        # Note: The punctuation model already handles apostrophes/single quotes
        assert "goodbye" in result  # Content should be preserved


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
