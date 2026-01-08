#!/usr/bin/env python3
"""Dynamic i18n-aware pattern builders.

This module contains all functions that build regex patterns dynamically
based on language-specific resources. These patterns support internationalization.
"""

import re
from re import Pattern

from .components import COMMON_TLDS


# ==============================================================================
# NUMERIC RANGE PATTERN
# ==============================================================================

def _build_number_word_sequence() -> str:
    """Build the number word sequence pattern from NumberParser."""
    from ..common import NumberParser

    # Use English as default for pattern building
    number_parser_instance = NumberParser("en")
    # Sort by length (descending) to match longer words first
    sorted_number_words = sorted(number_parser_instance.all_number_words, key=len, reverse=True)
    number_words_pattern = "(?:" + "|".join(re.escape(w) for w in sorted_number_words) + ")"

    # Define a reusable pattern for a sequence of one or more number words
    # Allow "and", "point", "dot" within the sequence
    return f"{number_words_pattern}(?:\\s+(?:and\\s+|point\\s+|dot\\s+)?{number_words_pattern})*"


# Build the number word sequence pattern at module load time
NUMBER_WORD_SEQUENCE = _build_number_word_sequence()

# Build the range pattern from components
SPOKEN_NUMERIC_RANGE_PATTERN = re.compile(
    rf"""
    \b                      # Word boundary
    (                       # Capture group 1: Start of range
        {NUMBER_WORD_SEQUENCE}
    )
    \s+(?:to|through)\s+    # The word "to" or "through"
    (                       # Capture group 2: End of range
        {NUMBER_WORD_SEQUENCE}
    )
    \b                      # Word boundary
    """,
    re.IGNORECASE | re.VERBOSE,
)


# ==============================================================================
# WEB-RELATED PATTERN BUILDERS
# ==============================================================================


def build_spoken_url_pattern(language: str = "en") -> Pattern:
    """Builds the spoken URL pattern dynamically from keywords in constants."""
    from ..constants import get_resources
    from ..common import NumberParser

    # Get resources for the specified language
    resources = get_resources(language)
    url_keywords = resources["spoken_keywords"]["url"]

    # Get keyword patterns from URL_KEYWORDS
    dot_keywords = [k for k, v in url_keywords.items() if v == "."]
    slash_keywords = [k for k, v in url_keywords.items() if v == "/"]
    question_mark_keywords = [k for k, v in url_keywords.items() if v == "?"]
    colon_keywords = [k for k, v in url_keywords.items() if v == ":"]

    # Create alternation patterns for each keyword type (inline implementation)
    # Sort by length to match longer phrases first
    dot_keywords_sorted = sorted(dot_keywords, key=len, reverse=True)
    slash_keywords_sorted = sorted(slash_keywords, key=len, reverse=True)
    question_mark_keywords_sorted = sorted(question_mark_keywords, key=len, reverse=True)
    colon_keywords_sorted = sorted(colon_keywords, key=len, reverse=True)

    dot_escaped = [re.escape(k) for k in dot_keywords_sorted] + [r"\."]
    dot_pattern = "|".join(dot_escaped)

    slash_escaped = [re.escape(k) for k in slash_keywords_sorted]
    slash_pattern = "|".join(slash_escaped)

    question_mark_escaped = [re.escape(k) for k in question_mark_keywords_sorted]
    question_mark_pattern = "|".join(question_mark_escaped)

    colon_escaped = [re.escape(k) for k in colon_keywords_sorted]
    colon_pattern = "|".join(colon_escaped)

    # Create number words pattern from language-specific resources
    number_parser_instance = NumberParser(language)
    number_words = list(number_parser_instance.all_number_words)
    number_words_escaped = [re.escape(word) for word in number_words]
    number_words_pattern = "|".join(number_words_escaped)

    # Build the complete pattern using the dynamic keyword patterns
    pattern_str = rf"""
    \b                                  # Word boundary
    (                                   # Capture group 1: full URL
        (?:                             # Non-capturing group for subdomains
            (?:                         # Domain part alternatives
                # Option 1: Alphanumeric word followed by number words (e.g. "server one")
                [a-zA-Z0-9-]+\s+(?:{number_words_pattern})(?:\s+(?:{number_words_pattern}))*
            |                           # OR
                # Option 2: Just alphanumeric domain part
                [a-zA-Z0-9-]+
            |                           # OR
                # Option 3: Just number words
                (?:{number_words_pattern})
                (?:\s+(?:{number_words_pattern}))*
            )
            (?:                         # Non-capturing group for dot
                \s+(?:{dot_pattern})\s+ # Spoken "dot" or regular dot
            )
        )*                              # Zero or more subdomains
        (?:                             # Main domain name part alternatives
            [a-zA-Z0-9-]+               # Alphanumeric domain part
        |                               # OR
            (?:{number_words_pattern})
            (?:\s+(?:{number_words_pattern}))*      # Multiple number words
        )
        (?:                             # Non-capturing group for dot
            \s+(?:{dot_pattern})\s+     # Spoken "dot" or regular dot
        )
        (?:{"|".join(COMMON_TLDS)})     # TLD alternatives
        (?:                             # Optional path part
            \s+(?:{slash_pattern})\s+   # Spoken "slash"
            [a-zA-Z0-9-]+               # Path segment
            (?:                         # Additional path segments
                \s+[a-zA-Z0-9-]+        # More path parts
            )*                          # Zero or more additional segments
        )*                              # Zero or more path groups
        (?:                             # Optional query string
            \s+(?:{question_mark_pattern})\s+ # Spoken "question mark"
            .+                          # Query parameters
        )?                              # Optional query string
        (?:                             # Optional port part
            \s+(?:{colon_pattern})\s+   # " colon "
            (?:{number_words_pattern})  # Port number (number words)
            (?:\s+(?:{number_words_pattern}))* # Additional number words
        )?
    )
    ([.!?]?)                            # Capture group 2: optional punctuation
    """
    return re.compile(pattern_str, re.VERBOSE | re.IGNORECASE)


