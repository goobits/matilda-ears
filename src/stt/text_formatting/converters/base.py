"""Base pattern converter class with shared utilities."""

# Standard library imports
from abc import ABC, abstractmethod
from typing import Dict, Any

# Local imports - common data structures
from stt.text_formatting.common import Entity, EntityType, NumberParser
from stt.text_formatting.constants import get_resources


class BasePatternConverter(ABC):
    """Base class for all pattern converters with shared utilities."""
    
    def __init__(self, number_parser: NumberParser, language: str = "en"):
        """Initialize with number parser and language resources."""
        self.number_parser = number_parser
        self.language = language
        self.resources = get_resources(language)
        
        # Each converter defines its supported entity types
        self.supported_types: Dict[EntityType, str] = {}
        
    @abstractmethod
    def convert(self, entity: Entity, full_text: str = "") -> str:
        """Convert an entity to its final form.
        
        Args:
            entity: The entity to convert
            full_text: The full text containing the entity (for context)
            
        Returns:
            The converted text
        """
        pass
        
    def supports(self, entity_type: EntityType) -> bool:
        """Check if this converter supports the given entity type."""
        return entity_type in self.supported_types
        
    def get_converter_method(self, entity_type: EntityType) -> str:
        """Get the converter method name for an entity type."""
        return self.supported_types.get(entity_type, "")
        
    # Shared utility methods
    def _parse_number_words(self, text: str) -> str:
        """Parse number words to digits using the number parser."""
        return self.number_parser.parse(text)
        
    def _convert_to_snake_case(self, text: str) -> str:
        """Convert text to snake_case."""
        # Remove extra spaces and convert to lowercase
        text = " ".join(text.split()).lower()
        # Replace spaces with underscores
        return text.replace(" ", "_")
        
    def _convert_to_camel_case(self, text: str, pascal: bool = False) -> str:
        """Convert text to camelCase or PascalCase."""
        words = text.split()
        if not words:
            return ""
            
        if pascal:
            return "".join(word.capitalize() for word in words)
        else:
            return words[0].lower() + "".join(word.capitalize() for word in words[1:])
            
    def _format_with_commas(self, number_str: str) -> str:
        """Format a number string with commas."""
        try:
            # Handle decimal numbers
            if "." in number_str:
                integer_part, decimal_part = number_str.split(".")
                integer_part = "{:,}".format(int(integer_part))
                return f"{integer_part}.{decimal_part}"
            else:
                return "{:,}".format(int(number_str))
        except (ValueError, AttributeError):
            return number_str