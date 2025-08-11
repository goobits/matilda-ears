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

# Theory 20: Spanish Technical Context Pattern Recognition
try:
    from ...spanish_technical_patterns import get_spanish_technical_recognizer
    _spanish_technical_available = True
except ImportError:
    _spanish_technical_available = False

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

    # THEORY 19: Check for entity-capitalization coordination guidance
    coordination_overrides = {}
    if pipeline_state and hasattr(pipeline_state, 'entity_capitalization_coordinator'):
        logger.debug("THEORY_19: Checking for entity-capitalization coordination guidance")
        
        # Check each entity for coordination guidance
        for entity in entities:
            should_coordinate, coordination_type = pipeline_state.should_coordinate_entity_capitalization(
                entity.type, entity.start
            )
            
            if should_coordinate:
                guidance = pipeline_state.get_entity_capitalization_guidance(entity.start)
                if guidance:
                    coordination_overrides[entity.start] = {
                        'entity': entity,
                        'guidance': guidance,
                        'coordination_type': coordination_type
                    }
                    logger.debug(f"THEORY_19: Found coordination guidance for {entity.type} at {entity.start}: {coordination_type}")
    
    # Theory 20: Check for Spanish technical context patterns
    use_technical_capitalization = False
    spanish_technical_guidance = {}
    
    if (pipeline_state and 
        getattr(pipeline_state, 'language', 'en') == 'es' and 
        _spanish_technical_available):
        
        # Check for stored technical contexts from conversion step
        spanish_technical_contexts = getattr(pipeline_state, 'spanish_technical_contexts', [])
        
        if spanish_technical_contexts:
            # Find highest confidence technical context
            best_context = max(spanish_technical_contexts, key=lambda ctx: ctx.confidence)
            
            if best_context.confidence >= 0.7:
                logger.info(f"THEORY_20: Using technical capitalization mode (confidence: {best_context.confidence:.2f})")
                use_technical_capitalization = True
                
                # Get technical-specific capitalization guidance
                try:
                    recognizer = get_spanish_technical_recognizer('es')
                    for i, char in enumerate(text):
                        if char.isalpha():
                            guidance = recognizer.get_capitalization_guidance(text, i, char)
                            if guidance.get('rule') != 'standard':
                                spanish_technical_guidance[i] = guidance
                                
                    if spanish_technical_guidance:
                        logger.debug(f"THEORY_20: Applied technical guidance to {len(spanish_technical_guidance)} positions")
                except Exception as e:
                    logger.warning(f"THEORY_20: Error getting capitalization guidance: {e}")
    
    # Theory 17: Check for conversational flow preservation
    preserve_conversational_case = False
    if (pipeline_state and 
        getattr(pipeline_state, 'conversational_context', False) and
        getattr(pipeline_state, 'conversational_analyzer', None) and
        not use_technical_capitalization):  # Technical mode overrides conversational
        
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
            # THEORY 19: Apply coordination-aware capitalization
            if coordination_overrides:
                capitalized_text = apply_coordination_aware_capitalization(
                    text, entities, capitalizer, coordination_overrides, doc
                )
            else:
                capitalized_text = capitalizer.capitalize(text, entities, doc=doc)
    elif use_technical_capitalization:
        # THEORY 20: Apply technical-aware capitalization
        logger.info("THEORY_20: Applying technical-aware capitalization")
        if coordination_overrides:
            capitalized_text = apply_coordination_aware_capitalization(
                text, entities, capitalizer, coordination_overrides, doc
            )
        else:
            capitalized_text = capitalizer.capitalize(text, entities, doc=doc)
            
        # Apply Spanish technical guidance post-processing
        if spanish_technical_guidance:
            capitalized_text = apply_spanish_technical_capitalization_guidance(
                capitalized_text, spanish_technical_guidance
            )
    else:
        # THEORY 19: Apply coordination-aware capitalization  
        if coordination_overrides:
            capitalized_text = apply_coordination_aware_capitalization(
                text, entities, capitalizer, coordination_overrides, doc
            )
        else:
            # --- CHANGE 3: Pass the `doc` object to the capitalizer ---
            capitalized_text = capitalizer.capitalize(text, entities, doc=doc)
    
    logger.debug(f"Received from capitalizer: '{capitalized_text}'")

    return capitalized_text


