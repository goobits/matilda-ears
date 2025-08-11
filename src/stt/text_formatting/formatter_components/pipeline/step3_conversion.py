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

# Theory 14: Post-Conversion Entity Boundary Preservation
from stt.text_formatting.entity_boundary_tracker import EntityBoundaryTracker

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
    
    Theory 14: Enhanced with post-conversion entity boundary preservation to fix
    boundary tracking issues after Spanish entity conversion.
    
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
    if not entities:
        return text, []
        
    language = getattr(pipeline_state, 'language', 'en') if pipeline_state else 'en'
    logger.info(f"THEORY_14_DEBUG: Processing {len(entities)} entities for language '{language}'")
    
    # Step 3a: Pre-conversion conflict check
    # Resolve any remaining conflicts before conversion to prevent position tracking issues
    # DISABLED temporarily - focus on detection improvements first
    # if len(entities) > 1:
    #     logger.debug(f"Pre-conversion conflict check for {len(entities)} entities")
    #     entities = resolve_entity_conflicts(entities, text, language)
    #     logger.debug(f"After pre-conversion conflict resolution: {len(entities)} entities")
    
    # Theory 14: Initialize boundary tracker for multi-word entity handling
    # Use boundary tracking for Spanish (primary use case) or when we have many entities
    if (language == 'es' and len(entities) > 1) or len(entities) >= 3:
        logger.info(f"THEORY_14: Using EntityBoundaryTracker for {language} text with {len(entities)} entities")
        logger.info(f"THEORY_14: Entities: {[(e.type, e.text) for e in entities]}")
        return convert_entities_with_boundary_tracking(text, entities, pattern_converter, pipeline_state)
    
    # Step 3b: Original conversion logic for non-Spanish or single entity cases
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


def convert_entities_with_boundary_tracking(
    text: str,
    entities: list[Entity],
    pattern_converter: PatternConverter,
    pipeline_state: PipelineState = None
) -> tuple[str, list[Entity]]:
    """
    Convert entities with boundary tracking for Spanish multi-word entities.
    
    Theory 14: Post-Conversion Entity Boundary Preservation
    
    This function uses EntityBoundaryTracker to maintain accurate entity positions
    throughout the conversion process, particularly for Spanish entities that change
    text length (e.g., "guión guión" -> "--").
    
    Args:
        text: The original text containing entities
        entities: List of detected entities to convert
        pattern_converter: The converter to use for entity transformations
        pipeline_state: Pipeline state for context
        
    Returns:
        Tuple of (processed_text, converted_entities) with accurate boundaries
    """
    logger.debug(f"Converting {len(entities)} entities with boundary tracking")
    
    # Initialize the boundary tracker
    boundary_tracker = EntityBoundaryTracker(entities, text)
    language = getattr(pipeline_state, 'language', 'en') if pipeline_state else 'en'
    
    # Sort entities by start position to process in sequence
    sorted_entities = sorted(boundary_tracker.entities, key=lambda e: e.start)
    
    # Process each entity with boundary tracking
    for entity in sorted_entities:
        # Skip overlapping entities
        if any(other.start < entity.end and other.end > entity.start and other != entity 
               for other in sorted_entities):
            # Only skip if this entity starts after an overlapping one
            overlapping_entities = [
                other for other in sorted_entities 
                if other.start < entity.end and other.end > entity.start and other != entity
            ]
            if any(other.start < entity.start for other in overlapping_entities):
                logger.debug(f"Skipping overlapping entity: {entity.type}('{entity.text}')")
                continue
        
        # Pass pipeline state to entity for intelligent context-aware conversion
        if pipeline_state:
            entity._pipeline_state = pipeline_state
        
        original_text = entity.text
        
        try:
            # Convert the entity
            converted_text = pattern_converter.convert(entity, boundary_tracker.current_text)
            
            # Apply Spanish-specific spacing rules if needed
            if language == 'es' and converted_text != original_text:
                # Get context for spacing decisions
                context_start = max(0, entity.start - 10)
                context_end = min(len(boundary_tracker.current_text), entity.end + 10)
                context_before = boundary_tracker.current_text[context_start:entity.start]
                context_after = boundary_tracker.current_text[entity.end:context_end]
                
                converted_text = boundary_tracker.apply_spanish_spacing_rules(
                    original_text, converted_text, context_before, context_after
                )
            
            # Record the conversion in the boundary tracker
            if converted_text != original_text:
                boundary_tracker.record_conversion(entity, original_text, converted_text)
                logger.debug(f"Converted entity {entity.type}: '{original_text}' -> '{converted_text}'")
            
        except Exception as e:
            logger.warning(f"Error converting entity {entity.type}('{original_text}'): {e}")
            # Don't record conversion if it failed
    
    # Get the final text and updated entities
    final_text = boundary_tracker.current_text
    updated_entities = boundary_tracker.get_updated_entities()
    
    logger.debug(f"Boundary tracking completed: {len(updated_entities)} entities with valid boundaries")
    
    # Log debug information for troubleshooting
    debug_info = boundary_tracker.get_debug_info()
    if debug_info['changes_count'] > 0:
        logger.debug(f"Boundary tracker applied {debug_info['changes_count']} changes")
        for change in debug_info['changes'][:3]:  # Log first 3 changes
            logger.debug(f"  Change: '{change['old_text']}' -> '{change['new_text']}' (Δ{change['length_change']})")
    
    return final_text, updated_entities