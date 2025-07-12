"""Entity detection and conversion for quantities and measurements.

This module handles all entities that represent a number attached to a specific,
real-world unit (e.g., currency, temperature, data size, measurements).
"""

import re
from typing import List, Dict, Any
from .common import Entity, EntityType, NumberParser
from .utils import is_inside_entity
from ..core.config import setup_logging

logger = setup_logging(__name__, log_filename="text_formatting.txt")


class QuantityEntityDetector:
    """Detects quantity and measurement entities in text."""

    def __init__(self, nlp=None):
        self.nlp = nlp
        self._setup_patterns()
        self.entity_types = {
            EntityType.CURRENCY,
            EntityType.MONEY,
            EntityType.DOLLARS,
            EntityType.DOLLAR_CENTS,
            EntityType.CENTS,
            EntityType.POUNDS,
            EntityType.EUROS,
            EntityType.PERCENT,
            EntityType.DATA_SIZE,
            EntityType.FREQUENCY,
            EntityType.TIME_DURATION,
            EntityType.PHONE_LONG,
            EntityType.TEMPERATURE,
            EntityType.METRIC_LENGTH,
            EntityType.METRIC_WEIGHT,
            EntityType.METRIC_VOLUME,
            EntityType.QUANTITY,
        }

    def _setup_patterns(self):
        """Set up regex patterns for quantity detection."""
        # Currency patterns
        self.currency_pattern = re.compile(
            r"\b(?:"
            r"(?:[$£€])\s*\d+(?:,\d{3})*(?:\.\d{2})?|"  # $123.45, £1,234.56
            r"\d+(?:,\d{3})*(?:\.\d{2})?\s*(?:dollars?|pounds?|euros?)|"  # 123 dollars
            r"\d+\s+cents?"  # 50 cents
            r")\b",
            re.IGNORECASE,
        )



        # Frequency pattern
        self.frequency_pattern = re.compile(
            r"\b\d+(?:\.\d+)?\s*(?:hz|khz|mhz|ghz|hertz|kilohertz|megahertz|gigahertz)\b", re.IGNORECASE
        )

        # Phone number pattern (10-11 digits)
        self.phone_pattern = re.compile(r"\b(?:\d{3}[-.\s]?\d{3}[-.\s]?\d{4}|\d{10,11})\b")

        # Temperature pattern
        self.temperature_pattern = re.compile(
            r"\b(?:"
            r"(?:negative\s+|minus\s+)?"
            r"(?:zero|one|two|three|four|five|six|seven|eight|nine|ten|"
            r"eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|"
            r"eighteen|nineteen|twenty|thirty|forty|fifty|sixty|seventy|"
            r"eighty|ninety|hundred|thousand|\d+)"
            r"(?:\s+(?:point|dot)\s+\w+)?"
            r"\s*(?:degrees?\s*)?"
            r"(?:celsius|centigrade|fahrenheit|kelvin|c|f|k)"
            r"|(?:negative\s+|minus\s+)?"
            r"\d+(?:\.\d+)?"
            r"\s*(?:degrees?\s*)?"
            r"(?:celsius|centigrade|fahrenheit|kelvin|°?[cfk])"
            r")\b",
            re.IGNORECASE,
        )

        # Metric unit patterns
        self.metric_patterns = {
            "length": re.compile(
                r"\b\d+(?:\.\d+)?\s*(?:mm|cm|m|km|millimeters?|centimeters?|meters?|kilometres?|kilometers?)\b",
                re.IGNORECASE,
            ),
            "weight": re.compile(
                r"\b\d+(?:\.\d+)?\s*(?:mg|g|kg|t|milligrams?|grams?|kilograms?|tonnes?|tons?)\b", re.IGNORECASE
            ),
            "volume": re.compile(
                r"\b\d+(?:\.\d+)?\s*(?:ml|l|milliliters?|millilitres?|liters?|litres?)\b", re.IGNORECASE
            ),
        }

        # Time duration pattern
        self.time_duration_pattern = re.compile(
            r"\b(?:"
            r"\d+(?:\.\d+)?\s*(?:seconds?|secs?|minutes?|mins?|hours?|hrs?|days?|weeks?|months?|years?)|"
            r"(?:one|two|three|four|five|six|seven|eight|nine|ten|"
            r"eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|"
            r"eighteen|nineteen|twenty|thirty|forty|fifty|sixty|seventy|"
            r"eighty|ninety|hundred|thousand)"
            r"\s+(?:seconds?|minutes?|hours?|days?|weeks?|months?|years?)"
            r")\b",
            re.IGNORECASE,
        )

        # General measurement pattern
        self.measurement_pattern = re.compile(
            r"\b(?:"
            r"(?:zero|one|two|three|four|five|six|seven|eight|nine|ten|"
            r"eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|"
            r"eighteen|nineteen|twenty|thirty|forty|fifty|sixty|seventy|"
            r"eighty|ninety|hundred|thousand|\d+)"
            r"(?:\s+(?:point|dot)\s+\w+)?"
            r"\s+(?:inches?|feet|foot|yards?|miles?|ounces?|pounds?|gallons?|"
            r"millimeters?|centimeters?|meters?|kilometers?|grams?|kilograms?|"
            r"liters?|milliliters?|celsius|fahrenheit|kelvin|degrees?)"
            r")\b",
            re.IGNORECASE,
        )

    def detect(self, text: str, existing_entities: List[Entity] = None) -> List[Entity]:
        """Detect quantity entities in the text."""
        entities = []
        existing_entities = existing_entities or []

        # Detect currency
        entities.extend(self._detect_currency(text, existing_entities))



        # Detect frequencies
        entities.extend(self._detect_frequencies(text, existing_entities))

        # Detect phone numbers
        entities.extend(self._detect_phone_numbers(text, existing_entities))

        # Detect temperatures
        entities.extend(self._detect_temperatures(text, existing_entities))

        # Detect metric units
        entities.extend(self._detect_metric_units(text, existing_entities))

        # Detect time durations
        entities.extend(self._detect_time_durations(text, existing_entities))

        # Detect general measurements
        entities.extend(self._detect_measurements(text, existing_entities))

        return entities

    def _detect_currency(self, text: str, existing_entities: List[Entity]) -> List[Entity]:
        """Detect currency entities."""
        entities = []

        for match in self.currency_pattern.finditer(text):
            if not is_inside_entity(match.start(), match.end(), existing_entities):
                value = match.group()

                # Determine specific currency type
                if "$" in value:
                    if "cent" in value.lower():
                        entity_type = EntityType.CENTS
                    else:
                        entity_type = EntityType.DOLLARS
                elif "£" in value:
                    entity_type = EntityType.POUNDS
                elif "€" in value:
                    entity_type = EntityType.EUROS
                else:
                    entity_type = EntityType.CURRENCY

                entities.append(Entity(start=match.start(), end=match.end(), text=value, type=entity_type))

        return entities



    def _detect_frequencies(self, text: str, existing_entities: List[Entity]) -> List[Entity]:
        """Detect frequency entities."""
        entities = []

        for match in self.frequency_pattern.finditer(text):
            if not is_inside_entity(match.start(), match.end(), existing_entities):
                entities.append(
                    Entity(start=match.start(), end=match.end(), text=match.group(), type=EntityType.FREQUENCY)
                )

        return entities

    def _detect_phone_numbers(self, text: str, existing_entities: List[Entity]) -> List[Entity]:
        """Detect phone number entities."""
        entities = []

        for match in self.phone_pattern.finditer(text):
            if not is_inside_entity(match.start(), match.end(), existing_entities):
                # Only consider it a phone number if it's 10-11 digits
                digits_only = re.sub(r"[^\d]", "", match.group())
                if 10 <= len(digits_only) <= 11:
                    entities.append(
                        Entity(start=match.start(), end=match.end(), text=match.group(), type=EntityType.PHONE_LONG)
                    )

        return entities

    def _detect_temperatures(self, text: str, existing_entities: List[Entity]) -> List[Entity]:
        """Detect temperature entities."""
        entities = []

        for match in self.temperature_pattern.finditer(text):
            if not is_inside_entity(match.start(), match.end(), existing_entities):
                entities.append(
                    Entity(start=match.start(), end=match.end(), text=match.group(), type=EntityType.TEMPERATURE)
                )

        return entities

    def _detect_metric_units(self, text: str, existing_entities: List[Entity]) -> List[Entity]:
        """Detect metric unit entities."""
        entities = []

        # Length units
        for match in self.metric_patterns["length"].finditer(text):
            if not is_inside_entity(match.start(), match.end(), existing_entities):
                entities.append(
                    Entity(start=match.start(), end=match.end(), text=match.group(), type=EntityType.METRIC_LENGTH)
                )

        # Weight units
        for match in self.metric_patterns["weight"].finditer(text):
            if not is_inside_entity(match.start(), match.end(), existing_entities):
                entities.append(
                    Entity(start=match.start(), end=match.end(), text=match.group(), type=EntityType.METRIC_WEIGHT)
                )

        # Volume units
        for match in self.metric_patterns["volume"].finditer(text):
            if not is_inside_entity(match.start(), match.end(), existing_entities):
                entities.append(
                    Entity(start=match.start(), end=match.end(), text=match.group(), type=EntityType.METRIC_VOLUME)
                )

        return entities

    def _detect_time_durations(self, text: str, existing_entities: List[Entity]) -> List[Entity]:
        """Detect time duration entities."""
        entities = []

        for match in self.time_duration_pattern.finditer(text):
            if not is_inside_entity(match.start(), match.end(), existing_entities):
                entities.append(
                    Entity(start=match.start(), end=match.end(), text=match.group(), type=EntityType.TIME_DURATION)
                )

        return entities

    def _detect_measurements(self, text: str, existing_entities: List[Entity]) -> List[Entity]:
        """Detect general measurement entities."""
        entities = []

        for match in self.measurement_pattern.finditer(text):
            if not is_inside_entity(match.start(), match.end(), existing_entities):
                entities.append(
                    Entity(start=match.start(), end=match.end(), text=match.group(), type=EntityType.QUANTITY)
                )

        return entities