def apply_coordination_aware_capitalization(
    text: str, 
    entities: list[Entity], 
    capitalizer: 'SmartCapitalizer',
    coordination_overrides: dict,
    doc=None
) -> str:
    """
    Apply capitalization with entity-capitalization coordination guidance.
    
    THEORY 19: This function implements the coordination between entity conversion
    and capitalization steps by applying specific capitalization rules based on
    guidance from the EntityCapitalizationCoordinator.
    
    Args:
        text: Text to capitalize
        entities: List of entities
        capitalizer: SmartCapitalizer instance
        coordination_overrides: Dictionary of coordination guidance by position
        doc: Optional spaCy doc object
        
    Returns:
        Capitalized text with coordination overrides applied
    """
    logger.debug(f"THEORY_19: Applying coordination-aware capitalization with {len(coordination_overrides)} overrides")
    
    # First apply standard capitalization
    capitalized_text = capitalizer.capitalize(text, entities, doc=doc)
    
    # Then apply coordination overrides
    # Sort by position (reverse order to maintain string positions)
    override_positions = sorted(coordination_overrides.keys(), reverse=True)
    
    for position in override_positions:
        override_info = coordination_overrides[position]
        entity = override_info['entity']
        guidance = override_info['guidance']
        coordination_type = override_info['coordination_type']
        
        logger.debug(f"THEORY_19: Applying {coordination_type} coordination for {entity.type} at {position}")
        
        # Apply specific coordination based on guidance
        if guidance.should_preserve_case:
            # Preserve the exact case from the converted entity
            if entity.start < len(capitalized_text) and entity.end <= len(capitalized_text):
                # Keep the converted text case exactly as it is
                logger.debug(f"THEORY_19: Preserving case for {entity.type}: '{entity.text}'")
                # The case is already preserved by entity protection in the capitalizer
                
        elif guidance.should_force_lowercase:
            # Force entity to lowercase (e.g., --flags, filenames)
            if entity.start < len(capitalized_text) and entity.end <= len(capitalized_text):
                current_entity_text = capitalized_text[entity.start:entity.end]
                if current_entity_text != entity.text.lower():
                    logger.debug(f"THEORY_19: Forcing lowercase for {entity.type}: '{current_entity_text}' -> '{entity.text.lower()}'")
                    capitalized_text = (
                        capitalized_text[:entity.start] + 
                        entity.text.lower() + 
                        capitalized_text[entity.end:]
                    )
                    
        elif guidance.should_force_title_case:
            # Force entity to title case (rare for technical entities)
            if entity.start < len(capitalized_text) and entity.end <= len(capitalized_text):
                current_entity_text = capitalized_text[entity.start:entity.end]
                title_cased = entity.text.title()
                if current_entity_text != title_cased:
                    logger.debug(f"THEORY_19: Forcing title case for {entity.type}: '{current_entity_text}' -> '{title_cased}'")
                    capitalized_text = (
                        capitalized_text[:entity.start] + 
                        title_cased + 
                        capitalized_text[entity.end:]
                    )
        
        # Handle specific coordination contexts
        if guidance.capitalization_context == "long_flag_command":
            # Ensure flags like "--version" stay lowercase even at sentence start
            if entity.start == 0 or (entity.start == 1 and capitalized_text[0].isupper()):
                # This is at sentence start but should stay lowercase
                if entity.text.startswith('--') and entity.start < len(capitalized_text):
                    current_text = capitalized_text[entity.start:entity.end]
                    if current_text != entity.text.lower():
                        logger.debug(f"THEORY_19: Preserving lowercase flag at sentence start: '{entity.text}'")
                        capitalized_text = (
                            capitalized_text[:entity.start] + 
                            entity.text.lower() + 
                            capitalized_text[entity.end:]
                        )
        
        elif guidance.capitalization_context == "underscore_variable":
            # Ensure underscore variables maintain their case
            if '_' in entity.text:
                logger.debug(f"THEORY_19: Preserving underscore variable case: '{entity.text}'")
                # Case preservation is already handled above
                
        elif guidance.capitalization_context == "dot_filename":
            # Ensure dot filenames stay lowercase
            if '.' in entity.text and entity.start < len(capitalized_text):
                current_text = capitalized_text[entity.start:entity.end]
                if current_text != entity.text.lower():
                    logger.debug(f"THEORY_19: Forcing lowercase for dot filename: '{entity.text}'")
                    capitalized_text = (
                        capitalized_text[:entity.start] + 
                        entity.text.lower() + 
                        capitalized_text[entity.end:]
                    )
    
    logger.debug(f"THEORY_19: Coordination-aware capitalization complete")
    return capitalized_text


def apply_spanish_technical_capitalization_guidance(text: str, guidance_map: dict) -> str:
    """
    Apply Spanish technical capitalization guidance to text.
    
    THEORY 20: This function applies technical-specific capitalization rules
    based on Spanish technical pattern recognition results.
    
    Args:
        text: Text to apply guidance to
        guidance_map: Dictionary mapping positions to capitalization guidance
        
    Returns:
        Text with technical capitalization applied
    """
    if not guidance_map:
        return text
        
    logger.debug(f"THEORY_20: Applying technical capitalization guidance to {len(guidance_map)} positions")
    
    # Convert to list of characters for easy modification
    text_chars = list(text)
    
    # Apply guidance in reverse order to maintain positions
    for position in sorted(guidance_map.keys(), reverse=True):
        if position >= len(text_chars):
            continue
            
        guidance = guidance_map[position]
        char = text_chars[position]
        
        if not char.isalpha():
            continue
            
        rule = guidance.get('rule', 'standard')
        preserve_case = guidance.get('preserve_case', 'false').lower() == 'true'
        context_type = guidance.get('context_type', 'conversational')
        
        logger.debug(f"THEORY_20: Applying rule '{rule}' to character '{char}' at position {position} (context: {context_type})")
        
        if rule == 'preserve_technical' and preserve_case:
            # Keep the character as-is (already processed by technical systems)
            logger.debug(f"THEORY_20: Preserving technical case for '{char}' at {position}")
            continue
            
        elif rule == 'force_lowercase_technical':
            if char.isupper():
                text_chars[position] = char.lower()
                logger.debug(f"THEORY_20: Forced lowercase: '{char}' -> '{text_chars[position]}' at {position}")
                
        elif context_type in ['command_instruction', 'configuration'] and position > 0:
            # For technical contexts, prefer lowercase for non-sentence-start positions
            if char.isupper() and not _is_sentence_start_position(text, position):
                text_chars[position] = char.lower()
                logger.debug(f"THEORY_20: Technical context lowercase: '{char}' -> '{text_chars[position]}' at {position}")
    
    result_text = ''.join(text_chars)
    logger.debug(f"THEORY_20: Technical capitalization guidance applied")
    return result_text


def _is_sentence_start_position(text: str, position: int) -> bool:
    """Check if a position is at the start of a sentence"""
    if position == 0:
        return True
        
    # Look for sentence endings before this position
    before_text = text[:position].rstrip()
    if not before_text:
        return True
        
    # Check for sentence-ending punctuation
    return before_text[-1] in '.!?'


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