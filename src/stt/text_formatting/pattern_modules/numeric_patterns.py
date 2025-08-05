#!/usr/bin/env python3
"""
Numeric-related regular expression patterns for text formatting.

This module contains all number, mathematical, currency, time, and phone patterns
used throughout the text formatting system, organized logically and using verbose
formatting for readability and maintainability.

All patterns use re.VERBOSE flag where beneficial and include detailed comments
explaining each component.
"""
from __future__ import annotations

import re
from typing import Pattern

from ..common import NumberParser
from ..constants import get_resources


# ==============================================================================
# NUMERIC CONSTANTS
# ==============================================================================

# Number words for speech recognition
NUMBER_WORDS = [
    "zero",
    "one",
    "two",
    "three",
    "four",
    "five",
    "six",
    "seven",
    "eight",
    "nine",
    "ten",
    "eleven",
    "twelve",
    "thirteen",
    "fourteen",
    "fifteen",
    "sixteen",
    "seventeen",
    "eighteen",
    "nineteen",
    "twenty",
    "thirty",
    "forty",
    "fifty",
    "sixty",
    "seventy",
    "eighty",
    "ninety",
    "hundred",
    "thousand",
    "million",
    "billion",
    "trillion",
]

# Mathematical operators
MATH_OPERATORS = ["plus", "minus", "times", "divided by", "over", "equals"]


# ==============================================================================
# ORDINAL AND FRACTION PATTERN BUILDERS
# ==============================================================================


def build_ordinal_pattern(language: str = "en") -> re.Pattern[str]:
    """Build the spoken ordinal pattern for the specified language."""
    # For now, use English patterns. Could be extended for other languages.
    return re.compile(
        r"\b(first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth|"
        r"eleventh|twelfth|thirteenth|fourteenth|fifteenth|sixteenth|seventeenth|"
        r"eighteenth|nineteenth|twentieth|twenty[-\s]?first|twenty[-\s]?second|"
        r"twenty[-\s]?third|twenty[-\s]?fourth|twenty[-\s]?fifth|twenty[-\s]?sixth|"
        r"twenty[-\s]?seventh|twenty[-\s]?eighth|twenty[-\s]?ninth|thirtieth|"
        r"thirty[-\s]?first|fortieth|fiftieth|sixtieth|seventieth|eightieth|"
        r"ninetieth|hundredth|thousandth)\b",
        re.IGNORECASE,
    )


def build_fraction_pattern(language: str = "en") -> re.Pattern[str]:
    """Build the spoken fraction pattern for the specified language."""
    return re.compile(
        r"\b(one|two|three|four|five|six|seven|eight|nine|ten)\s+"
        r"(half|halves|third|thirds|quarter|quarters|fourth|fourths|fifth|fifths|"
        r"sixth|sixths|seventh|sevenths|eighth|eighths|ninth|ninths|tenth|tenths)\b",
        re.IGNORECASE,
    )


def build_compound_fraction_pattern(language: str = "en") -> re.Pattern[str]:
    """Build the compound fraction pattern for mixed numbers like 'one and one half'."""
    return re.compile(
        r"\b(one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)\s+"
        r"and\s+"
        r"(one|two|three|four|five|six|seven|eight|nine|ten)\s+"
        r"(half|halves|third|thirds|quarter|quarters|fourth|fourths|fifth|fifths|"
        r"sixth|sixths|seventh|sevenths|eighth|eighths|ninth|ninths|tenth|tenths)\b",
        re.IGNORECASE,
    )


def build_numeric_range_pattern(language: str = "en") -> re.Pattern[str]:
    """Build the numeric range pattern for ranges like 'one to ten'."""
    # Get the number words from a single source of truth
    _number_parser_instance = NumberParser(language)
    _number_words_pattern = "(?:" + "|".join(_number_parser_instance.all_number_words) + ")"

    # Define a reusable pattern for a sequence of one or more number words
    number_word_sequence = f"{_number_words_pattern}(?:\\s+{_number_words_pattern})*"

    # Build the range pattern from components - much more readable and maintainable
    return re.compile(
        rf"""
        \b                      # Word boundary
        (                       # Capture group 1: Start of range
            {number_word_sequence}
        )
        \s+to\s+                # The word "to"
        (                       # Capture group 2: End of range
            {number_word_sequence}
        )
        \b                      # Word boundary
        """,
        re.IGNORECASE | re.VERBOSE,
    )


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
# PHONE AND TIME PATTERN BUILDERS
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


def get_ordinal_pattern(language: str = "en") -> re.Pattern[str]:
    """Get the ordinal pattern for the specified language."""
    return build_ordinal_pattern(language)


def get_fraction_pattern(language: str = "en") -> re.Pattern[str]:
    """Get the fraction pattern for the specified language."""
    return build_fraction_pattern(language)


