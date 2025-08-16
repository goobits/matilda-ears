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
        from stt.text_formatting.processors.financial_processor import FinancialProcessor
        
        # Test Spanish cultural formatting (comma for decimal, period for thousands)
        es_processor = MeasurementProcessor(language="es")
        result_es = es_processor._apply_cultural_formatting("12.5")
        assert result_es == "12,5", f"Spanish should use decimal comma: {result_es}"
        
        result_es_thousands = es_processor._apply_cultural_formatting("1,250.75")
        assert result_es_thousands == "1.250,75", f"Spanish should use period for thousands: {result_es_thousands}"
        
        # Test French cultural formatting (comma for decimal, space for thousands)
        fr_processor = MeasurementProcessor(language="fr")
        result_fr = fr_processor._apply_cultural_formatting("12.5")
        assert result_fr == "12,5", f"French should use decimal comma: {result_fr}"
        
        result_fr_thousands = fr_processor._apply_cultural_formatting("1,250.75")
        assert result_fr_thousands == "1 250,75", f"French should use space for thousands: {result_fr_thousands}"
        
        # Test English cultural formatting (regression - no change)
        en_processor = MeasurementProcessor(language="en")
        result_en = en_processor._apply_cultural_formatting("12.5")
        assert result_en == "12.5", f"English should use decimal point: {result_en}"
        
        result_en_thousands = en_processor._apply_cultural_formatting("1,250.75")
        assert result_en_thousands == "1,250.75", f"English should remain unchanged: {result_en_thousands}"
        
        # Test that FinancialProcessor also has cultural formatting
        es_financial = FinancialProcessor(language="es")
        result_es_financial = es_financial._apply_cultural_formatting("25.50")
        assert result_es_financial == "25,50", f"Spanish financial formatting should use comma: {result_es_financial}"

    def test_language_variant_cultural_formatting_method(self):
        """Test that language variants get correct cultural formatting using base language."""
        from stt.text_formatting.processors.measurement_processor import MeasurementProcessor
        
        # Test Spanish variant (es-MX should use Spanish formatting via resource fallback)
        es_mx_processor = MeasurementProcessor(language="es-MX")  
        assert es_mx_processor.language == "es-MX", "Processor should store original language"
        result = es_mx_processor._apply_cultural_formatting("12.5")
        # Since es-MX falls back to 'es' resources, it should use Spanish formatting
        assert result == "12,5", "es-MX should use Spanish formatting via resource fallback"
        
        # Test French variant (fr-CA should use French formatting via resource fallback)
        fr_ca_processor = MeasurementProcessor(language="fr-CA")
        result = fr_ca_processor._apply_cultural_formatting("12.5") 
        assert result == "12,5", "fr-CA should use French formatting via resource fallback"
        
        # Test Spanish variant with thousands separator
        result_thousands = es_mx_processor._apply_cultural_formatting("1,250.75")
        assert result_thousands == "1.250,75", "es-MX should use Spanish thousands formatting"

    def test_regional_defaults_integration(self):
        """Test that Phase 1 regional defaults work with language variants."""
        from stt.text_formatting.constants import get_regional_defaults
        
        # Test Spanish variants use celsius (from Phase 1)
        assert get_regional_defaults("es-MX")["temperature"] == "celsius"
        assert get_regional_defaults("es-ES")["temperature"] == "celsius"
        
        # Test French variants use celsius (from Phase 1)  
        assert get_regional_defaults("fr-CA")["temperature"] == "celsius"
        assert get_regional_defaults("fr-FR")["temperature"] == "celsius"

    def test_end_to_end_cultural_formatting(self):
        """Test end-to-end cultural formatting across different processors and entity types."""
        from stt.text_formatting.common import Entity, EntityType
        from stt.text_formatting.processors.measurement_processor import MeasurementProcessor
        from stt.text_formatting.processors.financial_processor import FinancialProcessor
        
        # Test Spanish temperature formatting (decimal comma)
        es_processor = MeasurementProcessor(language="es")
        temp_entity = Entity(
            start=0, end=10, text="25.5°C", type=EntityType.TEMPERATURE,
            metadata={"sign": None, "number": "25.5", "unit": "celsius"}
        )
        result = es_processor.convert_temperature(temp_entity)
        assert "25,5°C" in result, f"Spanish temperature should use decimal comma: {result}"
        
        # Test Spanish currency formatting (decimal comma)
        es_financial = FinancialProcessor(language="es")
        dollar_cents_entity = Entity(
            start=0, end=20, text="25 dollars 50 cents", type=EntityType.DOLLAR_CENTS,
            metadata={"dollars": "25", "cents": "50"}
        )
        result = es_financial.convert_dollar_cents(dollar_cents_entity)
        assert result == "$25,50", f"Spanish currency should use decimal comma: {result}"
        
        # Test French measurement formatting (decimal comma, space thousands)
        fr_processor = MeasurementProcessor(language="fr")
        metric_entity = Entity(
            start=0, end=15, text="12.5 kilometers", type=EntityType.QUANTITY,
            metadata={"number": "12.5", "unit": "kilometers", "is_metric": True}
        )
        result = fr_processor.convert_metric_unit(metric_entity)
        assert result == "12,5 km", f"French metric should use decimal comma: {result}"
        
        # Test English unchanged (regression test)
        en_processor = MeasurementProcessor(language="en")
        temp_entity_en = Entity(
            start=0, end=10, text="25.5°C", type=EntityType.TEMPERATURE,
            metadata={"sign": None, "number": "25.5", "unit": "celsius"}
        )
        result = en_processor.convert_temperature(temp_entity_en)
        assert "25.5°C" in result, f"English temperature should remain unchanged: {result}"

    def test_comprehensive_processor_coverage(self):
        """Test that cultural formatting is applied consistently across all relevant processors."""
        from stt.text_formatting.processors.measurement_processor import MeasurementProcessor
        from stt.text_formatting.processors.financial_processor import FinancialProcessor
        from stt.text_formatting.processors.basic_numeric_processor import BasicNumericProcessor
        
        # Verify all numeric processors have cultural formatting method
        processors = [
            MeasurementProcessor(language="es"),
            FinancialProcessor(language="es"),
            BasicNumericProcessor(language="es")
        ]
        
        for processor in processors:
            assert hasattr(processor, '_apply_cultural_formatting'), \
                f"{processor.__class__.__name__} should have cultural formatting method"
            
            # Test method works correctly
            result = processor._apply_cultural_formatting("12.5")
            assert result == "12,5", \
                f"{processor.__class__.__name__} should format Spanish decimals with comma"

    def test_implementation_completeness(self):
        """Validate that all components of the comprehensive cultural formatting are implemented."""
        from stt.text_formatting.constants import get_regional_defaults, get_resources
        from stt.text_formatting.processors.measurement_processor import MeasurementProcessor
        
        # Phase 1: Regional defaults and variant support
        assert get_regional_defaults("es")["temperature"] == "celsius"
        assert get_regional_defaults("fr")["temperature"] == "celsius"
        assert get_regional_defaults("es-MX")["temperature"] == "celsius"
        assert get_regional_defaults("fr-CA")["temperature"] == "celsius"
        
        # Phase 2: Cultural formatting resources exist
        es_resources = get_resources("es")
        fr_resources = get_resources("fr")
        
        assert "cultural_formatting" in es_resources, "Spanish resources should have cultural_formatting section"
        assert "cultural_formatting" in fr_resources, "French resources should have cultural_formatting section"
        
        assert es_resources["cultural_formatting"]["decimal_separator"] == ","
        assert es_resources["cultural_formatting"]["thousands_separator"] == "."
        assert fr_resources["cultural_formatting"]["decimal_separator"] == ","
        assert fr_resources["cultural_formatting"]["thousands_separator"] == " "
        
        # Phase 3: Cultural formatting method exists in BaseNumericProcessor
        processor = MeasurementProcessor(language="es")
        assert hasattr(processor, '_apply_cultural_formatting'), "Cultural formatting method should exist"
        
        # Phase 4: Cultural formatting works correctly across numeric types
        assert processor._apply_cultural_formatting("12.5") == "12,5", "Spanish decimal comma formatting"

    def test_multilingual_temperature_units_available(self):
        """Test that multilingual temperature units are properly loaded in JSON resources."""
        from stt.text_formatting.processors.measurement_processor import MeasurementProcessor
        
        # Test Spanish temperature units include 'grados'
        es_processor = MeasurementProcessor(language="es")
        es_temp_units = es_processor.resources.get("units", {}).get("temperature_units", [])
        assert "grados" in es_temp_units, "Spanish should include 'grados' in temperature_units"
        assert "celsius" in es_temp_units, "Spanish should include 'celsius' in temperature_units"
        
        # Test French temperature units include 'degrés'
        fr_processor = MeasurementProcessor(language="fr")
        fr_temp_units = fr_processor.resources.get("units", {}).get("temperature_units", [])
        assert "degrés" in fr_temp_units, "French should include 'degrés' in temperature_units"
        assert "celsius" in fr_temp_units, "French should include 'celsius' in temperature_units"
        
        # Test English still works (no 'grados')
        en_processor = MeasurementProcessor(language="en")
        en_temp_units = en_processor.resources.get("units", {}).get("temperature_units", [])
        assert "celsius" in en_temp_units, "English should include 'celsius' in temperature_units"
        assert "grados" not in en_temp_units, "English should not include 'grados'"

    def test_json_driven_temperature_patterns(self):
        """Test that temperature patterns are now JSON-driven instead of hard-coded."""
        from stt.text_formatting.processors.measurement_processor import MeasurementProcessor
        
        # Test that Spanish patterns include Spanish units
        es_processor = MeasurementProcessor(language="es")
        pattern = es_processor._build_temperature_pattern_with_units()
        pattern_str = pattern.pattern
        
        # Should include Spanish units from JSON
        assert "grados" in pattern_str, "Spanish temperature pattern should include 'grados'"
        assert "celsius" in pattern_str, "Spanish temperature pattern should include 'celsius'"
        
        # Test that pattern can match Spanish input
        import re
        match = pattern.search("veinticinco grados celsius")
        assert match is not None, "Spanish pattern should match 'veinticinco grados celsius'"
        
        match_number_only = pattern.search("25 grados celsius") 
        assert match_number_only is not None, "Spanish pattern should match '25 grados celsius'"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
