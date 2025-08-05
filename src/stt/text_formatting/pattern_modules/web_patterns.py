#!/usr/bin/env python3
"""
Web-related regular expression patterns for text formatting.

This module contains all URL, email, domain, and protocol patterns used throughout
the text formatting system, organized logically and using verbose formatting for
readability and maintainability.

All patterns use re.VERBOSE flag where beneficial and include detailed comments
explaining each component.
"""
from __future__ import annotations

import re
from typing import Pattern

from ..constants import get_resources


# ==============================================================================
# COMMON WEB CONSTANTS
# ==============================================================================

# Common domain TLDs
COMMON_TLDS = [
    "com",
    "org",
    "net",
    "edu",
    "gov",
    "io",
    "co",
    "uk",
    "ca",
    "au",
    "de",
    "fr",
    "jp",
    "cn",
    "in",
    "br",
    "mx",
    "es",
    "it",
    "nl",
    "local",  # Development domain
]


# Words that commonly end with TLD patterns and should NOT be split
DOMAIN_EXCLUDE_WORDS = {
    # Words ending in "com"
    "become",
    "income",
    "welcome",
    "outcome",
    "overcome",
    # Words ending in "org"
    "inform",
    "perform",
    "transform",
    "platform",
    "uniform",
    # Words ending in "net"
    "internet",
    "cabinet",
    "planet",
    "magnet",
    "helmet",
    # Words ending in "io"
    "video",
    "radio",
    "studio",
    "ratio",
    "audio",
    # Words ending in common short TLDs
    "to",
    "do",
    "go",
    "so",
    "no",
}


# ==============================================================================
# SPOKEN WEB PATTERN BUILDERS
# ==============================================================================


def build_spoken_url_pattern(language: str = "en") -> re.Pattern[str]:
    """Builds the spoken URL pattern dynamically from keywords in constants."""
    # Get resources for the specified language
    resources = get_resources(language)
    url_keywords = resources["spoken_keywords"]["url"]

    # Get keyword patterns from URL_KEYWORDS
    dot_keywords = [k for k, v in url_keywords.items() if v == "."]
    slash_keywords = [k for k, v in url_keywords.items() if v == "/"]
    question_mark_keywords = [k for k, v in url_keywords.items() if v == "?"]

    # Create alternation patterns for each keyword type (inline implementation)
    # Sort by length to match longer phrases first
    dot_keywords_sorted = sorted(dot_keywords, key=len, reverse=True)
    slash_keywords_sorted = sorted(slash_keywords, key=len, reverse=True)
    question_mark_keywords_sorted = sorted(question_mark_keywords, key=len, reverse=True)

    dot_escaped = [re.escape(k) for k in dot_keywords_sorted] + [r"\."]
    dot_pattern = "|".join(dot_escaped)

    slash_escaped = [re.escape(k) for k in slash_keywords_sorted]
    slash_pattern = "|".join(slash_escaped)

    question_mark_escaped = [re.escape(k) for k in question_mark_keywords_sorted]
    question_mark_pattern = "|".join(question_mark_escaped)

    # Create number words pattern from language-specific resources
    from ..common import NumberParser

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
                [a-zA-Z0-9-]+           # Alphanumeric domain part
            |                           # OR
                (?:{number_words_pattern})
                (?:\s+(?:{number_words_pattern}))*  # Multiple number words
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
    )
    ([.!?]?)                            # Capture group 2: optional punctuation
    """
    return re.compile(pattern_str, re.VERBOSE | re.IGNORECASE)


def build_spoken_email_pattern(language: str = "en") -> re.Pattern[str]:
    """Builds the spoken email pattern dynamically for the specified language."""
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
    # This pattern looks for actual email-like structures
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


def build_spoken_protocol_pattern(language: str = "en") -> re.Pattern[str]:
    """Builds the spoken protocol pattern dynamically for the specified language."""
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
    question_pattern = (
        "|".join(re.escape(k) for k in question_keywords_sorted) if question_keywords_sorted else "question\\s+mark"
    )

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


def build_port_number_pattern(language: str = "en") -> re.Pattern[str]:
    """Builds the port number pattern dynamically from keywords in constants."""
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
    from ..common import NumberParser

    number_parser_instance = NumberParser(language)
    number_words = list(number_parser_instance.all_number_words)
    number_words_escaped = [re.escape(word) for word in number_words]
    number_words_pattern = "|".join(number_words_escaped)

    # Get dot keywords for spoken domain detection
    dot_keywords = [k for k, v in url_keywords.items() if v == "."]
    dot_keywords_sorted = sorted(dot_keywords, key=len, reverse=True)
    dot_pattern = "|".join(re.escape(k) for k in dot_keywords_sorted)

    # Build the complete pattern using the dynamic keyword patterns
    pattern_str = rf"""
    \b                                  # Word boundary
    (                                   # Capture group 1: hostname (expanded for spoken domains and IP addresses)
        (?:                             # Alternative 1: IP address like "one two seven dot zero dot zero dot one"
            (?:                         # IP address octet: can be number words or alphanumeric
                (?:{number_words_pattern})(?:\s+(?:{number_words_pattern}))*  # Multiple number words
                |                       # OR
                [a-zA-Z0-9-]+           # Regular alphanumeric part
            )
            (?:                         # Three more octets (4 total for IP)
                \s+(?:{dot_pattern})\s+ # Spoken "dot"
                (?:                     # Another octet
                    (?:{number_words_pattern})(?:\s+(?:{number_words_pattern}))*  # Multiple number words
                    |                   # OR
                    [a-zA-Z0-9-]+       # Regular alphanumeric part
                )
            ){{3}}                      # Exactly 3 more octets (for 4 total)
        )
        |                               # OR
        (?:                             # Alternative 2: spoken domain like "api dot service dot com"
            [a-zA-Z0-9-]+               # Domain part
            (?:\s+(?:{dot_pattern})\s+[a-zA-Z0-9-]+)+  # One or more " dot " separated parts
        )
        |                               # OR
        (?:localhost|[\w.-]+)           # Alternative 3: localhost or regular hostname
    )
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


