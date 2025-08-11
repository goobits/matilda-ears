#!/usr/bin/env python3
"""
Step 1 of the text formatting pipeline: Cleanup and Filtering.

This module contains the initial text cleaning operations that prepare raw transcribed
text for entity detection and formatting. This includes:
- Removing transcription artifacts
- Applying configured text filters
- Normalizing whitespace and punctuation

Extracted from the main TextFormatter to create a modular pipeline architecture.
"""

import re
import logging
from typing import Dict, List, Any

from ... import regex_patterns
from ...constants import get_resources
from ....core.config import get_config

# Import batch regex processing for string optimization
from ...batch_regex import batch_substitutions

# Setup logging for this module
logger = logging.getLogger(__name__)

# Get configuration for filter settings
config = get_config()


def clean_artifacts(text: str, resources: Dict[str, Any]) -> str:
    """
    Clean audio artifacts and normalize text.
    
    Originally from TextFormatter._clean_artifacts() (lines 571-632).
    
    Args:
        text: Raw transcribed text to clean
        resources: Language-specific resources dictionary containing:
            - context_words.meta_discussion: Words that indicate meta-discussion
            - filtering.contextual_fillers: Filler words that may be preserved in context
            - filtering.transcription_artifacts: Artifacts to remove
            
    Returns:
        Cleaned text with artifacts removed and whitespace normalized
    """
    # Early special phrase replacements to prevent incorrect number parsing
    temporal_resources = resources.get("temporal", {})
    special_phrases = temporal_resources.get("special_phrases", {})
    
    for phrase, replacement in special_phrases.items():
        # Use word boundaries to avoid partial matches
        pattern = r'\b' + re.escape(phrase) + r'\b'
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    # Get context words from resources for i18n support
    meta_discussion_words = resources.get("context_words", {}).get(
        "meta_discussion",
        ["words", "word", "term", "terms", "phrase", "phrases", "say", "says", "said", "saying", "using", "called"],
    )

    # Define which artifacts should be preserved in meta-discussion contexts
    contextual_artifacts = resources.get("filtering", {}).get(
        "contextual_fillers", ["like", "actually", "literally", "basically", "sort of", "kind of"]
    )

    # Get transcription artifacts to remove
    transcription_artifacts = resources.get("filtering", {}).get("transcription_artifacts", [])

    # Remove various transcription artifacts using context-aware replacement
    artifact_patterns = regex_patterns.create_artifact_patterns(transcription_artifacts)

    for i, pattern in enumerate(artifact_patterns):
        # Get the original artifact word
        artifact_word = transcription_artifacts[i]

        # For certain filler words, check if they're being discussed or used meaningfully
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
            
            # Additional preservation logic for meaningful contexts
            if not preserved and artifact_word.lower() in ["actually", "basically", "literally"]:
                # Preserve filler words when they're used for emphasis or clarification
                meaningful_patterns = []
                
                if artifact_word.lower() == "actually":
                    # "actually" patterns for emphasis or clarification
                    meaningful_patterns = [
                        r"\bI\s+actually\b",                    # "I actually"
                        r"\bactually\s+(?:finished|completed|did|made|got|found|learned|understood|realized)\b", # completion
                        r"\b(?:we|they|you)\s+actually\b",      # other pronouns + actually
                        r"\bactually\s+(?:correct|true|right|wrong)\b", # correctness
                    ]
                elif artifact_word.lower() == "basically":
                    # "basically" patterns for clarification or simplification
                    meaningful_patterns = [
                        r"\bbasically\s+(?:correct|true|right|wrong|done|finished)\b", # assessment
                        r"\bbasically\s+(?:means|says|tells)\b", # explanation
                        r"\bit's\s+basically\b",                # "it's basically"
                        r"\bthat's\s+basically\b",              # "that's basically"
                    ]
                elif artifact_word.lower() == "literally":
                    # "literally" patterns for emphasis
                    meaningful_patterns = [
                        r"\bliterally\s+(?:true|correct|right|wrong)\b", # correctness
                        r"\bliterally\s+(?:said|told|meant)\b",          # quotation context
                        r"\bI\s+literally\b",                           # personal emphasis
                        r"\b(?:he|she|they)\s+literally\s+said\b",      # reported speech
                    ]
                
                for meaningful_pattern in meaningful_patterns:
                    if re.search(meaningful_pattern, text, re.IGNORECASE):
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
    profanity_words = resources.get("filtering", {}).get("profanity_words", [])
    profanity_pattern = regex_patterns.create_profanity_pattern(profanity_words)
    result: str = profanity_pattern.sub(lambda m: "*" * len(m.group()), text)
    return result


def apply_filters(text: str) -> str:
    """
    Apply configured text filters.
    
    Originally from TextFormatter._apply_filters() (lines 634-653).
    
    Args:
        text: Text to filter
        
    Returns:
        Filtered text, empty string if text matches exact filter phrases
    """
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