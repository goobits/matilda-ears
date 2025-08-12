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
from stt.text_formatting.common import Entity, EntityType
from ..pipeline_state import PipelineState

# Theory 12: Entity Interaction Conflict Resolution
from stt.text_formatting.entity_conflict_resolver import resolve_entity_conflicts

# Theory 14: Post-Conversion Entity Boundary Preservation
from stt.text_formatting.entity_boundary_tracker import EntityBoundaryTracker

# Theory 17: Spanish Conversational Flow Preservation
from stt.text_formatting.conversational_entity_processor import ConversationalEntityProcessor

# Theory 18: Intelligent Word-After-Entity Classification
from stt.text_formatting.intelligent_word_classifier import IntelligentWordClassifier

# Theory 20: Spanish Technical Context Pattern Recognition
from stt.text_formatting.spanish_technical_patterns import get_spanish_technical_recognizer

# PHASE 19: Entity Validation Framework
from stt.text_formatting.formatter_components.validation import create_entity_validator

# Setup logging
logger = logging.getLogger(__name__)

# PHASE 21: Debug Mode Enhancement - Entity Conversion Pipeline Tracing
from stt.text_formatting.debug_utils import (
    get_entity_debugger, debug_entity_operation, debug_entity_list, debug_performance,
    DebugModule, is_debug_enabled
)


