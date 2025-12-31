#!/usr/bin/env python3
"""Text preprocessing: artifact cleaning and filtering."""

import re

from .. import regex_patterns
from ..constants import get_resources
from ...core.config import get_config, setup_logging

config = get_config()
logger = setup_logging(__name__, log_filename="text_formatting.txt")


class TextPreprocessor:
    """Handles text cleaning and filtering before entity detection."""

    def __init__(self, language: str = "en"):
        self.language = language
        self.resources = get_resources(language)

        # Use artifacts and profanity lists from resources
        self.transcription_artifacts = self.resources.get("filtering", {}).get("transcription_artifacts", [])
        self.profanity_words = self.resources.get("filtering", {}).get("profanity_words", [])

        # Cache for compiled patterns
        self._artifact_patterns = None

    def clean_artifacts(self, text: str) -> str:
        """Clean audio artifacts and normalize text."""
        # Get context words from resources for i18n support
        meta_discussion_words = self.resources.get("context_words", {}).get(
            "meta_discussion",
            ["words", "word", "term", "terms", "phrase", "phrases", "say", "says", "said", "saying", "using", "called"],
        )

        # Define which artifacts should be preserved in meta-discussion contexts
        contextual_artifacts = self.resources.get("filtering", {}).get(
            "contextual_fillers", ["like", "actually", "literally", "basically", "sort of", "kind of"]
        )

        # Remove various transcription artifacts using context-aware replacement
        if self._artifact_patterns is None:
            self._artifact_patterns = regex_patterns.create_artifact_patterns(self.transcription_artifacts)

        for i, pattern in enumerate(self._artifact_patterns):
            # Get the original artifact word
            artifact_word = self.transcription_artifacts[i]

            # For certain filler words, check if they're being discussed
            if artifact_word in contextual_artifacts:
                # Check if this word appears in a meta-discussion context
                # Look for patterns like "words like X" or "saying X"
                preserved = False
                for meta_word in meta_discussion_words:
                    # Check if meta word appears before the artifact (within reasonable distance)
                    # Allow up to 3 words between meta word and artifact
                    meta_pattern = re.compile(
                        rf"\b{re.escape(meta_word)}\s+(?:\w+\s+){{0,3}}{re.escape(artifact_word)}\b", re.IGNORECASE
                    )
                    if meta_pattern.search(text):
                        preserved = True
                        break

                if not preserved:
                    text = pattern.sub("", text).strip()
            else:
                text = pattern.sub("", text).strip()

        # Remove filler words using centralized pattern
        text = regex_patterns.FILLER_WORDS_PATTERN.sub("", text)

        # Clean up orphaned commas at the beginning of text
        # This handles cases like "Actually, that's great" → ", that's great" → "that's great"
        text = re.sub(r"^\s*,\s*", "", text)

        # Also clean up double commas that might result from removal
        text = re.sub(r",\s*,", ",", text)

        # Normalize repeated punctuation using centralized patterns
        for pattern, replacement in regex_patterns.REPEATED_PUNCTUATION_PATTERNS:
            text = pattern.sub(replacement, text)

        # Normalize whitespace using pre-compiled pattern
        text = regex_patterns.WHITESPACE_NORMALIZATION_PATTERN.sub(" ", text).strip()

        # Filter profanity using centralized pattern creation
        profanity_pattern = regex_patterns.create_profanity_pattern(self.profanity_words)
        text = profanity_pattern.sub(lambda m: "*" * len(m.group()), text)

        return text

    def apply_filters(self, text: str) -> str:
        """Apply configured filters."""
        if not text:
            return text

        # Remove common phrases from config
        for phrase in config.filter_phrases:
            text = text.replace(phrase, "").strip()

        # Remove exact matches
        if text.lower() in [p.lower() for p in config.exact_filter_phrases]:
            logger.info(f"Transcription filtered: exact match '{text}' found in filter list")
            text = ""

        # Basic cleanup
        if text:
            text = "".join(char for char in text if ord(char) >= 32 or char in "\n\t")
            text = text.strip()

        return text
