#!/usr/bin/env python3
"""Public API for regex patterns.

This module provides the public interface for all regex patterns used in text formatting.
It re-exports everything from components, static, and builders modules for backward
compatibility.
"""

# ==============================================================================
# COMPONENTS - Data constants and helpers
# ==============================================================================
from .components import (
    # File extensions
    FILE_EXTENSIONS,
    ALL_FILE_EXTENSIONS,
    # Domain TLDs
    COMMON_TLDS,
    # Number words
    NUMBER_WORDS,
    # Math operators
    MATH_OPERATORS,
    # Filler words
    FILLER_WORDS,
    # Domain exclude words
    DOMAIN_EXCLUDE_WORDS,
    # Abbreviation mappings
    ABBREVIATION_RESTORATION_PATTERNS,
    # Emoji mappings
    SPOKEN_EMOJI_IMPLICIT_MAP,
    SPOKEN_EMOJI_EXPLICIT_MAP,
    # Helper functions
    get_file_extensions_by_category,
    get_all_file_extensions,
    create_alternation_pattern,
)

# ==============================================================================
# STATIC - Pre-compiled patterns
# ==============================================================================
from .static import (
    # Filler patterns
    FILLER_WORDS_PATTERN,
    REPEATED_PUNCTUATION_PATTERNS,
    # Ordinal and time patterns
    SPOKEN_ORDINAL_PATTERN,
    SPOKEN_TIME_RELATIVE_PATTERN,
    # Fraction patterns
    SPOKEN_FRACTION_PATTERN,
    SPOKEN_MIXED_FRACTION_PATTERN,
    # Capitalization patterns
    ALL_CAPS_PRESERVATION_PATTERN,
    SENTENCE_CAPITALIZATION_PATTERN,
    PRONOUN_I_PATTERN,
    # Technical content patterns
    FILE_EXTENSION_DETECTION_PATTERN,
    TECHNICAL_CONTENT_PATTERNS,
    # Code patterns
    FILENAME_WITH_EXTENSION_PATTERN,
    ABBREVIATION_PATTERN,
    # Math patterns
    COMPLEX_MATH_EXPRESSION_PATTERN,
    SIMPLE_MATH_EXPRESSION_PATTERN,
    NUMBER_CONSTANT_PATTERN,
    TIME_EXPRESSION_PATTERNS,
    SPOKEN_PHONE_PATTERN,
    # Web static patterns
    WWW_DOMAIN_RESCUE_PATTERN,
    URL_PARAMETER_SPLIT_PATTERN,
    URL_PARAMETER_PARSE_PATTERN,
    # Placeholder patterns
    PLACEHOLDER_PATTERN,
    # Pre-compiled optimization patterns
    WHITESPACE_NORMALIZATION_PATTERN,
    REPEATED_DOTS_PATTERN,
    REPEATED_QUESTION_MARKS_PATTERN,
    REPEATED_EXCLAMATION_MARKS_PATTERN,
    PRONOUN_I_STANDALONE_PATTERN,
    URL_PROTECTION_PATTERN,
    EMAIL_PROTECTION_PATTERN,
    TECH_SEQUENCE_PATTERN,
    MATH_EXPRESSION_PATTERN,
    TEMPERATURE_PROTECTION_PATTERN,
    MIXED_CASE_TECH_PATTERN,
    TIME_AM_PM_COLON_PATTERN,
    TIME_AM_PM_SPACE_PATTERN,
    SPOKEN_DOT_FILENAME_PATTERN,
    FULL_SPOKEN_FILENAME_PATTERN,
    JAVA_PACKAGE_PATTERN,
    SPOKEN_FILENAME_PATTERN,
    DOLLAR_PATTERN,
    CENTS_PATTERN,
    VERSION_PATTERN,
    WWW_DOMAIN_RESCUE,
    ENTITY_BOUNDARY_PATTERN,
    # Pattern factory functions
    create_profanity_pattern,
    create_domain_rescue_pattern,
    create_abbreviation_restoration_pattern,
    create_artifact_patterns,
    get_compiled_pattern,
)

# ==============================================================================
# BUILDERS - Dynamic i18n-aware pattern builders
# ==============================================================================
from .builders import (
    # Number word sequence
    NUMBER_WORD_SEQUENCE,
    SPOKEN_NUMERIC_RANGE_PATTERN,
    # URL pattern builders
    build_spoken_url_pattern,
    get_spoken_url_pattern,
    SPOKEN_URL_PATTERN,
    # Email pattern builders
    build_spoken_email_pattern,
    get_spoken_email_pattern,
    SPOKEN_EMAIL_PATTERN,
    # Protocol pattern builders
    build_spoken_protocol_pattern,
    get_spoken_protocol_pattern,
    SPOKEN_PROTOCOL_PATTERN,
    # IP pattern builders
    build_spoken_ip_pattern,
    get_spoken_ip_pattern,
    # Port pattern builders
    build_port_number_pattern,
    get_port_number_pattern,
    PORT_NUMBER_PATTERN,
    # Code pattern builders - getter functions
    get_slash_command_pattern,
    get_underscore_delimiter_pattern,
    get_simple_underscore_pattern,
    get_long_flag_pattern,
    get_short_flag_pattern,
    get_assignment_pattern,
    # Code pattern builders - build functions
    build_slash_command_pattern,
    build_underscore_delimiter_pattern,
    build_simple_underscore_pattern,
    build_long_flag_pattern,
    build_short_flag_pattern,
    build_assignment_pattern,
    # Default English patterns
    SLASH_COMMAND_PATTERN,
    UNDERSCORE_DELIMITER_PATTERN,
    SIMPLE_UNDERSCORE_PATTERN,
    LONG_FLAG_PATTERN,
    SHORT_FLAG_PATTERN,
    ASSIGNMENT_PATTERN,
)

