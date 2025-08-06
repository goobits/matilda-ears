#!/usr/bin/env python3
"""
General text processing regular expression patterns for text formatting.

This module serves as the main interface for all text-related patterns used
throughout the text formatting system. It imports and re-exports functionality
from specialized pattern modules while maintaining backward compatibility.

The functionality is organized into several specialized modules:
- filler_patterns: Filler words and basic text cleaning
- punctuation_patterns: Punctuation normalization and profanity filtering
- capitalization_patterns: Capitalization logic and technical content detection
- letter_patterns: Letter detection, sequences, and abbreviations
- emoji_patterns: Emoji mappings and patterns
- utility_patterns: Utility functions, placeholders, and whitespace patterns
"""
from __future__ import annotations

# Import and re-export everything from specialized modules
# This maintains backward compatibility while organizing code into logical modules

# Filler words and text cleaning
from .filler_patterns import (
    FILLER_WORDS,
    FILLER_WORDS_PATTERN,
    build_filler_pattern,
    get_filler_pattern,
    get_filler_words,
    create_artifact_patterns,
)

# Punctuation normalization and profanity filtering
from .punctuation_patterns import (
    REPEATED_PUNCTUATION_PATTERNS,
    REPEATED_DOTS_PATTERN,
    REPEATED_QUESTION_MARKS_PATTERN,
    REPEATED_EXCLAMATION_MARKS_PATTERN,
    get_repeated_punctuation_patterns,
    build_repeated_dots_pattern,
    build_repeated_question_marks_pattern,
    build_repeated_exclamation_marks_pattern,
    get_repeated_dots_pattern,
    get_repeated_question_marks_pattern,
    get_repeated_exclamation_marks_pattern,
    create_profanity_pattern,
)

# Capitalization patterns and technical content detection
from .capitalization_patterns import (
    ALL_CAPS_PRESERVATION_PATTERN,
    SENTENCE_CAPITALIZATION_PATTERN,
    PRONOUN_I_PATTERN,
    PRONOUN_I_STANDALONE_PATTERN,
    TEMPERATURE_PROTECTION_PATTERN,
    TECHNICAL_CONTENT_PATTERNS,
    build_all_caps_preservation_pattern,
    build_sentence_capitalization_pattern,
    build_pronoun_i_pattern,
    build_pronoun_i_standalone_pattern,
    build_temperature_protection_pattern,
    build_technical_content_patterns,
    get_all_caps_preservation_pattern,
    get_sentence_capitalization_pattern,
    get_pronoun_i_pattern,
    get_pronoun_i_standalone_pattern,
    get_temperature_protection_pattern,
    get_technical_content_patterns,
)

# Letter patterns and abbreviations
from .letter_patterns import (
    SPOKEN_LETTER_PATTERN,
    LETTER_SEQUENCE_PATTERN,
    ABBREVIATION_PATTERN,
    ABBREVIATION_RESTORATION_PATTERNS,
    build_spoken_letter_pattern,
    build_letter_sequence_pattern,
    build_abbreviation_pattern,
    get_spoken_letter_pattern,
    get_letter_sequence_pattern,
    get_abbreviation_pattern,
    create_abbreviation_restoration_pattern,
    get_abbreviation_restoration_patterns,
)

# Emoji patterns and mappings
from .emoji_patterns import (
    SPOKEN_EMOJI_IMPLICIT_MAP,
    SPOKEN_EMOJI_EXPLICIT_MAP,
    get_spoken_emoji_implicit_map,
    get_spoken_emoji_explicit_map,
)

# Utility patterns and functions
from .utility_patterns import (
    PLACEHOLDER_PATTERN,
    WHITESPACE_NORMALIZATION_PATTERN,
    ENTITY_BOUNDARY_PATTERN,
    build_placeholder_pattern,
    build_whitespace_normalization_pattern,
    build_entity_boundary_pattern,
    get_placeholder_pattern,
    get_whitespace_normalization_pattern,
    get_entity_boundary_pattern,
    get_compiled_text_pattern,
)

# Re-export everything for backward compatibility
__all__ = [
    # Filler words and text cleaning
    "FILLER_WORDS",
    "FILLER_WORDS_PATTERN",
    "build_filler_pattern",
    "get_filler_pattern",
    "get_filler_words",
    "create_artifact_patterns",
    
    # Punctuation normalization
    "REPEATED_PUNCTUATION_PATTERNS",
    "REPEATED_DOTS_PATTERN",
    "REPEATED_QUESTION_MARKS_PATTERN",
    "REPEATED_EXCLAMATION_MARKS_PATTERN",
    "get_repeated_punctuation_patterns",
    "build_repeated_dots_pattern",
    "build_repeated_question_marks_pattern",
    "build_repeated_exclamation_marks_pattern",
    "get_repeated_dots_pattern",
    "get_repeated_question_marks_pattern",
    "get_repeated_exclamation_marks_pattern",
    "create_profanity_pattern",
    
    # Capitalization patterns
    "ALL_CAPS_PRESERVATION_PATTERN",
    "SENTENCE_CAPITALIZATION_PATTERN",
    "PRONOUN_I_PATTERN",
    "PRONOUN_I_STANDALONE_PATTERN",
    "TEMPERATURE_PROTECTION_PATTERN",
    "TECHNICAL_CONTENT_PATTERNS",
    "build_all_caps_preservation_pattern",
    "build_sentence_capitalization_pattern",
    "build_pronoun_i_pattern",
    "build_pronoun_i_standalone_pattern",
    "build_temperature_protection_pattern",
    "build_technical_content_patterns",
    "get_all_caps_preservation_pattern",
    "get_sentence_capitalization_pattern",
    "get_pronoun_i_pattern",
    "get_pronoun_i_standalone_pattern",
    "get_temperature_protection_pattern",
    "get_technical_content_patterns",
    
    # Letter patterns
    "SPOKEN_LETTER_PATTERN",
    "LETTER_SEQUENCE_PATTERN",
    "ABBREVIATION_PATTERN",
    "ABBREVIATION_RESTORATION_PATTERNS",
    "build_spoken_letter_pattern",
    "build_letter_sequence_pattern",
    "build_abbreviation_pattern",
    "get_spoken_letter_pattern",
    "get_letter_sequence_pattern",
    "get_abbreviation_pattern",
    "create_abbreviation_restoration_pattern",
    "get_abbreviation_restoration_patterns",
    
    # Emoji patterns
    "SPOKEN_EMOJI_IMPLICIT_MAP",
    "SPOKEN_EMOJI_EXPLICIT_MAP",
    "get_spoken_emoji_implicit_map",
    "get_spoken_emoji_explicit_map",
    
    # Utility patterns
    "PLACEHOLDER_PATTERN",
    "WHITESPACE_NORMALIZATION_PATTERN",
    "ENTITY_BOUNDARY_PATTERN",
    "build_placeholder_pattern",
    "build_whitespace_normalization_pattern",
    "build_entity_boundary_pattern",
    "get_placeholder_pattern",
    "get_whitespace_normalization_pattern",
    "get_entity_boundary_pattern",
    "get_compiled_text_pattern",
]