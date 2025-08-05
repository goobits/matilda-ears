#!/usr/bin/env python3
"""
Text formatter for Matilda transcriptions.

Clean architecture with 4 specialized classes:
- EntityDetector: SpaCy-powered entity detection
- NumberParser: Algorithmic number parsing
- PatternConverter: Entity-specific conversions
- SmartCapitalizer: Intelligent capitalization
"""
from __future__ import annotations

import contextlib
import os
import re

from stt.core.config import get_config, setup_logging

# Import centralized regex patterns
from . import regex_patterns
from .capitalizer import SmartCapitalizer

# Import common data structures
from .common import Entity, EntityType, NumberParser

# Import resource loader for i18n constants
from .constants import get_resources
from .detectors.code_detector import CodeEntityDetector
from .detectors.numeric_detector import NumericalEntityDetector
from .detectors.spoken_letter_detector import SpokenLetterDetector

# Import specialized formatters
from .detectors.web_detector import WebEntityDetector
from .nlp_provider import get_nlp, get_punctuator
from .pattern_converter import PatternConverter as UnifiedPatternConverter
from .utils import is_inside_entity

# Setup config and logging
config = get_config()
# Default to no console logging - will be overridden by modes if needed
logger = setup_logging(__name__, log_filename="text_formatting.txt", include_console=False)


# Import the extracted classes
from .formatter_components.entity_detector import EntityDetector
from .formatter_components.pattern_converter import PatternConverter

# Import pipeline step functions
from .formatter_components.pipeline.step1_cleanup import clean_artifacts, apply_filters
from .formatter_components.pipeline.step2_detection import detect_all_entities
from .formatter_components.pipeline.step3_conversion import convert_entities
from .formatter_components.pipeline.step4_punctuation import add_punctuation, clean_standalone_entity_punctuation
from .formatter_components.pipeline.step5_capitalization import apply_capitalization_with_entity_protection, is_standalone_technical
from .formatter_components.pipeline.step6_postprocess import (
    restore_abbreviations, 
    convert_orphaned_keywords, 
    rescue_mangled_domains, 
    apply_smart_quotes
)


