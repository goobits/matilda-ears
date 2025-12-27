#!/usr/bin/env python3
"""Data constants and helper functions for regex patterns.

This module contains all data constants (dictionaries, lists) and helper functions
used to build regex patterns. It is the foundation layer with no regex pattern
compilation.
"""

import re
from typing import List


# ==============================================================================
# FILE EXTENSIONS BY CATEGORY
# ==============================================================================

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
ALL_FILE_EXTENSIONS: List[str] = []
for category in FILE_EXTENSIONS.values():
    ALL_FILE_EXTENSIONS.extend(category)


# ==============================================================================
# COMMON DOMAIN TLDS
# ==============================================================================

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


# ==============================================================================
# NUMBER WORDS FOR SPEECH RECOGNITION
# ==============================================================================

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


# ==============================================================================
# MATHEMATICAL OPERATORS
# ==============================================================================

MATH_OPERATORS = ["plus", "minus", "times", "divided by", "over", "equals"]


# ==============================================================================
# FILLER WORDS FOR REMOVAL
# ==============================================================================

FILLER_WORDS = ["um", "uh", "er", "ah", "umm", "uhh", "hmm", "huh", "mhm", "mm-hmm", "uh-huh"]


# ==============================================================================
# DOMAIN EXCLUDE WORDS
# Words that commonly end with TLD patterns and should NOT be split
# ==============================================================================

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
# ABBREVIATION RESTORATION MAPPINGS
# ==============================================================================

ABBREVIATION_RESTORATION_PATTERNS = {
    "ie": "i.e.",
    "eg": "e.g.",
    "ex": "e.g.",  # "ex" is converted to "e.g." in this system
    "etc": "etc.",
    "vs": "vs.",
    "cf": "cf.",
}


# ==============================================================================
# EMOJI MAPPINGS
# ==============================================================================

# Tier 1: Implicit emoji patterns (can be used without "emoji" trigger word)
SPOKEN_EMOJI_IMPLICIT_MAP = {
    "smiley face": ":",
    "smiley": ":",
    "sad face": ":",
    "winking face": ";)",
    "crying face": ":'(",
    "laughing face": ":D",
    "angry face": ">:(",
    "screaming face": ":O",
    "thumbs up": "(y)",
    "thumbs down": "(n)",
}

# Tier 2: Explicit emoji patterns (must be followed by "emoji", "icon", or "emoticon")
SPOKEN_EMOJI_EXPLICIT_MAP = {
    # Common Symbols & Reactions
    "heart": "<3",
    "broken heart": "</3",
    "fire": "(fire)",
    "star": "*",
    "check mark": "(check)",
    "cross mark": "(x)",
    "one hundred": "100",
    "100": "100",
    "clapping hands": "(clap)",
    "applause": "(clap)",
    "folded hands": "(pray)",
    "praying hands": "(pray)",
    "flexed biceps": "(muscle)",
    "strong": "(muscle)",
    # Objects & Technology
    "rocket": "(rocket)",
    "light bulb": "(idea)",
    "bomb": "(bomb)",
    "money bag": "($)",
    "gift": "(gift)",
    "ghost": "(ghost)",
    "robot": "(robot)",
    "camera": "(camera)",
    "laptop": "(laptop)",
    "phone": "(phone)",
    "magnifying glass": "(search)",
    # Nature & Animals
    "sun": "(sun)",
    "cloud": "(cloud)",
    "rain cloud": "(rain)",
    "lightning bolt": "(zap)",
    "snowflake": "(snow)",
    "snowman": "(snowman)",
    "cat": "(cat)",
    "dog": "(dog)",
    "monkey": "(monkey)",
    "pig": "(pig)",
    "unicorn": "(unicorn)",
    "t-rex": "(dino)",
    # Food & Drink
    "pizza": "(pizza)",
    "coffee": "(coffee)",
    "cake": "(cake)",
    "taco": "(taco)",
}


# ==============================================================================
# HELPER FUNCTIONS
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
