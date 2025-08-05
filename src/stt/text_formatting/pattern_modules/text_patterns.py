#!/usr/bin/env python3
"""
General text processing regular expression patterns for text formatting.

This module contains all general text-related patterns used throughout the text 
formatting system, including filler words, abbreviations, emoji patterns, 
capitalization patterns, and letter patterns.

All patterns use re.VERBOSE flag where beneficial and include detailed comments
explaining each component.
"""
from __future__ import annotations

import re
from typing import Pattern

from ..constants import get_resources


# ==============================================================================
# FILLER WORDS AND TEXT CLEANING
# ==============================================================================

# Filler words for removal
FILLER_WORDS = ["um", "uh", "er", "ah", "umm", "uhh", "hmm", "huh", "mhm", "mm-hmm", "uh-huh"]


def build_filler_pattern() -> re.Pattern[str]:
    """Build the filler words pattern."""
    return re.compile(
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


def get_filler_pattern() -> re.Pattern[str]:
    """Get the compiled filler words pattern."""
    return FILLER_WORDS_PATTERN


# Pre-compiled pattern for performance
FILLER_WORDS_PATTERN = build_filler_pattern()


# ==============================================================================
# PUNCTUATION NORMALIZATION
# ==============================================================================

# Normalize repeated punctuation
REPEATED_PUNCTUATION_PATTERNS = [
    (re.compile(r"([,;:])\1+"), r"\1"),  # Repeated commas, semicolons, colons
    (re.compile(r"\.\.+"), "."),  # Multiple dots to single dot
    (re.compile(r"\?\?+"), "?"),  # Multiple question marks
    (re.compile(r"!!+"), "!"),  # Multiple exclamation marks
]


def get_repeated_punctuation_patterns() -> list[tuple[re.Pattern[str], str]]:
    """Get the repeated punctuation patterns."""
    return REPEATED_PUNCTUATION_PATTERNS


# ==============================================================================
# PROFANITY FILTERING
# ==============================================================================

def create_profanity_pattern(profanity_words: list[str]) -> re.Pattern[str]:
    """
    Create a pattern to filter profanity words.

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

def build_all_caps_preservation_pattern() -> re.Pattern[str]:
    """Build pattern to preserve all-caps words (acronyms) and technical units."""
    return re.compile(
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


def build_sentence_capitalization_pattern() -> re.Pattern[str]:
    """Build pattern to capitalize letters after sentence-ending punctuation."""
    return re.compile(
        r"""
        ([.!?]\s+)                          # Sentence-ending punctuation + space(s)
        ([a-z])                             # Lowercase letter to capitalize
        """,
        re.VERBOSE,
    )


def build_pronoun_i_pattern() -> re.Pattern[str]:
    """Build pattern to capitalize pronoun 'i' while avoiding code variables."""
    return re.compile(
        r"""
        (?<![a-zA-Z])                       # Not preceded by letter
        i                                   # The letter 'i'
        (?![a-zA-Z+\-])                     # Not followed by letter, plus, or minus
        """,
        re.VERBOSE,
    )


def get_all_caps_preservation_pattern() -> re.Pattern[str]:
    """Get the compiled all-caps preservation pattern."""
    return ALL_CAPS_PRESERVATION_PATTERN


def get_sentence_capitalization_pattern() -> re.Pattern[str]:
    """Get the compiled sentence capitalization pattern."""
    return SENTENCE_CAPITALIZATION_PATTERN


def get_pronoun_i_pattern() -> re.Pattern[str]:
    """Get the compiled pronoun I pattern."""
    return PRONOUN_I_PATTERN


# Pre-compiled patterns
ALL_CAPS_PRESERVATION_PATTERN = build_all_caps_preservation_pattern()
SENTENCE_CAPITALIZATION_PATTERN = build_sentence_capitalization_pattern()
PRONOUN_I_PATTERN = build_pronoun_i_pattern()


# ==============================================================================
# TECHNICAL CONTENT DETECTION
# ==============================================================================

def build_technical_content_patterns() -> list[re.Pattern[str]]:
    """Build patterns for technical content that don't need punctuation."""
    return [
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


def get_technical_content_patterns() -> list[re.Pattern[str]]:
    """Get the technical content detection patterns."""
    return TECHNICAL_CONTENT_PATTERNS


# Pre-compiled patterns
TECHNICAL_CONTENT_PATTERNS = build_technical_content_patterns()


# ==============================================================================
# LETTER PATTERNS
# ==============================================================================

def build_spoken_letter_pattern(language: str = "en") -> re.Pattern[str]:
    """Builds the spoken letter pattern dynamically from keywords in constants."""
    # Get resources for the specified language
    resources = get_resources(language)

    # Get letter case keywords and letter keywords from resources
    letter_case_keywords = resources.get("letters", {})
    letter_keywords = resources.get("spoken_keywords", {}).get("letters", {})

    # Create pattern for case words (capital, uppercase, lowercase, etc.)
    case_words = list(letter_case_keywords.keys())
    case_words_escaped = [re.escape(word) for word in case_words]
    case_pattern = "|".join(case_words_escaped) if case_words_escaped else "capital|uppercase|lowercase|small"

    # Create pattern for individual letters A-Z
    letters = [chr(i) for i in range(ord("A"), ord("Z") + 1)]
    letters_lower = [chr(i) for i in range(ord("a"), ord("z") + 1)]
    all_letters = letters + letters_lower

    # Add any custom letter pronunciations from resources
    letter_pronunciations = []
    for key, value in letter_keywords.items():
        if len(value) == 1 and value.isalpha():
            letter_pronunciations.append(re.escape(key))

    # Create letter pattern (including phonetic pronunciations if available)
    if letter_pronunciations:
        letter_pattern = "|".join(letter_pronunciations + [re.escape(letter) for letter in all_letters])
    else:
        letter_pattern = "|".join(re.escape(letter) for letter in all_letters)

    # Check language to determine word order
    if language == "es":
        # Spanish: "A mayúscula" (letter + case)
        pattern_str = rf"""
        \b                                  # Word boundary
        ({letter_pattern})                  # Capture group 1: letter
        \s+                                 # Space
        ({case_pattern})                    # Capture group 2: case modifier
        \b                                  # Word boundary
        """
    else:
        # English and other languages: "capital A" (case + letter)
        pattern_str = rf"""
        \b                                  # Word boundary
        ({case_pattern})                    # Capture group 1: case modifier
        \s+                                 # Space
        ({letter_pattern})                  # Capture group 2: letter
        \b                                  # Word boundary
        """

    return re.compile(pattern_str, re.VERBOSE | re.IGNORECASE)


def build_letter_sequence_pattern(language: str = "en") -> re.Pattern[str]:
    """Builds the letter sequence pattern for sequences like 'A B C' dynamically."""
    # Get resources for the specified language
    resources = get_resources(language)

    # Get letter case keywords and letter keywords from resources
    letter_case_keywords = resources.get("letters", {})
    letter_keywords = resources.get("spoken_keywords", {}).get("letters", {})

    # Create pattern for case words (capital, uppercase, lowercase, etc.)
    case_words = list(letter_case_keywords.keys())
    case_words_escaped = [re.escape(word) for word in case_words]
    case_pattern = "|".join(case_words_escaped) if case_words_escaped else "capital|uppercase|lowercase|small"

    # Create pattern for individual letters A-Z
    letters = [chr(i) for i in range(ord("A"), ord("Z") + 1)]
    letters_lower = [chr(i) for i in range(ord("a"), ord("z") + 1)]
    all_letters = letters + letters_lower

    # Add any custom letter pronunciations from resources
    letter_pronunciations = []
    for key, value in letter_keywords.items():
        if len(value) == 1 and value.isalpha():
            letter_pronunciations.append(re.escape(key))

    # Create letter pattern (including phonetic pronunciations if available)
    if letter_pronunciations:
        letter_pattern = "|".join(letter_pronunciations + [re.escape(letter) for letter in all_letters])
    else:
        letter_pattern = "|".join(re.escape(letter) for letter in all_letters)

    # Create a single letter unit pattern that can optionally have a case modifier
    letter_unit = rf"""
        (?:({case_pattern})\s+)?        # Optional case modifier
        ({letter_pattern})              # Letter
    """

    # Create the letter sequence pattern - matches 2 or more letter units
    pattern_str = rf"""
    \b                                  # Word boundary
    {letter_unit}                       # First letter (with optional case)
    (?:                                 # Additional letters
        \s+                             # Space separator
        {letter_unit}                   # Another letter unit (with optional case)
    ){{1,}}                             # One or more additional letters
    \b                                  # Word boundary
    """

    return re.compile(pattern_str, re.VERBOSE | re.IGNORECASE)


def get_spoken_letter_pattern(language: str = "en") -> re.Pattern[str]:
    """Get the compiled spoken letter pattern for the specified language."""
    if language == "en":
        return SPOKEN_LETTER_PATTERN
    else:
        return build_spoken_letter_pattern(language)


def get_letter_sequence_pattern(language: str = "en") -> re.Pattern[str]:
    """Get the compiled letter sequence pattern for the specified language."""
    if language == "en":
        return LETTER_SEQUENCE_PATTERN
    else:
        return build_letter_sequence_pattern(language)


# Pre-compiled patterns for English (default)
SPOKEN_LETTER_PATTERN = build_spoken_letter_pattern("en")
LETTER_SEQUENCE_PATTERN = build_letter_sequence_pattern("en")


# ==============================================================================
# ABBREVIATION PATTERNS
# ==============================================================================

def build_abbreviation_pattern() -> re.Pattern[str]:
    """Build the abbreviation pattern for Latin abbreviations."""
    return re.compile(
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


def get_abbreviation_pattern() -> re.Pattern[str]:
    """Get the compiled abbreviation pattern."""
    return ABBREVIATION_PATTERN


# Abbreviation restoration after punctuation model
ABBREVIATION_RESTORATION_PATTERNS = {
    "ie": "i.e.",
    "eg": "e.g.",
    "ex": "e.g.",  # "ex" is converted to "e.g." in this system
    "etc": "etc.",
    "vs": "vs.",
    "cf": "cf.",
}


def create_abbreviation_restoration_pattern(abbr: str) -> re.Pattern[str]:
    """Create a pattern to restore periods to abbreviations."""
    return re.compile(
        rf"""
        (?<![.])                        # Not preceded by period
        \b{re.escape(abbr)}\b           # The abbreviation
        (?![.])                         # Not followed by period
        """,
        re.VERBOSE | re.IGNORECASE,
    )


def get_abbreviation_restoration_patterns() -> dict[str, str]:
    """Get the abbreviation restoration mappings."""
    return ABBREVIATION_RESTORATION_PATTERNS.copy()


# Pre-compiled pattern
ABBREVIATION_PATTERN = build_abbreviation_pattern()


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


def get_spoken_emoji_implicit_map() -> dict[str, str]:
    """Get the implicit emoji mappings."""
    return SPOKEN_EMOJI_IMPLICIT_MAP.copy()


def get_spoken_emoji_explicit_map() -> dict[str, str]:
    """Get the explicit emoji mappings."""
    return SPOKEN_EMOJI_EXPLICIT_MAP.copy()


# ==============================================================================
# PLACEHOLDER PATTERNS
# ==============================================================================

def build_placeholder_pattern() -> re.Pattern[str]:
    """Build pattern for internal placeholder tokens used during processing."""
    return re.compile(
        r"""
        __PLACEHOLDER_\d+__ |               # Placeholder tokens
        __ENTITY_\d+__ |                    # Entity tokens
        __CAPS_\d+__                        # Capitalization tokens
        """,
        re.VERBOSE,
    )


def get_placeholder_pattern() -> re.Pattern[str]:
    """Get the compiled placeholder pattern."""
    return PLACEHOLDER_PATTERN


# Pre-compiled pattern
PLACEHOLDER_PATTERN = build_placeholder_pattern()


# ==============================================================================
# WHITESPACE AND CLEANING PATTERNS
# ==============================================================================

def build_whitespace_normalization_pattern() -> re.Pattern[str]:
    """Build pattern for normalizing whitespace."""
    return re.compile(r"\s+")


def build_repeated_dots_pattern() -> re.Pattern[str]:
    """Build pattern for repeated dots."""
    return re.compile(r"\.\.+")


def build_repeated_question_marks_pattern() -> re.Pattern[str]:
    """Build pattern for repeated question marks."""
    return re.compile(r"\?\?+")


def build_repeated_exclamation_marks_pattern() -> re.Pattern[str]:
    """Build pattern for repeated exclamation marks."""
    return re.compile(r"!!+")


def build_pronoun_i_standalone_pattern() -> re.Pattern[str]:
    """Build pattern for standalone pronoun 'i'."""
    return re.compile(r"\bi\b")


def build_temperature_protection_pattern() -> re.Pattern[str]:
    """Build pattern for temperature values protection."""
    return re.compile(r"-?\d+(?:\.\d+)?°[CF]?")


def build_entity_boundary_pattern() -> re.Pattern[str]:
    """Build pattern for entity boundaries."""
    return re.compile(r"\b(?=\w)")


def get_whitespace_normalization_pattern() -> re.Pattern[str]:
    """Get the whitespace normalization pattern."""
    return WHITESPACE_NORMALIZATION_PATTERN


def get_repeated_dots_pattern() -> re.Pattern[str]:
    """Get the repeated dots pattern."""
    return REPEATED_DOTS_PATTERN


def get_repeated_question_marks_pattern() -> re.Pattern[str]:
    """Get the repeated question marks pattern."""
    return REPEATED_QUESTION_MARKS_PATTERN


def get_repeated_exclamation_marks_pattern() -> re.Pattern[str]:
    """Get the repeated exclamation marks pattern."""
    return REPEATED_EXCLAMATION_MARKS_PATTERN


def get_pronoun_i_standalone_pattern() -> re.Pattern[str]:
    """Get the standalone pronoun I pattern."""
    return PRONOUN_I_STANDALONE_PATTERN


def get_temperature_protection_pattern() -> re.Pattern[str]:
    """Get the temperature protection pattern."""
    return TEMPERATURE_PROTECTION_PATTERN


def get_entity_boundary_pattern() -> re.Pattern[str]:
    """Get the entity boundary pattern."""
    return ENTITY_BOUNDARY_PATTERN


# Pre-compiled patterns for performance
WHITESPACE_NORMALIZATION_PATTERN = build_whitespace_normalization_pattern()
REPEATED_DOTS_PATTERN = build_repeated_dots_pattern()
REPEATED_QUESTION_MARKS_PATTERN = build_repeated_question_marks_pattern()
REPEATED_EXCLAMATION_MARKS_PATTERN = build_repeated_exclamation_marks_pattern()
PRONOUN_I_STANDALONE_PATTERN = build_pronoun_i_standalone_pattern()
TEMPERATURE_PROTECTION_PATTERN = build_temperature_protection_pattern()
ENTITY_BOUNDARY_PATTERN = build_entity_boundary_pattern()


# ==============================================================================
# UTILITY FUNCTIONS
# ==============================================================================

def create_artifact_patterns(artifacts: list[str]) -> list[Pattern]:
    """Create and cache compiled patterns for transcription artifacts."""
    return [re.compile(r"\b" + re.escape(artifact) + r"\b", re.IGNORECASE) for artifact in artifacts]


def get_compiled_text_pattern(pattern_name: str) -> Pattern | None:
    """Get a pre-compiled text pattern by name."""
    pattern_map = {
        # Cleaning patterns
        "filler": FILLER_WORDS_PATTERN,
        "whitespace": WHITESPACE_NORMALIZATION_PATTERN,
        "dots": REPEATED_DOTS_PATTERN,
        "questions": REPEATED_QUESTION_MARKS_PATTERN,
        "exclamations": REPEATED_EXCLAMATION_MARKS_PATTERN,
        "pronoun_i": PRONOUN_I_STANDALONE_PATTERN,
        "temperature": TEMPERATURE_PROTECTION_PATTERN,
        "entity_boundary": ENTITY_BOUNDARY_PATTERN,
        
        # Capitalization patterns
        "all_caps_preservation": ALL_CAPS_PRESERVATION_PATTERN,
        "sentence_capitalization": SENTENCE_CAPITALIZATION_PATTERN,
        "pronoun_i_case": PRONOUN_I_PATTERN,
        
        # Letter patterns
        "spoken_letter": SPOKEN_LETTER_PATTERN,
        "letter_sequence": LETTER_SEQUENCE_PATTERN,
        
        # Abbreviation patterns
        "abbreviation": ABBREVIATION_PATTERN,
        
        # Placeholder patterns
        "placeholder": PLACEHOLDER_PATTERN,
    }
    return pattern_map.get(pattern_name)


def get_filler_words() -> list[str]:
    """Get the list of filler words."""
    return FILLER_WORDS.copy()