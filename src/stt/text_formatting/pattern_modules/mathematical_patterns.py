#!/usr/bin/env python3
"""
Mathematical expression patterns for text formatting.

This module contains mathematical expression patterns including complex math,
simple math operations, and mathematical constants used throughout the text
formatting system.
"""
from __future__ import annotations

import re
from typing import Pattern


# ==============================================================================
# MATHEMATICAL CONSTANTS
# ==============================================================================

# Mathematical operators
MATH_OPERATORS = ["plus", "minus", "times", "divided by", "over", "equals"]


# ==============================================================================
# MATHEMATICAL PATTERN BUILDERS
# ==============================================================================


def build_complex_math_expression_pattern(language: str = "en") -> re.Pattern[str]:
    """Build the complex mathematical expression pattern."""
    return re.compile(
        r"""
        \b                                  # Word boundary
        (?:                                 # First alternative: operation chains
            \w+                             # Variable or number
            \s+                             # Space
            (?:plus|minus|times|divided\ by|over)  # Operator
            \s+                             # Space
            \w+                             # Variable or number
            (?:\s+(?:squared?|cubed?))?     # Optional power on second operand
            (?:                             # Optional continuation
                \s+                         # Space
                (?:times|equals?)           # Additional operator
                \s+                         # Space
                \w+                         # Variable or number
                (?:\s+(?:squared?|cubed?))?  # Optional power
            )?                              # Optional continuation
            |                               # OR
            \w+                             # Variable
            \s+equals?\s+                   # " equals "
            \w+                             # Value
            (?:                             # Optional mathematical operations
                \s+                         # Space
                (?:                         # Mathematical terms
                    plus|minus|times|
                    divided\ by|over|
                    squared?|cubed?
                )
                (?:\s+\w+)?                 # Optional additional variable
            )*                              # Zero or more operations
            |                               # OR
            \w+                             # Variable
            \s+                             # Space
            (?:squared?|cubed?)             # Simple power expressions
        )
        [.!?]?                              # Optional trailing punctuation
        """,
        re.VERBOSE | re.IGNORECASE,
    )


def build_simple_math_expression_pattern(language: str = "en") -> re.Pattern[str]:
    """Build the simple mathematical expression pattern."""
    return re.compile(
        r"""
        \b                                  # Word boundary
        (?:                                 # Non-capturing group for first operand
            (?:zero|one|two|three|four|five|six|seven|eight|nine|ten|
               eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|
               eighteen|nineteen|twenty|thirty|forty|fifty|sixty|seventy|
               eighty|ninety|hundred|thousand|million|billion)
            |                               # OR
            \d+                             # Digits
            |                               # OR
            [a-zA-Z]                        # Single letter variable
        )
        \s+                                 # Space
        (?:times|divided\ by|over|slash)   # Mathematical operator
        \s+                                 # Space
        (?:                                 # Non-capturing group for second operand
            (?:zero|one|two|three|four|five|six|seven|eight|nine|ten|
               eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|
               eighteen|nineteen|twenty|thirty|forty|fifty|sixty|seventy|
               eighty|ninety|hundred|thousand|million|billion)
            |                               # OR
            \d+                             # Digits
            |                               # OR
            [a-zA-Z]                        # Single letter variable
        )
        (?:\s|$|[.!?])                      # Followed by space, end, or punctuation
        """,
        re.VERBOSE | re.IGNORECASE,
    )


def build_number_constant_pattern(language: str = "en") -> re.Pattern[str]:
    """Build the number + mathematical constant pattern (e.g., 'two pi', 'three e')."""
    return re.compile(
        r"""
        \b                                  # Word boundary
        (?:one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|
        thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty|
        thirty|forty|fifty|sixty|seventy|eighty|ninety|hundred|thousand|
        million|billion|trillion|\d+)       # Number words or digits
        \s+                                 # Space
        (?:pi|e|infinity|inf)               # Mathematical constants
        \b                                  # Word boundary
        [.!?]?                              # Optional trailing punctuation
        """,
        re.VERBOSE | re.IGNORECASE,
    )


# ==============================================================================
# GETTER FUNCTIONS
# ==============================================================================


def get_complex_math_expression_pattern(language: str = "en") -> re.Pattern[str]:
    """Get the complex math expression pattern for the specified language."""
    return build_complex_math_expression_pattern(language)


def get_simple_math_expression_pattern(language: str = "en") -> re.Pattern[str]:
    """Get the simple math expression pattern for the specified language."""
    return build_simple_math_expression_pattern(language)


def get_number_constant_pattern(language: str = "en") -> re.Pattern[str]:
    """Get the number constant pattern for the specified language."""
    return build_number_constant_pattern(language)


def get_math_operators() -> list[str]:
    """Get the list of mathematical operators."""
    return MATH_OPERATORS.copy()