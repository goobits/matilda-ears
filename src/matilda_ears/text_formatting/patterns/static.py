#!/usr/bin/env python3
"""Pre-compiled static regex patterns.

This module contains all pre-compiled regex patterns that do not require
dynamic building from i18n resources. Patterns are organized by category.
"""

import re
from typing import List, Pattern, Optional

from .components import ALL_FILE_EXTENSIONS, COMMON_TLDS


# ==============================================================================
# FILLER WORD PATTERNS
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


# ==============================================================================
# ORDINAL AND TIME PATTERNS
# ==============================================================================

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


# ==============================================================================
# FRACTION PATTERNS
# ==============================================================================

# Fraction patterns
SPOKEN_FRACTION_PATTERN = re.compile(
    r"\b(one|two|three|four|five|six|seven|eight|nine|ten)\s+"
    r"(half|halves|third|thirds|quarter|quarters|fourth|fourths|fifth|fifths|"
    r"sixth|sixths|seventh|sevenths|eighth|eighths|ninth|ninths|tenth|tenths)\b",
    re.IGNORECASE,
)

# Mixed fraction pattern: "one and one half"
SPOKEN_MIXED_FRACTION_PATTERN = re.compile(
    r"\b(one|two|three|four|five|six|seven|eight|nine|ten)\s+and\s+"
    r"(one|two|three|four|five|six|seven|eight|nine|ten)\s+"
    r"(half|halves|third|thirds|quarter|quarters|fourth|fourths|fifth|fifths|"
    r"sixth|sixths|seventh|sevenths|eighth|eighths|ninth|ninths|tenth|tenths)\b",
    re.IGNORECASE,
)


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
        [A-Z0-9\u00b2\u00b3\u2074]+     # Value with possible superscripts (using unicode escapes)
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
        [+\-*/\u00d7\u00f7]             # Mathematical operator (using unicode escapes)
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
# CODE-RELATED PATTERNS
# ==============================================================================

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
# WEB-RELATED STATIC PATTERNS
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
MATH_EXPRESSION_PATTERN = re.compile(r"\b[a-zA-Z_]\w*\s*=\s*[\w\d]+(?:\s*[+\-*/\u00d7\u00f7]\s*[\w\d]+)*\b")
TEMPERATURE_PROTECTION_PATTERN = re.compile(r"-?\d+(?:\.\d+)?\u00b0[CF]?")

# Mixed case technical terms (pre-compiled)
MIXED_CASE_TECH_PATTERN = re.compile(
    r"\b(?:JavaScript|TypeScript|GitHub|GitLab|BitBucket|DevOps|GraphQL|MongoDB|"
    r"PostgreSQL|MySQL|NoSQL|WebSocket|OAuth|iOS|macOS|iPadOS|tvOS|watchOS|"
    r"iPhone|iPad|macBook|iMac|AirPods|WiFi|Bluetooth|HTTP|HTTPS|API|JSON|XML|"
    r"HTML|CSS|SQL|PDF|URL|UUID|CSV|TSV|ZIP|RAM|CPU|GPU|SSD|USB|HDMI|"
    r"YouTube|LinkedIn|Facebook|Twitter|Instagram|TikTok|WhatsApp|Zoom|Slack|"
    r"Visual\s+Studio|IntelliJ|PyCharm|WebStorm|Eclipse|NetBeans|Xcode)\b"
)

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

# Assign the simple anchor pattern to SPOKEN_FILENAME_PATTERN
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
# PATTERN FACTORY FUNCTIONS
# ==============================================================================


def create_profanity_pattern(profanity_words: List[str]) -> Pattern:
    """Create a pattern to filter profanity words.

    Only matches lowercase profanity to avoid filtering proper nouns
    and sentence beginnings (e.g., "Hell, Michigan" vs "go to hell").
    """
    escaped_words = [re.escape(word) for word in profanity_words]
    # Match only when the word starts with lowercase letter
    pattern_string = r"\b(?:" + "|".join(f"[{word[0].lower()}]{re.escape(word[1:])}" for word in escaped_words) + r")\b"
    return re.compile(pattern_string)


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


def create_artifact_patterns(artifacts: List[str]) -> List[Pattern]:
    """Create and cache compiled patterns for transcription artifacts."""
    return [re.compile(r"\b" + re.escape(artifact) + r"\b", re.IGNORECASE) for artifact in artifacts]


def get_compiled_pattern(pattern_name: str) -> Optional[Pattern]:
    """Get a pre-compiled pattern by name."""
    # Import builders here to avoid circular imports
    # These patterns are built dynamically and need the builder functions
    from .builders import (
        LONG_FLAG_PATTERN,
        SHORT_FLAG_PATTERN,
    )

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
