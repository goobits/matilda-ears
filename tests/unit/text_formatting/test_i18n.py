#!/usr/bin/env python3
"""Tests for internationalization (i18n) support in text formatting."""

import pytest

from stt.text_formatting.constants import get_resources


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


class TestCulturalNumberFormatting:
    """Test cultural number formatting implementation (within scope of 3-day enhancement)."""

    def test_cultural_formatting_method_direct(self):
        """Test the _apply_cultural_formatting method directly."""
        from stt.text_formatting.processors.measurement_processor import MeasurementProcessor
        
        # Test Spanish cultural formatting
        es_processor = MeasurementProcessor(language="es")
        result_es = es_processor._apply_cultural_formatting("12.5")
        assert result_es == "12,5", f"Spanish should use decimal comma: {result_es}"
        
        # Test French cultural formatting  
        fr_processor = MeasurementProcessor(language="fr")
        result_fr = fr_processor._apply_cultural_formatting("12.5")
        assert result_fr == "12,5", f"French should use decimal comma: {result_fr}"
        
        # Test English cultural formatting (regression)
        en_processor = MeasurementProcessor(language="en")
        result_en = en_processor._apply_cultural_formatting("12.5")
        assert result_en == "12.5", f"English should use decimal point: {result_en}"

    def test_language_variant_cultural_formatting_method(self):
        """Test that language variants get correct processor language."""
        from stt.text_formatting.processors.measurement_processor import MeasurementProcessor
        
        # Test Spanish variant (should resolve to 'es' internally)
        es_mx_processor = MeasurementProcessor(language="es-MX")  
        assert es_mx_processor.language == "es-MX", "Processor should store original language"
        result = es_mx_processor._apply_cultural_formatting("12.5")
        assert result == "12.5", "es-MX should fallback to English format (no es-MX in formats dict)"
        
        # Test French variant
        fr_ca_processor = MeasurementProcessor(language="fr-CA")
        result = fr_ca_processor._apply_cultural_formatting("12.5") 
        assert result == "12.5", "fr-CA should fallback to English format (no fr-CA in formats dict)"

    def test_regional_defaults_integration(self):
        """Test that Phase 1 regional defaults work with language variants."""
        from stt.text_formatting.constants import get_regional_defaults
        
        # Test Spanish variants use celsius (from Phase 1)
        assert get_regional_defaults("es-MX")["temperature"] == "celsius"
        assert get_regional_defaults("es-ES")["temperature"] == "celsius"
        
        # Test French variants use celsius (from Phase 1)  
        assert get_regional_defaults("fr-CA")["temperature"] == "celsius"
        assert get_regional_defaults("fr-FR")["temperature"] == "celsius"

    def test_implementation_completeness(self):
        """Validate that all components of the 3-day enhancement are implemented."""
        from stt.text_formatting.constants import get_regional_defaults
        from stt.text_formatting.processors.measurement_processor import MeasurementProcessor
        
        # Phase 1A & 1B: Regional defaults and variant support
        assert get_regional_defaults("es")["temperature"] == "celsius"
        assert get_regional_defaults("fr")["temperature"] == "celsius"
        assert get_regional_defaults("es-MX")["temperature"] == "celsius"
        assert get_regional_defaults("fr-CA")["temperature"] == "celsius"
        
        # Phase 2A: Cultural formatting method exists
        processor = MeasurementProcessor(language="es")
        assert hasattr(processor, '_apply_cultural_formatting'), "Cultural formatting method should exist"
        
        # Phase 2A: Cultural formatting works correctly
        assert processor._apply_cultural_formatting("12.5") == "12,5", "Spanish decimal comma formatting"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
