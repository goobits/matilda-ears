#!/usr/bin/env python3
"""
PatternConverter class for converting specific entity types to their final form.

Extracted from formatter.py for modular architecture.
"""
from __future__ import annotations

from ...core.config import setup_logging

# Import common data structures
from stt.text_formatting.common import Entity, EntityType, NumberParser
from ..pattern_converter import PatternConverter as UnifiedPatternConverter

# Setup logging
logger = setup_logging(__name__)

# PHASE 21: Debug Mode Enhancement - Pattern Converter Tracing
from stt.text_formatting.debug_utils import (
    get_entity_debugger, DebugModule, is_debug_enabled
)


class PatternConverter:
    """Converts specific entity types to their final form"""

    def __init__(self, language: str = "en"):
        self.language = language

        # Use the unified converter with all conversion methods
        self.unified_converter = UnifiedPatternConverter(NumberParser(language=language), language=language)

        # Entity type to converter method mapping
        self.converters = {}  # Start with an empty dict

        # Add all converters from the unified converter
        self.converters.update(self.unified_converter.converters)

    def convert(self, entity: Entity, full_text: str) -> str:
        """Convert entity based on its type"""
        # PHASE 21: Debug tracing - Pattern conversion start
        original_text = entity.text
        if is_debug_enabled(DebugModule.CONVERSION):
            debugger = get_entity_debugger()
            debugger.trace_entity_operation(
                entity,
                "conversion",
                "pattern_convert_start",
                DebugModule.CONVERSION,
                before_text=original_text,
                context_preview=full_text[max(0, entity.start-5):entity.end+5] if entity.start >= 0 else "",
                converter_available=entity.type in self.converters
            )
        
        # Check for trailing punctuation after entity in full text
        trailing_punct = ""
        if entity.end < len(full_text) and full_text[entity.end] in ".!?":
            trailing_punct = full_text[entity.end]

        # Get the appropriate converter for this entity type
        converter = self.converters.get(entity.type)
        if converter:
            # Determine conversion strategy based on entity type
            result = self._apply_converter(converter, entity, full_text)

            # Check if this entity type handles its own punctuation
            final_result = result if self._handles_own_punctuation(entity.type) else result + trailing_punct
            
            # PHASE 21: Debug tracing - Successful pattern conversion
            if is_debug_enabled(DebugModule.CONVERSION):
                debugger.trace_entity_conversion(
                    entity,
                    original_text,
                    final_result,
                    f"pattern_converter_{converter.__name__ if hasattr(converter, '__name__') else 'unknown'}",
                    success=True
                )
            
            return final_result

        # Default fallback for unknown entity types
        fallback_result = entity.text + trailing_punct
        
        # PHASE 21: Debug tracing - Fallback conversion
        if is_debug_enabled(DebugModule.CONVERSION):
            debugger.trace_entity_conversion(
                entity,
                original_text,
                fallback_result,
                "pattern_converter_fallback",
                success=False,
                error=f"No converter found for {entity.type}"
            )
        
        return fallback_result

    def _apply_converter(self, converter, entity: Entity, full_text: str) -> str:
        """Apply the converter with appropriate parameters based on entity type"""
        # Entity types that need full_text parameter
        full_text_entity_types = {
            EntityType.SPOKEN_URL,
            EntityType.CARDINAL,
            EntityType.MONEY,
            EntityType.CURRENCY,
            EntityType.QUANTITY,
            EntityType.FILENAME,  # Added to detect spoken underscores in context
            EntityType.ORDINAL,   # Added for context-aware ordinal conversion
        }

        if entity.type in full_text_entity_types:
            return str(converter(entity, full_text))
        return str(converter(entity))

    def _handles_own_punctuation(self, entity_type: EntityType) -> bool:
        """Check if entity type handles its own punctuation"""
        # Entity types that manage their own punctuation and shouldn't get extra trailing punctuation
        self_punctuating_types = {
            EntityType.SPOKEN_URL,
            EntityType.SPOKEN_PROTOCOL_URL,
            EntityType.MATH,
            EntityType.MATH_EXPRESSION,
            EntityType.EMAIL,
            EntityType.PHYSICS_SQUARED,
            EntityType.PHYSICS_TIMES,
            EntityType.MONEY,
            EntityType.FILENAME,
            EntityType.INCREMENT_OPERATOR,
            EntityType.DECREMENT_OPERATOR,
            EntityType.ABBREVIATION,
            EntityType.ASSIGNMENT,
            EntityType.COMPARISON,
            EntityType.PORT_NUMBER,
            EntityType.URL,  # Regular URLs also handle their own punctuation
        }

        # Fix for test "That makes me a happy 🙂."
        # Emojis need to handle their own punctuation to avoid having it placed before them.
        self_punctuating_types.add(EntityType.SPOKEN_EMOJI)

        return entity_type in self_punctuating_types