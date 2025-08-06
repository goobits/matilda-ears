#!/usr/bin/env python3
"""
Financial and currency patterns for text formatting.

This module contains currency-related patterns including dollar and cents patterns
used throughout the text formatting system.
"""
from __future__ import annotations

import re
from typing import Pattern


# ==============================================================================
# CURRENCY PATTERN BUILDERS
# ==============================================================================


def build_dollar_pattern(language: str = "en") -> re.Pattern[str]:
    """Build the dollar pattern for currency detection."""
    return re.compile(
        r"\b(?:(?:one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|"
        r"thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty|"
        r"thirty|forty|fifty|sixty|seventy|eighty|ninety|hundred|thousand|million|"
        r"billion|trillion)\s+)*dollars?\b",
        re.IGNORECASE,
    )


def build_cents_pattern(language: str = "en") -> re.Pattern[str]:
    """Build the cents pattern for currency detection."""
    return re.compile(
        r"\b(?:(?:one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|"
        r"thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty|"
        r"thirty|forty|fifty|sixty|seventy|eighty|ninety|hundred)\s+)*cents?\b",
        re.IGNORECASE,
    )


# ==============================================================================
# GETTER FUNCTIONS
# ==============================================================================


def get_dollar_pattern(language: str = "en") -> re.Pattern[str]:
    """Get the dollar pattern for the specified language."""
    return build_dollar_pattern(language)


def get_cents_pattern(language: str = "en") -> re.Pattern[str]:
    """Get the cents pattern for the specified language."""
    return build_cents_pattern(language)