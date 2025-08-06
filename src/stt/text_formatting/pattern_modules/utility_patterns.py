#!/usr/bin/env python3
"""
Utility patterns and miscellaneous functions for text formatting.

This module contains utility functions, placeholder patterns, whitespace
normalization patterns, and general helper functions for text processing.
"""
from __future__ import annotations

import re
from typing import Pattern


# ==============================================================================
# PLACEHOLDER PATTERNS
# ==============================================================================

def build_placeholder_pattern() -> re.Pattern[str]:
    """Build pattern for internal placeholder tokens used during processing."""
    return re.compile(
        r"""
        __PLACEHOLDER_\d+__ |               # Placeholder tokens
        __ENTITY_\d+__ |                    # Entity tokens
        __CAPS_\d+__                        # Capitalization tokens
        """,
        re.VERBOSE,
    )


def get_placeholder_pattern() -> re.Pattern[str]:
    """Get the compiled placeholder pattern."""
    return PLACEHOLDER_PATTERN


# Pre-compiled pattern
PLACEHOLDER_PATTERN = build_placeholder_pattern()


# ==============================================================================
# WHITESPACE AND CLEANING PATTERNS
# ==============================================================================

def build_whitespace_normalization_pattern() -> re.Pattern[str]:
    """Build pattern for normalizing whitespace."""
    return re.compile(r"\s+")


def build_entity_boundary_pattern() -> re.Pattern[str]:
    """Build pattern for entity boundaries."""
    return re.compile(r"\b(?=\w)")


def get_whitespace_normalization_pattern() -> re.Pattern[str]:
    """Get the whitespace normalization pattern."""
    return WHITESPACE_NORMALIZATION_PATTERN


def get_entity_boundary_pattern() -> re.Pattern[str]:
    """Get the entity boundary pattern."""
    return ENTITY_BOUNDARY_PATTERN


# Pre-compiled patterns for performance
WHITESPACE_NORMALIZATION_PATTERN = build_whitespace_normalization_pattern()
ENTITY_BOUNDARY_PATTERN = build_entity_boundary_pattern()


# ==============================================================================
# UTILITY FUNCTIONS
# ==============================================================================

def get_compiled_text_pattern(pattern_name: str) -> Pattern | None:
    """Get a pre-compiled text pattern by name."""
    # Import here to avoid circular imports
    from .filler_patterns import FILLER_WORDS_PATTERN
    from .punctuation_patterns import (
        REPEATED_DOTS_PATTERN,
        REPEATED_QUESTION_MARKS_PATTERN,
        REPEATED_EXCLAMATION_MARKS_PATTERN,
    )
    from .capitalization_patterns import (
        ALL_CAPS_PRESERVATION_PATTERN,
        SENTENCE_CAPITALIZATION_PATTERN,
        PRONOUN_I_PATTERN,
        PRONOUN_I_STANDALONE_PATTERN,
        TEMPERATURE_PROTECTION_PATTERN,
    )
    from .letter_patterns import (
        SPOKEN_LETTER_PATTERN,
        LETTER_SEQUENCE_PATTERN,
        ABBREVIATION_PATTERN,
    )
    
    pattern_map = {
        # Cleaning patterns
        "filler": FILLER_WORDS_PATTERN,
        "whitespace": WHITESPACE_NORMALIZATION_PATTERN,
        "dots": REPEATED_DOTS_PATTERN,
        "questions": REPEATED_QUESTION_MARKS_PATTERN,
        "exclamations": REPEATED_EXCLAMATION_MARKS_PATTERN,
        "pronoun_i": PRONOUN_I_STANDALONE_PATTERN,
        "temperature": TEMPERATURE_PROTECTION_PATTERN,
        "entity_boundary": ENTITY_BOUNDARY_PATTERN,
        
        # Capitalization patterns
        "all_caps_preservation": ALL_CAPS_PRESERVATION_PATTERN,
        "sentence_capitalization": SENTENCE_CAPITALIZATION_PATTERN,
        "pronoun_i_case": PRONOUN_I_PATTERN,
        
        # Letter patterns
        "spoken_letter": SPOKEN_LETTER_PATTERN,
        "letter_sequence": LETTER_SEQUENCE_PATTERN,
        
        # Abbreviation patterns
        "abbreviation": ABBREVIATION_PATTERN,
        
        # Placeholder patterns
        "placeholder": PLACEHOLDER_PATTERN,
    }
    return pattern_map.get(pattern_name)