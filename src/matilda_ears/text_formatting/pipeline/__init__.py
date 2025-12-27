#!/usr/bin/env python3
"""
Pipeline module for text formatting.

This module provides the core text formatting pipeline:
- EntityDetector: SpaCy-powered entity detection
- PatternConverter: Entity-specific conversions wrapper
- TextFormatter: Main formatting orchestrator
- format_transcription: Convenience function
"""

from .entity_detector import EntityDetector
from .converter import PatternConverter
from .text_formatter import TextFormatter, format_transcription

__all__ = [
    "EntityDetector",
    "PatternConverter",
    "TextFormatter",
    "format_transcription",
]
