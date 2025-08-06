#!/usr/bin/env python3
"""
Capitalization patterns and technical content detection for text formatting.

This module contains patterns and functions for handling capitalization,
preserving all-caps words, sentence capitalization, and detecting technical content.
"""
from __future__ import annotations

import re


# ==============================================================================
# CAPITALIZATION PATTERNS
# ==============================================================================

def build_all_caps_preservation_pattern() -> re.Pattern[str]:
    """Build pattern to preserve all-caps words (acronyms) and technical units."""
    return re.compile(
        r"""
        \b[A-Z]{2,}\b                       # Acronyms: CPU, API, JSON, etc.
        |                                   # OR
        (?<![vV])                           # Not preceded by 'v' (excludes version numbers)
        \d+                                 # One or more digits
        (?:\.\d+)?                          # Optional decimal part
        [A-Z]{2,}                           # Unit letters (MB, GHz, etc.)
        °?                                  # Optional degree symbol
        [A-Z]?                              # Optional additional letter
        \b                                  # Word boundary
        """,
        re.VERBOSE,
    )


def build_sentence_capitalization_pattern() -> re.Pattern[str]:
    """Build pattern to capitalize letters after sentence-ending punctuation."""
    return re.compile(
        r"""
        ([.!?]\s+)                          # Sentence-ending punctuation + space(s)
        ([a-z])                             # Lowercase letter to capitalize
        """,
        re.VERBOSE,
    )


def build_pronoun_i_pattern() -> re.Pattern[str]:
    """Build pattern to capitalize pronoun 'i' while avoiding code variables."""
    return re.compile(
        r"""
        (?<![a-zA-Z])                       # Not preceded by letter
        i                                   # The letter 'i'
        (?![a-zA-Z+\-])                     # Not followed by letter, plus, or minus
        """,
        re.VERBOSE,
    )


def build_pronoun_i_standalone_pattern() -> re.Pattern[str]:
    """Build pattern for standalone pronoun 'i'."""
    return re.compile(r"\bi\b")


def build_temperature_protection_pattern() -> re.Pattern[str]:
    """Build pattern for temperature values protection."""
    return re.compile(r"-?\d+(?:\.\d+)?°[CF]?")


def get_all_caps_preservation_pattern() -> re.Pattern[str]:
    """Get the compiled all-caps preservation pattern."""
    return ALL_CAPS_PRESERVATION_PATTERN


def get_sentence_capitalization_pattern() -> re.Pattern[str]:
    """Get the compiled sentence capitalization pattern."""
    return SENTENCE_CAPITALIZATION_PATTERN


def get_pronoun_i_pattern() -> re.Pattern[str]:
    """Get the compiled pronoun I pattern."""
    return PRONOUN_I_PATTERN


def get_pronoun_i_standalone_pattern() -> re.Pattern[str]:
    """Get the standalone pronoun I pattern."""
    return PRONOUN_I_STANDALONE_PATTERN


def get_temperature_protection_pattern() -> re.Pattern[str]:
    """Get the temperature protection pattern."""
    return TEMPERATURE_PROTECTION_PATTERN


# Pre-compiled patterns
ALL_CAPS_PRESERVATION_PATTERN = build_all_caps_preservation_pattern()
SENTENCE_CAPITALIZATION_PATTERN = build_sentence_capitalization_pattern()
PRONOUN_I_PATTERN = build_pronoun_i_pattern()
PRONOUN_I_STANDALONE_PATTERN = build_pronoun_i_standalone_pattern()
TEMPERATURE_PROTECTION_PATTERN = build_temperature_protection_pattern()


# ==============================================================================
# TECHNICAL CONTENT DETECTION
# ==============================================================================

def build_technical_content_patterns() -> list[re.Pattern[str]]:
    """Build patterns for technical content that don't need punctuation."""
    return [
        # Version numbers (only exact version patterns, not sentences)
        re.compile(r"^version\s+\d+(?:\.\d+)*$", re.IGNORECASE),
        # Currency amounts
        re.compile(r"^\$[\d,]+\.?\d*$"),
        # Domain names
        re.compile(
            r"""
            ^                               # Start of string
            [\w\s]+                         # Word characters and spaces
            \.                              # Literal dot
            (?:com|org|net|edu|gov|io)      # Common TLDs
            $                               # End of string
            """,
            re.VERBOSE | re.IGNORECASE,
        ),
        # Email addresses
        re.compile(
            r"""
            ^                               # Start of string
            [\w\.\-]+                       # Username part
            @                               # At symbol
            [\w\.\-]+                       # Domain part
            \.[a-z]+                        # TLD
            $                               # End of string
            """,
            re.VERBOSE | re.IGNORECASE,
        ),
        # Phone numbers
        re.compile(r"^\(\d{3}\)\s*\d{3}-?\d{4}$"),
        # Physics equations
        re.compile(
            r"""
            ^                               # Start of string
            [A-Z]+                          # Variable(s)
            \s*=\s*                         # Equals with optional spaces
            [A-Z0-9²³⁴]+                    # Value with possible superscripts
            $                               # End of string
            """,
            re.VERBOSE,
        ),
        # Math equations
        re.compile(
            r"""
            ^                               # Start of string
            \d+                             # First number
            \s*                             # Optional space
            [+\-*/×÷]                       # Mathematical operator
            \s*                             # Optional space
            \d+                             # Second number
            \s*=\s*                         # Equals with optional spaces
            \d+                             # Result
            $                               # End of string
            """,
            re.VERBOSE,
        ),
    ]


def get_technical_content_patterns() -> list[re.Pattern[str]]:
    """Get the technical content detection patterns."""
    return TECHNICAL_CONTENT_PATTERNS


# Pre-compiled patterns
TECHNICAL_CONTENT_PATTERNS = build_technical_content_patterns()