def get_spoken_url_pattern(language: str = "en") -> Pattern:
    """Get the spoken URL pattern for the specified language."""
    return build_spoken_url_pattern(language)


def build_spoken_email_pattern(language: str = "en") -> Pattern:
    """Builds the spoken email pattern dynamically for the specified language."""
    from ..constants import get_resources

    resources = get_resources(language)
    url_keywords = resources["spoken_keywords"]["url"]

    # Get keywords for email patterns
    at_keywords = [k for k, v in url_keywords.items() if v == "@"]
    dot_keywords = [k for k, v in url_keywords.items() if v == "."]

    # Create pattern strings - sort by length to match longer phrases first
    at_keywords_sorted = sorted(at_keywords, key=len, reverse=True)
    dot_keywords_sorted = sorted(dot_keywords, key=len, reverse=True)
    at_pattern = "|".join(re.escape(k) for k in at_keywords_sorted)
    dot_pattern = "|".join(re.escape(k) for k in dot_keywords_sorted)

    # Email action words from resources or defaults
    email_actions = resources.get("context_words", {}).get("email_actions", ["email", "contact", "write to", "send to"])
    email_actions_sorted = sorted(email_actions, key=len, reverse=True)
    action_pattern = "|".join(re.escape(action) for action in email_actions_sorted)

    # More restrictive pattern that doesn't capture action phrases
    pattern_str = rf"""
    (?:                                 # Overall non-capturing group
        # Pattern 1: With action prefix (e.g., "send to admin at...")
        (?:^|(?<=\s))                   # Start of string or preceded by space
        (?:                             # Non-capturing group for action phrase
            (?:{action_pattern})        # Action word
            (?:\s+(?:the|a|an))?\s+     # Optional article
            (?:\w+\s+)?                 # Optional object (e.g., "report")
            (?:to|for)\s+               # Preposition
        )
        (                               # Username (capture group 1)
            [a-zA-Z][a-zA-Z0-9]*        # Simple username starting with letter
            (?:                         # Optional parts
                (?:\s+(?:underscore|dash)\s+|[._-])  # Separator
                [a-zA-Z0-9]+            # Additional part
            )*                          # Zero or more additional parts
        )
        \s+(?:{at_pattern})\s+          # "at" keyword
        (                               # Domain (capture group 2)
            [a-zA-Z0-9]+                # Domain part starting with alphanumeric
            (?:\s+[a-zA-Z0-9]+)*        # Optional additional parts (for "server two")
            (?:                         # Repeated domain parts
                \s+(?:{dot_pattern})\s+ # "dot" keyword
                [a-zA-Z0-9]+            # Next domain part
                (?:\s+[a-zA-Z0-9]+)*    # Optional additional parts
            )+                          # One or more dots
        )
        (?=\s|$|[.!?])                  # End boundary
    |                                   # OR
        # Pattern 2: Without action prefix (e.g., "admin at...")
        (?:^|(?<=\s))                   # Start of string or preceded by space
        (?!(?:the|a|an|this|that|these|those|my|your|our|their|his|her|its|to|for|from|with|by)\s+)  # Not articles/determiners/prepositions
        (                               # Username (capture group 3)
            [a-zA-Z][a-zA-Z0-9]*        # Simple username starting with letter
            (?:                         # Optional parts
                (?:\s+(?:underscore|dash)\s+|[._-])  # Separator
                [a-zA-Z0-9]+            # Additional part
            )*                          # Zero or more additional parts
        )
        \s+(?:{at_pattern})\s+          # "at" keyword
        (                               # Domain (capture group 4)
            [a-zA-Z0-9]+                # Domain part starting with alphanumeric
            (?:\s+[a-zA-Z0-9]+)*        # Optional additional parts (for "server two")
            (?:                         # Repeated domain parts
                \s+(?:{dot_pattern})\s+ # "dot" keyword
                [a-zA-Z0-9]+            # Next domain part
                (?:\s+[a-zA-Z0-9]+)*    # Optional additional parts
            )+                          # One or more dots
        )
        (?=\s|$|[.!?])                  # End boundary
    )
    """
    return re.compile(pattern_str, re.VERBOSE | re.IGNORECASE)


