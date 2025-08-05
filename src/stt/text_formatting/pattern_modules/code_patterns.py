#!/usr/bin/env python3
"""
Code-related regular expression patterns for text formatting.

This module contains all programming, command, file, and technical patterns used
throughout the text formatting system, organized logically and using verbose
formatting for readability and maintainability.

All patterns use re.VERBOSE flag where beneficial and include detailed comments
explaining each component.
"""
from __future__ import annotations

import re
from typing import Pattern

from ..constants import get_resources


# ==============================================================================
# FILE EXTENSIONS CONSTANTS
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


# ==============================================================================
# CODE PATTERN BUILDERS
# ==============================================================================


def build_slash_command_pattern(language: str = "en") -> re.Pattern[str]:
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


def build_underscore_delimiter_pattern(language: str = "en") -> re.Pattern[str]:
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


def build_simple_underscore_pattern(language: str = "en") -> re.Pattern[str]:
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


def build_long_flag_pattern(language: str = "en") -> re.Pattern[str]:
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


def build_short_flag_pattern(language: str = "en") -> re.Pattern[str]:
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


def build_assignment_pattern(language: str = "en") -> re.Pattern[str]:
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


# ==============================================================================
# GETTER FUNCTIONS
# ==============================================================================


def get_slash_command_pattern(language: str = "en") -> re.Pattern[str]:
    """Get the slash command pattern for the specified language."""
    return build_slash_command_pattern(language)


def get_underscore_delimiter_pattern(language: str = "en") -> re.Pattern[str]:
    """Get the underscore delimiter pattern for the specified language."""
    return build_underscore_delimiter_pattern(language)


def get_simple_underscore_pattern(language: str = "en") -> re.Pattern[str]:
    """Get the simple underscore pattern for the specified language."""
    return build_simple_underscore_pattern(language)


def get_long_flag_pattern(language: str = "en") -> re.Pattern[str]:
    """Get the long flag pattern for the specified language."""
    return build_long_flag_pattern(language)


def get_short_flag_pattern(language: str = "en") -> re.Pattern[str]:
    """Get the short flag pattern for the specified language."""
    return build_short_flag_pattern(language)


def get_assignment_pattern(language: str = "en") -> re.Pattern[str]:
    """Get the assignment pattern for the specified language."""
    return build_assignment_pattern(language)


# ==============================================================================
# DEFAULT PATTERNS (BACKWARD COMPATIBILITY)
# ==============================================================================

# Default English patterns for backward compatibility
SLASH_COMMAND_PATTERN = build_slash_command_pattern("en")
UNDERSCORE_DELIMITER_PATTERN = build_underscore_delimiter_pattern("en")
SIMPLE_UNDERSCORE_PATTERN = build_simple_underscore_pattern("en")
LONG_FLAG_PATTERN = build_long_flag_pattern("en")
SHORT_FLAG_PATTERN = build_short_flag_pattern("en")
ASSIGNMENT_PATTERN = build_assignment_pattern("en")


# ==============================================================================
# FILENAME PATTERNS
# ==============================================================================

# File extension detection pattern
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

# Spoken filename patterns
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

# Java package pattern: "com dot example dot package"
JAVA_PACKAGE_PATTERN = re.compile(r"\b([a-zA-Z]\w*(?:\s+dot\s+[a-zA-Z]\w*){2,})\b", re.IGNORECASE)

# Main spoken filename pattern (simple anchor)
SPOKEN_FILENAME_PATTERN = SPOKEN_DOT_FILENAME_PATTERN


# ==============================================================================
# COMPARISON AND PROGRAMMING PATTERNS
# ==============================================================================

# Mixed case technical terms (pre-compiled)
MIXED_CASE_TECH_PATTERN = re.compile(
    r"\b(?:JavaScript|TypeScript|GitHub|GitLab|BitBucket|DevOps|GraphQL|MongoDB|"
    r"PostgreSQL|MySQL|NoSQL|WebSocket|OAuth|iOS|macOS|iPadOS|tvOS|watchOS|"
    r"iPhone|iPad|macBook|iMac|AirPods|WiFi|Bluetooth|HTTP|HTTPS|API|JSON|XML|"
    r"HTML|CSS|SQL|PDF|URL|UUID|CSV|TSV|ZIP|RAM|CPU|GPU|SSD|USB|HDMI|"
    r"YouTube|LinkedIn|Facebook|Twitter|Instagram|TikTok|WhatsApp|Zoom|Slack|"
    r"Visual\s+Studio|IntelliJ|PyCharm|WebStorm|Eclipse|NetBeans|Xcode)\b"
)

# Technical sequence pattern
TECH_SEQUENCE_PATTERN = re.compile(r"\b(?:[A-Z]{2,}(?:\s+[A-Z]{2,})+)\b")

# Math expression pattern for variable assignments
MATH_EXPRESSION_PATTERN = re.compile(r"\b[a-zA-Z_]\w*\s*=\s*[\w\d]+(?:\s*[+\-*/×÷]\s*[\w\d]+)*\b")

# Version number patterns
VERSION_PATTERN = re.compile(
    r"\bversion\s+(?:(?:zero|one|two|three|four|five|six|seven|eight|nine|ten|"
    r"eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|"
    r"twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety|hundred|thousand)\s*)+",
    re.IGNORECASE,
)


# ==============================================================================
# UTILITY FUNCTIONS
# ==============================================================================


def get_file_extensions_by_category(category: str) -> list[str]:
    """Get file extensions for a specific category."""
    return FILE_EXTENSIONS.get(category, [])


def get_all_file_extensions() -> list[str]:
    """Get all file extensions as a flat list."""
    return ALL_FILE_EXTENSIONS.copy()


def create_alternation_pattern(items: list[str], word_boundaries: bool = True) -> str:
    """Create a regex alternation pattern from a list of items."""
    escaped_items = [re.escape(item) for item in items]
    pattern = "|".join(escaped_items)
    if word_boundaries:
        pattern = rf"\b(?:{pattern})\b"
    return pattern


def get_compiled_code_pattern(pattern_name: str) -> Pattern | None:
    """Get a pre-compiled code pattern by name."""
    pattern_map = {
        "slash_command": SLASH_COMMAND_PATTERN,
        "underscore_delimiter": UNDERSCORE_DELIMITER_PATTERN,
        "simple_underscore": SIMPLE_UNDERSCORE_PATTERN,
        "long_flag": LONG_FLAG_PATTERN,
        "short_flag": SHORT_FLAG_PATTERN,
        "assignment": ASSIGNMENT_PATTERN,
        "file_extension_detection": FILE_EXTENSION_DETECTION_PATTERN,
        "filename_with_extension": FILENAME_WITH_EXTENSION_PATTERN,
        "spoken_dot_filename": SPOKEN_DOT_FILENAME_PATTERN,
        "full_spoken_filename": FULL_SPOKEN_FILENAME_PATTERN,
        "java_package": JAVA_PACKAGE_PATTERN,
        "spoken_filename": SPOKEN_FILENAME_PATTERN,
        "mixed_case_tech": MIXED_CASE_TECH_PATTERN,
        "tech_sequence": TECH_SEQUENCE_PATTERN,
        "math_expression": MATH_EXPRESSION_PATTERN,
        "version": VERSION_PATTERN,
    }
    return pattern_map.get(pattern_name)