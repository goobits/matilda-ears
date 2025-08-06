#!/usr/bin/env python3
"""
Punctuation normalization and profanity filtering patterns for text formatting.

This module contains patterns and functions for normalizing punctuation,
handling repeated punctuation marks, and filtering profanity.
"""
from __future__ import annotations

import re


# ==============================================================================
# PUNCTUATION NORMALIZATION
# ==============================================================================

# Normalize repeated punctuation
REPEATED_PUNCTUATION_PATTERNS = [
    (re.compile(r"([,;:])\1+"), r"\1"),  # Repeated commas, semicolons, colons
    (re.compile(r"\.\.+"), "."),  # Multiple dots to single dot
    (re.compile(r"\?\?+"), "?"),  # Multiple question marks
    (re.compile(r"!!+"), "!"),  # Multiple exclamation marks
]


def get_repeated_punctuation_patterns() -> list[tuple[re.Pattern[str], str]]:
    """Get the repeated punctuation patterns."""
    return REPEATED_PUNCTUATION_PATTERNS


def build_repeated_dots_pattern() -> re.Pattern[str]:
    """Build pattern for repeated dots."""
    return re.compile(r"\.\.+")


def build_repeated_question_marks_pattern() -> re.Pattern[str]:
    """Build pattern for repeated question marks."""
    return re.compile(r"\?\?+")


def build_repeated_exclamation_marks_pattern() -> re.Pattern[str]:
    """Build pattern for repeated exclamation marks."""
    return re.compile(r"!!+")


def get_repeated_dots_pattern() -> re.Pattern[str]:
    """Get the repeated dots pattern."""
    return REPEATED_DOTS_PATTERN


def get_repeated_question_marks_pattern() -> re.Pattern[str]:
    """Get the repeated question marks pattern."""
    return REPEATED_QUESTION_MARKS_PATTERN


def get_repeated_exclamation_marks_pattern() -> re.Pattern[str]:
    """Get the repeated exclamation marks pattern."""
    return REPEATED_EXCLAMATION_MARKS_PATTERN


# Pre-compiled patterns for performance
REPEATED_DOTS_PATTERN = build_repeated_dots_pattern()
REPEATED_QUESTION_MARKS_PATTERN = build_repeated_question_marks_pattern()
REPEATED_EXCLAMATION_MARKS_PATTERN = build_repeated_exclamation_marks_pattern()


# ==============================================================================
# PROFANITY FILTERING
# ==============================================================================

def create_profanity_pattern(profanity_words: list[str]) -> re.Pattern[str]:
    """
    Create a pattern to filter profanity words.

    Only matches lowercase profanity to avoid filtering proper nouns
    and sentence beginnings (e.g., "Hell, Michigan" vs "go to hell").
    """
    escaped_words = [re.escape(word) for word in profanity_words]
    # Match only when the word starts with lowercase letter
    pattern_string = r"\b(?:" + "|".join(f"[{word[0].lower()}]{re.escape(word[1:])}" for word in escaped_words) + r")\b"
    return re.compile(pattern_string)