#!/usr/bin/env python3
"""
Centralized regular expression patterns for text formatting.

This module serves as the main entry point for all regex patterns used throughout
the text formatting system. Patterns are now organized into specialized modules
under the pattern_modules directory for better maintainability.

All patterns maintain backward compatibility through this central import point.
"""
from __future__ import annotations

import re
from typing import Pattern
# Import specific patterns and functions from specialized modules for backward compatibility
from .pattern_modules import (
    get_compiled_code_pattern,
    get_compiled_numeric_pattern,
    get_compiled_text_pattern,
    get_compiled_web_pattern,
    get_compiled_common_pattern,
    URL_PROTECTION_PATTERN,
    EMAIL_PROTECTION_PATTERN,
    WWW_DOMAIN_RESCUE,
    # Common patterns
    EMAIL_BASIC_PATTERN,
    PRONOUN_I_BASIC_PATTERN,
    ORDINAL_SUFFIX_PATTERN,
    ABBREVIATION_SPACING_PATTERN,
    # Pattern building functions
    get_spoken_url_pattern,
    get_slash_command_pattern,
    get_underscore_delimiter_pattern,
    get_simple_underscore_pattern,
    get_long_flag_pattern,
    get_short_flag_pattern,
    get_assignment_pattern,
    get_port_number_pattern,
    get_spoken_email_pattern,
    get_spoken_protocol_pattern,
    # Text pattern functions
    build_spoken_letter_pattern,
    build_letter_sequence_pattern,
    create_artifact_patterns,
    create_profanity_pattern,
)

# ==============================================================================
# PATTERN COMPILATION HELPERS
# ==============================================================================


def get_compiled_pattern(pattern_name: str) -> Pattern | None:
    """Get a pre-compiled pattern by name."""
    # Check common patterns first (most frequently used)
    from .pattern_modules.common_patterns import get_compiled_common_pattern
    common_pattern = get_compiled_common_pattern(pattern_name)
    if common_pattern is not None:
        return common_pattern
    
    # Check code patterns
    code_pattern = get_compiled_code_pattern(pattern_name)
    if code_pattern is not None:
        return code_pattern
    
    # Check numeric patterns
    numeric_pattern = get_compiled_numeric_pattern(pattern_name)
    if numeric_pattern is not None:
        return numeric_pattern
    
    # Check text patterns
    text_pattern = get_compiled_text_pattern(pattern_name)
    if text_pattern is not None:
        return text_pattern
    
    # Check remaining web patterns
    pattern_map = {
        "url_protection": URL_PROTECTION_PATTERN,
        "email_protection": EMAIL_PROTECTION_PATTERN,
        "www_domain_rescue": WWW_DOMAIN_RESCUE,
    }
    return pattern_map.get(pattern_name)


# ==============================================================================
# BACKWARD COMPATIBILITY
# ==============================================================================

# Import all the patterns from pattern_modules for backward compatibility
# Explicit imports to avoid namespace pollution while maintaining compatibility
from .pattern_modules import (
    # Code patterns
    ABBREVIATION_PATTERN,
    ALL_FILE_EXTENSIONS,
    ASSIGNMENT_PATTERN,
    FILE_EXTENSIONS,
    FILE_EXTENSION_DETECTION_PATTERN,
    FILENAME_WITH_EXTENSION_PATTERN,
    FULL_SPOKEN_FILENAME_PATTERN,
    JAVA_PACKAGE_PATTERN,
    LONG_FLAG_PATTERN,
    MATH_EXPRESSION_PATTERN,
    MIXED_CASE_TECH_PATTERN,
    SHORT_FLAG_PATTERN,
    SIMPLE_UNDERSCORE_PATTERN,
    SLASH_COMMAND_PATTERN,
    SPOKEN_DOT_FILENAME_PATTERN,
    SPOKEN_FILENAME_PATTERN,
    TECH_SEQUENCE_PATTERN,
    UNDERSCORE_DELIMITER_PATTERN,
    VERSION_PATTERN,
    # Web patterns
    COMMON_TLDS,
    DOMAIN_EXCLUDE_WORDS,
    PORT_NUMBER_PATTERN,
    SPOKEN_EMAIL_PATTERN,
    SPOKEN_PROTOCOL_PATTERN,
    SPOKEN_URL_PATTERN,
    URL_PARAMETER_PARSE_PATTERN,
    URL_PARAMETER_SPLIT_PATTERN,
    WWW_DOMAIN_RESCUE_PATTERN,
    # Numeric patterns
    CENTS_PATTERN,
    COMPLEX_MATH_EXPRESSION_PATTERN,
    CONSECUTIVE_DIGITS_PATTERN,
    DOLLAR_PATTERN,
    MATH_OPERATORS,
    NUMBER_CONSTANT_PATTERN,
    NUMBER_WORDS,
    NUMBER_WORD_SEQUENCE,
    NUMERIC_RANGE_PATTERN,
    SIMPLE_MATH_EXPRESSION_PATTERN,
    SPOKEN_COMPOUND_FRACTION_PATTERN,
    SPOKEN_FRACTION_PATTERN,
    SPOKEN_NUMERIC_RANGE_PATTERN,
    SPOKEN_ORDINAL_PATTERN,
    SPOKEN_PHONE_PATTERN,
    SPOKEN_TIME_RELATIVE_PATTERN,
    TIME_AM_PM_COLON_PATTERN,
    TIME_AM_PM_SPACE_PATTERN,
    TIME_EXPRESSION_PATTERNS,
    # Text patterns
    ABBREVIATION_RESTORATION_PATTERNS,
    ALL_CAPS_PRESERVATION_PATTERN,
    ENTITY_BOUNDARY_PATTERN,
    FILLER_WORDS,
    FILLER_WORDS_PATTERN,
    LETTER_SEQUENCE_PATTERN,
    PLACEHOLDER_PATTERN,
    PRONOUN_I_PATTERN,
    PRONOUN_I_STANDALONE_PATTERN,
    REPEATED_DOTS_PATTERN,
    REPEATED_EXCLAMATION_MARKS_PATTERN,
    REPEATED_PUNCTUATION_PATTERNS,
    REPEATED_QUESTION_MARKS_PATTERN,
    SENTENCE_CAPITALIZATION_PATTERN,
    SPOKEN_EMOJI_EXPLICIT_MAP,
    SPOKEN_EMOJI_IMPLICIT_MAP,
    SPOKEN_LETTER_PATTERN,
    TECHNICAL_CONTENT_PATTERNS,
    TEMPERATURE_PROTECTION_PATTERN,
    DECIMAL_PROTECTION_PATTERN,
    WHITESPACE_NORMALIZATION_PATTERN,
)

# All utility functions and patterns are now explicitly imported
# This maintains full backward compatibility for existing code
