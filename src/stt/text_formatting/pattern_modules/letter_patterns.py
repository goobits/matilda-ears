#!/usr/bin/env python3
"""
Letter patterns and abbreviation handling for text formatting.

This module contains patterns and functions for handling spoken letters,
letter sequences, and abbreviation processing.
"""
from __future__ import annotations

import re

from ..constants import get_resources


# ==============================================================================
# LETTER PATTERNS
# ==============================================================================

def build_spoken_letter_pattern(language: str = "en") -> re.Pattern[str]:
    """Builds the spoken letter pattern dynamically from keywords in constants."""
    # Get resources for the specified language
    resources = get_resources(language)

    # Get letter case keywords and letter keywords from resources
    letter_case_keywords = resources.get("letters", {})
    letter_keywords = resources.get("spoken_keywords", {}).get("letters", {})

    # Create pattern for case words (capital, uppercase, lowercase, etc.)
    case_words = list(letter_case_keywords.keys())
    case_words_escaped = [re.escape(word) for word in case_words]
    case_pattern = "|".join(case_words_escaped) if case_words_escaped else "capital|uppercase|lowercase|small"

    # Create pattern for individual letters A-Z
    letters = [chr(i) for i in range(ord("A"), ord("Z") + 1)]
    letters_lower = [chr(i) for i in range(ord("a"), ord("z") + 1)]
    all_letters = letters + letters_lower

    # Add any custom letter pronunciations from resources
    letter_pronunciations = []
    for key, value in letter_keywords.items():
        if len(value) == 1 and value.isalpha():
            letter_pronunciations.append(re.escape(key))

    # Create letter pattern (including phonetic pronunciations if available)
    if letter_pronunciations:
        letter_pattern = "|".join(letter_pronunciations + [re.escape(letter) for letter in all_letters])
    else:
        letter_pattern = "|".join(re.escape(letter) for letter in all_letters)

    # Check language to determine word order
    if language == "es":
        # Spanish: "A mayúscula" (letter + case)
        pattern_str = rf"""
        \b                                  # Word boundary
        ({letter_pattern})                  # Capture group 1: letter
        \s+                                 # Space
        ({case_pattern})                    # Capture group 2: case modifier
        \b                                  # Word boundary
        """
    else:
        # English and other languages: "capital A" (case + letter)
        pattern_str = rf"""
        \b                                  # Word boundary
        ({case_pattern})                    # Capture group 1: case modifier
        \s+                                 # Space
        ({letter_pattern})                  # Capture group 2: letter
        \b                                  # Word boundary
        """

    return re.compile(pattern_str, re.VERBOSE | re.IGNORECASE)


def build_letter_sequence_pattern(language: str = "en") -> re.Pattern[str]:
    """Builds the letter sequence pattern for sequences like 'A B C' dynamically."""
    # Get resources for the specified language
    resources = get_resources(language)

    # Get letter case keywords and letter keywords from resources
    letter_case_keywords = resources.get("letters", {})
    letter_keywords = resources.get("spoken_keywords", {}).get("letters", {})

    # Create pattern for case words (capital, uppercase, lowercase, etc.)
    case_words = list(letter_case_keywords.keys())
    case_words_escaped = [re.escape(word) for word in case_words]
    case_pattern = "|".join(case_words_escaped) if case_words_escaped else "capital|uppercase|lowercase|small"

    # Create pattern for individual letters A-Z
    letters = [chr(i) for i in range(ord("A"), ord("Z") + 1)]
    letters_lower = [chr(i) for i in range(ord("a"), ord("z") + 1)]
    all_letters = letters + letters_lower

    # Add any custom letter pronunciations from resources
    letter_pronunciations = []
    for key, value in letter_keywords.items():
        if len(value) == 1 and value.isalpha():
            letter_pronunciations.append(re.escape(key))

    # Create letter pattern (including phonetic pronunciations if available)
    if letter_pronunciations:
        letter_pattern = "|".join(letter_pronunciations + [re.escape(letter) for letter in all_letters])
    else:
        letter_pattern = "|".join(re.escape(letter) for letter in all_letters)

    # Create a single letter unit pattern that can optionally have a case modifier
    letter_unit = rf"""
        (?:({case_pattern})\s+)?        # Optional case modifier
        ({letter_pattern})              # Letter
    """

    # Create the letter sequence pattern - matches 2 or more letter units
    pattern_str = rf"""
    \b                                  # Word boundary
    {letter_unit}                       # First letter (with optional case)
    (?:                                 # Additional letters
        \s+                             # Space separator
        {letter_unit}                   # Another letter unit (with optional case)
    ){{1,}}                             # One or more additional letters
    \b                                  # Word boundary
    """

    return re.compile(pattern_str, re.VERBOSE | re.IGNORECASE)


def get_spoken_letter_pattern(language: str = "en") -> re.Pattern[str]:
    """Get the compiled spoken letter pattern for the specified language."""
    if language == "en":
        return SPOKEN_LETTER_PATTERN
    else:
        return build_spoken_letter_pattern(language)


def get_letter_sequence_pattern(language: str = "en") -> re.Pattern[str]:
    """Get the compiled letter sequence pattern for the specified language."""
    if language == "en":
        return LETTER_SEQUENCE_PATTERN
    else:
        return build_letter_sequence_pattern(language)


# Pre-compiled patterns for English (default)
SPOKEN_LETTER_PATTERN = build_spoken_letter_pattern("en")
LETTER_SEQUENCE_PATTERN = build_letter_sequence_pattern("en")


# ==============================================================================
# ABBREVIATION PATTERNS
# ==============================================================================

def build_abbreviation_pattern() -> re.Pattern[str]:
    """Build the abbreviation pattern for Latin abbreviations."""
    return re.compile(
        r"""
        \b                                  # Word boundary
        (                                   # Capture group for abbreviation
            i\.e\. | e\.g\. | etc\. |       # With periods
            vs\. | cf\. |                   # With periods
            ie | eg | ex |                  # Without periods
            i\s+e |                         # Spoken form "i e"
            e\s+g |                         # Spoken form "e g"
            v\s+s |                         # Spoken form "v s"
            i\s+dot\s+e\s+dot |             # Spoken form "i dot e dot"
            e\s+dot\s+g\s+dot               # Spoken form "e dot g dot"
        )
        (?=\s|[,.:;!?]|$)                   # Lookahead: space, punctuation, or end
        """,
        re.VERBOSE | re.IGNORECASE,
    )


def get_abbreviation_pattern() -> re.Pattern[str]:
    """Get the compiled abbreviation pattern."""
    return ABBREVIATION_PATTERN


# Abbreviation restoration after punctuation model
ABBREVIATION_RESTORATION_PATTERNS = {
    "ie": "i.e.",
    "eg": "e.g.",
    "ex": "e.g.",  # "ex" is converted to "e.g." in this system
    "etc": "etc.",
    "vs": "vs.",
    "cf": "cf.",
}


def create_abbreviation_restoration_pattern(abbr: str) -> re.Pattern[str]:
    """Create a pattern to restore periods to abbreviations."""
    return re.compile(
        rf"""
        (?<![.])                        # Not preceded by period
        \b{re.escape(abbr)}\b           # The abbreviation
        (?![.])                         # Not followed by period
        """,
        re.VERBOSE | re.IGNORECASE,
    )


def get_abbreviation_restoration_patterns() -> dict[str, str]:
    """Get the abbreviation restoration mappings."""
    return ABBREVIATION_RESTORATION_PATTERNS.copy()


# Pre-compiled pattern
ABBREVIATION_PATTERN = build_abbreviation_pattern()