# ==============================================================================
# GETTER FUNCTIONS
# ==============================================================================


def get_spoken_url_pattern(language: str = "en") -> re.Pattern[str]:
    """Get the spoken URL pattern for the specified language."""
    return build_spoken_url_pattern(language)


def get_spoken_email_pattern(language: str = "en") -> re.Pattern[str]:
    """Get the spoken email pattern for the specified language."""
    return build_spoken_email_pattern(language)


def get_spoken_protocol_pattern(language: str = "en") -> re.Pattern[str]:
    """Get the spoken protocol pattern for the specified language."""
    return build_spoken_protocol_pattern(language)


def get_port_number_pattern(language: str = "en") -> re.Pattern[str]:
    """Get the port number pattern for the specified language."""
    return build_port_number_pattern(language)


# ==============================================================================
# DEFAULT PATTERNS (BACKWARD COMPATIBILITY)
# ==============================================================================

# Default English patterns for backward compatibility
SPOKEN_URL_PATTERN = build_spoken_url_pattern("en")
SPOKEN_EMAIL_PATTERN = build_spoken_email_pattern("en")
SPOKEN_PROTOCOL_PATTERN = build_spoken_protocol_pattern("en")
PORT_NUMBER_PATTERN = build_port_number_pattern("en")


# ==============================================================================
# DOMAIN RESCUE PATTERNS
# ==============================================================================


# WWW domain rescue pattern: "wwwgooglecom" -> "www.google.com"
WWW_DOMAIN_RESCUE_PATTERN = re.compile(
    r"""
    \b                                  # Word boundary
    (www)                               # "www" prefix
    ([a-zA-Z]+)                         # Domain name
    ("""
    + "|".join(COMMON_TLDS)
    + r""")  # TLD
    \b                                  # Word boundary
    """,
    re.VERBOSE | re.IGNORECASE,
)


# Generic domain rescue for concatenated domains
def create_domain_rescue_pattern(tld: str) -> re.Pattern[str]:
    """Create a pattern to rescue concatenated domains for a specific TLD."""
    return re.compile(
        rf"""
        \b                              # Word boundary
        ([a-zA-Z]{{3,}})                # Domain name (3+ characters)
        ({re.escape(tld)})              # TLD (escaped)
        \b                              # Word boundary
        """,
        re.VERBOSE | re.IGNORECASE,
    )


# ==============================================================================
# URL PARAMETER PATTERNS
# ==============================================================================


# URL parameter splitting: "a equals b and c equals d"
URL_PARAMETER_SPLIT_PATTERN = re.compile(r"\s+and\s+", re.IGNORECASE)

# URL parameter parsing: "key equals value"
URL_PARAMETER_PARSE_PATTERN = re.compile(
    r"""
    (\w+)                               # Parameter key
    \s+equals\s+                        # " equals "
    (.+)                                # Parameter value
    """,
    re.VERBOSE | re.IGNORECASE,
)


# ==============================================================================
# PRE-COMPILED PROTECTION PATTERNS
# ==============================================================================

# URL and email patterns for punctuation protection (pre-compiled)
URL_PROTECTION_PATTERN = re.compile(
    r"\b(?:https?://)?[a-zA-Z0-9-]+(?:\.[a-zA-Z0-9-]+)+(?:/[^?\s]*)?(?:\?[^\s]*)?", re.IGNORECASE
)
EMAIL_PROTECTION_PATTERN = re.compile(r"\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b", re.IGNORECASE)

# Domain rescue patterns (pre-compiled)
WWW_DOMAIN_RESCUE = re.compile(r"\b(www)([a-zA-Z]+)(com|org|net|edu|gov|io|co|uk)\b", re.IGNORECASE)


# ==============================================================================
# UTILITY FUNCTIONS
# ==============================================================================


def create_alternation_pattern(items: list[str], word_boundaries: bool = True) -> str:
    """Create a regex alternation pattern from a list of items."""
    escaped_items = [re.escape(item) for item in items]
    pattern = "|".join(escaped_items)
    if word_boundaries:
        pattern = rf"\b(?:{pattern})\b"
    return pattern


def get_compiled_web_pattern(pattern_name: str) -> Pattern | None:
    """Get a pre-compiled web pattern by name."""
    pattern_map = {
        "url_protection": URL_PROTECTION_PATTERN,
        "email_protection": EMAIL_PROTECTION_PATTERN,
        "www_domain_rescue": WWW_DOMAIN_RESCUE,
        "spoken_url": SPOKEN_URL_PATTERN,
        "spoken_email": SPOKEN_EMAIL_PATTERN,
        "spoken_protocol": SPOKEN_PROTOCOL_PATTERN,
        "port_number": PORT_NUMBER_PATTERN,
        "www_domain_rescue_pattern": WWW_DOMAIN_RESCUE_PATTERN,
        "url_parameter_split": URL_PARAMETER_SPLIT_PATTERN,
        "url_parameter_parse": URL_PARAMETER_PARSE_PATTERN,
    }
    return pattern_map.get(pattern_name)


def get_common_tlds() -> list[str]:
    """Get the list of common TLDs."""
    return COMMON_TLDS.copy()


def get_domain_exclude_words() -> set[str]:
    """Get the set of words that should not be split as domains."""
    return DOMAIN_EXCLUDE_WORDS.copy()