#!/usr/bin/env python3
"""
Unified Pattern Converter for Matilda transcriptions.

This class consolidates all entity conversion logic from WebPatternConverter,
CodePatternConverter, and NumericalPatternConverter into a single unified
converter for better maintainability and performance.
"""
from __future__ import annotations

import re

from stt.core.config import get_config, setup_logging

from . import regex_patterns
from .common import Entity, EntityType, NumberParser
from .constants import get_resources
from .converters import TextPatternConverter, WebPatternConverter, CodePatternConverter, MeasurementPatternConverter, NumericPatternConverter

logger = setup_logging(__name__, log_filename="text_formatting.txt", include_console=False)


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
        self.measurement_converter = MeasurementPatternConverter(number_parser, language)
        self.numeric_converter = NumericPatternConverter(number_parser, language)

        # Get URL keywords for web conversions
        self.url_keywords = self.resources["spoken_keywords"]["url"]

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
            EntityType.MATH_EXPRESSION: self.numeric_converter.convert,
            EntityType.CURRENCY: self.numeric_converter.convert,
            EntityType.MONEY: self.numeric_converter.convert,  # SpaCy detected money entity
            EntityType.DOLLAR_CENTS: self.numeric_converter.convert,
            EntityType.CENTS: self.numeric_converter.convert,
            EntityType.PERCENT: self.numeric_converter.convert,
            EntityType.DATA_SIZE: self.numeric_converter.convert,
            EntityType.FREQUENCY: self.numeric_converter.convert,
            EntityType.TIME_DURATION: self.numeric_converter.convert,
            EntityType.TIME: self.numeric_converter.convert,  # SpaCy detected TIME entity
            EntityType.TIME_CONTEXT: self.numeric_converter.convert,
            EntityType.TIME_AMPM: self.numeric_converter.convert,
            EntityType.PHONE_LONG: self.numeric_converter.convert,
            EntityType.CARDINAL: self.numeric_converter.convert,
            EntityType.ORDINAL: self.numeric_converter.convert,
            EntityType.TIME_RELATIVE: self.numeric_converter.convert,
            EntityType.FRACTION: self.numeric_converter.convert,
            EntityType.NUMERIC_RANGE: self.numeric_converter.convert,
            EntityType.VERSION: self.numeric_converter.convert,
            EntityType.QUANTITY: self.measurement_converter.convert_measurement,
            EntityType.TEMPERATURE: self.measurement_converter.convert_temperature,
            EntityType.METRIC_LENGTH: self.measurement_converter.convert_metric_unit,
            EntityType.METRIC_WEIGHT: self.measurement_converter.convert_metric_unit,
            EntityType.METRIC_VOLUME: self.measurement_converter.convert_metric_unit,
            EntityType.ROOT_EXPRESSION: self.numeric_converter.convert,
            EntityType.MATH_CONSTANT: self.numeric_converter.convert,
            EntityType.SCIENTIFIC_NOTATION: self.numeric_converter.convert,
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
                # Some converters need the full text for context
                if entity.type in [EntityType.CURRENCY, EntityType.CARDINAL, EntityType.ORDINAL, EntityType.QUANTITY]:
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
        return getattr(regex_patterns, entity_type.value.upper(), "")

    def get_entity_types(self) -> list[EntityType]:
        """Get all supported entity types."""
        return list(self.converters.keys())

    def has_converter(self, entity_type: EntityType) -> bool:
        """Check if a converter exists for the given entity type."""
        return entity_type in self.converters