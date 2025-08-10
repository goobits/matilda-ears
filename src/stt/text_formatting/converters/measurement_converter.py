"""Measurement pattern converter for quantities, temperatures, and metric units."""

import re
from typing import Dict

from stt.text_formatting.common import Entity, EntityType
from .base import BasePatternConverter
from stt.text_formatting.mapping_registry import get_mapping_registry


class MeasurementPatternConverter(BasePatternConverter):
    """Converter for measurement-related patterns like quantities, temperatures, and metric units."""
    
    def __init__(self, number_parser, language: str = "en"):
        """Initialize measurement pattern converter."""
        super().__init__(number_parser, language)
        self.mapping_registry = get_mapping_registry(language)
        
        # Define supported entity types and their converter methods
        self.supported_types: Dict[EntityType, str] = {
            EntityType.QUANTITY: "convert_measurement",
            EntityType.TEMPERATURE: "convert_temperature",
            EntityType.METRIC_LENGTH: "convert_metric_unit",
            EntityType.METRIC_WEIGHT: "convert_metric_unit",
            EntityType.METRIC_VOLUME: "convert_metric_unit",
        }
        
    def convert(self, entity: Entity, full_text: str = "") -> str:
        """Convert a measurement entity to its final form."""
        converter_method = self.get_converter_method(entity.type)
        if converter_method and hasattr(self, converter_method):
            if converter_method == "convert_measurement":
                # convert_measurement needs full_text parameter
                return getattr(self, converter_method)(entity, full_text)
            else:
                return getattr(self, converter_method)(entity)
        return entity.text

    def convert_measurement(self, entity: Entity, full_text: str = "") -> str:
        """
        Convert measurements to use proper symbols.

        Examples:
        - "six feet" → "6′"
        - "twelve inches" → "12″"
        - "5 foot 10" → "5′10″"
        - "three and a half feet" → "3.5′"
        - Also handles metric units and temperatures detected as QUANTITY

        """
        text = entity.text.lower()

        # First check if this is actually a temperature
        if "degrees" in text:
            # Check if this is an angle context (rotate, turn, angle, etc.) in the full text
            full_text_lower = full_text.lower() if full_text else ""
            angle_keywords = self.resources.get("context_words", {}).get("angle_keywords", [])
            if any(keyword in full_text_lower for keyword in angle_keywords):
                # This is an angle, not a temperature - return unchanged
                return entity.text
            # Also skip if there's no explicit unit (could be angle)
            if (
                not any(unit in text for unit in ["celsius", "centigrade", "fahrenheit", "c", "f"])
                and not full_text_lower
            ):
                return entity.text

            # Extract temperature parts
            temp_match = re.match(
                r"(?:(minus|negative)\s+)?"  # Optional sign
                r"(.*?)\s+degrees?"  # Number + degrees
                r"(?:\s+(celsius|centigrade|fahrenheit|c|f))?",  # Optional unit
                text,
                re.IGNORECASE,
            )
            if temp_match:
                sign = temp_match.group(1)
                number_text = temp_match.group(2)
                unit = temp_match.group(3)

                # Parse the number
                parsed_num = self.number_parser.parse(number_text)
                if parsed_num:
                    if sign:
                        parsed_num = f"-{parsed_num}"

                    if unit:
                        unit_lower = unit.lower()
                        if unit_lower in ["celsius", "centigrade", "c"]:
                            return f"{parsed_num}°C"
                        if unit_lower in ["fahrenheit", "f"]:
                            return f"{parsed_num}°F"

                    # No unit specified, just degrees symbol
                    return f"{parsed_num}°"

        # Check if this is a metric unit
        metric_match = re.match(
            r"(.*?)\s+(millimeters?|millimetres?|centimeters?|centimetres?|meters?|metres?|"
            r"kilometers?|kilometres?|milligrams?|grams?|kilograms?|metric\s+tons?|tonnes?|"
            r"milliliters?|millilitres?|liters?|litres?)",
            text,
            re.IGNORECASE,
        )
        if metric_match:
            number_text = metric_match.group(1)
            unit_text = metric_match.group(2).lower()

            # Handle decimal numbers including "and a half/quarter" patterns
            decimal_match = re.match(r"(\w+)\s+point\s+(\w+)", number_text, re.IGNORECASE)
            fraction_match = re.match(r"(\w+)\s+and\s+a\s+(half|quarter)", number_text, re.IGNORECASE)
            
            if decimal_match:
                whole_part = self.number_parser.parse(decimal_match.group(1))
                decimal_part = self.number_parser.parse_as_digits(decimal_match.group(2))
                if not decimal_part:
                    decimal_part = self.number_parser.parse(decimal_match.group(2))
                if whole_part and decimal_part:
                    parsed_num = f"{whole_part}.{decimal_part}"
                else:
                    parsed_num = self.number_parser.parse(number_text)
            elif fraction_match:
                whole_part = self.number_parser.parse(fraction_match.group(1))
                fraction_part = fraction_match.group(2)
                if whole_part:
                    if fraction_part == "half":
                        parsed_num = f"{whole_part}.5"
                    elif fraction_part == "quarter":
                        parsed_num = f"{whole_part}.25"
                    else:
                        parsed_num = f"{whole_part}.5"
                else:
                    parsed_num = self.number_parser.parse(number_text)
            else:
                parsed_num = self.number_parser.parse(number_text)

            if parsed_num:
                # Map to standard abbreviations using the mapping registry
                unit_map = self.mapping_registry.get_measurement_unit_map()
                standard_unit = unit_map.get(unit_text, unit_text.upper())
                return f"{parsed_num} {standard_unit}"

        # Original measurement conversion code continues...
        text = entity.text.lower()

        # Extract number and unit
        # Pattern for measurements with numbers (digits or words)
        # Match patterns like "six feet", "5 foot", "three and a half inches"
        patterns = [
            # "X and a half feet/inches" or "X and a quarter feet/inches"
            (r"(\w+)\s+and\s+a\s+(half|quarter)\s+(feet?|foot|inch(?:es)?)", "fraction"),
            # "X feet Y inches" (like "six feet two inches")
            (r"(\w+)\s+(feet?|foot)\s+(\w+)\s+(inch(?:es)?)", "feet_inches"),
            # "X foot Y" (like "5 foot 10" or "five foot ten")
            (r"(\w+)\s+foot\s+(\w+)", "height"),
            # "X miles/yards" (distance measurements)
            (r"(\w+)\s+(miles?|yards?)", "distance"),
            # "X pounds/ounces/lbs" (weight measurements)
            (r"(\w+)\s+(pounds?|lbs?|ounces?|oz)", "weight"),
            # "X gallons/quarts/pints/fluid ounces" (volume measurements)
            (r"(\w+)\s+(gallons?|quarts?|pints?|(?:fluid\s+)?ounces?)", "volume"),
            # "X feet/foot/inches/inch" (must come after compound patterns)
            (r"(\w+)\s+(feet?|foot|inch(?:es)?)", "simple"),
        ]

        for pattern, pattern_type in patterns:
            match = re.match(pattern, text, re.IGNORECASE)
            if match:
                if pattern_type == "fraction":
                    number_part = match.group(1)
                    fraction_part = match.group(2)
                    unit = match.group(3)

                    # Parse the number
                    parsed_num = self.number_parser.parse(number_part)
                    if parsed_num:
                        # Add appropriate fraction
                        try:
                            if fraction_part == "half":
                                num_value = float(parsed_num) + 0.5
                            elif fraction_part == "quarter":
                                num_value = float(parsed_num) + 0.25
                            else:
                                num_value = float(parsed_num) + 0.5  # default to half
                            number_str = str(num_value).rstrip("0").rstrip(".")
                        except (ValueError, TypeError):
                            if fraction_part == "quarter":
                                number_str = f"{parsed_num}.25"
                            else:
                                number_str = f"{parsed_num}.5"
                    else:
                        return entity.text  # Fallback if can't parse

                    # Use proper symbols
                    if "inch" in unit:
                        return f"{number_str}″"
                    if "foot" in unit or "feet" in unit:
                        return f"{number_str}′"

                elif pattern_type == "simple":
                    number_part = match.group(1)
                    unit = match.group(2)

                    # Parse the number
                    parsed_num = self.number_parser.parse(number_part)
                    if not parsed_num:
                        return entity.text  # Fallback if can't parse

                    # Use proper symbols
                    if "inch" in unit:
                        return f"{parsed_num}″"
                    if "foot" in unit or "feet" in unit:
                        return f"{parsed_num}′"

                elif pattern_type == "feet_inches":
                    feet_part = match.group(1)
                    # feet_unit = match.group(2)  # "feet" or "foot" (unused)
                    inches_part = match.group(3)
                    # inches_unit = match.group(4)  # "inches" or "inch" (unused)

                    # Parse both parts
                    parsed_feet = self.number_parser.parse(feet_part)
                    parsed_inches = self.number_parser.parse(inches_part)

                    if parsed_feet and parsed_inches:
                        return f"{parsed_feet}′{parsed_inches}″"
                    return entity.text  # Fallback if can't parse

                elif pattern_type == "distance":
                    number_part = match.group(1)
                    unit = match.group(2)

                    # Parse the number
                    parsed_num = self.number_parser.parse(number_part)
                    if not parsed_num:
                        return entity.text  # Fallback if can't parse

                    # Convert to abbreviations
                    if "mile" in unit:
                        return f"{parsed_num} mi"
                    if "yard" in unit:
                        return f"{parsed_num} yd"

                elif pattern_type == "weight":
                    number_part = match.group(1)
                    unit = match.group(2)

                    # Parse the number
                    parsed_num = self.number_parser.parse(number_part)
                    if not parsed_num:
                        return entity.text  # Fallback if can't parse

                    # Convert to abbreviations (avoiding currency symbols)
                    if "pound" in unit or "lbs" in unit:
                        return f"{parsed_num} lbs"
                    if "ounce" in unit and "fluid" not in unit:
                        return f"{parsed_num} oz"

                elif pattern_type == "volume":
                    number_part = match.group(1)
                    unit = match.group(2)

                    # Parse the number
                    parsed_num = self.number_parser.parse(number_part)
                    if not parsed_num:
                        return entity.text  # Fallback if can't parse

                    # Convert to abbreviations using mapping registry
                    unit_map = self.mapping_registry.get_measurement_unit_map()
                    unit_clean = unit.strip().lower()
                    
                    # Handle fluid ounces specially
                    if "fluid" in unit_clean or ("ounce" in unit_clean and "fluid" not in unit_clean):
                        return f"{parsed_num} fl oz"
                    
                    standard_unit = unit_map.get(unit_clean, unit_clean)
                    return f"{parsed_num} {standard_unit}"

                elif pattern_type == "height":
                    feet_part = match.group(1)
                    inches_part = match.group(2)

                    # Parse both parts
                    parsed_feet = self.number_parser.parse(feet_part)
                    parsed_inches = self.number_parser.parse(inches_part)

                    if parsed_feet and parsed_inches:
                        return f"{parsed_feet}′{parsed_inches}″"
                    return entity.text  # Fallback if can't parse

        # Fallback
        return entity.text

    def convert_temperature(self, entity: Entity) -> str:
        """
        Convert temperature expressions to proper format.

        Examples:
        - "twenty degrees celsius" → "20°C"
        - "thirty two degrees fahrenheit" → "32°F"
        - "minus ten degrees" → "-10°"

        """
        if not entity.metadata:
            return entity.text

        sign = entity.metadata.get("sign")
        number_text = entity.metadata.get("number", "")
        unit = entity.metadata.get("unit")

        # Use the improved number parser that handles decimals automatically
        parsed_num = self.number_parser.parse(number_text)

        if not parsed_num:
            return entity.text

        # Add sign if present
        if sign:
            parsed_num = f"-{parsed_num}"

        # Format based on unit
        if unit:
            unit_lower = unit.lower()
            if unit_lower in ["celsius", "centigrade", "c"]:
                return f"{parsed_num}°C"
            if unit_lower in ["fahrenheit", "f"]:
                return f"{parsed_num}°F"

        # No unit specified, just degrees
        return f"{parsed_num}°"

    def convert_metric_unit(self, entity: Entity) -> str:
        """
        Convert metric units to standard abbreviations.

        Examples:
        - "five kilometers" → "5 km"
        - "two point five centimeters" → "2.5 cm"
        - "ten kilograms" → "10 kg"
        - "three liters" → "3 L"

        """
        if not entity.metadata:
            return entity.text

        number_text = entity.metadata.get("number", "")
        unit = entity.metadata.get("unit", "").lower()

        # Use the improved number parser that handles decimals automatically
        parsed_num = self.number_parser.parse(number_text)

        if not parsed_num:
            return entity.text

        # Get unit mappings from registry
        unit_map = self.mapping_registry.get_measurement_unit_map()
        standard_unit = unit_map.get(unit, unit.upper())
        return f"{parsed_num} {standard_unit}"