def get_spoken_email_pattern(language: str = "en") -> Pattern:
    """Get the spoken email pattern for the specified language."""
    return build_spoken_email_pattern(language)


def build_spoken_protocol_pattern(language: str = "en") -> Pattern:
    """Builds the spoken protocol pattern dynamically for the specified language."""
    from ..constants import get_resources

    resources = get_resources(language)
    url_keywords = resources["spoken_keywords"]["url"]

    # Get keywords
    colon_keywords = [k for k, v in url_keywords.items() if v == ":"]
    slash_keywords = [k for k, v in url_keywords.items() if v == "/"]
    dot_keywords = [k for k, v in url_keywords.items() if v == "."]
    question_keywords = [k for k, v in url_keywords.items() if v == "?"]

    # Create pattern strings - sort by length to match longer phrases first
    colon_keywords_sorted = sorted(colon_keywords, key=len, reverse=True)
    slash_keywords_sorted = sorted(slash_keywords, key=len, reverse=True)
    dot_keywords_sorted = sorted(dot_keywords, key=len, reverse=True)
    question_keywords_sorted = sorted(question_keywords, key=len, reverse=True)

    colon_pattern = "|".join(re.escape(k) for k in colon_keywords_sorted)
    slash_pattern = "|".join(re.escape(k) for k in slash_keywords_sorted)
    dot_pattern = "|".join(re.escape(k) for k in dot_keywords_sorted)
    question_pattern = "|".join(re.escape(k) for k in question_keywords_sorted) if question_keywords_sorted else "question\\s+mark"

    pattern_str = rf"""
    \b                                  # Word boundary
    (https?|ftp)                        # Protocol
    \s+(?:{colon_pattern})\s+(?:{slash_pattern})\s+(?:{slash_pattern})\s+  # Language-specific " colon slash slash "
    (                                   # Capture group: domain (supports both spoken and normal formats)
        (?:                             # Non-capturing group for spoken domain
            [a-zA-Z0-9-]+               # Domain name part
            (?:                         # Optional spoken dots
                \s+(?:{dot_pattern})\s+ # Language-specific " dot "
                [a-zA-Z0-9-]+           # Domain part after dot
            )+                          # One or more spoken dots
        )
        |                               # OR
        (?:                             # Non-capturing group for normal domain
            [a-zA-Z0-9.-]+              # Domain characters
            (?:\.[a-zA-Z]{{2,}})?       # Optional TLD
        )
    )
    (                                   # Capture group: path and query
        (?:                             # Optional path segments
            \s+(?:{slash_pattern})\s+   # Language-specific " slash "
            [^?\s]+                     # Path content (not ? or space)
        )*                              # Zero or more path segments
        (?:                             # Optional query string
            \s+(?:{question_pattern})\s+  # Language-specific " question mark "
            .+                          # Query content
        )?                              # Optional query
    )
    """
    return re.compile(pattern_str, re.VERBOSE | re.IGNORECASE)


