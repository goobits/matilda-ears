"""Test contextual number handling to prevent unwanted conversions."""

import pytest


class TestContextualNumbers:
    """Test that number words in certain contexts are not converted to digits."""

    def test_number_words_in_natural_speech(self, preloaded_formatter):
        """Test that number words in natural speech contexts remain as words."""
        format_transcription = preloaded_formatter
        test_cases = [
            # "one" in non-numeric contexts
            ("the one thing I need", "The one thing I need"),
            ("one of us should go", "One of us should go"),
            ("which one do you prefer", "Which one do you prefer"),
            ("one or the other", "One or the other"),
            
            # "two" in non-numeric contexts
            ("the two of us", "The two of us"),
            ("two can play that game", "Two can play that game"),
            ("between the two options", "Between the two options"),
            
            # Mixed contexts
            ("one test for each of those two issues", "One test for each of those two issues"),
            ("create one or two examples", "Create one or two examples"),
        ]
        
        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            # Allow for optional punctuation at the end
            assert result in [expected, expected + "."], \
                f"Input '{input_text}' should format to '{expected}', got '{result}'"

    def test_number_words_that_should_convert(self, preloaded_formatter):
        """Test that number words in numeric contexts ARE converted to digits."""
        format_transcription = preloaded_formatter
        test_cases = [
            # Clear numeric contexts
            ("add one plus one", "Add 1 + 1"),
            ("multiply two times three", "Multiply 2 × 3"),
            ("version one point two", "Version 1.2"),
            ("page one of ten", "Page 1 of 10"),
            
            # With units
            ("wait one second", "Wait 1s"),  # Time duration gets abbreviated
            ("two minutes remaining", "2min remaining"),  # Time duration gets abbreviated
            ("one dollar fifty", "$1 50"),  # Currency gets $ symbol
        ]
        
        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            # Allow for optional punctuation at the end
            assert result in [expected, expected + "."], \
                f"Input '{input_text}' should format to '{expected}', got '{result}'"


class TestFillerWordPreservation:
    """Test that certain filler words are preserved when contextually important."""

    def test_filler_words_in_quotes_or_examples(self, preloaded_formatter):
        """Test that filler words are preserved when they're part of quoted speech or examples."""
        format_transcription = preloaded_formatter
        test_cases = [
            # When discussing the words themselves
            ("words like actually should be preserved", "Words like actually should be preserved"),
            ("I say things like actually or like", "I say things like actually or like"),
            ("he literally said literally", "He literally said literally"),
            
            # In quoted contexts (once quote detection is implemented)
            # ("she said like three times", "She said like three times"),
            
            # When they're meaningful
            ("I actually finished it", "I actually finished it"),
            ("basically correct", "Basically correct"),
            ("literally true", "Literally true"),
            # Test comma cleanup after filler word removal
            ("actually, that's freaking awesome", "That's freaking awesome"),
            ("like, this is really cool", "This is really cool"),
            ("basically, we need this", "We need this"),
        ]
        
        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            # Allow for optional punctuation at the end
            assert result in [expected, expected + "."], \
                f"Input '{input_text}' should format to '{expected}', got '{result}'"

    def test_filler_words_that_should_be_removed(self, preloaded_formatter):
        """Test that filler words ARE removed in appropriate contexts."""
        format_transcription = preloaded_formatter
        test_cases = [
            # Clear filler usage
            ("like I was saying", "I was saying"),
            ("it was like really hot", "It was really hot"),
            ("you know what I mean", "What I mean"),
            ("basically we need to go", "We need to go"),
            
            # Multiple fillers
            ("so like basically I think", "So I think"),
            ("actually like you know", ""),
        ]
        
        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            # Allow for optional punctuation at the end
            if expected:  # Non-empty expected output
                assert result in [expected, expected + "."], \
                    f"Input '{input_text}' should format to '{expected}', got '{result}'"
            else:  # Empty expected output
                assert result == expected, \
                    f"Input '{input_text}' should format to empty string, got '{result}'"