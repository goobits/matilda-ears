#!/usr/bin/env python3
"""Centralized regular expression patterns for text formatting.

This module contains all complex regex patterns used throughout the text formatting
system, organized logically and using verbose formatting for readability and
maintainability.

All patterns use re.VERBOSE flag where beneficial and include detailed comments
explaining each component.
"""

import re
from typing import List, Pattern, Optional
from .constants import get_resources
from .common import NumberParser


# ==============================================================================
# COMMON PATTERN COMPONENTS
# ==============================================================================

# File extensions organized by category
FILE_EXTENSIONS = {
    "code": [
        "py",
        "js",
        "ts",
        "tsx",
        "jsx",
        "cpp",
        "c",
        "h",
        "hpp",
        "java",
        "cs",
        "go",
        "rs",
        "rb",
        "php",
        "sh",
        "bash",
        "zsh",
        "fish",
        "bat",
        "cmd",
        "ps1",
        "swift",
        "kt",
        "scala",
        "r",
        "m",
        "lua",
        "pl",
        "asm",
    ],
    "data": [
        "json",
        "jsonl",
        "xml",
        "yaml",
        "yml",
        "toml",
        "ini",
        "cfg",
        "conf",
        "csv",
        "tsv",
        "sql",
        "db",
        "sqlite",
        "custom",
    ],
    "document": ["md", "txt", "rst", "tex", "pdf", "doc", "docx", "xls", "xlsx", "ppt", "pptx", "odt", "ods", "odp"],
    "web": ["html", "htm", "css", "scss", "sass", "less"],
    "media": [
        "png",
        "jpg",
        "jpeg",
        "gif",
        "svg",
        "ico",
        "bmp",
        "webp",
        "mp3",
        "mp4",
        "avi",
        "mov",
        "mkv",
        "webm",
        "wav",
        "flac",
        "ogg",
    ],
    "archive": ["zip", "tar", "gz", "bz2", "xz", "rar", "7z", "deb", "rpm", "dmg", "pkg", "exe", "msi", "app"],
}

# Flatten all extensions for use in patterns
ALL_FILE_EXTENSIONS = []
for category in FILE_EXTENSIONS.values():
    ALL_FILE_EXTENSIONS.extend(category)

# Ordinal number patterns
SPOKEN_ORDINAL_PATTERN = re.compile(
    r"\b(first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth|"
    r"eleventh|twelfth|thirteenth|fourteenth|fifteenth|sixteenth|seventeenth|"
    r"eighteenth|nineteenth|twentieth|twenty[-\s]?first|twenty[-\s]?second|"
    r"twenty[-\s]?third|twenty[-\s]?fourth|twenty[-\s]?fifth|twenty[-\s]?sixth|"
    r"twenty[-\s]?seventh|twenty[-\s]?eighth|twenty[-\s]?ninth|thirtieth|"
    r"thirty[-\s]?first|fortieth|fiftieth|sixtieth|seventieth|eightieth|"
    r"ninetieth|hundredth|thousandth)\b",
    re.IGNORECASE,
)

# Relative time patterns
SPOKEN_TIME_RELATIVE_PATTERN = re.compile(
    r"\b(quarter\s+past|half\s+past|quarter\s+to|ten\s+past|twenty\s+past|"
    r"twenty\-five\s+past|five\s+past|ten\s+to|twenty\s+to|twenty\-five\s+to|"
    r"five\s+to)\s+(\w+)\b",
    re.IGNORECASE,
)

# Fraction patterns
SPOKEN_FRACTION_PATTERN = re.compile(
    r"\b(one|two|three|four|five|six|seven|eight|nine|ten)\s+"
    r"(half|halves|third|thirds|quarter|quarters|fourth|fourths|fifth|fifths|"
    r"sixth|sixths|seventh|sevenths|eighth|eighths|ninth|ninths|tenth|tenths)\b",
    re.IGNORECASE,
)

