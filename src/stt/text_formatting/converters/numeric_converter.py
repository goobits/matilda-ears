"""Numeric pattern converter orchestrator that delegates to specialized converters."""

from typing import Dict, List

from stt.core.config import setup_logging
from stt.text_formatting.common import Entity, EntityType
from .base import BasePatternConverter
from .numeric import (
    BasicNumericConverter,
    FinancialConverter,
    MathematicalConverter,
    MeasurementConverter,
    TechnicalConverter,
    TemporalConverter,
)
from .numeric.base import BaseNumericConverter as NumericBase

logger = setup_logging(__name__, log_filename="text_formatting.txt", include_console=False)


class NumericPatternConverter(BasePatternConverter):
    """
    Orchestrator for numeric patterns - delegates to specialized converters.
    
    This class maintains the same public API as before but now routes conversion
    requests to appropriate specialized converters based on entity type.
    """
    
    def __init__(self, number_parser, language: str = "en"):
        """Initialize numeric pattern converter with specialized converters."""
        super().__init__(number_parser, language)
        
        # Initialize specialized converters
        self.basic_converter = BasicNumericConverter(number_parser, language)
        self.financial_converter = FinancialConverter(number_parser, language)
        self.mathematical_converter = MathematicalConverter(number_parser, language)
        self.measurement_converter = MeasurementConverter(number_parser, language)
        self.technical_converter = TechnicalConverter(number_parser, language)
        self.temporal_converter = TemporalConverter(number_parser, language)
        
        # Map entity types to their respective converters
        self.converter_map: Dict[EntityType, NumericBase] = {}
        self._build_converter_map()
        
        # Define supported entity types (combines all specialized converters)
        self.supported_types: Dict[EntityType, str] = {
            entity_type: "convert" 
            for entity_type in self.converter_map.keys()
        }
        
    def _build_converter_map(self) -> None:
        """Build mapping from entity types to their appropriate converters."""
        converters = [
            self.basic_converter,
            self.financial_converter,
            self.mathematical_converter,
            self.measurement_converter,
            self.technical_converter,
            self.temporal_converter,
        ]
        
        # Build the mapping based on each converter's supported types
        for converter in converters:
            for entity_type in converter.supported_types.keys():
                if entity_type in self.converter_map:
                    logger.warning(f"Entity type {entity_type} is supported by multiple converters")
                self.converter_map[entity_type] = converter
    
    def convert(self, entity: Entity, full_text: str = "") -> str:
        """
        Convert a numeric entity to its final form by delegating to the appropriate converter.
        
        Args:
            entity: The entity to convert
            full_text: Full text context for contextual analysis
            
        Returns:
            Converted entity text or original text if no converter found
        """
        # Find the appropriate converter for this entity type
        converter = self.converter_map.get(entity.type)
        
        if converter:
            try:
                return converter.convert(entity, full_text)
            except Exception as e:
                logger.error(f"Error converting {entity.type} with {converter.__class__.__name__}: {e}")
                return entity.text
        
        # Fallback: return original text if no converter found
        logger.debug(f"No converter found for entity type: {entity.type}")
        return entity.text
    
    def get_supported_types(self) -> List[EntityType]:
        """Get list of all supported entity types across all converters."""
        return list(self.converter_map.keys())
    
    def get_converter_for_type(self, entity_type: EntityType):
        """Get the converter responsible for a specific entity type."""
        return self.converter_map.get(entity_type)
    
    def get_converter_stats(self) -> Dict[str, int]:
        """Get statistics about how many entity types each converter handles."""
        stats = {}
        for converter in [
            self.basic_converter,
            self.financial_converter,
            self.mathematical_converter,
            self.measurement_converter,
            self.technical_converter,
            self.temporal_converter,
        ]:
            converter_name = converter.__class__.__name__
            stats[converter_name] = len(converter.supported_types)
        return stats