# ==============================================================================
# PUBLIC API
# ==============================================================================
__all__ = [
    # Components - Data constants
    "FILE_EXTENSIONS",
    "ALL_FILE_EXTENSIONS",
    "COMMON_TLDS",
    "NUMBER_WORDS",
    "MATH_OPERATORS",
    "FILLER_WORDS",
    "DOMAIN_EXCLUDE_WORDS",
    "ABBREVIATION_RESTORATION_PATTERNS",
    "SPOKEN_EMOJI_IMPLICIT_MAP",
    "SPOKEN_EMOJI_EXPLICIT_MAP",
    # Components - Helper functions
    "get_file_extensions_by_category",
    "get_all_file_extensions",
    "create_alternation_pattern",
    # Static - Filler patterns
    "FILLER_WORDS_PATTERN",
    "REPEATED_PUNCTUATION_PATTERNS",
    # Static - Ordinal and time patterns
    "SPOKEN_ORDINAL_PATTERN",
    "SPOKEN_TIME_RELATIVE_PATTERN",
    # Static - Fraction patterns
    "SPOKEN_FRACTION_PATTERN",
    "SPOKEN_MIXED_FRACTION_PATTERN",
    # Static - Capitalization patterns
    "ALL_CAPS_PRESERVATION_PATTERN",
    "SENTENCE_CAPITALIZATION_PATTERN",
    "PRONOUN_I_PATTERN",
    # Static - Technical content patterns
    "FILE_EXTENSION_DETECTION_PATTERN",
    "TECHNICAL_CONTENT_PATTERNS",
    # Static - Code patterns
    "FILENAME_WITH_EXTENSION_PATTERN",
    "ABBREVIATION_PATTERN",
    # Static - Math patterns
    "COMPLEX_MATH_EXPRESSION_PATTERN",
    "SIMPLE_MATH_EXPRESSION_PATTERN",
    "NUMBER_CONSTANT_PATTERN",
    "TIME_EXPRESSION_PATTERNS",
    "SPOKEN_PHONE_PATTERN",
    # Static - Web patterns
    "WWW_DOMAIN_RESCUE_PATTERN",
    "URL_PARAMETER_SPLIT_PATTERN",
    "URL_PARAMETER_PARSE_PATTERN",
    # Static - Placeholder patterns
    "PLACEHOLDER_PATTERN",
    # Static - Pre-compiled optimization patterns
    "WHITESPACE_NORMALIZATION_PATTERN",
    "REPEATED_DOTS_PATTERN",
    "REPEATED_QUESTION_MARKS_PATTERN",
    "REPEATED_EXCLAMATION_MARKS_PATTERN",
    "PRONOUN_I_STANDALONE_PATTERN",
    "URL_PROTECTION_PATTERN",
    "EMAIL_PROTECTION_PATTERN",
    "TECH_SEQUENCE_PATTERN",
    "MATH_EXPRESSION_PATTERN",
    "TEMPERATURE_PROTECTION_PATTERN",
    "MIXED_CASE_TECH_PATTERN",
    "TIME_AM_PM_COLON_PATTERN",
    "TIME_AM_PM_SPACE_PATTERN",
    "SPOKEN_DOT_FILENAME_PATTERN",
    "FULL_SPOKEN_FILENAME_PATTERN",
    "JAVA_PACKAGE_PATTERN",
    "SPOKEN_FILENAME_PATTERN",
    "DOLLAR_PATTERN",
    "CENTS_PATTERN",
    "VERSION_PATTERN",
    "WWW_DOMAIN_RESCUE",
    "ENTITY_BOUNDARY_PATTERN",
    # Static - Pattern factory functions
    "create_profanity_pattern",
    "create_domain_rescue_pattern",
    "create_abbreviation_restoration_pattern",
    "create_artifact_patterns",
    "get_compiled_pattern",
    # Builders - Number word sequence
    "NUMBER_WORD_SEQUENCE",
    "SPOKEN_NUMERIC_RANGE_PATTERN",
    # Builders - URL patterns
    "build_spoken_url_pattern",
    "get_spoken_url_pattern",
    "SPOKEN_URL_PATTERN",
    # Builders - Email patterns
    "build_spoken_email_pattern",
    "get_spoken_email_pattern",
    "SPOKEN_EMAIL_PATTERN",
    # Builders - Protocol patterns
    "build_spoken_protocol_pattern",
    "get_spoken_protocol_pattern",
    "SPOKEN_PROTOCOL_PATTERN",
    # Builders - IP patterns
    "build_spoken_ip_pattern",
    "get_spoken_ip_pattern",
    # Builders - Port patterns
    "build_port_number_pattern",
    "get_port_number_pattern",
    "PORT_NUMBER_PATTERN",
    # Builders - Code pattern getters
    "get_slash_command_pattern",
    "get_underscore_delimiter_pattern",
    "get_simple_underscore_pattern",
    "get_long_flag_pattern",
    "get_short_flag_pattern",
    "get_assignment_pattern",
    # Builders - Code pattern build functions
    "build_slash_command_pattern",
    "build_underscore_delimiter_pattern",
    "build_simple_underscore_pattern",
    "build_long_flag_pattern",
    "build_short_flag_pattern",
    "build_assignment_pattern",
    # Builders - Default English patterns
    "SLASH_COMMAND_PATTERN",
    "UNDERSCORE_DELIMITER_PATTERN",
    "SIMPLE_UNDERSCORE_PATTERN",
    "LONG_FLAG_PATTERN",
    "SHORT_FLAG_PATTERN",
    "ASSIGNMENT_PATTERN",
]
