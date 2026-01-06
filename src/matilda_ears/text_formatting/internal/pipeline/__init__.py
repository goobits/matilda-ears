#!/usr/bin/env python3
"""Pipeline module for text formatting.

This module provides the core text formatting pipeline:

Core components:
- EntityDetector: SpaCy-powered entity detection
- PatternConverter: Entity-specific conversions wrapper
- TextFormatter: Main formatting orchestrator
- format_transcription: Convenience function

Specialized processors:
- TextPreprocessor: Artifact cleaning and filtering
- PunctuationProcessor: Punctuation restoration and abbreviation handling
- TextPostprocessor: Domain rescue, keyword conversion, and final cleanup
"""

from .entity_detector import EntityDetector
from .converter import PatternConverter
from .text_formatter import TextFormatter, format_transcription
from .preprocessor import TextPreprocessor
from .punctuation import PunctuationProcessor
from .postprocessor import TextPostprocessor

__all__ = [
    "EntityDetector",
    "PatternConverter",
    "TextFormatter",
    "format_transcription",
    "TextPreprocessor",
    "PunctuationProcessor",
    "TextPostprocessor",
]
