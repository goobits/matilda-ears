#!/usr/bin/env python3
"""
Technical patterns for text formatting.

This module contains technical number patterns including phone numbers
and other technical identifiers used throughout the text formatting system.
"""
from __future__ import annotations

import re
from typing import Pattern


# ==============================================================================
# TECHNICAL PATTERN BUILDERS
# ==============================================================================


def build_spoken_phone_pattern(language: str = "en") -> re.Pattern[str]:
    """Build the spoken phone pattern for phone numbers as digits."""
    return re.compile(
        r"""
        \b                                  # Word boundary
        (?:five|six|seven|eight|nine|zero|one|two|three|four)  # First digit word
        (?:                                 # Nine more digit words
            \s+                             # Space separator
            (?:five|six|seven|eight|nine|zero|one|two|three|four)  # Digit word
        ){9}                                # Exactly 9 more (total 10)
        \b                                  # Word boundary
        """,
        re.VERBOSE | re.IGNORECASE,
    )


# ==============================================================================
# GETTER FUNCTIONS
# ==============================================================================


def get_spoken_phone_pattern(language: str = "en") -> re.Pattern[str]:
    """Get the spoken phone pattern for the specified language."""
    return build_spoken_phone_pattern(language)