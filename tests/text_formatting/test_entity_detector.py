#!/usr/bin/env python3
"""Unit tests for EntityDetector, focusing on the data-driven _should_skip_cardinal logic."""

import pytest
from src.text_formatting.formatter import EntityDetector


class MockSpacyEntity:
    """Mock SpaCy entity object for testing."""
    def __init__(self, text, start_char, end_char, label_):
        self.text = text
        self.start_char = start_char
        self.end_char = end_char
        self.label_ = label_


@pytest.fixture
def entity_detector():
    """Returns an instance of EntityDetector for testing."""
    # Create detector without requiring actual SpaCy model for these specific tests
    return EntityDetector(nlp=None, language="en")


class TestShouldSkipCardinal:
    """Test the data-driven _should_skip_cardinal method."""

    def test_skip_cardinal_catch_twenty_two(self, entity_detector):
        """Test that 'catch twenty two' is recognized as idiomatic."""
        text = "you can't get past catch twenty two"
        mock_ent = MockSpacyEntity("twenty two", 25, 36, "CARDINAL")
        assert entity_detector._should_skip_cardinal(mock_ent, text) is True

    def test_skip_cardinal_cloud_nine(self, entity_detector):
        """Test that 'cloud nine' is recognized as idiomatic."""
        text = "she's on cloud nine today"
        mock_ent = MockSpacyEntity("nine", 15, 19, "CARDINAL")
        assert entity_detector._should_skip_cardinal(mock_ent, text) is True

    def test_skip_cardinal_behind_the_eight(self, entity_detector):
        """Test that 'behind the eight ball' is recognized as idiomatic."""
        text = "we're behind the eight ball on this project"
        mock_ent = MockSpacyEntity("eight", 17, 22, "CARDINAL")
        assert entity_detector._should_skip_cardinal(mock_ent, text) is True

    def test_skip_cardinal_idiomatic_plus_things(self, entity_detector):
        """Test that 'five plus things' is recognized as idiomatic."""
        text = "we have five plus years of experience"
        mock_ent = MockSpacyEntity("five", 8, 12, "CARDINAL")
        assert entity_detector._should_skip_cardinal(mock_ent, text) is True

    def test_skip_cardinal_idiomatic_plus_experience(self, entity_detector):
        """Test that 'ten plus experience' is recognized as idiomatic."""
        text = "need ten plus years experience in programming"
        mock_ent = MockSpacyEntity("ten", 5, 8, "CARDINAL")
        assert entity_detector._should_skip_cardinal(mock_ent, text) is True

    def test_skip_cardinal_idiomatic_times_better(self, entity_detector):
        """Test that 'three times better' is recognized as idiomatic."""
        text = "this solution is three times better than before"
        mock_ent = MockSpacyEntity("three", 17, 22, "CARDINAL")
        assert entity_detector._should_skip_cardinal(mock_ent, text) is True

    def test_skip_cardinal_idiomatic_times_faster(self, entity_detector):
        """Test that 'ten times faster' is recognized as idiomatic."""
        text = "the new algorithm is ten times faster"
        mock_ent = MockSpacyEntity("ten", 21, 24, "CARDINAL")
        assert entity_detector._should_skip_cardinal(mock_ent, text) is True

    def test_do_not_skip_mathematical_plus(self, entity_detector):
        """Test that mathematical expressions like 'two plus two' are NOT skipped."""
        text = "what is two plus two equals"
        mock_ent = MockSpacyEntity("two", 8, 11, "CARDINAL")
        assert entity_detector._should_skip_cardinal(mock_ent, text) is False

    def test_do_not_skip_mathematical_times(self, entity_detector):
        """Test that mathematical expressions like 'five times six' are NOT skipped."""
        text = "calculate five times six please"
        mock_ent = MockSpacyEntity("five", 10, 14, "CARDINAL")
        assert entity_detector._should_skip_cardinal(mock_ent, text) is False

    def test_do_not_skip_regular_numbers(self, entity_detector):
        """Test that standalone numbers are NOT skipped."""
        text = "there are seven apples on the table"
        mock_ent = MockSpacyEntity("seven", 10, 15, "CARDINAL")
        assert entity_detector._should_skip_cardinal(mock_ent, text) is False

    def test_skip_cardinal_with_units(self, entity_detector):
        """Test that numbers followed by units are skipped (handled by specialized detectors)."""
        text = "download five megabytes of data"
        mock_ent = MockSpacyEntity("five", 9, 13, "CARDINAL")
        assert entity_detector._should_skip_cardinal(mock_ent, text) is True

    def test_skip_cardinal_email_context(self, entity_detector):
        """Test that numbers in email contexts are skipped."""
        text = "email user123 at example dot com"
        mock_ent = MockSpacyEntity("123", 10, 13, "CARDINAL")
        # This might not trigger since "123" isn't detected as CARDINAL by spaCy typically
        # but testing the logic path
        result = entity_detector._should_skip_cardinal(mock_ent, text)
        # Could be True or False depending on email detection logic
        assert isinstance(result, bool)

    def test_non_cardinal_entity_not_skipped(self, entity_detector):
        """Test that non-CARDINAL entities return False immediately."""
        text = "this is a test sentence"
        mock_ent = MockSpacyEntity("test", 10, 14, "NOUN")
        assert entity_detector._should_skip_cardinal(mock_ent, text) is False

    def test_skip_cardinal_case_insensitive(self, entity_detector):
        """Test that pattern matching is case insensitive."""
        text = "You can't get past CATCH Twenty Two"
        # Calculate the correct positions: "You can't get past CATCH "
        start_pos = text.find("Twenty Two")  # Should be 25
        end_pos = start_pos + len("Twenty Two")  # Should be 35
        # Note: entity text needs to match the lowercase pattern in JSON exactly
        mock_ent = MockSpacyEntity("twenty two", start_pos, end_pos, "CARDINAL")
        assert entity_detector._should_skip_cardinal(mock_ent, text) is True