class TextFormatter:
    """Main formatter orchestrating the pipeline"""

    def __init__(self, language: str = "en"):
        # Store the language for this formatter instance
        self.language = language

        # Load shared NLP model once
        self.nlp = get_nlp()

        # Initialize components with dependency injection and language support
        self.entity_detector = EntityDetector(nlp=self.nlp, language=self.language)
        self.pattern_converter = PatternConverter(language=self.language)
        self.smart_capitalizer = SmartCapitalizer(language=self.language)

        # Instantiate specialized detectors with shared NLP model and language
        # Note: Converters are now unified in PatternConverter
        self.web_detector = WebEntityDetector(nlp=self.nlp, language=self.language)
        self.code_detector = CodeEntityDetector(nlp=self.nlp, language=self.language)
        self.numeric_detector = NumericalEntityDetector(nlp=self.nlp, language=self.language)
        self.spoken_letter_detector = SpokenLetterDetector(language=self.language)

        # Load language-specific resources
        self.resources = get_resources(language)

        # Complete sentence phrases that need punctuation even when short
        self.complete_sentence_phrases = set(self.resources.get("technical", {}).get("complete_sentence_phrases", []))

        # Use artifacts and profanity lists from resources
        self.transcription_artifacts = self.resources.get("filtering", {}).get("transcription_artifacts", [])
        self.profanity_words = self.resources.get("filtering", {}).get("profanity_words", [])

    def format_transcription(
        self, text: str, key_name: str = "", enter_pressed: bool = False, language: str | None = None
    ) -> str:
        """
        Main formatting pipeline - NEW MODULAR ARCHITECTURE

        Args:
            text: Text to format
            key_name: Key name for context
            enter_pressed: Whether enter was pressed
            language: Optional language override (uses instance default if None)

        """
        # Use the override language if provided, otherwise use the instance's default
        current_language = language or self.language

        if not text or not text.strip():
            logger.debug("Empty text, skipping formatting")
            return ""

        logger.info(f"Original text: '{text}' (language: {current_language})")

        # Perform the single SpaCy processing pass at the beginning
        doc = None
        if self.nlp:
            try:
                doc = self.nlp(text)
            except (AttributeError, ValueError, IndexError) as e:
                logger.warning(f"SpaCy processing failed for text: {e}")
                # If SpaCy fails consistently, consider using fallback formatter
                self._spacy_failure_count = getattr(self, '_spacy_failure_count', 0) + 1
                if self._spacy_failure_count >= 3:
                    logger.warning("Multiple SpaCy failures detected, consider using FallbackTextFormatter")

        # Track original punctuation state for later use
        original_had_punctuation = bool(text.rstrip() and text.rstrip()[-1] in ".!?")

        # STEP 1: Clean artifacts and apply filters
        logger.debug(f"Step 1 - Before cleanup: '{text}'")
        text = clean_artifacts(text, self.resources)
        logger.debug(f"Step 1 - After artifact cleanup: '{text}'")
        
        text = apply_filters(text)
        logger.debug(f"Step 1 - After filters: '{text}'")

        if not text:
            logger.info("Transcription filtered: content matched filtering rules")
            return ""

        # STEP 2: Detect all entities with deduplication
        logger.debug(f"Step 2 - Starting entity detection on: '{text}'")
        detectors = {
            "web_detector": self.web_detector,
            "spoken_letter_detector": self.spoken_letter_detector,
            "code_detector": self.code_detector,
            "numeric_detector": self.numeric_detector,
            "entity_detector": self.entity_detector,
        }
        
        filtered_entities = detect_all_entities(text, detectors, self.nlp, doc=doc)
        logger.debug(f"Step 2 - Final entities: {len(filtered_entities)} entities detected")

        # STEP 3: Convert entities to their final representations
        logger.debug(f"Step 3 - Before entity conversion: '{text}'")
        processed_text, converted_entities = convert_entities(text, filtered_entities, self.pattern_converter)
        logger.debug(f"Step 3 - After entity conversion: '{processed_text}'")

        # STEP 4: Apply punctuation and clean standalone entity punctuation
        logger.debug(f"Step 4 - Before punctuation: '{processed_text}'")
        is_standalone_tech = is_standalone_technical(text, filtered_entities, self.resources)
        
        punctuated_text = add_punctuation(
            processed_text, 
            original_had_punctuation, 
            is_standalone_tech, 
            filtered_entities,
            nlp=self.nlp,
            language=current_language
        )
        logger.debug(f"Step 4 - After punctuation: '{punctuated_text}'")

        cleaned_text = clean_standalone_entity_punctuation(punctuated_text, converted_entities)
        logger.debug(f"Step 4 - After standalone cleanup: '{cleaned_text}'")

        # STEP 5: Apply capitalization with entity protection
        logger.debug(f"Step 5 - Before capitalization: '{cleaned_text}'")
        
        # Check if we should skip capitalization
        punctuation_was_removed = cleaned_text != punctuated_text
        has_cli_command = any(entity.type == EntityType.CLI_COMMAND for entity in converted_entities)
        has_lowercase_version = any(entity.type == EntityType.VERSION for entity in converted_entities) and re.match(
            r"^v\d", cleaned_text
        )
        skip_capitalization_for_cli = punctuation_was_removed and (has_cli_command or has_lowercase_version)
        
        # But always capitalize common sentence starters
        starts_with_common_word = any(cleaned_text.lower().startswith(word + " ") for word in ["version", "page", "chapter", "section", "line", "add", "multiply"])
        should_capitalize = not is_standalone_tech and not skip_capitalization_for_cli or starts_with_common_word
        
        if should_capitalize:
            final_text = apply_capitalization_with_entity_protection(
                cleaned_text, converted_entities, self.smart_capitalizer, doc=doc
            )
        else:
            final_text = cleaned_text
            
        logger.debug(f"Step 5 - After capitalization: '{final_text}'")

        # STEP 6: Post-processing operations
        logger.debug(f"Step 6 - Starting post-processing: '{final_text}'")
        
        # Clean up formatting artifacts
        final_text = re.sub(r"\.\.+", ".", final_text)
        final_text = re.sub(r"\?\?+", "?", final_text)
        final_text = re.sub(r"!!+", "!", final_text)
        logger.debug(f"Step 6 - After artifact cleanup: '{final_text}'")

        # Restore abbreviations
        final_text = restore_abbreviations(final_text, self.resources)
        logger.debug(f"Step 6 - After abbreviation restoration: '{final_text}'")

        # Convert orphaned keywords
        final_text = convert_orphaned_keywords(final_text, current_language)
        logger.debug(f"Step 6 - After keyword conversion: '{final_text}'")

        # Rescue mangled domains
        final_text = rescue_mangled_domains(final_text, self.resources)
        logger.debug(f"Step 6 - After domain rescue: '{final_text}'")

        # Apply smart quotes
        final_text = apply_smart_quotes(final_text)
        logger.debug(f"Step 6 - After smart quotes: '{final_text}'")

        logger.info(f"Final formatted: '{final_text[:50]}{'...' if len(final_text) > 50 else ''}'")
        return final_text


# ==============================================================================
# PUBLIC API - Single unified function for all text processing
# ==============================================================================

# Global formatter instance
_formatter_instance = None


def create_fallback_formatter(language: str = "en") -> 'FallbackTextFormatter':
    """
    Create a FallbackTextFormatter with the current TextFormatter as primary.
    
    Args:
        language: Language for formatting
        
    Returns:
        FallbackTextFormatter instance with comprehensive error handling
    """
    try:
        from .fallback_formatter import FallbackTextFormatter
        primary_formatter = TextFormatter(language=language)
        return FallbackTextFormatter(primary_formatter=primary_formatter, language=language)
    except Exception as e:
        logger.error(f"Failed to create FallbackTextFormatter: {e}")
        # Return a basic fallback that only does simple cleaning
        from .fallback_formatter import FallbackTextFormatter
        return FallbackTextFormatter(primary_formatter=None, language=language)


def format_transcription(text: str, key_name: str = "", enter_pressed: bool = False) -> str:
    """
    Format transcribed text with all processing steps.

    This is the main entry point for all text formatting. It combines:
    - Whisper artifact removal
    - Entity detection and conversion
    - Punctuation restoration
    - Smart capitalization
    - Domain rescue
    - Configurable suffix

    Args:
        text: The raw transcribed text
        key_name: The hotkey name (kept for compatibility)
        enter_pressed: Whether Enter key was pressed (affects suffix)

    Returns:
        Fully formatted text ready for output

    """
    global _formatter_instance
    if _formatter_instance is None:
        _formatter_instance = TextFormatter()

    return _formatter_instance.format_transcription(text, key_name, enter_pressed)
