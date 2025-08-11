#!/usr/bin/env python3
"""
Step 5: Capitalization Pipeline Module

This module contains the capitalization logic for the text formatting pipeline.
It handles intelligent capitalization while protecting entities from modification.

Functions:
- apply_capitalization_with_entity_protection: Main capitalization function with entity protection
- is_standalone_technical: Determines if text is standalone technical content
"""

import re
from typing import TYPE_CHECKING

from ....core.config import setup_logging
from stt.text_formatting.common import Entity, EntityType

if TYPE_CHECKING:
    from ...capitalizer import SmartCapitalizer

logger = setup_logging(__name__)


def apply_capitalization_with_entity_protection(
    text: str, 
    entities: list[Entity], 
    capitalizer: 'SmartCapitalizer',
    doc=None,
    pipeline_state=None
) -> str:
    """
    Apply capitalization while protecting entities - Phase 1 simplified version.
    
    Args:
        text: Text to capitalize
        entities: List of entities to protect from capitalization changes
        capitalizer: SmartCapitalizer instance to use
        doc: Optional spaCy doc object for context
        
    Returns:
        Capitalized text with entities protected
    """
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
                f"Entity {entity.type} position out of bounds: [{entity.start}:{entity.end}] for text length {len(text)}"
            )

    # Phase 1: Use the converted entities with their correct positions in the final text
    # Pass the entities directly to the capitalizer for protection
    logger.debug(f"Sending to capitalizer: '{text}'")
    logger.debug(f"Entities being passed to capitalizer: {[(e.type, e.text, e.start, e.end) for e in entities]}")

    # Theory 17: Check for conversational flow preservation
    preserve_conversational_case = False
    if (pipeline_state and 
        getattr(pipeline_state, 'conversational_context', False) and
        getattr(pipeline_state, 'conversational_analyzer', None)):
        
        analyzer = pipeline_state.conversational_analyzer
        original_text = getattr(pipeline_state, 'original_text', '')
        preserve_conversational_case = analyzer.should_preserve_conversational_capitalization(
            text, original_text=original_text
        )
        
        if preserve_conversational_case:
            logger.info("THEORY_17: Preserving conversational capitalization flow")
            # For conversational contexts, skip automatic capitalization to preserve natural flow
            # The conversational entity processor has already handled the necessary conversions
            capitalized_text = text
        else:
            capitalized_text = capitalizer.capitalize(text, entities, doc=doc)
    else:
        # --- CHANGE 3: Pass the `doc` object to the capitalizer ---
        capitalized_text = capitalizer.capitalize(text, entities, doc=doc)
    
    logger.debug(f"Received from capitalizer: '{capitalized_text}'")

    return capitalized_text


def is_standalone_technical(text: str, entities: list[Entity], resources: dict) -> bool:
    """
    Check if the text consists entirely of technical entities with no natural language.
    
    Args:
        text: Text to analyze
        entities: List of detected entities
        resources: Language resources for context words
        
    Returns:
        True if text is standalone technical content, False otherwise
    """
    if not entities:
        return False

    text_stripped = text.strip()

    # Special case: If text starts with a programming keyword or CLI command, it should be treated as a regular sentence
    # that needs capitalization, not standalone technical content
    sorted_entities = sorted(entities, key=lambda e: e.start)
    if (
        sorted_entities
        and sorted_entities[0].start == 0
        and sorted_entities[0].type in {EntityType.PROGRAMMING_KEYWORD, EntityType.CLI_COMMAND}
    ):
        logger.debug(
            f"Text starts with programming keyword/CLI command '{sorted_entities[0].text}' - not treating as standalone technical"
        )
        return False

    # Check if the text contains common verbs or action words that indicate it's a sentence
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

    # Check if any word in the text is NOT inside a detected entity and is a common English word
    # This ensures we only treat text as standalone technical if it contains ZERO common words outside entities
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
            # Check if this word position is covered by any entity
            covered = any(entity.start <= start and end <= entity.end for entity in entities)
            if not covered:
                logger.debug(f"Found common word '{word}' not covered by entity - treating as sentence")
                return False

    # Only treat as standalone technical if it consists ENTIRELY of very specific technical entity types
    technical_only_types = {
        EntityType.COMMAND_FLAG,
        EntityType.SLASH_COMMAND,
        EntityType.INCREMENT_OPERATOR,
        EntityType.DECREMENT_OPERATOR,
        EntityType.UNDERSCORE_DELIMITER,
        EntityType.SIMPLE_UNDERSCORE_VARIABLE,
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

    # If we get here, text should be treated as a regular sentence
    logger.debug("Text does not meet standalone technical criteria - treating as sentence")
    return False