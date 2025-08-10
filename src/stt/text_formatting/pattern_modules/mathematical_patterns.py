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

from ..pattern_cache import cached_pattern
from ..constants import get_nested_resource
from stt.core.config import setup_logging

logger = setup_logging(__name__)


# ==============================================================================
# MATHEMATICAL CONSTANTS
# ==============================================================================

def get_mathematical_operators(language: str = "en") -> list[str]:
    """Get mathematical operators from resources with fallback."""
    try:
        operations_dict = get_nested_resource(language, "spoken_keywords", "mathematical", "operations")
        return list(operations_dict.keys())
    except (KeyError, ValueError) as e:
        logger.debug(f"Failed to load math operators from resources for {language}: {e}")
        # Fallback to hardcoded operators
        return ["plus", "minus", "times", "divided by", "over", "equals"]

def get_mathematical_constants(language: str = "en") -> list[str]:
    """Get mathematical constants from resources with fallback."""
    try:
        constants_dict = get_nested_resource(language, "spoken_keywords", "mathematical", "constants")
        return list(constants_dict.keys())
    except (KeyError, ValueError) as e:
        logger.debug(f"Failed to load math constants from resources for {language}: {e}")
        # Fallback to hardcoded constants
        return ["pi", "e", "infinity", "inf"]


# ==============================================================================
# MATHEMATICAL PATTERN BUILDERS
# ==============================================================================


@cached_pattern
def build_complex_math_expression_pattern(language: str = "en") -> re.Pattern[str]:
    """Build the complex mathematical expression pattern."""
    # Get operators from resources
    operators = get_mathematical_operators(language)
    
    # Extract basic operators for pattern building
    basic_ops = []
    power_ops = []
    equals_ops = []
    
    for op in operators:
        # Simple classification based on common patterns
        if "squared" in op or "cubed" in op or "power" in op:
            power_ops.append(re.escape(op))
        elif "equals" in op or op == "is":
            equals_ops.append(re.escape(op))
        else:
            basic_ops.append(re.escape(op))
    
    # Build pattern components
    basic_ops_pattern = "|".join(basic_ops) if basic_ops else "plus|minus|times|divided\\ by|over"
    power_ops_pattern = "|".join(power_ops) if power_ops else "squared?|cubed?"
    equals_pattern = "|".join(equals_ops) if equals_ops else "equals?"
    
    return re.compile(
        rf"""
        \b                                  # Word boundary
        (?:                                 # First alternative: operation chains
            \w+                             # Variable or number
            \s+                             # Space
            (?:{basic_ops_pattern})         # Operator (from resources)
            \s+                             # Space
            \w+                             # Variable or number
            (?:\s+(?:{power_ops_pattern}))?     # Optional power on second operand
            (?:                             # Optional continuation
                \s+                         # Space
                (?:times|{equals_pattern})           # Additional operator
                \s+                         # Space
                \w+                         # Variable or number
                (?:\s+(?:{power_ops_pattern}))?  # Optional power
            )?                              # Optional continuation
            |                               # OR
            \w+                             # Variable
            \s+{equals_pattern}\s+                   # " equals "
            \w+                             # Value
            (?:                             # Optional mathematical operations
                \s+                         # Space
                (?:                         # Mathematical terms
                    {basic_ops_pattern}|
                    {power_ops_pattern}
                )
                (?:\s+\w+)?                 # Optional additional variable
            )*                              # Zero or more operations
            |                               # OR
            \w+                             # Variable
            \s+                             # Space
            (?:{power_ops_pattern})             # Simple power expressions
        )
        [.!?]?                              # Optional trailing punctuation
        """,
        re.VERBOSE | re.IGNORECASE,
    )


@cached_pattern
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


@cached_pattern
def build_number_constant_pattern(language: str = "en") -> re.Pattern[str]:
    """Build the number + mathematical constant pattern (e.g., 'two pi', 'three e')."""
    # Get constants from resources
    constants = get_mathematical_constants(language)
    constants_pattern = "|".join(re.escape(c) for c in constants)
    
    return re.compile(
        rf"""
        \b                                  # Word boundary
        (?:one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|
        thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty|
        thirty|forty|fifty|sixty|seventy|eighty|ninety|hundred|thousand|
        million|billion|trillion|\d+)       # Number words or digits
        \s+                                 # Space
        (?:{constants_pattern})             # Mathematical constants (from resources)
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


# Maintain backward compatibility
MATH_OPERATORS = get_mathematical_operators("en")

def get_math_operators(language: str = "en") -> list[str]:
    """Get the list of mathematical operators (use resource-based loader)."""
    return get_mathematical_operators(language)