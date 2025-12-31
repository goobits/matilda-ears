#!/usr/bin/env python3
"""Measurement and unit converters."""

import re

from ..common import Entity


class MeasurementConverterMixin:
    """Mixin class providing measurement and unit conversion methods.

    This mixin expects the host class to provide:
    - self.number_parser: NumberParser instance
    - self.resources: dict
    """

    def convert_data_size(self, entity: Entity) -> str:
        """Convert data size entities like 'five megabytes' -> '5MB'"""
        if entity.metadata and "number" in entity.metadata and "unit" in entity.metadata:
            number_text = entity.metadata["number"]
            unit = entity.metadata["unit"].lower()

            # Try to parse the entire number text first
            number_str = self.number_parser.parse(number_text)

            # If that fails, try parsing individual words from the number text
            if number_str is None:
                # Split and try to find valid number words
                words = number_text.split()
                for i, word in enumerate(words):
                    # Try parsing from this word onwards
                    remaining_text = " ".join(words[i:])
                    parsed = self.number_parser.parse(remaining_text)
                    if parsed:
                        number_str = parsed
                        break

            # Final fallback
            if number_str is None:
                number_str = number_text

            unit_map = {
                "byte": "B",
                "bytes": "B",
                "kilobyte": "KB",
                "kilobytes": "KB",
                "kb": "KB",
                "megabyte": "MB",
                "megabytes": "MB",
                "mb": "MB",
                "gigabyte": "GB",
                "gigabytes": "GB",
                "gb": "GB",
                "terabyte": "TB",
                "terabytes": "TB",
                "tb": "TB",
            }
            standard_unit = unit_map.get(unit, unit.upper())
            return f"{number_str}{standard_unit}"  # No space
        return entity.text

    def convert_frequency(self, entity: Entity) -> str:
        """Convert frequency entities like 'two megahertz' -> '2MHz'"""
        if entity.metadata and "number" in entity.metadata and "unit" in entity.metadata:
            number_text = entity.metadata["number"]
            unit = entity.metadata["unit"].lower()

            # Try to parse the entire number text first
            number_str = self.number_parser.parse(number_text)

            # If that fails, try parsing individual words from the number text
            if number_str is None:
                # Split and try to find valid number words
                words = number_text.split()
                for i, word in enumerate(words):
                    # Try parsing from this word onwards
                    remaining_text = " ".join(words[i:])
                    parsed = self.number_parser.parse(remaining_text)
                    if parsed:
                        number_str = parsed
                        break

            # Final fallback
            if number_str is None:
                number_str = number_text

            unit_map = {
                "hertz": "Hz",
                "hz": "Hz",
                "kilohertz": "kHz",
                "khz": "kHz",
                "megahertz": "MHz",
                "mhz": "MHz",
                "gigahertz": "GHz",
                "ghz": "GHz",
            }

            standard_unit = unit_map.get(unit, unit.upper())
            return f"{number_str}{standard_unit}"  # No space

        return entity.text

    def convert_measurement(self, entity: Entity, full_text: str = "") -> str:
        """Convert measurements to use proper symbols.

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

            # Handle decimal numbers
            decimal_match = re.match(r"(\w+)\s+point\s+(\w+)", number_text, re.IGNORECASE)
            if decimal_match:
                whole_part = self.number_parser.parse(decimal_match.group(1))
                decimal_part = self.number_parser.parse(decimal_match.group(2))
                if whole_part and decimal_part:
                    parsed_num = f"{whole_part}.{decimal_part}"
                else:
                    parsed_num = self.number_parser.parse(number_text)
            else:
                parsed_num = self.number_parser.parse(number_text)

            if parsed_num:
                # Map to standard abbreviations
                unit_map = {
                    # Length
                    "millimeter": "mm",
                    "millimeters": "mm",
                    "millimetre": "mm",
                    "millimetres": "mm",
                    "centimeter": "cm",
                    "centimeters": "cm",
                    "centimetre": "cm",
                    "centimetres": "cm",
                    "meter": "m",
                    "meters": "m",
                    "metre": "m",
                    "metres": "m",
                    "m": "m",
                    "kilometer": "km",
                    "kilometers": "km",
                    "kilometre": "km",
                    "kilometres": "km",
                    "km": "km",
                    # Weight
                    "milligram": "mg",
                    "milligrams": "mg",
                    "mg": "mg",
                    "gram": "g",
                    "grams": "g",
                    "g": "g",
                    "kilogram": "kg",
                    "kilograms": "kg",
                    "kg": "kg",
                    "metric ton": "t",
                    "metric tons": "t",
                    "tonne": "t",
                    "tonnes": "t",
                    "pound": "lbs",     # Imperial weight unit
                    "pounds": "lbs",    # Imperial weight unit
                    # Volume
                    "milliliter": "mL",
                    "milliliters": "mL",
                    "millilitre": "mL",
                    "millilitres": "mL",
                    "ml": "mL",
                    "liter": "L",
                    "liters": "L",
                    "litre": "L",
                    "litres": "L",
                    "l": "L",
                }

                standard_unit = unit_map.get(unit_text, unit_text.upper())
                return f"{parsed_num} {standard_unit}"

        # Original measurement conversion code continues...
        text = entity.text.lower()

        # Extract number and unit
        # Pattern for measurements with numbers (digits or words)
        # Match patterns like "six feet", "5 foot", "three and a half inches"
        patterns = [
            # "X and a half feet/inches"
            (r"(\w+)\s+and\s+a\s+half\s+(feet?|foot|inch(?:es)?)", "fraction"),
            # "X feet Y inches" (like "six feet two inches")
            (r"(\w+)\s+(feet?|foot)\s+(\w+)\s+(inch(?:es)?)", "feet_inches"),
            # "X foot Y" (like "5 foot 10" or "five foot ten")
            (r"(\w+)\s+foot\s+(\w+)", "height"),
            # "X miles/yards" (distance measurements)
            (r"(\w+)\s+(miles?|yards?)", "distance"),
            # "X pounds/ounces/lbs" (weight measurements)
            (r"(\w+)\s+(pounds?|lbs?|ounces?|oz)", "weight"),
            # "X feet/foot/inches/inch" (must come after compound patterns)
            (r"(\w+)\s+(feet?|foot|inch(?:es)?)", "simple"),
        ]

        for pattern, pattern_type in patterns:
            match = re.match(pattern, text, re.IGNORECASE)
            if match:
                if pattern_type == "fraction":
                    number_part = match.group(1)
                    unit = match.group(2)

                    # Parse the number
                    parsed_num = self.number_parser.parse(number_part)
                    if parsed_num:
                        # Add 0.5 for "and a half"
                        try:
                            num_value = float(parsed_num) + 0.5
                            number_str = str(num_value).rstrip("0").rstrip(".")
                        except (ValueError, TypeError):
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
                    if "ounce" in unit or "oz" in unit:
                        return f"{parsed_num} oz"

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
        """Convert temperature expressions to proper format.

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
        """Convert metric units to standard abbreviations.

        Examples:
        - "five kilometers" → "5 km"
        - "two point five centimeters" → "2.5 cm"
        - "ten kilograms" → "10 kg"
        - "three liters" → "3 L"
        - "three to five kilograms" → "3-5 kg"

        """
        if not entity.metadata:
            return entity.text

        number_text = entity.metadata.get("number", "")
        unit = entity.metadata.get("unit", "").lower()

        # Use the improved number parser that handles decimals automatically
        parsed_num = self.number_parser.parse(number_text)

        # If parsing failed, check if it might be a numeric range
        if not parsed_num:
            # Check for range pattern "X to Y"
            range_pattern = re.match(r"(.*?)\s+to\s+(.*)", number_text, re.IGNORECASE)
            if range_pattern:
                start_text = range_pattern.group(1)
                end_text = range_pattern.group(2)
                start_num = self.number_parser.parse(start_text)
                end_num = self.number_parser.parse(end_text)
                if start_num and end_num:
                    parsed_num = f"{start_num}-{end_num}"

        if not parsed_num:
            return entity.text

        # Unit mappings
        unit_map = {
            # Length
            "millimeter": "mm",
            "millimeters": "mm",
            "millimetre": "mm",
            "millimetres": "mm",
            "mm": "mm",
            "centimeter": "cm",
            "centimeters": "cm",
            "centimetre": "cm",
            "centimetres": "cm",
            "cm": "cm",
            "meter": "m",
            "meters": "m",
            "metre": "m",
            "metres": "m",
            "m": "m",
            "kilometer": "km",
            "kilometers": "km",
            "kilometre": "km",
            "kilometres": "km",
            "km": "km",
            # Weight
            "milligram": "mg",
            "milligrams": "mg",
            "mg": "mg",
            "gram": "g",
            "grams": "g",
            "g": "g",
            "kilogram": "kg",
            "kilograms": "kg",
            "kg": "kg",
            "metric ton": "t",
            "metric tons": "t",
            "tonne": "t",
            "tonnes": "t",
            "pound": "lbs",     # Imperial weight unit
            "pounds": "lbs",    # Imperial weight unit
            # Volume
            "milliliter": "mL",
            "milliliters": "mL",
            "millilitre": "mL",
            "millilitres": "mL",
            "ml": "mL",
            "liter": "L",
            "liters": "L",
            "litre": "L",
            "litres": "L",
            "l": "L",
        }

        standard_unit = unit_map.get(unit, unit.upper())
        return f"{parsed_num} {standard_unit}"
