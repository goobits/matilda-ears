#!/usr/bin/env python3
"""
Base PatternConverter class that combines all converter mixins.

This module provides the unified PatternConverter class by combining:
- WebConverterMixin: URL, email, and web-related conversions
- CodeConverterMixin: Programming keywords, filenames, operators
- NumericConverterMixin: Math, currency, measurements, etc.
"""

import re
from typing import Optional

from ..common import Entity, EntityType, NumberParser
from ..constants import get_resources
from ...core.config import get_config, setup_logging
from .. import regex_patterns
from .web import WebConverterMixin
from .code import CodeConverterMixin
from .numeric import NumericConverterMixin

logger = setup_logging(__name__, log_filename="text_formatting.txt")


class PatternConverter(WebConverterMixin, CodeConverterMixin, NumericConverterMixin):
    """Unified pattern converter handling all entity type conversions.

    Combines web, code, and numeric conversion capabilities through mixins.
    """

    def __init__(self, number_parser: NumberParser, language: str = "en"):
        self.number_parser = number_parser
        self.language = language
        self.config = get_config()

        # Load language-specific resources
        self.resources = get_resources(language)

        # Get URL keywords for web conversions
        self.url_keywords = self.resources["spoken_keywords"]["url"]

        # Operator mappings for numeric conversions - loaded from resources
        self.operators = {}
        operators_resource = self.resources.get("spoken_keywords", {}).get("operators", {})
        code_resource = self.resources.get("spoken_keywords", {}).get("code", {})

        # Merge operators from both sources
        for k, v in operators_resource.items():
            self.operators[k.lower()] = v
        for k, v in code_resource.items():
            self.operators[k.lower()] = v

        # Ensure mathematical operators are present if not in resources
        default_operators = {
            "plus": "+",
            "minus": "-",
            "times": "×",
            "divided by": "÷",
            "over": "/",
            "equals": "=",
        }
        for k, v in default_operators.items():
            if k not in self.operators:
                self.operators[k] = v

        # Comprehensive converter mapping
        self.converters = {
            # Web converters
            EntityType.SPOKEN_PROTOCOL_URL: self.convert_spoken_protocol_url,
            EntityType.SPOKEN_URL: self.convert_spoken_url,
            EntityType.SPOKEN_EMAIL: self.convert_spoken_email,
            EntityType.PORT_NUMBER: self.convert_port_number,
            EntityType.URL: self.convert_url,
            EntityType.EMAIL: self.convert_email,

            # Code converters
            EntityType.CLI_COMMAND: self.convert_cli_command,
            EntityType.PROGRAMMING_KEYWORD: self.convert_programming_keyword,
            EntityType.FILENAME: self.convert_filename,
            EntityType.INCREMENT_OPERATOR: self.convert_increment_operator,
            EntityType.DECREMENT_OPERATOR: self.convert_decrement_operator,
            EntityType.COMPARISON: self.convert_comparison,
            EntityType.ABBREVIATION: self.convert_abbreviation,
            EntityType.ASSIGNMENT: self.convert_assignment,
            EntityType.COMMAND_FLAG: self.convert_command_flag,
            EntityType.SLASH_COMMAND: self.convert_slash_command,
            EntityType.UNDERSCORE_DELIMITER: self.convert_underscore_delimiter,
            EntityType.SIMPLE_UNDERSCORE_VARIABLE: self.convert_simple_underscore_variable,

            # Numeric converters
            EntityType.MATH_EXPRESSION: self.convert_math_expression,
            EntityType.CURRENCY: self.convert_currency,
            EntityType.MONEY: self.convert_currency,  # SpaCy detected money entity
            EntityType.DOLLAR_CENTS: self.convert_dollar_cents,
            EntityType.PERCENT: self.convert_percent,
            EntityType.DATA_SIZE: self.convert_data_size,
            EntityType.FREQUENCY: self.convert_frequency,
            EntityType.TIME_DURATION: self.convert_time_duration,
            EntityType.TIME: self.convert_time_or_duration,  # SpaCy detected TIME entity
            EntityType.TIME_CONTEXT: self.convert_time,
            EntityType.TIME_AMPM: self.convert_time,
            EntityType.PHONE_LONG: self.convert_phone_long,
            EntityType.CARDINAL: self.convert_cardinal,
            EntityType.ORDINAL: self.convert_ordinal,
            EntityType.TIME_RELATIVE: self.convert_time_relative,
            EntityType.FRACTION: self.convert_fraction,
            EntityType.NUMERIC_RANGE: self.convert_numeric_range,
            EntityType.VERSION: self.convert_version,
            EntityType.QUANTITY: self.convert_measurement,
            EntityType.TEMPERATURE: self.convert_temperature,
            EntityType.METRIC_LENGTH: self.convert_metric_unit,
            EntityType.METRIC_WEIGHT: self.convert_metric_unit,
            EntityType.METRIC_VOLUME: self.convert_metric_unit,
            EntityType.ROOT_EXPRESSION: self.convert_root_expression,
            EntityType.MATH_CONSTANT: self.convert_math_constant,
            EntityType.SCIENTIFIC_NOTATION: self.convert_scientific_notation,
            EntityType.MUSIC_NOTATION: self.convert_music_notation,
            EntityType.SPOKEN_EMOJI: self.convert_spoken_emoji,
        }
