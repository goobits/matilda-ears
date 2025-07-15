#!/usr/bin/env python3
"""Tests for internationalization (i18n) support in text formatting."""

import pytest
from src.text_formatting.constants import get_resources


class TestI18nResourceLoader:
    """Test the i18n resource loading system."""

    def test_load_english_resources(self):
        """Test loading English resources (default)."""
        resources = get_resources("en")

        # Test that key sections exist
        assert "spoken_keywords" in resources
        assert "abbreviations" in resources
        assert "top_level_domains" in resources

        # Test specific English keywords
        assert resources["spoken_keywords"]["url"]["dot"] == "."
        assert resources["spoken_keywords"]["url"]["at"] == "@"
        assert resources["abbreviations"]["ie"] == "i.e."
        assert "com" in resources["top_level_domains"]

    def test_load_spanish_resources(self):
        """Test loading Spanish resources."""
        resources = get_resources("es")

        # Test that key sections exist
        assert "spoken_keywords" in resources
        assert "abbreviations" in resources
        assert "top_level_domains" in resources

        # Test specific Spanish keywords
        assert resources["spoken_keywords"]["url"]["punto"] == "."
        assert resources["spoken_keywords"]["url"]["arroba"] == "@"
        assert resources["abbreviations"]["es decir"] == "es decir,"
        assert "es" in resources["top_level_domains"]

    def test_resource_caching(self):
        """Test that resources are cached after first load."""
        # Load English twice - should be cached
        resources1 = get_resources("en")
        resources2 = get_resources("en")

        # Should be the same object (cached)
        assert resources1 is resources2

    def test_invalid_language_fallback(self):
        """Test fallback to English for invalid language file."""
        # Should fallback to English without raising an error
        resources = get_resources("invalid_lang")

        # Should be the same as English resources
        en_resources = get_resources("en")
        assert resources == en_resources

    def test_spanish_url_keywords_proof_of_concept(self):
        """Proof of concept: Spanish URL keywords could be used."""
        # This demonstrates how Spanish resources could be used
        # In a full implementation, the formatter would accept a language parameter

        es_resources = get_resources("es")
        url_keywords = es_resources["spoken_keywords"]["url"]

        # Example: Spanish spoken URL conversion
        # Input: "visita ejemplo punto com"
        # Could be processed using: url_keywords['punto'] -> '.'

        assert url_keywords["punto"] == "."
        assert url_keywords["arroba"] == "@"
        assert url_keywords["barra"] == "/"

        # This proves the infrastructure is ready for multilingual support


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