@debug_performance("entity_conversion", DebugModule.CONVERSION)
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
    
    # PHASE 21: Debug tracing - Conversion start
    debugger = get_entity_debugger()
    debugger.trace_pipeline_state(
        "conversion_start",
        text,
        entities,
        {
            "language": language,
            "entity_count": len(entities),
            "pattern_converter": type(pattern_converter).__name__,
            "has_pipeline_state": pipeline_state is not None
        }
    )
    
    if is_debug_enabled(DebugModule.CONVERSION):
        debug_entity_list(
            entities,
            "conversion",
            "entities_to_convert", 
            DebugModule.CONVERSION,
            text=text,
            language=language,
            converter_type=type(pattern_converter).__name__
        )
    
    # Theory 20: Apply Spanish technical pattern recognition
    spanish_technical_contexts = []
    if language == 'es':
        logger.debug("THEORY_20: Analyzing Spanish technical context patterns")
        try:
            recognizer = get_spanish_technical_recognizer(language)
            spanish_technical_contexts = recognizer.analyze_spanish_technical_context(text, entities)
            
            if spanish_technical_contexts:
                logger.info(f"THEORY_20: Found {len(spanish_technical_contexts)} Spanish technical contexts")
                for ctx in spanish_technical_contexts:
                    logger.debug(f"THEORY_20: Technical context: {ctx.context_type.value} (confidence: {ctx.confidence:.2f}) at {ctx.start_pos}-{ctx.end_pos}")
                
                # Store technical contexts in pipeline state for later use
                if pipeline_state:
                    pipeline_state.spanish_technical_contexts = spanish_technical_contexts
        except Exception as e:
            logger.warning(f"THEORY_20: Error in Spanish technical pattern recognition: {e}")
            spanish_technical_contexts = []
    
    # Theory 17: Apply conversational entity processing for Spanish
    logger.debug(f"THEORY_17 DEBUG: language='{language}', pipeline_state={pipeline_state is not None}, conversational_context={getattr(pipeline_state, 'conversational_context', 'NOT_FOUND') if pipeline_state else 'NO_PIPELINE_STATE'}")
    
    if language == 'es' and pipeline_state and getattr(pipeline_state, 'conversational_context', False):
        # Theory 20: Check if we should use technical or conversational processing
        has_technical_context = bool(spanish_technical_contexts and 
                                   any(ctx.confidence >= 0.7 for ctx in spanish_technical_contexts))
        
        if has_technical_context:
            logger.info("THEORY_20: Using technical processing mode for Spanish entities (overriding conversational)")
            # Set technical processing flags
            if pipeline_state:
                pipeline_state.use_technical_processing = True
                pipeline_state.technical_confidence = max(ctx.confidence for ctx in spanish_technical_contexts)
        else:
            logger.info("THEORY_17: Applying conversational entity processing")
            
            # Apply conversational replacements before standard entity conversion
            analyzer = getattr(pipeline_state, 'conversational_analyzer', None)
            if analyzer:
                conversational_result = analyzer.process_conversational_flow(text, entities)
                if conversational_result[0] != text:  # If text changed
                    logger.info(f"THEORY_17: Applied conversational flow processing: '{text}' -> '{conversational_result[0]}'")
                    text = conversational_result[0]
                    entities = conversational_result[1]
    
    
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
        
        # PHASE 21: Debug tracing - Before conversion
        original_entity_text = entity.text
        if is_debug_enabled(DebugModule.CONVERSION):
            debug_entity_operation(
                entity,
                "conversion",
                "pre_convert",
                DebugModule.CONVERSION,
                before_text=entity.text,
                position=(entity.start, entity.end),
                text_context=text[max(0, entity.start-10):entity.end+10]
            )
        
        try:
            converted_text = pattern_converter.convert(entity, text)
            
            # PHASE 21: Debug tracing - Successful conversion
            if is_debug_enabled(DebugModule.CONVERSION):
                debugger.trace_entity_conversion(
                    entity,
                    original_entity_text,
                    converted_text,
                    type(pattern_converter).__name__,
                    success=True
                )
            
            # PHASE 19: Validate entity conversion consistency
            validator = create_entity_validator(language)
            is_valid_conversion = validator.validate_entity_conversion_consistency(
                entity, converted_text, text
            )
            if not is_valid_conversion:
                logger.debug(f"PHASE_19_VALIDATION: Conversion validation failed for {entity.type}, but continuing processing")
            
        except Exception as e:
            logger.warning(f"Error converting entity {entity.type}('{entity.text}'): {e}")
            converted_text = entity.text  # Fallback to original text
            
            # PHASE 21: Debug tracing - Failed conversion
            if is_debug_enabled(DebugModule.CONVERSION):
                debugger.trace_entity_conversion(
                    entity,
                    original_entity_text,
                    converted_text,
                    type(pattern_converter).__name__,
                    success=False,
                    error=str(e)
                )
        
        # POSITION TRACKING: Update entity positions when conversion changes text length
        if converted_text != entity.text and pipeline_state:
            # Get entity ID from the universal entity tracker
            entity_id = pipeline_state.entity_tracker.generate_entity_id(entity)
            
            # Update the entity's converted text in the tracker
            if entity_id in pipeline_state.entity_tracker.entities:
                pipeline_state.entity_tracker.entities[entity_id].converted_text = converted_text
                pipeline_state.entity_tracker.mark_entity_converted(entity_id, converted_text, "step3_conversion")
                
                # If this is a text length change, we need to track position updates for subsequent entities
                length_delta = len(converted_text) - len(entity.text)
                if length_delta != 0:
                    logger.debug(f"POSITION_TRACKING: Entity {entity.type} conversion changed text length by {length_delta}")
                    # Note: We don't update positions yet - we do bulk position updates after all conversions
        
        # THEORY 19: Record conversion for capitalization coordination
        if pipeline_state and hasattr(pipeline_state, 'entity_capitalization_coordinator'):
            # Get entity ID from the universal entity tracker
            entity_id = pipeline_state.entity_tracker.generate_entity_id(entity)
            if converted_text != entity.text:  # Only record actual conversions
                guidance = pipeline_state.record_entity_conversion(
                    entity_id, entity.type, "step3_conversion", 
                    entity.text, converted_text, entity.start
                )
                logger.debug(f"THEORY_19: Recorded conversion guidance for {entity.type}: {guidance.capitalization_context}")
        
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
    
    # POSITION TRACKING: Update all entity positions in the pipeline state after conversion
    if pipeline_state:
        # Update the pipeline state's text to match the processed text
        pipeline_state.text = processed_text
        
        # Validate entity positions and log any mismatches
        position_warnings = pipeline_state.validate_entity_positions(processed_text, "step3_conversion")
        for warning in position_warnings:
            logger.warning(f"POSITION_TRACKING: {warning}")

    # Step 3c: Post-conversion validation and boundary repair
    # Ensure converted entities still have valid positions
    validated_entities = []
    for entity in converted_entities:
        if (entity.start >= 0 and entity.end <= len(processed_text) and 
            entity.start < entity.end and 
            processed_text[entity.start:entity.end] == entity.text):
            validated_entities.append(entity)
        else:
            logger.debug(f"Removing invalid converted entity: {entity.type}('{entity.text}')")

    # ENTITY BOUNDARY FIX: Additional validation for spacing issues
    # Check for common boundary problems like missing spaces around entities
    if validated_entities:
        processed_text = _fix_entity_spacing_issues(processed_text, validated_entities)

    # PHASE 21: Debug tracing - Conversion complete
    if is_debug_enabled(DebugModule.CONVERSION):
        debugger.trace_pipeline_state(
            "conversion_complete",
            processed_text,
            validated_entities,
            {
                "original_text_length": len(text),
                "processed_text_length": len(processed_text), 
                "text_length_change": len(processed_text) - len(text),
                "entities_input": len(entities),
                "entities_output": len(validated_entities),
                "entities_validated": len(converted_entities),
                "entities_removed_invalid": len(converted_entities) - len(validated_entities)
            }
        )
        
        debug_entity_list(
            validated_entities,
            "conversion",
            "final_converted_entities",
            DebugModule.CONVERSION,
            text=processed_text,
            conversion_summary=f"{len(entities)} -> {len(validated_entities)}"
        )

    return processed_text, validated_entities


