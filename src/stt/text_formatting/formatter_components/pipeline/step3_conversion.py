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

from ..pattern_converter import PatternConverter
from ...common import Entity
from ..pipeline_state import PipelineState


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
    
    Args:
        text: The original text containing entities
        entities: List of detected entities to convert
        pattern_converter: The converter to use for entity transformations
        
    Returns:
        Tuple of (processed_text, converted_entities) where:
        - processed_text: The text with all entities converted
        - converted_entities: List of entities with updated positions and text
    """
    # Step 3: Assemble final string AND track converted entity positions
    result_parts = []
    converted_entities = []
    last_end = 0
    current_pos_in_result = 0

    # Sort entities by start position to process in sequence
    sorted_entities = sorted(entities, key=lambda e: e.start)

    for entity in sorted_entities:
        if entity.start < last_end:
            continue  # Skip overlapping entities

        # Add plain text part
        plain_text_part = text[last_end : entity.start]
        result_parts.append(plain_text_part)
        current_pos_in_result += len(plain_text_part)

        # Convert entity and track its new position
        # Pass pipeline state to entity for intelligent context-aware conversion
        if pipeline_state:
            entity._pipeline_state = pipeline_state
        converted_text = pattern_converter.convert(entity, text)
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