"""Basic numeric converters for cardinal, ordinal, fraction, and range entities."""

import re
from typing import Dict

from stt.text_formatting.common import Entity, EntityType
from .base import BaseNumericConverter


class BasicNumericConverter(BaseNumericConverter):
    """Converter for basic numeric entities like cardinal, ordinal, fraction, and range."""
    
    def __init__(self, number_parser, language: str = "en"):
        """Initialize basic numeric converter."""
        super().__init__(number_parser, language)
        
        # Define supported entity types and their converter methods
        self.supported_types: Dict[EntityType, str] = {
            EntityType.CARDINAL: "convert_cardinal",
            EntityType.ORDINAL: "convert_ordinal",
            EntityType.FRACTION: "convert_fraction",
            EntityType.NUMERIC_RANGE: "convert_numeric_range",
        }
        
    def convert(self, entity: Entity, full_text: str = "") -> str:
        """Convert a basic numeric entity to its final form."""
        converter_method = self.get_converter_method(entity.type)
        if converter_method and hasattr(self, converter_method):
            if converter_method in ["convert_cardinal", "convert_ordinal"]:
                # These methods need full_text parameter
                return getattr(self, converter_method)(entity, full_text)
            else:
                return getattr(self, converter_method)(entity)
        return entity.text

    def convert_cardinal(self, entity: Entity, full_text: str = "") -> str:
        """Convert cardinal numbers - only convert standalone clear numbers"""
        # Handle consecutive digits specially
        if entity.metadata and entity.metadata.get("consecutive_digits"):
            return entity.metadata.get("parsed_value", entity.text)

        # Don't convert numbers that are part of hyphenated compounds
        if self.is_hyphenated_compound(entity, full_text):
            return entity.text

        # Don't convert simple numbers in natural speech contexts
        if self.is_natural_speech_context(entity, full_text):
            return entity.text  # Keep as word
        
        # Use the more general parser
        parsed = self.number_parser.parse(entity.text)
        return parsed if parsed else entity.text

    def convert_ordinal(self, entity: Entity, full_text: str = "") -> str:
        """Convert ordinal numbers with context awareness (first -> 1st, but 1st -> first in conversational contexts)."""
        text_lower = entity.text.lower().replace("-", " ")
        original_text = entity.text

        # Check if input is already numeric (1st, 2nd, etc.)
        numeric_ordinal_pattern = re.compile(r"(\d+)(st|nd|rd|th)", re.IGNORECASE)
        numeric_match = numeric_ordinal_pattern.match(original_text)

        if numeric_match:
            # Input is already numeric - check context to see if we should convert to words
            if full_text:
                # Check for conversational patterns
                if self.is_conversational_context(entity, full_text):
                    # Convert numeric to word form
                    num_str = numeric_match.group(1)
                    num = int(num_str)

                    if num in self.ordinal_numeric_to_word:
                        return self.ordinal_numeric_to_word[num]

                # Check for positional patterns - keep numeric
                if self.is_positional_context(entity, full_text):
                    return original_text  # Keep numeric form

            # Default: keep numeric form if no clear context
            return original_text

        # Input is word form - check for idiomatic phrases first
        if full_text and text_lower in self.ordinal_word_to_numeric:
            # Check if this ordinal is part of an idiomatic phrase
            if self.is_idiomatic_context(entity, full_text, text_lower):
                return original_text  # Keep word form for idiomatic phrases
            
        # Input is word form - convert to numeric (existing behavior)
        # First, try a direct lookup in the comprehensive map
        if text_lower in self.ordinal_word_to_numeric:
            return self.ordinal_word_to_numeric[text_lower]

        # If not found, parse the number and apply the suffix rule
        parsed_num_str = self.number_parser.parse_ordinal(text_lower)
        if parsed_num_str:
            num = int(parsed_num_str)
            suffix = self.get_ordinal_suffix(num)
            return f"{parsed_num_str}{suffix}"

        return entity.text

    def convert_fraction(self, entity: Entity) -> str:
        """Convert fraction expressions (one half -> ½) and decimal numbers (three point one four -> 3.14)."""
        if not entity.metadata:
            return entity.text

        # Handle decimal numbers (e.g., "three point one four" -> "3.14")
        if entity.metadata.get("is_decimal"):
            return self.number_parser.parse(entity.text) or entity.text

        # Handle compound fractions (e.g., "one and one half" -> "1½")
        if entity.metadata.get("is_compound"):
            whole_word = entity.metadata.get("whole_word", "").lower()
            numerator_word = entity.metadata.get("numerator_word", "").lower()
            denominator_word = entity.metadata.get("denominator_word", "").lower()

            whole = self.number_word_mappings.get(whole_word)
            numerator = self.number_word_mappings.get(numerator_word)
            denominator = self.denominator_mappings.get(denominator_word)

            if whole and numerator and denominator:
                # Create the x/y format first
                fraction_str = f"{numerator}/{denominator}"
                # Map common fractions to Unicode equivalents
                unicode_fraction = self.unicode_fraction_mappings.get(fraction_str, f"{numerator}/{denominator}")
                return f"{whole}{unicode_fraction}"

        # Handle simple fractions
        numerator_word = entity.metadata.get("numerator_word", "").lower()
        denominator_word = entity.metadata.get("denominator_word", "").lower()

        numerator = self.number_word_mappings.get(numerator_word)
        denominator = self.denominator_mappings.get(denominator_word)

        if numerator and denominator:
            # Create the x/y format first
            fraction_str = f"{numerator}/{denominator}"
            # Return Unicode character if available, otherwise return x/y format
            return self.unicode_fraction_mappings.get(fraction_str, fraction_str)

        return entity.text

    def convert_numeric_range(self, entity: Entity) -> str:
        """Convert numeric range expressions (ten to twenty -> 10-20)."""
        if not entity.metadata:
            return entity.text

        start_word = entity.metadata.get("start_word", "")
        end_word = entity.metadata.get("end_word", "")
        unit = entity.metadata.get("unit")  # The detector now provides this

        start_num = self.number_parser.parse(start_word)
        end_num = self.number_parser.parse(end_word)

        if start_num and end_num:
            result = f"{start_num}-{end_num}"
            if unit:
                if "dollar" in unit:
                    return f"${result}"
                if "percent" in unit:
                    return f"{result}%"
                # Handle time units
                if unit in ["hour", "hours"]:
                    return f"{result}h"
                if unit in ["minute", "minutes"]:
                    return f"{result}min"
                if unit in ["second", "seconds"]:
                    return f"{result}s"
                # Handle weight units
                if unit in ["kilogram", "kilograms", "kg"]:
                    return f"{result} kg"
                if unit in ["gram", "grams", "g"]:
                    return f"{result} g"
                # Handle other units
                if unit:
                    return f"{result} {unit}"
            return result

        return entity.text