# Component-based numeric range pattern for better maintainability
# Get the number words from a single source of truth
_number_parser_instance = NumberParser("en")  # Use English as default for pattern building
_number_words_pattern = "(?:" + "|".join(_number_parser_instance.all_number_words) + ")"

# Define a reusable pattern for a sequence of one or more number words
NUMBER_WORD_SEQUENCE = f"{_number_words_pattern}(?:\\s+{_number_words_pattern})*"

# Build the range pattern from components - much more readable and maintainable
SPOKEN_NUMERIC_RANGE_PATTERN = re.compile(
    rf"""
    \b                      # Word boundary
    (                       # Capture group 1: Start of range
        {NUMBER_WORD_SEQUENCE}
    )
    \s+to\s+                # The word "to"
    (                       # Capture group 2: End of range
        {NUMBER_WORD_SEQUENCE}
    )
    \b                      # Word boundary
    """,
    re.IGNORECASE | re.VERBOSE,
)

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

# Filler words for removal
FILLER_WORDS = ["um", "uh", "er", "ah", "umm", "uhh", "hmm", "huh", "mhm", "mm-hmm", "uh-huh"]


# ==============================================================================
# TEXT CLEANING PATTERNS
# ==============================================================================

# Remove filler words from transcription
FILLER_WORDS_PATTERN = re.compile(
    r"""
    \b                          # Word boundary
    (?:                         # Non-capturing group for alternatives
        um | uh | er | ah |     # Basic hesitation sounds
        umm | uhh |             # Extended hesitation sounds
        hmm | huh |             # Thinking sounds
        mhm | mm-hmm |          # Agreement sounds
        uh-huh                  # Confirmation sound
    )
    \b                          # Word boundary
    """,
    re.VERBOSE | re.IGNORECASE,
)

# Normalize repeated punctuation
REPEATED_PUNCTUATION_PATTERNS = [
    (re.compile(r"([,;:])\1+"), r"\1"),  # Repeated commas, semicolons, colons
    (re.compile(r"\.\.+"), "."),  # Multiple dots to single dot
    (re.compile(r"\?\?+"), "?"),  # Multiple question marks
    (re.compile(r"!!+"), "!"),  # Multiple exclamation marks
]


# Profanity filtering pattern (built dynamically)
def create_profanity_pattern(profanity_words: List[str]) -> Pattern:
    """Create a pattern to filter profanity words.

    Only matches lowercase profanity to avoid filtering proper nouns
    and sentence beginnings (e.g., "Hell, Michigan" vs "go to hell").
    """
    escaped_words = [re.escape(word) for word in profanity_words]
    # Match only when the word starts with lowercase letter
    pattern_string = r"\b(?:" + "|".join(f"[{word[0].lower()}]{re.escape(word[1:])}" for word in escaped_words) + r")\b"
    return re.compile(pattern_string)


# ==============================================================================
# CAPITALIZATION PATTERNS
# ==============================================================================

