#!/usr/bin/env python3
"""
Common patterns that are frequently used across multiple modules.

This module centralizes frequently duplicated regex patterns to reduce
code duplication and improve maintainability. All patterns here are
used in multiple places throughout the text formatting system.
"""
from __future__ import annotations

import re
from typing import Pattern

from ..pattern_cache import cached_pattern


# ==============================================================================
# EMAIL PATTERNS
# ==============================================================================

@cached_pattern
def build_email_basic_pattern() -> re.Pattern[str]:
    """Build basic email pattern for matching email addresses."""
    return re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")


def get_email_basic_pattern() -> re.Pattern[str]:
    """Get the basic email pattern."""
    return EMAIL_BASIC_PATTERN


# Pre-compiled pattern
EMAIL_BASIC_PATTERN = build_email_basic_pattern()


# ==============================================================================
# PRONOUN PATTERNS
# ==============================================================================

@cached_pattern
def build_pronoun_i_basic_pattern() -> re.Pattern[str]:
    """Build basic pattern for matching standalone 'i' pronoun."""
    return re.compile(r"\bi\b")


def get_pronoun_i_basic_pattern() -> re.Pattern[str]:
    """Get the basic pronoun 'i' pattern."""
    return PRONOUN_I_BASIC_PATTERN


# Pre-compiled pattern
PRONOUN_I_BASIC_PATTERN = build_pronoun_i_basic_pattern()


# ==============================================================================
# ORDINAL PATTERNS
# ==============================================================================

@cached_pattern
def build_ordinal_suffix_pattern() -> re.Pattern[str]:
    """Build pattern for matching ordinal suffixes (1st, 2nd, 3rd, 4th)."""
    return re.compile(r"(\d+)(st|nd|rd|th)", re.IGNORECASE)


def get_ordinal_suffix_pattern() -> re.Pattern[str]:
    """Get the ordinal suffix pattern."""
    return ORDINAL_SUFFIX_PATTERN


# Pre-compiled pattern
ORDINAL_SUFFIX_PATTERN = build_ordinal_suffix_pattern()


# ==============================================================================
# ABBREVIATION PATTERNS
# ==============================================================================

@cached_pattern
def build_abbreviation_spacing_pattern() -> re.Pattern[str]:
    """Build pattern for fixing abbreviation spacing (i.e., e.g., etc.)."""
    return re.compile(r'(^|\s)(i\.e\.|e\.g\.|etc\.|vs\.|cf\.)(\s|$)', re.IGNORECASE)


def get_abbreviation_spacing_pattern() -> re.Pattern[str]:
    """Get the abbreviation spacing pattern."""
    return ABBREVIATION_SPACING_PATTERN


# Pre-compiled pattern
ABBREVIATION_SPACING_PATTERN = build_abbreviation_spacing_pattern()


# ==============================================================================
# UTILITY FUNCTIONS
# ==============================================================================

def get_compiled_common_pattern(pattern_name: str) -> Pattern | None:
    """Get a pre-compiled common pattern by name."""
    pattern_map = {
        "email_basic": EMAIL_BASIC_PATTERN,
        "pronoun_i_basic": PRONOUN_I_BASIC_PATTERN,
        "ordinal_suffix": ORDINAL_SUFFIX_PATTERN,
        "abbreviation_spacing": ABBREVIATION_SPACING_PATTERN,
    }
    return pattern_map.get(pattern_name)


# ==============================================================================
# EXPORTS
# ==============================================================================

__all__ = [
    # Email patterns
    "EMAIL_BASIC_PATTERN",
    "build_email_basic_pattern",
    "get_email_basic_pattern",
    
    # Pronoun patterns
    "PRONOUN_I_BASIC_PATTERN", 
    "build_pronoun_i_basic_pattern",
    "get_pronoun_i_basic_pattern",
    
    # Ordinal patterns
    "ORDINAL_SUFFIX_PATTERN",
    "build_ordinal_suffix_pattern", 
    "get_ordinal_suffix_pattern",
    
    # Abbreviation patterns
    "ABBREVIATION_SPACING_PATTERN",
    "build_abbreviation_spacing_pattern",
    "get_abbreviation_spacing_pattern",
    
    # Utility functions
    "get_compiled_common_pattern",
]