def get_spoken_protocol_pattern(language: str = "en") -> Pattern:
    """Get the spoken protocol pattern for the specified language."""
    return build_spoken_protocol_pattern(language)


def build_spoken_ip_pattern(language: str = "en") -> Pattern:
    """Builds the spoken IP address pattern dynamically from keywords."""
    from ..constants import get_resources
    from ..common import NumberParser

    # Get resources for the specified language
    resources = get_resources(language)
    url_keywords = resources["spoken_keywords"]["url"]

    # Get dot and colon keywords
    dot_keywords = [k for k, v in url_keywords.items() if v == "."]
    dot_keywords_sorted = sorted(dot_keywords, key=len, reverse=True)
    dot_escaped = [re.escape(k) for k in dot_keywords_sorted]
    dot_pattern = "|".join(dot_escaped)

    colon_keywords = [k for k, v in url_keywords.items() if v == ":"]
    colon_keywords_sorted = sorted(colon_keywords, key=len, reverse=True)
    colon_escaped = [re.escape(k) for k in colon_keywords_sorted]
    colon_pattern = "|".join(colon_escaped)

    # Create number words pattern from language-specific resources
    number_parser_instance = NumberParser(language)
    number_words = list(number_parser_instance.all_number_words)
    number_words_escaped = [re.escape(word) for word in number_words]
    number_words_pattern = "|".join(number_words_escaped)

    # Pattern for an IP octet (digits or number words)
    octet_pattern = rf"""
    (?:
        \d+                             # Digits
        |
        (?:{number_words_pattern})      # Single number word
        (?:                             # Optional additional number words
            \s+(?:{number_words_pattern})
        )*
    )
    """

    pattern_str = rf"""
    \b                                  # Word boundary
    (                                   # Capture group 1: full IP with optional port
        {octet_pattern}
        \s+(?:{dot_pattern})\s+         # " dot "
        {octet_pattern}
        \s+(?:{dot_pattern})\s+         # " dot "
        {octet_pattern}
        \s+(?:{dot_pattern})\s+         # " dot "
        {octet_pattern}
        (?:                             # Optional port part
            \s+(?:{colon_pattern})\s+   # " colon "
            {octet_pattern}             # Port number (reuses octet pattern which matches numbers)
        )?
    )
    \b                                  # Word boundary
    """
    return re.compile(pattern_str, re.VERBOSE | re.IGNORECASE)


def get_spoken_ip_pattern(language: str = "en") -> Pattern:
    """Get the spoken IP pattern for the specified language."""
    return build_spoken_ip_pattern(language)


def build_port_number_pattern(language: str = "en") -> Pattern:
    """Builds the port number pattern dynamically from keywords in constants."""
    from ..constants import get_resources
    from ..common import NumberParser

    # Get resources for the specified language
    resources = get_resources(language)
    url_keywords = resources["spoken_keywords"]["url"]

    # Get colon keywords from URL_KEYWORDS
    colon_keywords = [k for k, v in url_keywords.items() if v == ":"]

    # Create alternation pattern for colon - sort by length to match longer phrases first
    colon_keywords_sorted = sorted(colon_keywords, key=len, reverse=True)
    colon_escaped = [re.escape(k) for k in colon_keywords_sorted]
    colon_pattern = "|".join(colon_escaped)

    # Create number words pattern from language-specific resources
    number_parser_instance = NumberParser(language)
    number_words = list(number_parser_instance.all_number_words)
    number_words_escaped = [re.escape(word) for word in number_words]
    number_words_pattern = "|".join(number_words_escaped)

    # Build the complete pattern using the dynamic keyword patterns
    pattern_str = rf"""
    \b                                  # Word boundary
    (localhost|[\w.-]+)                 # Hostname (capture group 1)
    \s+(?:{colon_pattern})\s+           # Spoken "colon"
    (                                   # Capture group 2: port number (allows compound numbers)
        (?:                             # Non-capturing group for number words
            {number_words_pattern}
        )
        (?:                             # Additional number words
            \s+                         # Space separator
            (?:                         # Another number word
                {number_words_pattern}
            )
        )*                              # Zero or more additional number words
    )
    (?=\s|$|/)                          # Lookahead: followed by space, end, or slash (not word boundary)
    """
    return re.compile(pattern_str, re.VERBOSE | re.IGNORECASE)


