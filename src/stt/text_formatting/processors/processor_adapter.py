"""
Adapter classes to maintain backward compatibility with existing detector/converter pattern.

This module provides adapter classes that wrap EntityProcessor instances to expose
the original detector/converter interfaces.
"""

from typing import List, Optional

from stt.text_formatting.common import Entity
from stt.text_formatting.entity_processor import EntityProcessor


class DetectorAdapter:
    """Adapter to expose EntityProcessor as a detector."""
    
    def __init__(self, processor: EntityProcessor):
        """Initialize detector adapter with an entity processor."""
        self.processor = processor
        # Copy relevant attributes for backward compatibility
        self.language = processor.language
        self.nlp = processor.nlp
        self.number_parser = processor.number_parser
        self.resources = processor.resources
        
    def detect_entities(self, text: str, entities: List[Entity], 
                       all_entities: Optional[List[Entity]] = None) -> None:
        """Detect entities using the processor."""
        self.processor.detect_entities(text, entities, all_entities)
        
    def __getattr__(self, name):
        """Forward unknown attributes to processor."""
        return getattr(self.processor, name)


class ConverterAdapter:
    """Adapter to expose EntityProcessor as a converter."""
    
    def __init__(self, processor: EntityProcessor):
        """Initialize converter adapter with an entity processor."""
        self.processor = processor
        # Copy relevant attributes for backward compatibility
        self.language = processor.language
        self.number_parser = processor.number_parser
        self.mapping_registry = processor.mapping_registry
        self.resources = processor.resources
        
        # Map entity types to converter methods for compatibility
        self.supported_types = processor.conversion_methods
        
    def convert(self, entity: Entity, full_text: str = "") -> str:
        """Convert entity using the processor."""
        return self.processor.convert_entity(entity, full_text)
        
    def get_converter_method(self, entity_type):
        """Get converter method name for entity type."""
        return self.supported_types.get(entity_type)
        
    def __getattr__(self, name):
        """Forward unknown attributes to processor."""
        return getattr(self.processor, name)


def create_detector_converter_pair(processor_class, *args, **kwargs):
    """
    Create a detector/converter pair from a processor class.
    
    This factory function creates both detector and converter adapters
    from a single processor instance, ensuring they share state.
    
    Args:
        processor_class: EntityProcessor subclass
        *args, **kwargs: Arguments for processor initialization
        
    Returns:
        tuple: (detector_adapter, converter_adapter)
    """
    processor = processor_class(*args, **kwargs)
    return DetectorAdapter(processor), ConverterAdapter(processor)


# Example usage for backward compatibility
def create_basic_numeric_pair(nlp=None, language="en"):
    """Create BasicNumberDetector and BasicNumericConverter compatible objects."""
    from .basic_numeric_processor import BasicNumericProcessor
    return create_detector_converter_pair(BasicNumericProcessor, nlp=nlp, language=language)