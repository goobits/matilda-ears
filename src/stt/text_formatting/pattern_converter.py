#!/usr/bin/env python3
"""
Unified Pattern Converter for Matilda transcriptions.

This class consolidates all entity conversion logic from WebPatternConverter,
CodePatternConverter, and NumericalPatternConverter into a single unified
converter for better maintainability and performance.
"""
from __future__ import annotations

# Standard library imports
import re

# Local imports - core/config
from stt.core.config import get_config, setup_logging

# Local imports - common data structures
from stt.text_formatting.common import Entity, EntityType, NumberParser

# Local imports - utilities and resources
# Note: regex_patterns import removed - now using pattern_modules directly in converters
from .constants import get_resources

# Local imports - specialized converters and processors
from .converters import TextPatternConverter, WebPatternConverter, CodePatternConverter, NumericPatternConverter
from .processors.measurement_processor import MeasurementProcessor
from .processors.mathematical_processor import MathematicalProcessor
from .processors.temporal_processor import TemporalProcessor

logger = setup_logging(__name__)


class PatternConverter:
    """Unified pattern converter handling all entity type conversions."""

    def __init__(self, number_parser: NumberParser, language: str = "en"):
        self.number_parser = number_parser
        self.language = language
        self.config = get_config()

        # Load language-specific resources
        self.resources = get_resources(language)
        
        # Initialize sub-converters
        self.text_converter = TextPatternConverter(number_parser, language)
        self.web_converter = WebPatternConverter(number_parser, language)
        self.code_converter = CodePatternConverter(number_parser, language)
        self.measurement_processor = MeasurementProcessor(nlp=None, language=language)
        self.mathematical_processor = MathematicalProcessor(nlp=None, language=language)
        self.temporal_processor = TemporalProcessor(nlp=None, language=language)
        self.numeric_converter = NumericPatternConverter(number_parser, language)

        # Get URL keywords for web conversions
        self.url_keywords = self.resources["spoken_keywords"]["url"]

        # Pre-compute entity types that need full text context for performance
        self._full_text_entity_types = frozenset([
            EntityType.CURRENCY, EntityType.CARDINAL, EntityType.ORDINAL, EntityType.QUANTITY
        ])

        # Comprehensive converter mapping
        self.converters = {
            # Web converters
            EntityType.SPOKEN_PROTOCOL_URL: self.web_converter.convert_spoken_protocol_url,
            EntityType.SPOKEN_URL: self.web_converter.convert_spoken_url,
            EntityType.SPOKEN_EMAIL: self.web_converter.convert_spoken_email,
            EntityType.PORT_NUMBER: self.web_converter.convert_port_number,
            EntityType.URL: self.web_converter.convert_url,
            EntityType.EMAIL: self.web_converter.convert_email,
            # Code converters
            EntityType.CLI_COMMAND: self.code_converter.convert_cli_command,
            EntityType.PROGRAMMING_KEYWORD: self.code_converter.convert_programming_keyword,
            EntityType.FILENAME: self.code_converter.convert_filename,
            EntityType.INCREMENT_OPERATOR: self.code_converter.convert_increment_operator,
            EntityType.DECREMENT_OPERATOR: self.code_converter.convert_decrement_operator,
            EntityType.COMPARISON: self.code_converter.convert_comparison,
            EntityType.ABBREVIATION: self.code_converter.convert_abbreviation,
            EntityType.ASSIGNMENT: self.code_converter.convert_assignment,
            EntityType.COMMAND_FLAG: self.code_converter.convert_command_flag,
            EntityType.SLASH_COMMAND: self.code_converter.convert_slash_command,
            EntityType.UNDERSCORE_DELIMITER: self.code_converter.convert_underscore_delimiter,
            EntityType.SIMPLE_UNDERSCORE_VARIABLE: self.code_converter.convert_simple_underscore_variable,
            # Numeric converters - using generic convert method that delegates to specialized converters
            EntityType.MATH_EXPRESSION: lambda entity, full_text="": self.mathematical_processor.convert_entity(entity, full_text),
            EntityType.CURRENCY: self.numeric_converter.convert,
            EntityType.MONEY: self.numeric_converter.convert,  # SpaCy detected money entity
            EntityType.DOLLAR_CENTS: self.numeric_converter.convert,
            EntityType.EURO_CENTS: self.numeric_converter.convert,
            EntityType.POUND_PENCE: self.numeric_converter.convert,
            EntityType.CENTS: self.numeric_converter.convert,
            EntityType.PERCENT: lambda entity, full_text="": self.measurement_processor.convert_entity(entity, full_text),
            EntityType.DATA_SIZE: lambda entity, full_text="": self.measurement_processor.convert_entity(entity, full_text),
            EntityType.FREQUENCY: lambda entity, full_text="": self.measurement_processor.convert_entity(entity, full_text),
            EntityType.TIME_DURATION: lambda entity, full_text="": self.measurement_processor.convert_entity(entity, full_text),
            EntityType.TIME: lambda entity, full_text="": self.temporal_processor.convert_time_or_duration(entity),  # SpaCy detected TIME entity
            EntityType.TIME_CONTEXT: self.numeric_converter.convert,
            EntityType.TIME_AMPM: self.numeric_converter.convert,
            EntityType.DATE: lambda entity, full_text="": self.temporal_processor.convert_date(entity),
            EntityType.PHONE_LONG: self.numeric_converter.convert,
            EntityType.CARDINAL: self.numeric_converter.convert,
            EntityType.ORDINAL: self.numeric_converter.convert,
            EntityType.TIME_RELATIVE: self.numeric_converter.convert,
            EntityType.FRACTION: self.numeric_converter.convert,
            EntityType.NUMERIC_RANGE: self.numeric_converter.convert,
            EntityType.VERSION: self.numeric_converter.convert,
            EntityType.QUANTITY: lambda entity, full_text="": self.measurement_processor.convert_entity(entity, full_text),
            EntityType.TEMPERATURE: lambda entity, full_text="": self.measurement_processor.convert_entity(entity, full_text),
            EntityType.METRIC_LENGTH: lambda entity, full_text="": self.measurement_processor.convert_entity(entity, full_text),
            EntityType.METRIC_WEIGHT: lambda entity, full_text="": self.measurement_processor.convert_entity(entity, full_text),
            EntityType.METRIC_VOLUME: lambda entity, full_text="": self.measurement_processor.convert_entity(entity, full_text),
            EntityType.ROOT_EXPRESSION: lambda entity, full_text="": self.mathematical_processor.convert_entity(entity, full_text),
            EntityType.MATH_CONSTANT: lambda entity, full_text="": self.mathematical_processor.convert_entity(entity, full_text),
            EntityType.SCIENTIFIC_NOTATION: lambda entity, full_text="": self.mathematical_processor.convert_entity(entity, full_text),
            EntityType.MUSIC_NOTATION: self.text_converter.convert_music_notation,
            EntityType.SPOKEN_EMOJI: self.text_converter.convert_spoken_emoji,
            # Spoken letter converters
            EntityType.SPOKEN_LETTER: self.text_converter.convert_spoken_letter,
            EntityType.LETTER_SEQUENCE: self.text_converter.convert_letter_sequence,
        }

    def convert(self, entity: Entity, full_text: str = "") -> str:
        """Convert an entity using the appropriate converter."""
        try:
            converter = self.converters.get(entity.type)
            if converter:
                # Some converters need the full text for context - use pre-computed set
                if entity.type in self._full_text_entity_types:
                    return converter(entity, full_text)
                else:
                    return converter(entity)
            else:
                logger.debug(f"No converter found for entity type: {entity.type}")
                return entity.text
        except Exception as e:
            logger.error(f"Error converting entity {entity.type}: {e}")
            return entity.text

    def get_pattern_regex(self, entity_type: EntityType) -> str:
        """Get the regex pattern for a given entity type."""
        # This method is deprecated - patterns are now accessed directly through pattern_modules
        logger.warning(f"get_pattern_regex is deprecated for entity type: {entity_type}")
        return ""

    def get_entity_types(self) -> list[EntityType]:
        """Get all supported entity types."""
        return list(self.converters.keys())

    def has_converter(self, entity_type: EntityType) -> bool:
        """Check if a converter exists for the given entity type."""
        return entity_type in self.converters