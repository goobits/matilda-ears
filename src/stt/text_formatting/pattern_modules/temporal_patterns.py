#!/usr/bin/env python3
"""
Temporal (time and date) patterns for text formatting.

This module contains time-related patterns including relative time, AM/PM formats,
and various time expression patterns used throughout the text formatting system.
"""
from __future__ import annotations

import re
from typing import Pattern


# ==============================================================================
# TIME PATTERN BUILDERS
# ==============================================================================


def build_time_relative_pattern(language: str = "en") -> re.Pattern[str]:
    """Build the relative time pattern (quarter past, half past, etc.)."""
    return re.compile(
        r"\b(quarter\s+past|half\s+past|quarter\s+to|ten\s+past|twenty\s+past|"
        r"twenty\-five\s+past|five\s+past|ten\s+to|twenty\s+to|twenty\-five\s+to|"
        r"five\s+to)\s+(\w+)\b",
        re.IGNORECASE,
    )


def build_time_am_pm_colon_pattern(language: str = "en") -> re.Pattern[str]:
    """Build the AM/PM colon time pattern."""
    return re.compile(r"\b(\d+):([ap])\s+m\b", re.IGNORECASE)


def build_time_am_pm_space_pattern(language: str = "en") -> re.Pattern[str]:
    """Build the AM/PM space time pattern."""
    return re.compile(r"\b(\d+)\s+([ap])\s+m\b", re.IGNORECASE)


def build_time_expression_patterns(language: str = "en") -> list[re.Pattern[str]]:
    """Build the time expression patterns for various time formats."""
    return [
        # Context with time: "meet at three thirty"
        re.compile(
            r"""
            \b                              # Word boundary
            (meet\ at|at)                   # Context phrase
            \s+                             # Space
            (one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)  # Hour
            \s+                             # Space
            (oh\s+)?                        # Optional "oh" for minutes
            (zero|oh|one|two|three|four|five|six|seven|eight|nine|ten|
             eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|
             eighteen|nineteen|twenty|thirty|forty|fifty|
             o\'clock|oclock)               # Minutes (specific number words only)
            (?:\s+(AM|PM))?                 # Optional AM/PM
            \b                              # Word boundary
            """,
            re.VERBOSE | re.IGNORECASE,
        ),
        # Direct time: "three thirty PM"
        re.compile(
            r"""
            \b                              # Word boundary
            (one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)  # Hour
            \s+                             # Space
            (\w+)                           # Minutes
            \s+                             # Space
            (AM|PM)                         # AM/PM indicator
            \b                              # Word boundary
            """,
            re.VERBOSE | re.IGNORECASE,
        ),
        # Spoken AM/PM with spaces: "ten a m", "three p m"
        re.compile(
            r"""
            \b                              # Word boundary
            (one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)  # Hour
            \s+                             # Space
            ([ap])\s+m                      # Spoken "a m" or "p m"
            \b                              # Word boundary
            """,
            re.VERBOSE | re.IGNORECASE,
        ),
        # Time without minutes: "at three PM", "at five AM"
        re.compile(
            r"""
            \b                              # Word boundary
            (at)\s+                         # "at " prefix
            (one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)  # Hour
            \s+                             # Space
            (AM|PM)                         # AM/PM indicator
            \b                              # Word boundary
            """,
            re.VERBOSE | re.IGNORECASE,
        ),
        # Direct time without minutes: "three PM", "five AM"
        re.compile(
            r"""
            \b                              # Word boundary
            (one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)  # Hour
            \s+                             # Space
            (AM|PM)                         # AM/PM indicator
            \b                              # Word boundary
            """,
            re.VERBOSE | re.IGNORECASE,
        ),
    ]


# ==============================================================================
# GETTER FUNCTIONS
# ==============================================================================


def get_time_relative_pattern(language: str = "en") -> re.Pattern[str]:
    """Get the time relative pattern for the specified language."""
    return build_time_relative_pattern(language)


def get_time_am_pm_colon_pattern(language: str = "en") -> re.Pattern[str]:
    """Get the time AM/PM colon pattern for the specified language."""
    return build_time_am_pm_colon_pattern(language)


def get_time_am_pm_space_pattern(language: str = "en") -> re.Pattern[str]:
    """Get the time AM/PM space pattern for the specified language."""
    return build_time_am_pm_space_pattern(language)


def get_time_expression_patterns(language: str = "en") -> list[re.Pattern[str]]:
    """Get the time expression patterns for the specified language."""
    return build_time_expression_patterns(language)