class QuantityPatternConverter:
    """Converts quantity patterns to their formatted representation."""

    def __init__(self, number_parser: NumberParser):
        self.number_parser = number_parser
        self.converters = self._get_converters()

    def _get_converters(self) -> Dict[EntityType, Any]:
        """Get the pattern converters for each entity type."""
        return {
            EntityType.CURRENCY: self.convert_currency,
            EntityType.MONEY: self.convert_money,
            EntityType.DOLLARS: self.convert_dollars,
            EntityType.DOLLAR_CENTS: self.convert_dollar_cents,
            EntityType.CENTS: self.convert_cents,
            EntityType.POUNDS: self.convert_pounds,
            EntityType.EUROS: self.convert_euros,
            EntityType.PERCENT: self.convert_percent,
            EntityType.DATA_SIZE: self.convert_data_size,
            EntityType.FREQUENCY: self.convert_frequency,
            EntityType.TIME_DURATION: self.convert_time_duration,
            EntityType.PHONE_LONG: self.convert_phone_long,
            EntityType.TEMPERATURE: self.convert_temperature,
            EntityType.METRIC_LENGTH: self.convert_metric_unit,
            EntityType.METRIC_WEIGHT: self.convert_metric_unit,
            EntityType.METRIC_VOLUME: self.convert_metric_unit,
            EntityType.QUANTITY: self.convert_measurement,
        }

    def convert_currency(self, entity, full_text: str = None) -> str:
        """Convert spoken currency to symbols."""
        value = entity.text
        value_lower = value.lower()

        # Handle specific currency words
        if "dollar" in value_lower:
            return value.replace("dollars", "$").replace("dollar", "$")
        if "pound" in value_lower:
            return value.replace("pounds", "£").replace("pound", "£")
        if "euro" in value_lower:
            return value.replace("euros", "€").replace("euro", "€")

        return value

    def convert_money(self, entity, full_text: str = None) -> str:
        """Convert money entities."""
        return self.convert_currency(entity)

    def convert_dollars(self, entity) -> str:
        """Convert dollar amounts."""
        value = entity.text
        # Extract number and format with $
        match = re.search(r"(\d+(?:\.\d{2})?)", value)
        if match:
            return f"${match.group(1)}"
        return value

    def convert_dollar_cents(self, value: str) -> str:
        """Convert dollar and cents amounts."""
        return self.convert_dollars(value)

    def convert_cents(self, value: str) -> str:
        """Convert cent amounts."""
        match = re.search(r"(\d+)", value)
        if match:
            return f"{match.group(1)}¢"
        return value

    def convert_pounds(self, value: str) -> str:
        """Convert pound amounts."""
        match = re.search(r"(\d+(?:\.\d{2})?)", value)
        if match:
            return f"£{match.group(1)}"
        return value

    def convert_euros(self, value: str) -> str:
        """Convert euro amounts."""
        match = re.search(r"(\d+(?:\.\d{2})?)", value)
        if match:
            return f"€{match.group(1)}"
        return value

    def convert_percent(self, entity) -> str:
        """Convert spoken percent to symbol."""
        value = entity.text
        if "percent" in value.lower():
            return value.replace("percent", "%").replace(" %", "%")
        return value

    def convert_data_size(self, entity) -> str:
        """Convert data size units to standard abbreviations."""
        value = entity.text
        replacements = {
            "kilobytes": "KB",
            "kilobyte": "KB",
            "megabytes": "MB",
            "megabyte": "MB",
            "gigabytes": "GB",
            "gigabyte": "GB",
            "terabytes": "TB",
            "terabyte": "TB",
            "petabytes": "PB",
            "petabyte": "PB",
            "bytes": "B",
            "byte": "B",
        }

        result = value
        for full, abbr in replacements.items():
            result = re.sub(rf"\b{full}\b", abbr, result, flags=re.IGNORECASE)

        return result

    def convert_frequency(self, value: str) -> str:
        """Convert frequency units to standard abbreviations."""
        replacements = {
            "hertz": "Hz",
            "kilohertz": "kHz",
            "megahertz": "MHz",
            "gigahertz": "GHz",
        }

        result = value
        for full, abbr in replacements.items():
            result = re.sub(rf"\b{full}\b", abbr, result, flags=re.IGNORECASE)

        return result

    def convert_time_duration(self, value: str) -> str:
        """Convert time duration to standard format."""
        # Convert spoken numbers to digits
        result = self.number_parser.parse(value)

        # Standardize unit abbreviations
        replacements = {
            "seconds": "s",
            "second": "s",
            "minutes": "min",
            "minute": "min",
            "hours": "h",
            "hour": "h",
            "days": "d",
            "day": "d",
        }

        for full, abbr in replacements.items():
            result = re.sub(rf"\b{full}\b", abbr, result, flags=re.IGNORECASE)

        return result

    def convert_phone_long(self, entity) -> str:
        """Format phone numbers consistently."""
        value = entity.text
        # Remove all non-digits
        digits = re.sub(r"[^\d]", "", value)

        # Format as XXX-XXX-XXXX for 10 digits
        if len(digits) == 10:
            return f"{digits[:3]}-{digits[3:6]}-{digits[6:]}"
        # Format as X-XXX-XXX-XXXX for 11 digits
        if len(digits) == 11:
            return f"{digits[0]}-{digits[1:4]}-{digits[4:7]}-{digits[7:]}"

        return value

    def convert_temperature(self, entity) -> str:
        """Convert temperature expressions."""
        value = entity.text
        # Parse spoken numbers
        result = self.number_parser.parse(value)
        if result is None:
            result = value

        # Standardize temperature scales
        result = re.sub(r"\b(degrees?\s*)?celsius\b", "°C", result, flags=re.IGNORECASE)
        result = re.sub(r"\b(degrees?\s*)?centigrade\b", "°C", result, flags=re.IGNORECASE)
        result = re.sub(r"\b(degrees?\s*)?fahrenheit\b", "°F", result, flags=re.IGNORECASE)
        result = re.sub(r"\b(degrees?\s*)?kelvin\b", "K", result, flags=re.IGNORECASE)

        # Handle single letter abbreviations
        result = re.sub(r"\b(degrees?\s*)?c\b", "°C", result, flags=re.IGNORECASE)
        result = re.sub(r"\b(degrees?\s*)?f\b", "°F", result, flags=re.IGNORECASE)
        result = re.sub(r"\b(degrees?\s*)?k\b", "K", result, flags=re.IGNORECASE)

        return result

    def convert_metric_unit(self, entity) -> str:
        """Convert metric units to standard abbreviations."""
        value = entity.text
        # Parse numbers
        result = self.number_parser.parse(value)
        if result is None:
            result = value

        # Length units
        length_replacements = {
            "kilometers": "km",
            "kilometer": "km",
            "kilometres": "km",
            "kilometre": "km",
            "meters": "m",
            "meter": "m",
            "metres": "m",
            "metre": "m",
            "centimeters": "cm",
            "centimeter": "cm",
            "centimetres": "cm",
            "centimetre": "cm",
            "millimeters": "mm",
            "millimeter": "mm",
            "millimetres": "mm",
            "millimetre": "mm",
        }

        # Weight units
        weight_replacements = {
            "kilograms": "kg",
            "kilogram": "kg",
            "grams": "g",
            "gram": "g",
            "milligrams": "mg",
            "milligram": "mg",
            "tonnes": "t",
            "tonne": "t",
            "tons": "t",
            "ton": "t",
        }

        # Volume units
        volume_replacements = {
            "liters": "L",
            "liter": "L",
            "litres": "L",
            "litre": "L",
            "milliliters": "mL",
            "milliliter": "mL",
            "millilitres": "mL",
            "millilitre": "mL",
        }

        # Apply all replacements
        all_replacements = {**length_replacements, **weight_replacements, **volume_replacements}
        for full, abbr in all_replacements.items():
            result = re.sub(rf"\b{full}\b", abbr, result, flags=re.IGNORECASE)

        return result

    def convert_measurement(self, entity, full_text: str = None) -> str:
        """Convert general measurements."""
        # Parse numbers
        value = entity.text
        result = self.number_parser.parse(value)
        if result is None:
            result = value

        # Apply standard abbreviations for common units
        replacements = {
            "inches": "in",
            "inch": "in",
            "feet": "ft",
            "foot": "ft",
            "yards": "yd",
            "yard": "yd",
            "miles": "mi",
            "mile": "mi",
            "ounces": "oz",
            "ounce": "oz",
            "pounds": "lbs",
            "pound": "lb",
            "gallons": "gal",
            "gallon": "gal",
        }

        for full, abbr in replacements.items():
            result = re.sub(rf"\b{full}\b", abbr, result, flags=re.IGNORECASE)

        return result
