#!/usr/bin/env python3
"""Text formatter for Matilda transcriptions.

This module provides backward compatibility by re-exporting classes
from the pipeline submodule.

The implementation has been split into:
- pipeline/entity_detector.py: EntityDetector class
- pipeline/converter.py: PatternConverter wrapper class
- pipeline/text_formatter.py: TextFormatter class and format_transcription
"""

# Re-export all public classes for backward compatibility
from .pipeline import (
    EntityDetector,
    PatternConverter,
    TextFormatter,
    format_transcription,
)

# Also re-export commonly used types
from .common import Entity, EntityType, NumberParser

__all__ = [
    "EntityDetector",
    "PatternConverter",
    "TextFormatter",
    "format_transcription",
    "Entity",
    "EntityType",
    "NumberParser",
]
