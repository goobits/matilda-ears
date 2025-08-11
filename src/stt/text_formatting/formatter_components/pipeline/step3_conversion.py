#!/usr/bin/env python3
"""
Step 3: Entity Conversion Pipeline

This module handles the conversion of detected entities to their final text representations.
Extracted from the main formatter to modularize the pipeline processing.

This is Step 3 of the 4-step formatting pipeline:
1. Cleanup (step1_cleanup.py)
2. Detection (step2_detection.py) 
3. Conversion (step3_conversion.py) ← This module
4. Punctuation (step4_punctuation.py)
"""

from __future__ import annotations

import logging
from typing import List, Tuple

from ..pattern_converter import PatternConverter
from stt.text_formatting.common import Entity
from ..pipeline_state import PipelineState

# Theory 12: Entity Interaction Conflict Resolution
from stt.text_formatting.entity_conflict_resolver import resolve_entity_conflicts

# Setup logging
logger = logging.getLogger(__name__)


def convert_entities(
    text: str,
    entities: list[Entity],
    pattern_converter: PatternConverter,
    pipeline_state: PipelineState = None
) -> tuple[str, list[Entity]]:
    """
    Convert detected entities to their final text representations.
    
    This function processes entities in order, converting each one using the pattern
    converter while tracking the new positions of converted entities in the result text.
    
    Theory 12: Enhanced with conflict-aware conversion to handle entity interactions
    that arise during the conversion process itself.
    
    Args:
        text: The original text containing entities
        entities: List of detected entities to convert
        pattern_converter: The converter to use for entity transformations
        pipeline_state: Pipeline state for context
        
    Returns:
        Tuple of (processed_text, converted_entities) where:
        - processed_text: The text with all entities converted
        - converted_entities: List of entities with updated positions and text
    """
    # Step 3a: Pre-conversion conflict check
    # Resolve any remaining conflicts before conversion to prevent position tracking issues
    # DISABLED temporarily - focus on detection improvements first
    # if len(entities) > 1:
    #     logger.debug(f"Pre-conversion conflict check for {len(entities)} entities")
    #     language = getattr(pipeline_state, 'language', 'en') if pipeline_state else 'en'
    #     entities = resolve_entity_conflicts(entities, text, language)
    #     logger.debug(f"After pre-conversion conflict resolution: {len(entities)} entities")
    
    # Step 3b: Assemble final string AND track converted entity positions
    result_parts = []
    converted_entities = []
    last_end = 0
    current_pos_in_result = 0

    # Sort entities by start position to process in sequence
    sorted_entities = sorted(entities, key=lambda e: e.start)

    for entity in sorted_entities:
        if entity.start < last_end:
            logger.debug(f"Skipping overlapping entity: {entity.type}('{entity.text}')")
            continue  # Skip overlapping entities

        # Add plain text part
        plain_text_part = text[last_end : entity.start]
        result_parts.append(plain_text_part)
        current_pos_in_result += len(plain_text_part)

        # Convert entity and track its new position
        # Pass pipeline state to entity for intelligent context-aware conversion
        if pipeline_state:
            entity._pipeline_state = pipeline_state
        
        try:
            converted_text = pattern_converter.convert(entity, text)
        except Exception as e:
            logger.warning(f"Error converting entity {entity.type}('{entity.text}'): {e}")
            converted_text = entity.text  # Fallback to original text
        
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

    # Step 3c: Post-conversion validation
    # Ensure converted entities still have valid positions
    validated_entities = []
    for entity in converted_entities:
        if (entity.start >= 0 and entity.end <= len(processed_text) and 
            entity.start < entity.end and 
            processed_text[entity.start:entity.end] == entity.text):
            validated_entities.append(entity)
        else:
            logger.debug(f"Removing invalid converted entity: {entity.type}('{entity.text}')")

    return processed_text, validated_entities