# Preserve all-caps words (acronyms) and technical units
ALL_CAPS_PRESERVATION_PATTERN = re.compile(
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

# Capitalize letters after sentence-ending punctuation
SENTENCE_CAPITALIZATION_PATTERN = re.compile(
    r"""
    ([.!?]\s+)                          # Sentence-ending punctuation + space(s)
    ([a-z])                             # Lowercase letter to capitalize
    """,
    re.VERBOSE,
)

# Capitalize pronoun "i" while avoiding code variables
PRONOUN_I_PATTERN = re.compile(
    r"""
    (?<![a-zA-Z])                       # Not preceded by letter
    i                                   # The letter 'i'
    (?![a-zA-Z+\-])                     # Not followed by letter, plus, or minus
    """,
    re.VERBOSE,
)


# ==============================================================================
# TECHNICAL CONTENT DETECTION PATTERNS
# ==============================================================================

# File extensions for technical content detection
FILE_EXTENSION_DETECTION_PATTERN = re.compile(
    r"""
    \.                                  # Literal dot
    (?:                                 # Non-capturing group for file extensions
        """
    + "|".join(ALL_FILE_EXTENSIONS)
    + r"""
    )
    \b                                  # Word boundary
    """,
    re.VERBOSE | re.IGNORECASE,
)

# Technical content patterns that don't need punctuation
TECHNICAL_CONTENT_PATTERNS = [
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


# ==============================================================================
# WEB-RELATED PATTERNS
# ==============================================================================


def build_spoken_url_pattern(language: str = "en") -> Pattern:
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
    from .common import NumberParser

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


# Function to get pattern for specific language
def get_spoken_url_pattern(language: str = "en") -> Pattern:
    """Get the spoken URL pattern for the specified language."""
    return build_spoken_url_pattern(language)


# Backward compatibility: default English pattern
SPOKEN_URL_PATTERN = build_spoken_url_pattern("en")


def build_spoken_email_pattern(language: str = "en") -> Pattern:
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


def get_spoken_email_pattern(language: str = "en") -> Pattern:
    """Get the spoken email pattern for the specified language."""
    return build_spoken_email_pattern(language)


def build_spoken_protocol_pattern(language: str = "en") -> Pattern:
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


# Spoken protocol pattern: "http colon slash slash example.com" or "http colon slash slash example dot com"
SPOKEN_PROTOCOL_PATTERN = build_spoken_protocol_pattern("en")

# Legacy pattern removed - now using dynamic pattern built from i18n resources

# Spoken email pattern: "john at example.com" or "john at example dot com"
# Now with better action word filtering and centralized keywords
# Pattern will be built dynamically after create_alternation_pattern is defined


def build_port_number_pattern(language: str = "en") -> Pattern:
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
    from .common import NumberParser

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


# Create the pattern instance for immediate use
def get_port_number_pattern(language: str = "en") -> Pattern:
    """Get the port number pattern for the specified language."""
    return build_port_number_pattern(language)


# Backward compatibility: default English pattern
PORT_NUMBER_PATTERN = build_port_number_pattern("en")

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
# CODE-RELATED I18N-AWARE PATTERN BUILDERS
# ==============================================================================

def get_slash_command_pattern(language: str = "en") -> Pattern:
    """Builds the slash command pattern dynamically."""
    resources = get_resources(language)
    code_keywords = resources.get("spoken_keywords", {}).get("code", {})
    slash_keywords = [k for k, v in code_keywords.items() if v == "/"]
    slash_keywords_sorted = sorted(slash_keywords, key=len, reverse=True)
    slash_pattern = "|".join(re.escape(k) for k in slash_keywords_sorted)

    return re.compile(
        rf"""
        \b(?:{slash_pattern})\s+([a-zA-Z][a-zA-Z0-9_-]*)
        """, re.VERBOSE | re.IGNORECASE
    )

def get_underscore_delimiter_pattern(language: str = "en") -> Pattern:
    """Builds the dunder/underscore delimiter pattern dynamically."""
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
        """, re.VERBOSE | re.IGNORECASE
    )

def get_simple_underscore_pattern(language: str = "en") -> Pattern:
    """Builds the simple underscore variable pattern dynamically."""
    resources = get_resources(language)
    code_keywords = resources.get("spoken_keywords", {}).get("code", {})
    underscore_keywords = [k for k, v in code_keywords.items() if v == "_"]
    underscore_keywords_sorted = sorted(underscore_keywords, key=len, reverse=True)
    underscore_pattern = "|".join(re.escape(k) for k in underscore_keywords_sorted)

    return re.compile(
        rf"""
        \b([\w][\w0-9_-]*)\s+(?:{underscore_pattern})\s+([\w][\w0-9_-]*)\b
        """, re.VERBOSE | re.IGNORECASE | re.UNICODE
    )

def get_long_flag_pattern(language: str = "en") -> Pattern:
    """Builds the long command flag pattern dynamically."""
    resources = get_resources(language)
    code_keywords = resources.get("spoken_keywords", {}).get("code", {})
    dash_keywords = [k for k, v in code_keywords.items() if v == "-"]
    dash_pattern = "|".join(re.escape(k) for k in sorted(dash_keywords, key=len, reverse=True))

    return re.compile(rf"\b(?:{dash_pattern})\s+(?:{dash_pattern})\s+([a-zA-Z][\w-]*(\s+[a-zA-Z][\w-]*)?)", re.IGNORECASE)

def get_short_flag_pattern(language: str = "en") -> Pattern:
    """Builds the short command flag pattern dynamically and safely."""
    resources = get_resources(language)
    code_keywords = resources.get("spoken_keywords", {}).get("code", {})

    # Get all keywords that map to "-"
    dash_keywords = [k for k, v in code_keywords.items() if v == "-"]

    # Sort by length to match longer phrases first (e.g., "dash dash" vs "dash")
    dash_keywords_sorted = sorted(dash_keywords, key=len, reverse=True)

    # Create the pattern without any language-specific if-statements
    dash_pattern = "|".join(re.escape(k) for k in dash_keywords_sorted)

    # This pattern now correctly handles "guión" in Spanish and "dash" in English
    # without special casing, as long as the JSON files are correct.
    return re.compile(rf"\b(?:{dash_pattern})\s+([a-zA-Z0-9-]+)\b", re.IGNORECASE)

def get_assignment_pattern(language: str = "en") -> Pattern:
    """Builds the assignment pattern dynamically."""
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
            (?!=\s*(?:{equals_pattern})) # Not followed by another equals
            .+?
        )
        (?=\s*(?:;|\n|$)|--|\+\+) # Ends at semicolon, newline, end, or other operator
        """, re.VERBOSE | re.IGNORECASE
    )

# ==============================================================================
# CODE-RELATED PATTERNS
# ==============================================================================

# Slash command pattern: "slash commit" -> "/commit"
# Placeholder - pattern will be assigned after function definition
SLASH_COMMAND_PATTERN = None

# Underscore delimiter pattern: "underscore underscore blah underscore underscore" -> "__blah__"
# Placeholder - pattern will be assigned after function definition
UNDERSCORE_DELIMITER_PATTERN = None

# Simple underscore variable pattern: "user underscore id" -> "user_id"
# Placeholder - pattern will be assigned after function definition
SIMPLE_UNDERSCORE_PATTERN = None

# Filename detection with extension
FILENAME_WITH_EXTENSION_PATTERN = re.compile(
    r"""
    \b                                  # Word boundary
    (?:                                 # Filename part
        \w+                             # First word/component
        (?:[_\-]\w+)*                   # Additional components connected by _ or - (NOT space)
    )                                   # Required filename
    \.                                  # Literal dot
    ("""
    + "|".join(ALL_FILE_EXTENSIONS)
    + r""")  # File extension (grouped)
    \b                                  # Word boundary
    """,
    re.VERBOSE | re.IGNORECASE,
)

# More precise spoken filename pattern: "readme dot md", "my new file dot py"
# This pattern is designed to be less greedy than the SpaCy backward-walking approach
# Use the simple dot pattern as the primary anchor - defined below
# The complex detection logic is handled in match_code.py using spaCy
SPOKEN_FILENAME_PATTERN = None  # Will be assigned after SPOKEN_DOT_FILENAME_PATTERN is defined

# Assignment pattern: "variable equals value" or "let variable equals value" etc.
# Placeholder - pattern will be assigned after function definition
ASSIGNMENT_PATTERN = None

# Latin abbreviations: "i.e.", "e.g.", etc.
ABBREVIATION_PATTERN = re.compile(
    r"""
    \b                                  # Word boundary
    (                                   # Capture group for abbreviation
        i\.e\. | e\.g\. | etc\. |       # With periods
        vs\. | cf\. |                   # With periods
        ie | eg | ex |                  # Without periods
        i\s+e |                         # Spoken form "i e"
        e\s+g |                         # Spoken form "e g"
        v\s+s |                         # Spoken form "v s"
        i\s+dot\s+e\s+dot |             # Spoken form "i dot e dot"
        e\s+dot\s+g\s+dot               # Spoken form "e dot g dot"
    )
    (?=\s|[,.:;!?]|$)                   # Lookahead: space, punctuation, or end
    """,
    re.VERBOSE | re.IGNORECASE,
)


# ==============================================================================
# MATHEMATICAL PATTERNS
# ==============================================================================

# Complex mathematical expressions
COMPLEX_MATH_EXPRESSION_PATTERN = re.compile(
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

# Simple mathematical expressions
SIMPLE_MATH_EXPRESSION_PATTERN = re.compile(
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

# Number + mathematical constant patterns (e.g., "two pi", "three e")
NUMBER_CONSTANT_PATTERN = re.compile(
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

# Time expressions: "meet at three thirty PM"
TIME_EXPRESSION_PATTERNS = [
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

# Phone number as spoken digits: "five five five one two three four"
SPOKEN_PHONE_PATTERN = re.compile(
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
# DOMAIN RESCUE PATTERNS
# ==============================================================================


# Generic domain rescue for concatenated domains
def create_domain_rescue_pattern(tld: str) -> Pattern:
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
# ABBREVIATION RESTORATION PATTERNS
# ==============================================================================

# Abbreviation restoration after punctuation model
ABBREVIATION_RESTORATION_PATTERNS = {
    "ie": "i.e.",
    "eg": "e.g.",
    "ex": "e.g.",  # "ex" is converted to "e.g." in this system
    "etc": "etc.",
    "vs": "vs.",
    "cf": "cf.",
}


def create_abbreviation_restoration_pattern(abbr: str) -> Pattern:
    """Create a pattern to restore periods to abbreviations."""
    return re.compile(
        rf"""
        (?<![.])                        # Not preceded by period
        \b{re.escape(abbr)}\b           # The abbreviation
        (?![.])                         # Not followed by period
        """,
        re.VERBOSE | re.IGNORECASE,
    )


# ==============================================================================
# PLACEHOLDER PATTERNS
# ==============================================================================

# Internal placeholder tokens used during processing
PLACEHOLDER_PATTERN = re.compile(
    r"""
    __PLACEHOLDER_\d+__ |               # Placeholder tokens
    __ENTITY_\d+__ |                    # Entity tokens
    __CAPS_\d+__                        # Capitalization tokens
    """,
    re.VERBOSE,
)


# ==============================================================================
# EMOJI PATTERNS
# ==============================================================================

# Tier 1: Implicit emoji patterns (can be used without "emoji" trigger word)
SPOKEN_EMOJI_IMPLICIT_MAP = {
    "smiley face": "🙂",
    "smiley": "🙂",
    "sad face": "🙁",
    "winking face": "😉",
    "crying face": "😢",
    "laughing face": "😂",
    "angry face": "😠",
    "screaming face": "😱",
    "thumbs up": "👍",
    "thumbs down": "👎",
}

# Tier 2: Explicit emoji patterns (must be followed by "emoji", "icon", or "emoticon")
SPOKEN_EMOJI_EXPLICIT_MAP = {
    # Common Symbols & Reactions
    "heart": "❤️",
    "broken heart": "💔",
    "fire": "🔥",
    "star": "⭐",
    "check mark": "✅",
    "cross mark": "❌",
    "one hundred": "💯",
    "100": "💯",
    "clapping hands": "👏",
    "applause": "👏",
    "folded hands": "🙏",
    "praying hands": "🙏",
    "flexed biceps": "💪",
    "strong": "💪",
    # Objects & Technology
    "rocket": "🚀",
    "light bulb": "💡",
    "bomb": "💣",
    "money bag": "💰",
    "gift": "🎁",
    "ghost": "👻",
    "robot": "🤖",
    "camera": "📷",
    "laptop": "💻",
    "phone": "📱",
    "magnifying glass": "🔎",
    # Nature & Animals
    "sun": "☀️",
    "cloud": "☁️",
    "rain cloud": "🌧️",
    "lightning bolt": "⚡",
    "snowflake": "❄️",
    "snowman": "⛄",
    "cat": "🐱",
    "dog": "🐶",
    "monkey": "🐵",
    "pig": "🐷",
    "unicorn": "🦄",
    "t-rex": "🦖",
    # Food & Drink
    "pizza": "🍕",
    "coffee": "☕",
    "cake": "🍰",
    "taco": "🌮",
}

# ==============================================================================
# PRE-COMPILED OPTIMIZATION PATTERNS
# ==============================================================================

# Common formatting patterns (pre-compiled for performance)
WHITESPACE_NORMALIZATION_PATTERN = re.compile(r"\s+")
REPEATED_DOTS_PATTERN = re.compile(r"\.\.+")
REPEATED_QUESTION_MARKS_PATTERN = re.compile(r"\?\?+")
REPEATED_EXCLAMATION_MARKS_PATTERN = re.compile(r"!!+")
PRONOUN_I_STANDALONE_PATTERN = re.compile(r"\bi\b")

# URL and email patterns for punctuation protection (pre-compiled)
URL_PROTECTION_PATTERN = re.compile(
    r"\b(?:https?://)?[a-zA-Z0-9-]+(?:\.[a-zA-Z0-9-]+)+(?:/[^?\s]*)?(?:\?[^\s]*)?", re.IGNORECASE
)
EMAIL_PROTECTION_PATTERN = re.compile(r"\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b", re.IGNORECASE)
TECH_SEQUENCE_PATTERN = re.compile(r"\b(?:[A-Z]{2,}(?:\s+[A-Z]{2,})+)\b")
MATH_EXPRESSION_PATTERN = re.compile(r"\b[a-zA-Z_]\w*\s*=\s*[\w\d]+(?:\s*[+\-*/×÷]\s*[\w\d]+)*\b")
TEMPERATURE_PROTECTION_PATTERN = re.compile(r"-?\d+(?:\.\d+)?°[CF]?")

# Mixed case technical terms (pre-compiled)
MIXED_CASE_TECH_PATTERN = re.compile(
    r"\b(?:JavaScript|TypeScript|GitHub|GitLab|BitBucket|DevOps|GraphQL|MongoDB|"
    r"PostgreSQL|MySQL|NoSQL|WebSocket|OAuth|iOS|macOS|iPadOS|tvOS|watchOS|"
    r"iPhone|iPad|macBook|iMac|AirPods|WiFi|Bluetooth|HTTP|HTTPS|API|JSON|XML|"
    r"HTML|CSS|SQL|PDF|URL|UUID|CSV|TSV|ZIP|RAM|CPU|GPU|SSD|USB|HDMI|"
    r"YouTube|LinkedIn|Facebook|Twitter|Instagram|TikTok|WhatsApp|Zoom|Slack|"
    r"Visual\s+Studio|IntelliJ|PyCharm|WebStorm|Eclipse|NetBeans|Xcode)\b"
)

# Command flag patterns (pre-compiled)
# Placeholders - patterns will be assigned after function definitions
LONG_FLAG_PATTERN = None
SHORT_FLAG_PATTERN = None

# Time formatting patterns (pre-compiled)
TIME_AM_PM_COLON_PATTERN = re.compile(r"\b(\d+):([ap])\s+m\b", re.IGNORECASE)
TIME_AM_PM_SPACE_PATTERN = re.compile(r"\b(\d+)\s+([ap])\s+m\b", re.IGNORECASE)

# Filename patterns (pre-compiled)
SPOKEN_DOT_FILENAME_PATTERN = re.compile(r"\s+dot\s+(" + "|".join(ALL_FILE_EXTENSIONS) + r")\b", re.IGNORECASE)

# Comprehensive spoken filename pattern that captures the full filename
# Matches patterns like "my script dot py", "config loader dot json", etc.
# Uses capture groups to separate filename and extension
FULL_SPOKEN_FILENAME_PATTERN = re.compile(
    rf"""
    \b                                          # Word boundary
    ([a-z]\w*(?:\s+[a-z]\w*)*)                 # Capture filename part (one or more words)
    \s+dot\s+                                   # " dot "
    ({"|".join(ALL_FILE_EXTENSIONS)})           # Capture file extension
    \b                                          # Word boundary
    """,
    re.VERBOSE | re.IGNORECASE,
)
JAVA_PACKAGE_PATTERN = re.compile(r"\b([a-zA-Z]\w*(?:\s+dot\s+[a-zA-Z]\w*){2,})\b", re.IGNORECASE)

# Now assign the simple anchor pattern to SPOKEN_FILENAME_PATTERN
SPOKEN_FILENAME_PATTERN = SPOKEN_DOT_FILENAME_PATTERN

# Currency and numeric patterns (pre-compiled)
DOLLAR_PATTERN = re.compile(
    r"\b(?:(?:one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|"
    r"thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty|"
    r"thirty|forty|fifty|sixty|seventy|eighty|ninety|hundred|thousand|million|"
    r"billion|trillion)\s+)*dollars?\b",
    re.IGNORECASE,
)
CENTS_PATTERN = re.compile(
    r"\b(?:(?:one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|"
    r"thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty|"
    r"thirty|forty|fifty|sixty|seventy|eighty|ninety|hundred)\s+)*cents?\b",
    re.IGNORECASE,
)

# Version number patterns (pre-compiled)
VERSION_PATTERN = re.compile(
    r"\bversion\s+(?:(?:zero|one|two|three|four|five|six|seven|eight|nine|ten|"
    r"eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|"
    r"twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety|hundred|thousand)\s*)+",
    re.IGNORECASE,
)

# Domain rescue patterns (pre-compiled)
WWW_DOMAIN_RESCUE = re.compile(r"\b(www)([a-zA-Z]+)(com|org|net|edu|gov|io|co|uk)\b", re.IGNORECASE)

# Entity protection patterns for capitalization
ENTITY_BOUNDARY_PATTERN = re.compile(r"\b(?=\w)")


# ==============================================================================
# PATTERN COMPILATION HELPERS
# ==============================================================================


def create_artifact_patterns(artifacts: List[str]) -> List[Pattern]:
    """Create and cache compiled patterns for transcription artifacts."""
    return [re.compile(r"\b" + re.escape(artifact) + r"\b", re.IGNORECASE) for artifact in artifacts]


def get_compiled_pattern(pattern_name: str) -> Optional[Pattern]:
    """Get a pre-compiled pattern by name."""
    pattern_map = {
        "whitespace": WHITESPACE_NORMALIZATION_PATTERN,
        "dots": REPEATED_DOTS_PATTERN,
        "questions": REPEATED_QUESTION_MARKS_PATTERN,
        "exclamations": REPEATED_EXCLAMATION_MARKS_PATTERN,
        "pronoun_i": PRONOUN_I_STANDALONE_PATTERN,
        "url_protection": URL_PROTECTION_PATTERN,
        "email_protection": EMAIL_PROTECTION_PATTERN,
        "tech_sequence": TECH_SEQUENCE_PATTERN,
        "math_expression": MATH_EXPRESSION_PATTERN,
        "temperature": TEMPERATURE_PROTECTION_PATTERN,
        "mixed_case_tech": MIXED_CASE_TECH_PATTERN,
        "long_flag": LONG_FLAG_PATTERN,
        "short_flag": SHORT_FLAG_PATTERN,
        "time_am_pm_colon": TIME_AM_PM_COLON_PATTERN,
        "time_am_pm_space": TIME_AM_PM_SPACE_PATTERN,
        "spoken_dot_filename": SPOKEN_DOT_FILENAME_PATTERN,
        "full_spoken_filename": FULL_SPOKEN_FILENAME_PATTERN,
        "java_package": JAVA_PACKAGE_PATTERN,
        "dollar": DOLLAR_PATTERN,
        "cents": CENTS_PATTERN,
        "version": VERSION_PATTERN,
        "www_domain_rescue": WWW_DOMAIN_RESCUE,
        "entity_boundary": ENTITY_BOUNDARY_PATTERN,
    }
    return pattern_map.get(pattern_name)


# ==============================================================================
# UTILITY FUNCTIONS
# ==============================================================================


def get_file_extensions_by_category(category: str) -> List[str]:
    """Get file extensions for a specific category."""
    return FILE_EXTENSIONS.get(category, [])


def get_all_file_extensions() -> List[str]:
    """Get all file extensions as a flat list."""
    return ALL_FILE_EXTENSIONS.copy()


def create_alternation_pattern(items: List[str], word_boundaries: bool = True) -> str:
    """Create a regex alternation pattern from a list of items."""
    escaped_items = [re.escape(item) for item in items]
    pattern = "|".join(escaped_items)
    if word_boundaries:
        pattern = rf"\b(?:{pattern})\b"
    return pattern


def build_slash_command_pattern(language: str = "en") -> Pattern:
    """Builds the slash command pattern dynamically from keywords in constants."""
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




# Backward compatibility: default English pattern
SLASH_COMMAND_PATTERN = build_slash_command_pattern("en")


def build_underscore_delimiter_pattern(language: str = "en") -> Pattern:
    """Builds the underscore delimiter pattern dynamically from keywords in constants."""
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




# Backward compatibility: default English patterns
UNDERSCORE_DELIMITER_PATTERN = build_underscore_delimiter_pattern("en")
SIMPLE_UNDERSCORE_PATTERN = build_simple_underscore_pattern("en")


def build_long_flag_pattern(language: str = "en") -> Pattern:
    """Builds the long flag pattern dynamically from keywords in constants."""
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
    # Get resources for the specified language
    resources = get_resources(language)
    code_keywords = resources["spoken_keywords"]["code"]

    # Get dash keywords from CODE_KEYWORDS
    dash_keywords = [k for k, v in code_keywords.items() if v == "-"]
    dash_keywords_sorted = sorted(dash_keywords, key=len, reverse=True)

    # Create the pattern without any language-specific if-statements
    dash_pattern = "|".join(re.escape(k) for k in dash_keywords_sorted)

    # This pattern now correctly handles all languages without special casing,
    # as long as the JSON files are correctly configured
    return re.compile(rf"\b(?:{dash_pattern})\s+([a-zA-Z0-9-]+)\b", re.IGNORECASE)




# Backward compatibility: default English patterns
LONG_FLAG_PATTERN = build_long_flag_pattern("en")
SHORT_FLAG_PATTERN = build_short_flag_pattern("en")


def build_assignment_pattern(language: str = "en") -> Pattern:
    """Builds the assignment pattern dynamically from keywords in constants."""
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
        (?!\s*{equals_pattern})             # Negative lookahead: not followed by another equals keyword (with optional space for ==)
        (                                   # Value (capture group 3)
            (?!.*\b(?:times|plus|minus|divided\s+by|over|squared?|cubed?)\b)  # Not a math expression
            (?:(?!\s+(?:and|or|but|if|when|then|while|unless)\s+).)+?        # Stop at conjunctions
        )
        (?=\s*$|\s*[.!?]|\s+(?:and|or|but|if|when|then|while|unless)\s+|--|\+\+)  # Lookahead: end of string, punctuation, conjunctions, or operators
        """,
        re.VERBOSE | re.IGNORECASE,
    )




# Backward compatibility: default English pattern
ASSIGNMENT_PATTERN = build_assignment_pattern("en")


# Legacy pattern removed - now using dynamic pattern built from i18n resources


# Use the language-aware pattern
SPOKEN_EMAIL_PATTERN = build_spoken_email_pattern("en")