def get_port_number_pattern(language: str = "en") -> Pattern:
    """Get the port number pattern for the specified language."""
    return build_port_number_pattern(language)


# ==============================================================================
# CODE-RELATED PATTERN BUILDERS
# ==============================================================================


def get_slash_command_pattern(language: str = "en") -> Pattern:
    """Builds the slash command pattern dynamically."""
    from ..constants import get_resources

    resources = get_resources(language)
    code_keywords = resources.get("spoken_keywords", {}).get("code", {})
    slash_keywords = [k for k, v in code_keywords.items() if v == "/"]
    slash_keywords_sorted = sorted(slash_keywords, key=len, reverse=True)
    slash_pattern = "|".join(re.escape(k) for k in slash_keywords_sorted)

    return re.compile(
        rf"""
        \b(?:{slash_pattern})\s+([a-zA-Z][a-zA-Z0-9_-]*)
        """,
        re.VERBOSE | re.IGNORECASE,
    )


def get_underscore_delimiter_pattern(language: str = "en") -> Pattern:
    """Builds the dunder/underscore delimiter pattern dynamically."""
    from ..constants import get_resources

    resources = get_resources(language)
    code_keywords = resources.get("spoken_keywords", {}).get("code", {})
    underscore_keywords = [k for k, v in code_keywords.items() if v == "_"]
    underscore_keywords_sorted = sorted(underscore_keywords, key=len, reverse=True)
    underscore_pattern = "|".join(re.escape(k) for k in underscore_keywords_sorted)

    return re.compile(
        rf"""
        \b((?:{underscore_pattern}\s+)+)
        ([a-zA-Z][\w-]*)
        ((?:\s+{underscore_pattern})+)
        (?=\s|$)
        """,
        re.VERBOSE | re.IGNORECASE,
    )


def get_simple_underscore_pattern(language: str = "en") -> Pattern:
    """Builds the simple underscore variable pattern dynamically."""
    from ..constants import get_resources

    resources = get_resources(language)
    code_keywords = resources.get("spoken_keywords", {}).get("code", {})
    underscore_keywords = [k for k, v in code_keywords.items() if v == "_"]
    underscore_keywords_sorted = sorted(underscore_keywords, key=len, reverse=True)
    underscore_pattern = "|".join(re.escape(k) for k in underscore_keywords_sorted)

    return re.compile(
        rf"""
        \b([\w][\w0-9_-]*)\s+(?:{underscore_pattern})\s+([\w][\w0-9_-]*)\b
        """,
        re.VERBOSE | re.IGNORECASE | re.UNICODE,
    )


def get_long_flag_pattern(language: str = "en") -> Pattern:
    """Builds the long command flag pattern dynamically."""
    from ..constants import get_resources

    resources = get_resources(language)
    code_keywords = resources.get("spoken_keywords", {}).get("code", {})
    dash_keywords = [k for k, v in code_keywords.items() if v == "-"]
    dash_pattern = "|".join(re.escape(k) for k in sorted(dash_keywords, key=len, reverse=True))

    return re.compile(rf"\b(?:{dash_pattern})\s+(?:{dash_pattern})\s+([a-zA-Z][\w-]*(\s+[a-zA-Z][\w-]*)?)", re.IGNORECASE)


def get_short_flag_pattern(language: str = "en") -> Pattern:
    """Builds the short command flag pattern dynamically and safely."""
    from ..constants import get_resources

    resources = get_resources(language)
    code_keywords = resources.get("spoken_keywords", {}).get("code", {})

    # Get all keywords that map to "-"
    dash_keywords = [k for k, v in code_keywords.items() if v == "-"]

    # Sort by length to match longer phrases first (e.g., "dash dash" vs "dash")
    dash_keywords_sorted = sorted(dash_keywords, key=len, reverse=True)

    # Create the pattern without any language-specific if-statements
    dash_pattern = "|".join(re.escape(k) for k in dash_keywords_sorted)

    return re.compile(rf"\b(?:{dash_pattern})\s+([a-zA-Z0-9-]+)\b", re.IGNORECASE)


