"""Measurements converter for percentages and other measurement units."""

import re
from typing import Dict

from stt.core.config import setup_logging
from stt.text_formatting.common import Entity, EntityType
from .base import BaseNumericConverter

logger = setup_logging(__name__)


class MeasurementConverter(BaseNumericConverter):
    """Converter for measurement entities like percentages."""
    
    def __init__(self, number_parser, language: str = "en"):
        """Initialize measurement converter."""
        super().__init__(number_parser, language)
        
        # Define supported entity types and their converter methods
        self.supported_types: Dict[EntityType, str] = {
            EntityType.PERCENT: "convert_percent",
        }
        
    def convert(self, entity: Entity, full_text: str = "") -> str:
        """Convert a measurement entity to its final form."""
        converter_method = self.get_converter_method(entity.type)
        if converter_method and hasattr(self, converter_method):
            return getattr(self, converter_method)(entity)
        return entity.text

    def convert_percent(self, entity: Entity) -> str:
        """Convert numerical percent entities"""
        # Handle new version number detection format
        if entity.metadata and "groups" in entity.metadata and entity.metadata.get("is_percentage"):
            groups = entity.metadata["groups"]
            
            if len(groups) >= 2:
                # For decimal patterns like "nine point five" where group[0]="nine", group[1]="five"
                integer_part = groups[0]
                decimal_part = groups[1]
                
                # Parse the integer part
                integer_parsed = None
                if integer_part:
                    integer_parsed = self.number_parser.parse(integer_part)
                    if not integer_parsed and integer_part.isdigit():
                        integer_parsed = integer_part
                
                # Parse the decimal part - handle as digits for true decimal representation
                decimal_parsed = None
                if decimal_part:
                    # For decimal parts, try to parse as a sequence of digits first
                    decimal_parsed = self.number_parser.parse_as_digits(decimal_part)
                    if not decimal_parsed:
                        # Fallback to regular parsing
                        decimal_parsed = self.number_parser.parse(decimal_part)
                    if not decimal_parsed and decimal_part.isdigit():
                        decimal_parsed = decimal_part
                
                if integer_parsed and decimal_parsed:
                    return f"{integer_parsed}.{decimal_parsed}%"
                elif integer_parsed:
                    return f"{integer_parsed}%"
            
            # Fallback: convert the numeric parts individually and join
            parts = []
            for group in groups:
                if group:
                    parsed = self.number_parser.parse(group)
                    if parsed:
                        parts.append(parsed)
                    elif group and group.isdigit():
                        parts.append(group)

            if parts:
                # Join with dots for decimal percentages
                percent_str = ".".join(parts)
                return f"{percent_str}%"

        # Original handling for SpaCy-detected percentages
        if entity.metadata and "number" in entity.metadata:
            number_text = entity.metadata["number"]
            # Parse the number text to convert words to digits
            parsed_number = self.number_parser.parse(number_text)
            if parsed_number is not None:
                return f"{parsed_number}%"
            # Fallback to original if parsing fails
            return f"{number_text}%"

        # Fallback: parse from text if no metadata available
        text = entity.text.lower()
        # Try to extract number from text
        match = re.search(r"(.+?)\s+percent", text)
        if match:
            number_text = match.group(1).strip()
            # Use the number parser to convert words to numbers
            number = self.number_parser.parse(number_text)
            if number is not None:
                return f"{number}%"

        return entity.text