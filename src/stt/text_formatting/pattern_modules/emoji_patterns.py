#!/usr/bin/env python3
"""
Emoji patterns and mappings for text formatting.

This module contains emoji mappings and patterns for converting
spoken emoji descriptions to actual emoji characters.
"""
from __future__ import annotations


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