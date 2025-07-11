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

# Numeric range patterns - matches compound number words with "to" between them
# Uses a simpler approach that captures multiple number words on each side
SPOKEN_NUMERIC_RANGE_PATTERN = re.compile(
    r"\b((?:(?:zero|one|two|three|four|five|six|seven|eight|nine|ten|"
    r"eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|"
    r"twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety|hundred|thousand)(?:\s+(?:zero|one|two|three|four|five|six|seven|eight|nine|ten|"
    r"eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|"
    r"twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety|hundred|thousand))*)+)\s+to\s+"
    r"((?:(?:zero|one|two|three|four|five|six|seven|eight|nine|ten|"
    r"eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|"
    r"twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety|hundred|thousand)(?:\s+(?:zero|one|two|three|four|five|six|seven|eight|nine|ten|"
    r"eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|"
    r"twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety|hundred|thousand))*)+)\b",
    re.IGNORECASE,
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

# Spoken URL pattern: "example dot com slash path" or "example.com slash path"
# Also supports spoken numbers: "one one one one dot com"
SPOKEN_URL_PATTERN = re.compile(
    r"""
    \b                                  # Word boundary
    (                                   # Capture group 1: full URL
        (?:                             # Non-capturing group for subdomains
            (?:                         # Domain part alternatives
                [a-zA-Z0-9-]+           # Alphanumeric domain part
            |                           # OR
                (?:zero|one|two|three|four|five|six|seven|eight|nine|ten|
                   eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|
                   eighteen|nineteen|twenty|thirty|forty|fifty|sixty|seventy|
                   eighty|ninety|hundred|thousand)
                (?:\s+(?:zero|one|two|three|four|five|six|seven|eight|nine|ten|
                       eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|
                       eighteen|nineteen|twenty|thirty|forty|fifty|sixty|seventy|
                       eighty|ninety|hundred|thousand))*  # Multiple number words
            )
            (?:                         # Non-capturing group for dot
                \s+dot\s+               # Spoken "dot"
            |                           # OR
                \.                      # Regular dot
            )
        )*                              # Zero or more subdomains
        (?:                             # Main domain name part alternatives
            [a-zA-Z0-9-]+               # Alphanumeric domain part
        |                               # OR
            (?:zero|one|two|three|four|five|six|seven|eight|nine|ten|
               eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|
               eighteen|nineteen|twenty|thirty|forty|fifty|sixty|seventy|
               eighty|ninety|hundred|thousand)
            (?:\s+(?:zero|one|two|three|four|five|six|seven|eight|nine|ten|
                   eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|
                   eighteen|nineteen|twenty|thirty|forty|fifty|sixty|seventy|
                   eighty|ninety|hundred|thousand))*      # Multiple number words
        )
        (?:                             # Non-capturing group for dot
            \s+dot\s+                   # Spoken "dot"
        |                               # OR
            \.                          # Regular dot
        )
        (?:"""
    + "|".join(COMMON_TLDS)
    + r""")  # TLD alternatives
        (?:                             # Optional path part
            \s+slash\s+                 # " slash "
            [a-zA-Z0-9-]+               # Path segment
            (?:                         # Additional path segments
                \s+[a-zA-Z0-9-]+        # More path parts
            )*                          # Zero or more additional segments
        )*                              # Zero or more path groups
        (?:                             # Optional query string
            \s+question\s+mark\s+       # " question mark "
            .+                          # Query parameters
        )?                              # Optional query string
    )
    ([.!?]?)                            # Capture group 2: optional punctuation
    """,
    re.VERBOSE | re.IGNORECASE,
)

# Spoken protocol pattern: "http colon slash slash example.com" or "http colon slash slash example dot com"
SPOKEN_PROTOCOL_PATTERN = re.compile(
    r"""
    \b                                  # Word boundary
    (https?|ftp)                        # Protocol
    \s+colon\s+slash\s+slash\s+         # " colon slash slash "
    (                                   # Capture group: domain (supports both spoken and normal formats)
        (?:                             # Non-capturing group for spoken domain
            [a-zA-Z0-9-]+               # Domain name part
            (?:                         # Optional spoken dots
                \s+dot\s+               # " dot "
                [a-zA-Z0-9-]+           # Domain part after dot
            )+                          # One or more spoken dots
        )
        |                               # OR
        (?:                             # Non-capturing group for normal domain
            [a-zA-Z0-9.-]+              # Domain characters
            (?:\.[a-zA-Z]{2,})?         # Optional TLD
        )
    )
    (                                   # Capture group: path and query
        (?:                             # Optional path segments
            \s+slash\s+                 # " slash "
            [^?\s]+                     # Path content (not ? or space)
        )*                              # Zero or more path segments
        (?:                             # Optional query string
            \s+question\s+mark\s+       # " question mark "
            .+                          # Query content
        )?                              # Optional query
    )
    """,
    re.VERBOSE | re.IGNORECASE,
)

# Spoken email pattern: "john at example.com" or "john at example dot com"
# Now with better action word filtering
SPOKEN_EMAIL_PATTERN = re.compile(
    r"""
    (?:^|(?<=\s))                       # Start of string or preceded by space
    (?:                                 # Non-capturing group for email action prefix
        (?:email|contact|write\s+to|send\s+to)\s+  # Action prefixes we want to capture and handle
    )
    (?!(?:to|for|from|with|by|in|on|at|the|a|an|this|that|these|those|reach|call|find|locate|get|contact|tell|ask|see|talk|speak|say|me|you|us|him|her|them|it|i|we|he|she|they|look|go|come|think|if|when|where|what|how|why|please|can|could|would|should|will|shall|may|might)\s+)  # Negative lookahead: don't start with common non-name words or pronouns
    (                                   # Username part (capture group 1)
        [a-zA-Z]+                       # Must start with letters (no numbers at start of name)
        (?:                             # Optional additional parts
            \s+                         # Space separator
            (?:                         # Choice of what can follow
                (?:underscore|dash)     # Spoken separators
                |                       # OR
                (?:zero|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety|hundred|thousand|million)  # Number words
                |                       # OR
                [a-zA-Z0-9._-]+         # Regular alphanumeric parts
            )
        )*                              # Zero or more additional parts
    )
    \s+at\s+                            # " at "
    (                                   # Domain part (capture group 2)
        [a-zA-Z0-9][a-zA-Z0-9.-]*       # Domain starting with alphanumeric
        (?:                             # Optional additional domain parts
            \s+                         # Space separator
            (?:                         # Choice of what can follow
                (?:zero|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety|hundred|thousand|million)  # Number words
                |                       # OR
                [a-zA-Z0-9._-]+         # Regular alphanumeric parts
            )
        )*                              # Zero or more additional parts
        (?:                             # Non-capturing group for dots
            \s+dot\s+                   # " dot " for spoken dots
            [a-zA-Z0-9.-]+              # Domain part after dot
            (?:                         # Optional additional number words after dots
                \s+(?:zero|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety|hundred|thousand|million)
                |                       # OR
                \s+[a-zA-Z0-9._-]+
            )*                          # Zero or more
        |                               # OR
            \.                          # Regular dot
            [a-zA-Z0-9.-]+              # Domain part after dot
        )+                              # One or more dots
    )
    (?=\s|$|[.!?])                      # Followed by space, end, or punctuation
    """,
    re.VERBOSE | re.IGNORECASE,
)

# Port number pattern: "localhost colon eight zero eight zero" or "localhost colon three thousand"
PORT_NUMBER_PATTERN = re.compile(
    r"""
    \b                                  # Word boundary
    (localhost|[\w.-]+)                 # Hostname
    \s+colon\s+                         # " colon "
    (                                   # Capture group: port number (allows compound numbers)
        (?:                             # Non-capturing group for number words
            zero|one|two|three|four|five|six|seven|eight|nine|ten|
            eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|
            twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety|
            hundred|thousand|million
        )
        (?:                             # Additional number words
            \s+                         # Space separator
            (?:                         # Another number word
                zero|one|two|three|four|five|six|seven|eight|nine|ten|
                eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|
                twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety|
                hundred|thousand|million
            )
        )*                              # Zero or more additional number words
    )
    \b                                  # Word boundary
    """,
    re.VERBOSE | re.IGNORECASE,
)

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
# CODE-RELATED PATTERNS
# ==============================================================================

# Slash command pattern: "slash commit" -> "/commit"
SLASH_COMMAND_PATTERN = re.compile(
    r"""
    \b                                  # Word boundary
    slash\s+                            # "slash "
    ([a-zA-Z][a-zA-Z0-9_-]*)           # Command name (starts with letter, can contain letters, numbers, underscore, hyphen)
    \b                                  # Word boundary
    """,
    re.VERBOSE | re.IGNORECASE,
)

# Underscore delimiter pattern: "underscore underscore blah underscore underscore" -> "__blah__"
UNDERSCORE_DELIMITER_PATTERN = re.compile(
    r"""
    \b                                  # Word boundary
    ((?:underscore\s+)+)                # One or more "underscore " patterns (captured)
    ([a-zA-Z][a-zA-Z0-9_-]*)           # Content (starts with letter, can contain letters, numbers, underscore, hyphen)
    ((?:\s+underscore)+)                # One or more " underscore" patterns (captured)
    (?=\s|$)                           # Must be followed by space or end of string
    """,
    re.VERBOSE | re.IGNORECASE,
)

# Simple underscore variable pattern: "user underscore id" -> "user_id"
SIMPLE_UNDERSCORE_PATTERN = re.compile(
    r"""
    \b                                  # Word boundary
    ([a-zA-Z][a-zA-Z0-9_-]*)           # First word (starts with letter)
    \s+underscore\s+                    # " underscore "
    ([a-zA-Z][a-zA-Z0-9_-]*)           # Second word (starts with letter)
    \b                                  # Word boundary
    """,
    re.VERBOSE | re.IGNORECASE,
)

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

# Spoken filename pattern: "readme dot md", "my new file dot py"
SPOKEN_FILENAME_PATTERN = re.compile(
    r"""
    \b                                  # Word boundary
    (                                   # Capture group for filename
        (?:my|the|this|that|our|your|his|her|its|their)\s+  # Possessive/descriptive words (now required when present)
        \w+                             # First word after possessive
        (?:                             # Additional components
            \s+                         # Space
            (?:underscore\s+|dash\s+)?  # Optional spoken separator
            \w+                         # Next component
        ){0,5}                          # 0-5 additional components
        |                               # OR
        \w+                             # Single word filename (no possessive)
        (?:                             # Additional components
            \s+                         # Space
            (?:underscore\s+|dash\s+)?  # Optional spoken separator
            \w+                         # Next component
        ){0,5}                          # 0-5 additional components
    )
    \s+dot\s+                           # " dot "
    ("""
    + "|".join(ALL_FILE_EXTENSIONS)
    + r""")  # File extension (grouped)
    \b                                  # Word boundary
    """,
    re.VERBOSE | re.IGNORECASE,
)

# Assignment pattern: "variable equals value" or "let variable equals value" etc.
ASSIGNMENT_PATTERN = re.compile(
    r"""
    \b                                  # Word boundary
    (?:(let|const|var)\s+)?             # Optional variable declaration keyword (capture group 1)
    ((?!equals\b)[a-zA-Z_]\w*)          # Variable name (capture group 2) - not "equals"
    \s+equals\s+                        # " equals "
    (?!equals\b)                        # Negative lookahead: not followed by "equals" as a whole word (for ==)
    (?!.*(?:                            # Negative lookahead: not followed by math terms
        squared?|cubed?|                # Powers
        times|plus|minus|               # Basic math operators
        divided\s+by|over               # Division operators
    ))
    ((?:(?!\s+(?:and|or|but|if|when|then|while|unless)\s+).)+?)  # Value (capture group 3, non-greedy, stops at conjunctions)
    (?=\s*$|\s*[.!?]|\s+(?:and|or|but|if|when|then|while|unless)\s+)  # Lookahead: end of string, punctuation, or conjunctions
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
    \w+                                 # First operand
    \s+                                 # Space
    (?:times|divided\ by|over|slash)    # Mathematical operator
    \s+                                 # Space
    \w+                                 # Second operand
    [.!?]?                              # Optional trailing punctuation
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
LONG_FLAG_PATTERN = re.compile(
    r"\bdash\s+dash\s+([a-zA-Z][a-zA-Z0-9]*(?:\s+(?:dev|run|dir|cache|config|output|input|quiet|force|dry))?)",
    re.IGNORECASE,
)
SHORT_FLAG_PATTERN = re.compile(r"\bdash\s+([a-zA-Z0-9-]+)\b", re.IGNORECASE)

# Time formatting patterns (pre-compiled)
TIME_AM_PM_COLON_PATTERN = re.compile(r"\b(\d+):([ap])\s+m\b", re.IGNORECASE)
TIME_AM_PM_SPACE_PATTERN = re.compile(r"\b(\d+)\s+([ap])\s+m\b", re.IGNORECASE)

# Filename patterns (pre-compiled)
SPOKEN_DOT_FILENAME_PATTERN = re.compile(r"\s+dot\s+(" + "|".join(ALL_FILE_EXTENSIONS) + r")\b", re.IGNORECASE)
JAVA_PACKAGE_PATTERN = re.compile(r"\b([a-zA-Z]\w*(?:\s+dot\s+[a-zA-Z]\w*){2,})\b", re.IGNORECASE)

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
    return [re.compile(re.escape(artifact), re.IGNORECASE) for artifact in artifacts]


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