def _fix_entity_spacing_issues(text: str, entities: list[Entity]) -> str:
    """
    Fix common entity spacing issues that occur during conversion.
    
    This catches problems like "Check the.com sites" and fixes them to "Check .com sites".
    """
    fixed_text = text
    adjustments_made = 0  # Track cumulative position adjustments
    
    # Sort entities by start position to process from left to right
    sorted_entities = sorted(entities, key=lambda e: e.start)
    
    for entity in sorted_entities:
        # Adjust entity position based on previous insertions
        adjusted_start = entity.start + adjustments_made
        adjusted_end = entity.end + adjustments_made
        
        # Check for missing space before web entities that start with symbols
        if entity.type in [EntityType.SPOKEN_URL, EntityType.URL, EntityType.SPOKEN_EMAIL, EntityType.EMAIL] and adjusted_start > 0:
            entity_text = entity.text
            # If entity starts with a symbol or if there's no space before the entity when there should be
            if (entity_text.startswith(('.', '/', '@', ':')) and 
                adjusted_start > 0 and 
                adjusted_start < len(fixed_text) and
                not fixed_text[adjusted_start - 1].isspace()):
                
                # Check if the character before is alphabetic (indicating we need a space)
                if fixed_text[adjusted_start - 1].isalpha():
                    logger.debug(f"ENTITY_BOUNDARY_FIX: Adding space before {entity.type} '{entity_text}' at position {adjusted_start}")
                    # Insert space before the entity
                    fixed_text = fixed_text[:adjusted_start] + " " + fixed_text[adjusted_start:]
                    adjustments_made += 1
                    
                    # Update the current entity's stored positions
                    entity.start += 1
                    entity.end += 1
            
            # Also check for email entities that might need space before them
            elif (entity.type in [EntityType.SPOKEN_EMAIL, EntityType.EMAIL] and 
                  adjusted_start > 0 and 
                  adjusted_start < len(fixed_text) and
                  not fixed_text[adjusted_start - 1].isspace() and
                  fixed_text[adjusted_start - 1].isalpha()):
                
                logger.debug(f"ENTITY_BOUNDARY_FIX: Adding space before email {entity.type} '{entity_text}' at position {adjusted_start}")
                # Insert space before the entity
                fixed_text = fixed_text[:adjusted_start] + " " + fixed_text[adjusted_start:]
                adjustments_made += 1
                
                # Update the current entity's stored positions
                entity.start += 1
                entity.end += 1
    
    return fixed_text


@debug_performance("boundary_tracking_conversion", DebugModule.CONVERSION)
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
    
    # PHASE 21: Debug tracing - Boundary tracking conversion start
    if is_debug_enabled(DebugModule.CONVERSION):
        debug_entity_list(
            entities,
            "conversion",
            "boundary_tracking_start",
            DebugModule.CONVERSION,
            text=text,
            tracking_reason="Spanish multi-word entities or large entity count"
        )
    
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
            
            # PHASE 19: Validate entity conversion consistency (boundary tracking version)
            validator = create_entity_validator(language)
            is_valid_conversion = validator.validate_entity_conversion_consistency(
                entity, converted_text, boundary_tracker.current_text
            )
            if not is_valid_conversion:
                logger.debug(f"PHASE_19_VALIDATION: Boundary conversion validation failed for {entity.type}, but continuing processing")
            
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
                
                # THEORY 19: Record conversion for capitalization coordination
                if pipeline_state and hasattr(pipeline_state, 'entity_capitalization_coordinator'):
                    entity_id = pipeline_state.entity_tracker.generate_entity_id(entity)
                    guidance = pipeline_state.record_entity_conversion(
                        entity_id, entity.type, "step3_boundary_conversion", 
                        original_text, converted_text, entity.start
                    )
                    logger.debug(f"THEORY_19: Recorded boundary conversion guidance for {entity.type}: {guidance.capitalization_context}")
            
        except Exception as e:
            logger.warning(f"Error converting entity {entity.type}('{original_text}'): {e}")
            # Don't record conversion if it failed
    
    # Get the final text and updated entities
    final_text = boundary_tracker.current_text
    updated_entities = boundary_tracker.get_updated_entities()
    
    logger.debug(f"Boundary tracking completed: {len(updated_entities)} entities with valid boundaries")
    
    # ENTITY BOUNDARY FIX: Apply spacing fixes to boundary-tracked entities too
    if updated_entities:
        final_text = _fix_entity_spacing_issues(final_text, updated_entities)
    
    # Log debug information for troubleshooting
    debug_info = boundary_tracker.get_debug_info()
    if debug_info['changes_count'] > 0:
        logger.debug(f"Boundary tracker applied {debug_info['changes_count']} changes")
        for change in debug_info['changes'][:3]:  # Log first 3 changes
            logger.debug(f"  Change: '{change['old_text']}' -> '{change['new_text']}' (Δ{change['length_change']})")
    
    # PHASE 21: Debug tracing - Boundary tracking complete
    if is_debug_enabled(DebugModule.CONVERSION):
        debugger = get_entity_debugger()
        debugger.trace_pipeline_state(
            "boundary_tracking_complete",
            final_text,
            updated_entities,
            {
                "boundary_changes": debug_info['changes_count'],
                "entities_processed": len(entities),
                "entities_final": len(updated_entities),
                "text_length_change": len(final_text) - len(text),
                "tracking_effectiveness": f"{debug_info['changes_count']} boundary fixes applied"
            }
        )
    
    return final_text, updated_entities