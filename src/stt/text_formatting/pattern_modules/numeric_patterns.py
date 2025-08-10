#!/usr/bin/env python3
"""
Numeric-related regular expression patterns for text formatting.

This module serves as the main interface for all numeric patterns, importing from
specialized modules and maintaining backward compatibility with the existing API.

All patterns are organized into logical modules:
- basic_numeric_patterns: Basic numbers, ordinals, fractions, ranges
- financial_patterns: Currency and financial patterns
- temporal_patterns: Time and date patterns
- mathematical_patterns: Math expressions and constants
- technical_patterns: Phone numbers and technical identifiers
"""
from __future__ import annotations

# Standard library imports
import re
from typing import Pattern

# Local imports - common data structures
from ..common import NumberParser

# Local imports - specialized pattern modules
from .basic_numeric_patterns import (
    NUMBER_WORDS,
    build_ordinal_pattern,
    build_fraction_pattern,
    build_compound_fraction_pattern,
    build_numeric_range_pattern,
    build_consecutive_digits_pattern,
    get_ordinal_pattern,
    get_fraction_pattern,
    get_compound_fraction_pattern,
    get_numeric_range_pattern,
    get_consecutive_digits_pattern,
    get_number_words,
)
from .financial_patterns import (
    build_dollar_pattern,
    build_cents_pattern,
    get_dollar_pattern,
    get_cents_pattern,
)
from .mathematical_patterns import (
    MATH_OPERATORS,
    build_complex_math_expression_pattern,
    build_simple_math_expression_pattern,
    build_number_constant_pattern,
    get_complex_math_expression_pattern,
    get_simple_math_expression_pattern,
    get_number_constant_pattern,
    get_math_operators,
)
from .technical_patterns import (
    build_spoken_phone_pattern,
    get_spoken_phone_pattern,
)
from .temporal_patterns import (
    build_time_relative_pattern,
    build_time_am_pm_colon_pattern,
    build_time_am_pm_space_pattern,
    build_time_expression_patterns,
    get_time_relative_pattern,
    get_time_am_pm_colon_pattern,
    get_time_am_pm_space_pattern,
    get_time_expression_patterns,
)


# ==============================================================================
# GETTER FUNCTIONS
# ==============================================================================

# All getter functions are imported from their respective modules
# and re-exported here for backward compatibility

# Note: The getter functions are already imported above:
# get_ordinal_pattern, get_fraction_pattern, get_compound_fraction_pattern,
# get_numeric_range_pattern, get_complex_math_expression_pattern,
# get_simple_math_expression_pattern, get_number_constant_pattern,
# get_dollar_pattern, get_cents_pattern, get_spoken_phone_pattern,
# get_time_relative_pattern, get_time_am_pm_colon_pattern,
# get_time_am_pm_space_pattern, get_time_expression_patterns


# ==============================================================================
# DEFAULT PATTERNS (BACKWARD COMPATIBILITY)
# ==============================================================================

# Default English patterns for backward compatibility
SPOKEN_ORDINAL_PATTERN = build_ordinal_pattern("en")
SPOKEN_FRACTION_PATTERN = build_fraction_pattern("en")
SPOKEN_COMPOUND_FRACTION_PATTERN = build_compound_fraction_pattern("en")
SPOKEN_NUMERIC_RANGE_PATTERN = build_numeric_range_pattern("en")
NUMERIC_RANGE_PATTERN = SPOKEN_NUMERIC_RANGE_PATTERN  # Alias for backward compatibility
CONSECUTIVE_DIGITS_PATTERN = build_consecutive_digits_pattern("en")
COMPLEX_MATH_EXPRESSION_PATTERN = build_complex_math_expression_pattern("en")
SIMPLE_MATH_EXPRESSION_PATTERN = build_simple_math_expression_pattern("en")
NUMBER_CONSTANT_PATTERN = build_number_constant_pattern("en")
DOLLAR_PATTERN = build_dollar_pattern("en")
CENTS_PATTERN = build_cents_pattern("en")
SPOKEN_PHONE_PATTERN = build_spoken_phone_pattern("en")
SPOKEN_TIME_RELATIVE_PATTERN = build_time_relative_pattern("en")
TIME_AM_PM_COLON_PATTERN = build_time_am_pm_colon_pattern("en")
TIME_AM_PM_SPACE_PATTERN = build_time_am_pm_space_pattern("en")
TIME_EXPRESSION_PATTERNS = build_time_expression_patterns("en")

# Number word sequence helpers for backward compatibility
_number_parser_instance = NumberParser("en")
_number_words_pattern = "(?:" + "|".join(_number_parser_instance.all_number_words) + ")"
NUMBER_WORD_SEQUENCE = f"{_number_words_pattern}(?:\\s+{_number_words_pattern})*"


# ==============================================================================
# UTILITY FUNCTIONS
# ==============================================================================


def get_compiled_numeric_pattern(pattern_name: str) -> Pattern | None:
    """Get a pre-compiled numeric pattern by name."""
    pattern_map = {
        "ordinal": SPOKEN_ORDINAL_PATTERN,
        "fraction": SPOKEN_FRACTION_PATTERN,
        "compound_fraction": SPOKEN_COMPOUND_FRACTION_PATTERN,
        "numeric_range": SPOKEN_NUMERIC_RANGE_PATTERN,
        "consecutive_digits": CONSECUTIVE_DIGITS_PATTERN,
        "complex_math": COMPLEX_MATH_EXPRESSION_PATTERN,
        "simple_math": SIMPLE_MATH_EXPRESSION_PATTERN,
        "number_constant": NUMBER_CONSTANT_PATTERN,
        "dollar": DOLLAR_PATTERN,
        "cents": CENTS_PATTERN,
        "spoken_phone": SPOKEN_PHONE_PATTERN,
        "time_relative": SPOKEN_TIME_RELATIVE_PATTERN,
        "time_am_pm_colon": TIME_AM_PM_COLON_PATTERN,
        "time_am_pm_space": TIME_AM_PM_SPACE_PATTERN,
    }
    return pattern_map.get(pattern_name)


# Utility functions are imported from their respective modules
# get_number_words is imported from basic_numeric_patterns
# get_math_operators is imported from mathematical_patterns


def get_number_word_sequence() -> str:
    """Get the number word sequence pattern string."""
    return NUMBER_WORD_SEQUENCE


def create_number_parser_instance(language: str = "en") -> NumberParser:
    """Create a NumberParser instance for the specified language."""
    return NumberParser(language)