def get_assignment_pattern(language: str = "en") -> Pattern:
    """Builds the assignment pattern dynamically."""
    from ..constants import get_resources

    resources = get_resources(language)
    code_keywords = resources.get("spoken_keywords", {}).get("code", {})
    equals_keywords = [k for k, v in code_keywords.items() if v == "="]
    equals_keywords_sorted = sorted(equals_keywords, key=len, reverse=True)
    equals_pattern = "|".join(re.escape(k) for k in equals_keywords_sorted)

    return re.compile(
        rf"""
        \b(?:(let|const|var)\s+)?
        ([a-zA-Z_]\w*)\s+(?:{equals_pattern})\s+
        (
            (?!\s*(?:{equals_pattern})) # Not followed by another equals
            .+?
        )
        (?=\s*(?:;|\n|$)|--|\+\+) # Ends at semicolon, newline, end, or other operator
        """,
        re.VERBOSE | re.IGNORECASE,
    )


def build_slash_command_pattern(language: str = "en") -> Pattern:
    """Builds the slash command pattern dynamically from keywords in constants."""
    from ..constants import get_resources

    # Get resources for the specified language
    resources = get_resources(language)
    code_keywords = resources["spoken_keywords"]["code"]

    # Get slash keywords from CODE_KEYWORDS
    slash_keywords = [k for k, v in code_keywords.items() if v == "/"]
    slash_keywords_sorted = sorted(slash_keywords, key=len, reverse=True)
    slash_escaped = [re.escape(k) for k in slash_keywords_sorted]
    slash_pattern = f"(?:{'|'.join(slash_escaped)})"

    return re.compile(
        rf"""
        \b                                  # Word boundary
        {slash_pattern}\s+                  # Slash keyword followed by space
        ([a-zA-Z][a-zA-Z0-9_-]*)           # Command name (starts with letter, can contain letters, numbers, underscore, hyphen)
        \b                                  # Word boundary
        """,
        re.VERBOSE | re.IGNORECASE,
    )


def build_underscore_delimiter_pattern(language: str = "en") -> Pattern:
    """Builds the underscore delimiter pattern dynamically from keywords in constants."""
    from ..constants import get_resources

    # Get resources for the specified language
    resources = get_resources(language)
    code_keywords = resources["spoken_keywords"]["code"]

    # Get underscore keywords from CODE_KEYWORDS
    underscore_keywords = [k for k, v in code_keywords.items() if v == "_"]
    underscore_keywords_sorted = sorted(underscore_keywords, key=len, reverse=True)
    underscore_escaped = [re.escape(k) for k in underscore_keywords_sorted]
    underscore_pattern = f"(?:{'|'.join(underscore_escaped)})"

    return re.compile(
        rf"""
        \b                                  # Word boundary
        ((?:{underscore_pattern}\s+)+)      # One or more underscore keywords followed by space (captured)
        ([a-zA-Z][a-zA-Z0-9_-]*)           # Content (starts with letter, can contain letters, numbers, underscore, hyphen)
        ((?:\s+{underscore_pattern})+)      # One or more space followed by underscore keywords (captured)
        (?=\s|$)                           # Must be followed by space or end of string
        """,
        re.VERBOSE | re.IGNORECASE,
    )


def build_simple_underscore_pattern(language: str = "en") -> Pattern:
    """Builds the simple underscore pattern dynamically from keywords in constants."""
    from ..constants import get_resources

    # Get resources for the specified language
    resources = get_resources(language)
    code_keywords = resources["spoken_keywords"]["code"]

    # Get underscore keywords from CODE_KEYWORDS
    underscore_keywords = [k for k, v in code_keywords.items() if v == "_"]
    underscore_keywords_sorted = sorted(underscore_keywords, key=len, reverse=True)
    underscore_escaped = [re.escape(k) for k in underscore_keywords_sorted]
    underscore_pattern = f"(?:{'|'.join(underscore_escaped)})"

    return re.compile(
        rf"""
        \b                                  # Word boundary
        ([\w][\w0-9_-]*)                   # First word (starts with letter, supports Unicode)
        \s+{underscore_pattern}\s+          # Space, underscore keyword, space
        ([\w][\w0-9_-]*)                   # Second word (starts with letter, supports Unicode)
        \b                                  # Word boundary
        """,
        re.VERBOSE | re.IGNORECASE | re.UNICODE,
    )


