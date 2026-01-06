#!/usr/bin/env python3
"""Main text formatting orchestrator.

This module provides the TextFormatter class which orchestrates the complete
text formatting pipeline using specialized processors:

- TextPreprocessor: Artifact cleaning and filtering
- PunctuationProcessor: Punctuation restoration and abbreviation handling
- TextPostprocessor: Domain rescue, keyword conversion, and final cleanup

The pipeline processes text in this order:
1. Clean artifacts and apply filters (preprocessor)
2. Detect entities (web, code, numeric, base SpaCy)
3. Convert entities to formatted text
4. Add punctuation with entity protection (punctuation)
5. Apply capitalization with entity protection
6. Post-process (orphaned keywords, domain rescue, smart quotes)
"""

import re
from typing import List, Optional

from intervaltree import IntervalTree

from ...common import Entity, EntityType
from ...constants import get_resources
from ...detectors.code_detector import CodeEntityDetector
from ...detectors.numeric_detector import NumericalEntityDetector
from ...detectors.web_detector import WebEntityDetector
from ..nlp_provider import get_nlp
from ...capitalizer import SmartCapitalizer
from ....core.config import setup_logging
from .entity_detector import EntityDetector
from .converter import PatternConverter
from .preprocessor import TextPreprocessor
from .punctuation import PunctuationProcessor
from .postprocessor import TextPostprocessor

logger = setup_logging(__name__, log_filename="text_formatting.txt")


