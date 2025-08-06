#!/usr/bin/env python3
"""
Filler words and basic text cleaning patterns for text formatting.

This module contains patterns and functions for handling filler words, 
basic text cleaning, and artifact removal during text processing.
"""
from __future__ import annotations

import re
from typing import Pattern


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


def get_filler_words() -> list[str]:
    """Get the list of filler words."""
    return FILLER_WORDS.copy()


def create_artifact_patterns(artifacts: list[str]) -> list[Pattern]:
    """Create and cache compiled patterns for transcription artifacts."""
    return [re.compile(r"\b" + re.escape(artifact) + r"\b", re.IGNORECASE) for artifact in artifacts]


# Pre-compiled pattern for performance
FILLER_WORDS_PATTERN = build_filler_pattern()