def build_long_flag_pattern(language: str = "en") -> Pattern:
    """Builds the long flag pattern dynamically from keywords in constants."""
    from ..constants import get_resources

    # Get resources for the specified language
    resources = get_resources(language)
    code_keywords = resources["spoken_keywords"]["code"]

    # Get dash keywords from CODE_KEYWORDS
    dash_keywords = [k for k, v in code_keywords.items() if v == "-"]
    dash_keywords_sorted = sorted(dash_keywords, key=len, reverse=True)
    dash_escaped = [re.escape(k) for k in dash_keywords_sorted]
    dash_pattern = f"(?:{'|'.join(dash_escaped)})"

    return re.compile(
        rf"\b{dash_pattern}\s+{dash_pattern}\s+([a-zA-Z][a-zA-Z0-9_-]*(?:\s+[a-zA-Z][a-zA-Z0-9_-]*)?)",
        re.IGNORECASE,
    )


def build_short_flag_pattern(language: str = "en") -> Pattern:
    """Builds the short flag pattern dynamically from keywords in constants."""
    from ..constants import get_resources

    # Get resources for the specified language
    resources = get_resources(language)
    code_keywords = resources["spoken_keywords"]["code"]

    # Get dash keywords from CODE_KEYWORDS
    dash_keywords = [k for k, v in code_keywords.items() if v == "-"]
    dash_keywords_sorted = sorted(dash_keywords, key=len, reverse=True)

    # Create the pattern without any language-specific if-statements
    dash_pattern = "|".join(re.escape(k) for k in dash_keywords_sorted)

    return re.compile(rf"\b(?:{dash_pattern})\s+([a-zA-Z0-9-]+)\b", re.IGNORECASE)


def build_assignment_pattern(language: str = "en") -> Pattern:
    """Builds the assignment pattern dynamically from keywords in constants."""
    from ..constants import get_resources

    # Get resources for the specified language
    resources = get_resources(language)
    code_keywords = resources["spoken_keywords"]["code"]

    # Get equals keywords from CODE_KEYWORDS
    equals_keywords = [k for k, v in code_keywords.items() if v == "="]
    equals_keywords_sorted = sorted(equals_keywords, key=len, reverse=True)
    equals_escaped = [re.escape(k) for k in equals_keywords_sorted]
    equals_pattern = f"(?:{'|'.join(equals_escaped)})"

    return re.compile(
        rf"""
        \b                                  # Word boundary
        (?:(let|const|var)\s+)?             # Optional variable declaration keyword (capture group 1)
        ([a-zA-Z_]\w*)                      # Variable name (capture group 2)
        \s+{equals_pattern}\s+              # Space, equals keyword, space
        (?!\s*(?:{equals_pattern}))         # Negative lookahead: not followed by another equals keyword (with optional space for ==)
        (                                   # Value (capture group 3)
            (?:(?!\s+(?:and|or|but|if|when|then|while|unless)\s+).)+?        # Stop at conjunctions
        )
        (?=\s*$|\s*[.!?]|\s+(?:and|or|but|if|when|then|while|unless)\s+|--|\+\+)  # Lookahead: end of string, punctuation, conjunctions, or operators
        """,
        re.VERBOSE | re.IGNORECASE,
    )


# ==============================================================================
# DEFAULT ENGLISH PATTERNS (Backward compatibility)
# ==============================================================================

# Create default English patterns for backward compatibility
SPOKEN_URL_PATTERN = build_spoken_url_pattern("en")
SPOKEN_EMAIL_PATTERN = build_spoken_email_pattern("en")
SPOKEN_PROTOCOL_PATTERN = build_spoken_protocol_pattern("en")
PORT_NUMBER_PATTERN = build_port_number_pattern("en")
SLASH_COMMAND_PATTERN = build_slash_command_pattern("en")
UNDERSCORE_DELIMITER_PATTERN = build_underscore_delimiter_pattern("en")
SIMPLE_UNDERSCORE_PATTERN = build_simple_underscore_pattern("en")
LONG_FLAG_PATTERN = build_long_flag_pattern("en")
SHORT_FLAG_PATTERN = build_short_flag_pattern("en")
ASSIGNMENT_PATTERN = build_assignment_pattern("en")