def get_compound_fraction_pattern(language: str = "en") -> re.Pattern[str]:
    """Get the compound fraction pattern for the specified language."""
    return build_compound_fraction_pattern(language)


def get_numeric_range_pattern(language: str = "en") -> re.Pattern[str]:
    """Get the numeric range pattern for the specified language."""
    return build_numeric_range_pattern(language)


def get_complex_math_expression_pattern(language: str = "en") -> re.Pattern[str]:
    """Get the complex math expression pattern for the specified language."""
    return build_complex_math_expression_pattern(language)


def get_simple_math_expression_pattern(language: str = "en") -> re.Pattern[str]:
    """Get the simple math expression pattern for the specified language."""
    return build_simple_math_expression_pattern(language)


def get_number_constant_pattern(language: str = "en") -> re.Pattern[str]:
    """Get the number constant pattern for the specified language."""
    return build_number_constant_pattern(language)


def get_dollar_pattern(language: str = "en") -> re.Pattern[str]:
    """Get the dollar pattern for the specified language."""
    return build_dollar_pattern(language)


def get_cents_pattern(language: str = "en") -> re.Pattern[str]:
    """Get the cents pattern for the specified language."""
    return build_cents_pattern(language)


def get_spoken_phone_pattern(language: str = "en") -> re.Pattern[str]:
    """Get the spoken phone pattern for the specified language."""
    return build_spoken_phone_pattern(language)


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


# ==============================================================================
# DEFAULT PATTERNS (BACKWARD COMPATIBILITY)
# ==============================================================================

# Default English patterns for backward compatibility
SPOKEN_ORDINAL_PATTERN = build_ordinal_pattern("en")
SPOKEN_FRACTION_PATTERN = build_fraction_pattern("en")
SPOKEN_COMPOUND_FRACTION_PATTERN = build_compound_fraction_pattern("en")
SPOKEN_NUMERIC_RANGE_PATTERN = build_numeric_range_pattern("en")
COMPLEX_MATH_EXPRESSION_PATTERN = build_complex_math_expression_pattern("en")
SIMPLE_MATH_EXPRESSION_PATTERN = build_simple_math_expression_pattern("en")
NUMBER_CONSTANT_PATTERN = build_number_constant_pattern("en")
DOLLAR_PATTERN = build_dollar_pattern("en")
CENTS_PATTERN = build_cents_pattern("en")
SPOKEN_PHONE_PATTERN = build_spoken_phone_pattern("en")
SPOKEN_TIME_RELATIVE_PATTERN = build_time_relative_pattern("en")
TIME_AM_PM_COLON_PATTERN = build_time_am_pm_colon_pattern("en")
TIME_AM_PM_SPACE_PATTERN = build_time_am_pm_space_pattern("en")
TIME_EXPRESSION_PATTERNS = build_time_expression_patterns("en")

# Number word sequence helpers for backward compatibility
_number_parser_instance = NumberParser("en")
_number_words_pattern = "(?:" + "|".join(_number_parser_instance.all_number_words) + ")"
NUMBER_WORD_SEQUENCE = f"{_number_words_pattern}(?:\\s+{_number_words_pattern})*"


# ==============================================================================
# UTILITY FUNCTIONS
# ==============================================================================


def get_compiled_numeric_pattern(pattern_name: str) -> Pattern | None:
    """Get a pre-compiled numeric pattern by name."""
    pattern_map = {
        "ordinal": SPOKEN_ORDINAL_PATTERN,
        "fraction": SPOKEN_FRACTION_PATTERN,
        "compound_fraction": SPOKEN_COMPOUND_FRACTION_PATTERN,
        "numeric_range": SPOKEN_NUMERIC_RANGE_PATTERN,
        "complex_math": COMPLEX_MATH_EXPRESSION_PATTERN,
        "simple_math": SIMPLE_MATH_EXPRESSION_PATTERN,
        "number_constant": NUMBER_CONSTANT_PATTERN,
        "dollar": DOLLAR_PATTERN,
        "cents": CENTS_PATTERN,
        "spoken_phone": SPOKEN_PHONE_PATTERN,
        "time_relative": SPOKEN_TIME_RELATIVE_PATTERN,
        "time_am_pm_colon": TIME_AM_PM_COLON_PATTERN,
        "time_am_pm_space": TIME_AM_PM_SPACE_PATTERN,
    }
    return pattern_map.get(pattern_name)


def get_number_words() -> list[str]:
    """Get the list of number words."""
    return NUMBER_WORDS.copy()


def get_math_operators() -> list[str]:
    """Get the list of mathematical operators."""
    return MATH_OPERATORS.copy()


def get_number_word_sequence() -> str:
    """Get the number word sequence pattern string."""
    return NUMBER_WORD_SEQUENCE


def create_number_parser_instance(language: str = "en") -> NumberParser:
    """Create a NumberParser instance for the specified language."""
    return NumberParser(language)