class TextFormatter:
    """Main formatter orchestrating the pipeline."""

    def __init__(self, language: str = "en"):
        # Store the language for this formatter instance
        self.language = language

        # Load shared NLP model once
        self.nlp = get_nlp()

        # Initialize specialized processors
        self.preprocessor = TextPreprocessor(language=self.language)
        self.punctuation_processor = PunctuationProcessor(language=self.language, nlp=self.nlp)
        self.postprocessor = TextPostprocessor(language=self.language)

        # Initialize components with dependency injection and language support
        self.entity_detector = EntityDetector(nlp=self.nlp, language=self.language)
        self.pattern_converter = PatternConverter(language=self.language)
        self.smart_capitalizer = SmartCapitalizer(language=self.language)

        # Instantiate specialized detectors with shared NLP model and language
        self.web_detector = WebEntityDetector(nlp=self.nlp, language=self.language)
        self.code_detector = CodeEntityDetector(nlp=self.nlp, language=self.language)
        self.numeric_detector = NumericalEntityDetector(nlp=self.nlp, language=self.language)

        # Load language-specific resources
        self.resources = get_resources(language)

    def format_transcription(
        self, text: str, key_name: str = "", enter_pressed: bool = False, language: Optional[str] = None
    ) -> str:
        """Main formatting pipeline.

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

        # Track original punctuation state for later use
        original_had_punctuation = bool(text.rstrip() and text.rstrip()[-1] in ".!?")

        # Step 1: Clean artifacts and filter (preserve case)
        text = self.preprocessor.clean_artifacts(text)
        text = self.preprocessor.apply_filters(text)

        if not text:
            logger.info("Transcription filtered: content matched filtering rules")
            return ""

        # Step 2: Entity detection pipeline (most specific to most general)
        final_entities: list[Entity] = []

        # Code and Web entities are highly specific and should run first
        web_entities = self.web_detector.detect(text, final_entities)
        final_entities.extend(web_entities)
        logger.debug(f"Web entities detected: {len(web_entities)} - {[f'{e.type}:{e.text}' for e in web_entities]}")

        code_entities = self.code_detector.detect(text, final_entities)
        final_entities.extend(code_entities)
        logger.debug(f"Code entities detected: {len(code_entities)} - {[f'{e.type}:{e.text}' for e in code_entities]}")

        # Numeric entities are next, as they are more specific than base SpaCy entities
        numeric_entities = self.numeric_detector.detect(text, final_entities)
        final_entities.extend(numeric_entities)
        logger.debug(
            f"Numeric entities detected: {len(numeric_entities)} - {[f'{e.type}:{e.text}' for e in numeric_entities]}"
        )

        # Finally, run the base SpaCy detector for general entities like DATE, TIME, etc.
        base_spacy_entities = self.entity_detector.detect_entities(text, final_entities, doc=doc)
        final_entities.extend(base_spacy_entities)
        logger.debug(
            f"Base SpaCy entities detected: {len(base_spacy_entities)} - "
            f"{[f'{e.type}:{e.text}' for e in base_spacy_entities]}"
        )

        # Step 3: Deduplicate and prioritize entities
        filtered_entities = self._deduplicate_entities(final_entities)

        # Step 4: Convert entities and assemble final string
        processed_text, converted_entities = self._convert_and_assemble(text, filtered_entities)
        logger.debug(f"Processed text after entity conversion: '{processed_text}'")

        # Step 5: Apply punctuation with entity protection
        is_standalone_technical = self._is_standalone_technical(text, filtered_entities)
        final_text = self.punctuation_processor.add_punctuation(
            processed_text, original_had_punctuation, is_standalone_technical, converted_entities
        )
        logger.debug(f"Text after punctuation: '{final_text}'")

        # Step 6: Remove trailing punctuation from standalone entities
        logger.debug(f"Text before standalone entity cleanup: '{final_text}'")
        cleaned_text = self.postprocessor.clean_standalone_entity_punctuation(final_text, converted_entities)
        logger.debug(f"Text after standalone entity cleanup: '{cleaned_text}'")

        # Check if capitalization should be skipped
        punctuation_was_removed = cleaned_text != final_text
        has_cli_command = any(entity.type == EntityType.CLI_COMMAND for entity in converted_entities)
        has_lowercase_version = any(entity.type == EntityType.VERSION for entity in converted_entities) and re.match(
            r"^v\d", cleaned_text
        )
        skip_capitalization_for_cli = punctuation_was_removed and (has_cli_command or has_lowercase_version)

        final_text = cleaned_text

        # Step 7: Apply capitalization
        if not is_standalone_technical and not skip_capitalization_for_cli:
            logger.debug(f"Text before capitalization: '{final_text}'")
            final_text = self._apply_capitalization_with_entity_protection(final_text, converted_entities, doc=doc)
            logger.debug(f"Text after capitalization: '{final_text}'")

        text = final_text
        logger.debug(f"Text after processing: '{text}'")

        # Step 8: Clean up formatting artifacts
        text = re.sub(r"\.\.+", ".", text)
        text = re.sub(r"\?\?+", "?", text)
        text = re.sub(r"!!+", "!", text)

        # Step 9: Restore abbreviations
        text = self.punctuation_processor.restore_abbreviations(text)

        # Step 10: Convert orphaned keywords
        logger.debug(f"Text before keyword conversion: '{text}'")
        text = self.postprocessor.convert_orphaned_keywords(text)
        logger.debug(f"Text after keyword conversion: '{text}'")

        # Step 11: Domain rescue
        logger.debug(f"Text before domain rescue: '{text}'")
        text = self.postprocessor.rescue_mangled_domains(text)
        logger.debug(f"Text after domain rescue: '{text}'")

        # Step 12: Apply smart quotes
        logger.debug(f"Text before smart quotes: '{text}'")
        text = self.postprocessor.apply_smart_quotes(text)
        logger.debug(f"Text after smart quotes: '{text}'")

        logger.debug(f"Final formatted: '{text[:50]}...'")
        return text

    def _deduplicate_entities(self, entities: List[Entity]) -> List[Entity]:
        """Deduplicate entities using interval tree for O(n log n) performance."""
        logger.debug(f"Starting deduplication with {len(entities)} entities:")
        for i, entity in enumerate(entities):
            logger.debug(f"  {i}: {entity.type}('{entity.text}') at [{entity.start}:{entity.end}]")

        # Define entity priority (higher number = higher priority)
        entity_priorities = {
            EntityType.MATH_EXPRESSION: 10,
            EntityType.COMPARISON: 9,
            EntityType.ASSIGNMENT: 8,
            EntityType.FILENAME: 7,
            EntityType.UNDERSCORE_DELIMITER: 6,
            EntityType.SCIENTIFIC_NOTATION: 5,
            EntityType.NUMERIC_RANGE: 5,
            EntityType.FRACTION: 5,
            EntityType.TIME_AMPM: 4,
            EntityType.TIME: 4,
            EntityType.SIMPLE_UNDERSCORE_VARIABLE: 3,
            EntityType.CARDINAL: 1,
            EntityType.QUANTITY: 1,
        }

        # Sort entities by priority (desc), then by length (desc) for tie-breaking
        def entity_sort_key(e):
            priority = entity_priorities.get(e.type, 0)
            length = e.end - e.start
            return (-priority, -length, e.start)

        sorted_entities = sorted(entities, key=entity_sort_key)

        # Use interval tree for O(log n) overlap detection
        tree = IntervalTree()
        filtered_entities = []

        for entity in sorted_entities:
            # Check for overlaps in O(log n) time
            overlaps = tree[entity.start : entity.end]

            if not overlaps:
                # No overlap, add this entity
                tree[entity.start : entity.end] = entity
                filtered_entities.append(entity)
                logger.debug(f"Added entity: {entity.type}('{entity.text}') at [{entity.start}:{entity.end}]")
            else:
                # Entity overlaps with existing higher-priority entities, skip it
                existing = list(overlaps)[0].data
                logger.debug(
                    f"Skipping overlapping entity: {entity.type}('{entity.text}') "
                    f"in favor of {existing.type}('{existing.text}')"
                )

        # Sort by position for final output
        filtered_entities = sorted(filtered_entities, key=lambda e: e.start)
        logger.debug(f"Found {len(filtered_entities)} final non-overlapping entities:")
        for i, entity in enumerate(filtered_entities):
            logger.debug(f"  Final {i}: {entity.type}('{entity.text}') at [{entity.start}:{entity.end}]")

        return filtered_entities

    def _convert_and_assemble(self, text: str, entities: List[Entity]) -> tuple[str, List[Entity]]:
        """Convert entities and assemble the final string, tracking positions."""
        result_parts = []
        converted_entities = []
        last_end = 0
        current_pos_in_result = 0

        for entity in entities:
            if entity.start < last_end:
                continue  # Skip overlapping entities

            # Add plain text part
            plain_text_part = text[last_end : entity.start]
            result_parts.append(plain_text_part)
            current_pos_in_result += len(plain_text_part)

            # Convert entity and track its new position
            converted_text = self.pattern_converter.convert(entity, text)
            result_parts.append(converted_text)

            # Create a new entity with updated position and text for capitalization protection
            converted_entity = Entity(
                start=current_pos_in_result,
                end=current_pos_in_result + len(converted_text),
                text=converted_text,
                type=entity.type,
                metadata=entity.metadata,
            )
            converted_entities.append(converted_entity)

            current_pos_in_result += len(converted_text)
            last_end = entity.end

        # Add any remaining text after the last entity
        result_parts.append(text[last_end:])

        # Join everything into a single string
        processed_text = "".join(result_parts)

        return processed_text, converted_entities

    def _is_standalone_technical(self, text: str, entities: List[Entity]) -> bool:
        """Check if the text consists entirely of technical entities with no natural language."""
        if not entities:
            return False

        text_stripped = text.strip()

        # Special case: If text starts with a programming keyword or CLI command,
        # it should be treated as a regular sentence
        sorted_entities = sorted(entities, key=lambda e: e.start)
        if (
            sorted_entities
            and sorted_entities[0].start == 0
            and sorted_entities[0].type in {EntityType.PROGRAMMING_KEYWORD, EntityType.CLI_COMMAND}
        ):
            logger.debug(
                f"Text starts with programming keyword/CLI command '{sorted_entities[0].text}' "
                "- not treating as standalone technical"
            )
            return False

        # Check if the text contains common verbs or action words
        words = text_stripped.lower().split()
        common_verbs = {
            "git",
            "run",
            "use",
            "set",
            "install",
            "update",
            "create",
            "delete",
            "open",
            "edit",
            "save",
            "check",
            "test",
            "build",
            "deploy",
            "start",
            "stop",
        }
        if any(word in common_verbs for word in words):
            logger.debug("Text contains common verbs - treating as sentence, not standalone technical")
            return False

        # Check if any word is NOT inside a detected entity and is a common English word
        common_words = {
            "the",
            "a",
            "is",
            "in",
            "for",
            "with",
            "and",
            "or",
            "but",
            "if",
            "when",
            "where",
            "what",
            "how",
            "why",
            "that",
            "this",
            "it",
            "to",
            "from",
            "on",
            "at",
            "by",
        }
        word_positions = []
        current_pos = 0
        for word in words:
            word_start = text_stripped.lower().find(word, current_pos)
            if word_start != -1:
                word_end = word_start + len(word)
                word_positions.append((word, word_start, word_end))
                current_pos = word_end

        # Check if any common word is not covered by an entity
        for word, start, end in word_positions:
            if word in common_words:
                covered = any(entity.start <= start and end <= entity.end for entity in entities)
                if not covered:
                    logger.debug(f"Found common word '{word}' not covered by entity - treating as sentence")
                    return False

        # Only treat as standalone technical if it consists ENTIRELY of specific technical entity types
        technical_only_types = {
            EntityType.COMMAND_FLAG,
            EntityType.SLASH_COMMAND,
            EntityType.INCREMENT_OPERATOR,
            EntityType.DECREMENT_OPERATOR,
            EntityType.UNDERSCORE_DELIMITER,
        }

        non_technical_entities = [e for e in entities if e.type not in technical_only_types]
        if non_technical_entities:
            logger.debug("Text contains non-technical entities - treating as sentence")
            return False

        # For pure technical entities, check if they cover most of the text
        if entities:
            total_entity_length = sum(len(e.text) for e in entities)
            text_length = len(text_stripped)

            # If entities cover most of the text (>95%), treat as standalone technical
            if total_entity_length / text_length > 0.95:
                logger.debug("Pure technical entities cover almost all text, treating as standalone technical content.")
                return True

        logger.debug("Text does not meet standalone technical criteria - treating as sentence")
        return False

    def _apply_capitalization_with_entity_protection(
        self, text: str, entities: List[Entity], doc=None
    ) -> str:
        """Apply capitalization while protecting entities."""
        logger.debug(f"Capitalization protection called with text: '{text}' and {len(entities)} entities")
        if not text:
            return ""

        # Debug: Check for entity position misalignment
        for entity in entities:
            if entity.start < len(text) and entity.end <= len(text):
                actual_text = text[entity.start : entity.end]
                logger.debug(
                    f"Entity {entity.type} at [{entity.start}:{entity.end}] text='{entity.text}' actual='{actual_text}'"
                )
                if actual_text != entity.text:
                    logger.warning(f"Entity position mismatch! Expected '{entity.text}' but found '{actual_text}'")
            else:
                logger.warning(
                    f"Entity {entity.type} position out of bounds: [{entity.start}:{entity.end}] "
                    f"for text length {len(text)}"
                )

        # Pass the entities directly to the capitalizer for protection
        logger.debug(f"Sending to capitalizer: '{text}'")
        capitalized_text = self.smart_capitalizer.capitalize(text, entities, doc=doc)
        logger.debug(f"Received from capitalizer: '{capitalized_text}'")

        return capitalized_text


# ==============================================================================
# PUBLIC API - Single unified function for all text processing
# ==============================================================================

# Global formatter instance
_formatter_instance = None


def format_transcription(text: str, key_name: str = "", enter_pressed: bool = False) -> str:
    """Format transcribed text with all processing steps.

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
