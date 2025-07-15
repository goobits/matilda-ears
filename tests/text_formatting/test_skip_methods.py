#!/usr/bin/env python3
"""Unit tests for the data-driven _should_skip_* methods in TextFormatter."""

import pytest
from src.text_formatting.formatter import TextFormatter


class MockSpacyEntity:
    """Mock SpaCy entity for testing."""
    def __init__(self, text: str, start: int, end: int, label: str):
        self.text = text
        self.start_char = start
        self.end_char = end
        self.label_ = label


@pytest.fixture
def entity_detector():
    """Create an EntityDetector instance for testing."""
    formatter = TextFormatter(language="en")
    return formatter.entity_detector


@pytest.fixture
def formatter():
    """Create a TextFormatter instance for testing resources."""
    return TextFormatter(language="en")


class TestSkipMoney:
    """Test cases for _should_skip_money method."""

    def test_skip_money_as_weight_with_weight_context(self, entity_detector):
        """Test that MONEY entities with weight context are skipped."""
        text = "the package weighs ten pounds"
        mock_ent = MockSpacyEntity("ten pounds", 20, 30, "MONEY")
        assert entity_detector._should_skip_money(mock_ent, text) is True

    def test_keep_money_as_currency_with_currency_context(self, entity_detector):
        """Test that MONEY entities with currency context are kept."""
        text = "the ticket costs ten pounds"
        mock_ent = MockSpacyEntity("ten pounds", 17, 27, "MONEY")
        assert entity_detector._should_skip_money(mock_ent, text) is False

    def test_skip_money_with_measurement_verb(self, entity_detector):
        """Test that MONEY entities with measurement verbs are skipped."""
        text = "the box is ten pounds"
        mock_ent = MockSpacyEntity("ten pounds", 11, 21, "MONEY")
        assert entity_detector._should_skip_money(mock_ent, text) is True

    def test_keep_money_without_pounds(self, entity_detector):
        """Test that MONEY entities without 'pounds' are kept."""
        text = "it costs ten dollars"
        mock_ent = MockSpacyEntity("ten dollars", 9, 20, "MONEY")
        assert entity_detector._should_skip_money(mock_ent, text) is False

    def test_skip_non_money_entity(self, entity_detector):
        """Test that non-MONEY entities are not affected."""
        text = "the weight is significant"
        mock_ent = MockSpacyEntity("significant", 14, 25, "ORG")
        assert entity_detector._should_skip_money(mock_ent, text) is False


class TestSkipDate:
    """Test cases for _should_skip_date method."""

    def test_keep_date_with_month_name(self, entity_detector):
        """Test that DATE entities with month names are kept."""
        text = "meet me on january fifth"
        mock_ent = MockSpacyEntity("january fifth", 11, 24, "DATE")
        assert entity_detector._should_skip_date(mock_ent, text) is False

    def test_keep_date_with_relative_day(self, entity_detector):
        """Test that DATE entities with relative days are kept."""
        text = "see you tomorrow"
        mock_ent = MockSpacyEntity("tomorrow", 8, 16, "DATE")
        assert entity_detector._should_skip_date(mock_ent, text) is False

    def test_skip_date_as_ordinal_without_date_context(self, entity_detector):
        """Test that ordinal phrases without date context are skipped."""
        text = "this is the fourth time"
        mock_ent = MockSpacyEntity("the fourth", 8, 18, "DATE")
        assert entity_detector._should_skip_date(mock_ent, text) is True

    def test_skip_date_as_short_ordinal_phrase(self, entity_detector):
        """Test that short ordinal phrases are skipped."""
        text = "on the third day"
        mock_ent = MockSpacyEntity("the third day", 3, 16, "DATE")
        assert entity_detector._should_skip_date(mock_ent, text) is True

    def test_skip_non_date_entity(self, entity_detector):
        """Test that non-DATE entities are not affected."""
        text = "the fourth company"
        mock_ent = MockSpacyEntity("fourth company", 4, 18, "ORG")
        assert entity_detector._should_skip_date(mock_ent, text) is False


class TestSkipQuantity:
    """Test cases for _should_skip_quantity method."""

    def test_skip_quantity_with_data_unit(self, entity_detector):
        """Test that QUANTITY entities with data units are skipped."""
        text = "download five megabytes"
        mock_ent = MockSpacyEntity("five megabytes", 9, 23, "QUANTITY")
        assert entity_detector._should_skip_quantity(mock_ent, text) is True

    def test_skip_quantity_with_gigabytes(self, entity_detector):
        """Test that QUANTITY entities with gigabytes are skipped."""
        text = "storage of ten gigabytes"
        mock_ent = MockSpacyEntity("ten gigabytes", 11, 24, "QUANTITY")
        assert entity_detector._should_skip_quantity(mock_ent, text) is True

    def test_keep_quantity_without_data_unit(self, entity_detector):
        """Test that QUANTITY entities without data units are kept."""
        text = "add five liters"
        mock_ent = MockSpacyEntity("five liters", 4, 15, "QUANTITY")
        assert entity_detector._should_skip_quantity(mock_ent, text) is False

    def test_skip_non_quantity_entity(self, entity_detector):
        """Test that non-QUANTITY entities are not affected."""
        text = "five megabytes of data"
        mock_ent = MockSpacyEntity("data", 18, 22, "ORG")
        assert entity_detector._should_skip_quantity(mock_ent, text) is False


class TestDataDrivenRules:
    """Test that the methods use data-driven rules from resources."""

    def test_currency_contexts_from_resources(self, formatter):
        """Test that currency contexts are loaded from resources."""
        currency_contexts = formatter.resources.get("context_words", {}).get("currency_contexts", [])
        assert "cost" in currency_contexts
        assert "price" in currency_contexts
        assert "pay" in currency_contexts

    def test_weight_contexts_from_resources(self, formatter):
        """Test that weight contexts are loaded from resources."""
        weight_contexts = formatter.resources.get("context_words", {}).get("weight_contexts", [])
        assert "weigh" in weight_contexts
        assert "weight" in weight_contexts
        assert "heavy" in weight_contexts

    def test_data_units_from_resources(self, formatter):
        """Test that data units are loaded from resources."""
        data_units = formatter.resources.get("data_units", {}).get("storage", [])
        assert "megabyte" in data_units or "megabytes" in data_units
        assert "gigabyte" in data_units or "gigabytes" in data_units

    def test_temporal_data_from_resources(self, formatter):
        """Test that temporal data is loaded from resources."""
        month_names = formatter.resources.get("temporal", {}).get("month_names", [])
        assert "january" in month_names
        assert "december" in month_names

        date_ordinals = formatter.resources.get("temporal", {}).get("date_ordinals", [])
        assert "first" in date_ordinals
        assert "second" in date_ordinals
