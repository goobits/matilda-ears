#!/usr/bin/env python3
"""Shared utility functions for text formatting modules."""

from typing import List
from .common import Entity


def is_inside_entity(start: int, end: int, entities: List[Entity]) -> bool:
    """Check if a span is inside any existing entity.

    Args:
        start: Start position of the span to check
        end: End position of the span to check
        entities: List of existing entities to check against

    Returns:
        True if the span is inside any existing entity, False otherwise

    """
    for entity in entities:
        if start >= entity.start and end <= entity.end:
            return True
    return False


def overlaps_with_entity(start: int, end: int, entities: List[Entity]) -> bool:
    """Check if a span overlaps with any existing entity.

    Args:
        start: Start position of the span to check
        end: End position of the span to check
        entities: List of existing entities to check against

    Returns:
        True if the span overlaps with any existing entity, False otherwise

    """
    for entity in entities:
        # Two spans overlap if they are not completely separated
        if not (end <= entity.start or start >= entity.end):
            return True
    return False
