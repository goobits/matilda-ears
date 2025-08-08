"""
Measurement entity processor combining detection and conversion.

This module migrates MeasurementDetector and MeasurementPatternConverter to the new
EntityProcessor pattern, handling all measurement-related entities including:
- General measurements (feet, inches, pounds, miles)
- Temperature detection (with context awareness) 
- Metric units (length, weight, volume)
- Data sizes (KB, MB, GB)
- Frequencies (Hz, kHz, MHz)
- Time durations
- Percentages
"""

import re
from typing import Dict, List, Any, Optional, Pattern

from stt.text_formatting.entity_processor import BaseNumericProcessor, ProcessingRule
from stt.text_formatting.common import Entity, EntityType
from stt.text_formatting.utils import is_inside_entity


class MeasurementProcessor(BaseNumericProcessor):
    """Processor for measurement entities (quantities, temperatures, metric units, etc.)."""
    
    def _init_detection_rules(self) -> List[ProcessingRule]:
        """Initialize detection rules for measurement entities."""
        # Build number pattern for all rules
        number_pattern = self._build_number_pattern()
        
        return [
            # Temperature patterns (highest priority for context-sensitive detection)
            ProcessingRule(
                pattern=self._build_temperature_pattern_with_units(),
                entity_type=EntityType.TEMPERATURE,
                metadata_extractor=self._extract_temperature_metadata,
                priority=80
            ),
            ProcessingRule(
                pattern=self._build_temperature_degrees_pattern(),
                entity_type=EntityType.TEMPERATURE,
                metadata_extractor=self._extract_temperature_degrees_metadata,
                context_filters=[self._filter_temperature_degrees_context],
                priority=78
            ),
            
            # Angle degrees patterns (for rotate, turn, etc.)
            ProcessingRule(
                pattern=self._build_angle_degrees_pattern(),
                entity_type=EntityType.QUANTITY,
                metadata_extractor=self._extract_angle_degrees_metadata,
                context_filters=[self._filter_angle_degrees_context],
                priority=76
            ),
            
            # Measurement patterns (feet/inches compounds)
            ProcessingRule(
                pattern=self._build_feet_inches_pattern(),
                entity_type=EntityType.QUANTITY,
                metadata_extractor=self._extract_compound_measurement_metadata,
                priority=74
            ),
            ProcessingRule(
                pattern=self._build_fraction_feet_pattern(),
                entity_type=EntityType.QUANTITY,
                metadata_extractor=self._extract_fraction_measurement_metadata,
                priority=72
            ),
            # Metric fractional measurements (kilometers, meters, etc.)
            ProcessingRule(
                pattern=self._build_metric_fraction_pattern(),
                entity_type=EntityType.QUANTITY,
                metadata_extractor=self._extract_fraction_measurement_metadata,
                priority=71
            ),
            # Metric measurements with Unicode fractions (after BasicNumericProcessor converts fractions)
            ProcessingRule(
                pattern=self._build_metric_unicode_fraction_pattern(),
                entity_type=EntityType.QUANTITY,
                metadata_extractor=self._extract_unicode_fraction_measurement_metadata,
                priority=69
            ),
            ProcessingRule(
                pattern=self._build_height_pattern(),
                entity_type=EntityType.QUANTITY,
                metadata_extractor=self._extract_height_metadata,
                priority=70
            ),
            
            # Data size patterns
            ProcessingRule(
                pattern=self._build_data_size_pattern(),
                entity_type=EntityType.DATA_SIZE,
                metadata_extractor=self._extract_general_unit_metadata,
                priority=68
            ),
            
            # Frequency patterns
            ProcessingRule(
                pattern=self._build_frequency_pattern(),
                entity_type=EntityType.FREQUENCY,
                metadata_extractor=self._extract_general_unit_metadata,
                priority=66
            ),
            
            # Time duration patterns
            ProcessingRule(
                pattern=self._build_time_duration_pattern(),
                entity_type=EntityType.TIME_DURATION,
                metadata_extractor=self._extract_general_unit_metadata,
                priority=64
            ),
            
            # Percentage patterns
            ProcessingRule(
                pattern=self._build_percentage_pattern(),
                entity_type=EntityType.PERCENT,
                metadata_extractor=self._extract_percentage_metadata,
                priority=62
            ),
            
            # Basic metric unit patterns (higher priority than general measurements)
            ProcessingRule(
                pattern=self._build_basic_metric_pattern(),
                entity_type=EntityType.QUANTITY,  # Will route to convert_metric_unit via metadata
                metadata_extractor=self._extract_basic_metric_metadata,
                priority=5  # Very low priority - cleanup step after other processors
            ),
            
            # General measurement patterns (lower priority)
            ProcessingRule(
                pattern=self._build_general_measurement_pattern(),
                entity_type=EntityType.QUANTITY,
                metadata_extractor=self._extract_general_measurement_metadata,
                priority=60
            ),
        ]
    
    def _init_conversion_methods(self) -> Dict[EntityType, str]:
        """Initialize conversion methods for measurement types."""
        return {
            EntityType.QUANTITY: "convert_measurement",
            EntityType.TEMPERATURE: "convert_temperature",
            EntityType.METRIC_LENGTH: "convert_metric_unit",
            EntityType.METRIC_WEIGHT: "convert_metric_unit", 
            EntityType.METRIC_VOLUME: "convert_metric_unit",
            EntityType.DATA_SIZE: "convert_data_size",
            EntityType.FREQUENCY: "convert_frequency",
            EntityType.TIME_DURATION: "convert_time_duration",
            EntityType.PERCENT: "convert_percent",
        }
    
    def detect_entities(self, text: str, entities: List[Entity], 
                       all_entities: Optional[List[Entity]] = None) -> None:
        """
        Detect measurement entities with additional SpaCy-based detection.
        
        This overrides the base method to add SpaCy-based metric unit detection.
        """
        # First apply regex-based rules
        super().detect_entities(text, entities, all_entities)
        
        # Then apply SpaCy-based detection for complex patterns
        if self.nlp:
            doc = self.get_spacy_doc(text)
            if doc:
                self._detect_metric_units_with_spacy(doc, text, entities, all_entities)
                self._detect_general_units_with_spacy(doc, text, entities, all_entities)
                self._detect_temperature_context_with_spacy(doc, text, entities, all_entities)
    
    # Pattern builders
    
    def _build_number_pattern(self) -> str:
        """Build pattern for number words."""
        return r"\b(?:" + "|".join(sorted(self.number_parser.all_number_words, key=len, reverse=True)) + r")"
    
    def _build_temperature_pattern_with_units(self) -> Pattern[str]:
        """Build pattern for temperature with explicit units."""
        number_pattern = self._build_number_pattern()
        return re.compile(
            r"\b(?:(minus|negative)\s+)?"  # Optional minus/negative
            r"((?:" + number_pattern + r")(?:\s+(?:and\s+)?(?:" + number_pattern + r"))*"  # Numbers
            r"(?:\s+point\s+(?:" + number_pattern + r")(?:\s+(?:" + number_pattern + r"))*)?|\d+(?:\.\d+)?)"  # Numbers with optional decimal
            r"(?:\s+degrees?)?"  # Optional "degree" or "degrees"
            r"\s+(celsius|centigrade|fahrenheit|c|f)"  # Required unit
            r"\b",
            re.IGNORECASE,
        )
    
    def _build_temperature_degrees_pattern(self) -> Pattern[str]:
        """Build pattern for temperature with degrees but optional units."""
        number_pattern = self._build_number_pattern()
        return re.compile(
            r"\b(?:(minus|negative)\s+)?"  # Optional minus/negative
            r"((?:" + number_pattern + r")(?:\s+(?:and\s+)?(?:" + number_pattern + r"))*"  # Numbers
            r"(?:\s+point\s+(?:" + number_pattern + r")(?:\s+(?:" + number_pattern + r"))*)?|\d+(?:\.\d+)?)"  # Numbers with optional decimal
            r"\s+degrees?"  # Required "degree" or "degrees"
            r"(?:\s+(celsius|centigrade|fahrenheit|c|f))?"  # Optional unit
            r"\b",
            re.IGNORECASE,
        )
    
    def _build_angle_degrees_pattern(self) -> Pattern[str]:
        """Build pattern for angle degrees (rotate, turn, etc.)."""
        number_pattern = self._build_number_pattern()
        return re.compile(
            r"((?:" + number_pattern + r")(?:\s+(?:and\s+)?(?:" + number_pattern + r"))*"  # Numbers
            r"(?:\s+point\s+(?:" + number_pattern + r")(?:\s+(?:" + number_pattern + r"))*)?|\d+(?:\.\d+)?)"  # Numbers with optional decimal
            r"\s+degrees?"  # Required "degree" or "degrees"
            r"\b",
            re.IGNORECASE,
        )
    
    def _build_feet_inches_pattern(self) -> Pattern[str]:
        """Build pattern for 'X feet Y inches'."""
        number_pattern = self._build_number_pattern()
        return re.compile(
            rf"\b({number_pattern})\s+(feet?|foot)\s+({number_pattern})\s+(inch(?:es)?)\b",
            re.IGNORECASE
        )
    
    def _build_fraction_feet_pattern(self) -> Pattern[str]:
        """Build pattern for 'X and a half feet/inches'."""
        number_pattern = self._build_number_pattern()
        return re.compile(
            rf"\b({number_pattern})\s+and\s+a\s+half\s+(feet?|foot|inch(?:es)?)\b",
            re.IGNORECASE
        )
    
    def _build_metric_fraction_pattern(self) -> Pattern[str]:
        """Build pattern for 'X and a half kilometers/meters/etc'."""
        number_pattern = self._build_number_pattern()
        # Common metric units
        metric_units = [
            "kilometers?", "kilometres?", "meters?", "metres?", "centimeters?", "centimetres?",
            "millimeters?", "millimetres?", "kilograms?", "grams?", "liters?", "litres?",
            "milliliters?", "millilitres?", "km", "m", "cm", "mm", "kg", "g", "l", "ml"
        ]
        unit_pattern = r"(?:" + "|".join(sorted(metric_units, key=len, reverse=True)) + r")"
        return re.compile(
            rf"\b({number_pattern})\s+and\s+(?:a\s+(half|quarter)|({number_pattern})\s+(quarters?))\s+({unit_pattern})\b",
            re.IGNORECASE
        )
    
    def _build_metric_unicode_fraction_pattern(self) -> Pattern[str]:
        """Build pattern for 'X and ½/¾/¼ unit' (after Unicode conversion)."""
        number_pattern = self._build_number_pattern()
        # Common metric units
        metric_units = [
            "kilometers?", "kilometres?", "meters?", "metres?", "centimeters?", "centimetres?",
            "millimeters?", "millimetres?", "kilograms?", "grams?", "liters?", "litres?",
            "milliliters?", "millilitres?", "km", "m", "cm", "mm", "kg", "g", "l", "ml"
        ]
        unit_pattern = r"(?:" + "|".join(sorted(metric_units, key=len, reverse=True)) + r")"
        return re.compile(
            rf"\b({number_pattern})\s+and\s+([½¾¼⅞⅝⅜⅛])\s+({unit_pattern})\b",
            re.IGNORECASE
        )
    
    def _build_height_pattern(self) -> Pattern[str]:
        """Build pattern for 'X foot Y' (height format)."""
        number_pattern = self._build_number_pattern()
        return re.compile(
            rf"\b({number_pattern})\s+foot\s+({number_pattern})(?:\s+inch(?:es)?)?\b",
            re.IGNORECASE
        )
    
    def _build_data_size_pattern(self) -> Pattern[str]:
        """Build pattern for data sizes."""
        number_pattern = self._build_number_pattern()
        data_units = self.resources.get("data_units", {}).get("storage", [])
        unit_pattern = r"(?:" + "|".join(sorted(data_units, key=len, reverse=True)) + r")"
        
        return re.compile(
            number_pattern + r"(?:\s+" + number_pattern + r")*\s+" + unit_pattern + r"\b",
            re.IGNORECASE
        )
    
    def _build_frequency_pattern(self) -> Pattern[str]:
        """Build pattern for frequencies."""
        number_pattern = self._build_number_pattern()
        frequency_units = self.resources.get("units", {}).get("frequency_units", [])
        unit_pattern = r"(?:" + "|".join(sorted(frequency_units, key=len, reverse=True)) + r")"
        
        return re.compile(
            number_pattern + r"(?:\s+" + number_pattern + r")*\s+" + unit_pattern + r"\b",
            re.IGNORECASE
        )
    
    def _build_time_duration_pattern(self) -> Pattern[str]:
        """Build pattern for time durations."""
        number_pattern = self._build_number_pattern()
        time_units = self.resources.get("units", {}).get("time_units", [])
        unit_pattern = r"(?:" + "|".join(sorted(time_units, key=len, reverse=True)) + r")"
        
        return re.compile(
            number_pattern + r"(?:\s+" + number_pattern + r")*\s+" + unit_pattern + r"\b",
            re.IGNORECASE
        )
    
    def _build_percentage_pattern(self) -> Pattern[str]:
        """Build pattern for percentages."""
        number_pattern = self._build_number_pattern()
        percent_units = self.resources.get("units", {}).get("percent_units", [])
        unit_pattern = r"(?:" + "|".join(sorted(percent_units, key=len, reverse=True)) + r")"
        
        # Enhanced pattern that handles decimals with "point"
        return re.compile(
            r"(?:"
            r"(?:" + number_pattern + r")"  # Main number
            r"(?:\s+(?:and\s+)?(?:" + number_pattern + r"))*"  # Optional additional numbers
            r"(?:\s+point\s+(?:" + number_pattern + r")(?:\s+(?:" + number_pattern + r"))*)?|"  # Optional decimal part
            r"\d+(?:\.\d+)?"  # Also handle digit decimals
            r")\s+" + unit_pattern + r"\b",
            re.IGNORECASE
        )
    
    def _build_general_measurement_pattern(self) -> Pattern[str]:
        """Build pattern for general measurements (feet, inches, pounds, miles, yards, ounces)."""
        number_pattern = self._build_number_pattern()
        # General US measurement units
        measurement_units = [
            "feet", "foot", "inches", "inch", "pounds", "pound", "lbs", "lb",
            "miles", "mile", "yards", "yard", "ounces", "ounce", "oz"
        ]
        unit_pattern = r"(?:" + "|".join(sorted(measurement_units, key=len, reverse=True)) + r")"
        
        return re.compile(
            number_pattern + r"(?:\s+" + number_pattern + r")*\s+" + unit_pattern + r"\b",
            re.IGNORECASE
        )
    
    def _build_basic_metric_pattern(self) -> Pattern[str]:
        """Build pattern for basic metric units (kilometers, kilograms, etc.)."""
        number_pattern = self._build_number_pattern()
        # Basic metric units that should be abbreviated
        metric_units = [
            "kilometers", "kilometres", "meters", "metres", "centimeters", "centimetres",
            "millimeters", "millimetres", "kilograms", "grams", "liters", "litres", 
            "milliliters", "millilitres"
        ]
        unit_pattern = r"(?:" + "|".join(sorted(metric_units, key=len, reverse=True)) + r")"
        
        return re.compile(
            r"\b(" + number_pattern + r")\s+(" + unit_pattern + r")\b",
            re.IGNORECASE
        )
    
    # Metadata extractors
    
    def _extract_temperature_metadata(self, match: re.Match) -> Dict[str, Any]:
        """Extract metadata from temperature matches with explicit units."""
        return {
            "sign": match.group(1) if len(match.groups()) >= 1 else None,
            "number": match.group(2) if len(match.groups()) >= 2 else "",
            "unit": match.group(3) if len(match.groups()) >= 3 else None
        }
    
    def _extract_temperature_degrees_metadata(self, match: re.Match) -> Dict[str, Any]:
        """Extract metadata from temperature degrees matches."""
        return {
            "sign": match.group(1) if len(match.groups()) >= 1 else None,
            "number": match.group(2) if len(match.groups()) >= 2 else "",
            "unit": match.group(3) if len(match.groups()) >= 3 else None
        }
    
    def _extract_angle_degrees_metadata(self, match: re.Match) -> Dict[str, Any]:
        """Extract metadata from angle degrees matches."""
        return {
            "number": match.group(1) if len(match.groups()) >= 1 else "",
            "unit": "degrees",
            "type": "angle"
        }
    
    def _extract_compound_measurement_metadata(self, match: re.Match) -> Dict[str, Any]:
        """Extract metadata from compound measurements like 'X feet Y inches'."""
        return {
            "feet": match.group(1) if len(match.groups()) >= 1 else "",
            "feet_unit": match.group(2) if len(match.groups()) >= 2 else "",
            "inches": match.group(3) if len(match.groups()) >= 3 else "",
            "inches_unit": match.group(4) if len(match.groups()) >= 4 else "",
            "type": "feet_inches"
        }
    
    def _extract_fraction_measurement_metadata(self, match: re.Match) -> Dict[str, Any]:
        """Extract metadata from fractional measurements like 'X and a half feet'."""
        groups = match.groups()
        if len(groups) >= 5:
            # For new metric patterns: (number, a_fraction_type, explicit_numerator, explicit_denominator, unit)
            main_number = groups[0]
            a_fraction_type = groups[1]  # "half" or "quarter" or None
            explicit_numerator = groups[2]  # e.g., "three" or None
            explicit_denominator = groups[3]  # e.g., "quarters" or None
            unit = groups[4]
            
            if a_fraction_type:
                # "X and a half/quarter Y"
                return {
                    "number": main_number,
                    "fraction_type": a_fraction_type,
                    "unit": unit,
                    "type": "fraction"
                }
            elif explicit_numerator and explicit_denominator:
                # "X and three quarters Y"
                return {
                    "number": main_number,
                    "fraction_numerator": explicit_numerator,
                    "fraction_denominator": explicit_denominator,
                    "unit": unit,
                    "type": "fraction"
                }
        elif len(groups) >= 3:
            # For old metric patterns: (number, fraction_type, unit)
            return {
                "number": groups[0],
                "fraction_type": groups[1],  # "half" or "quarter"
                "unit": groups[2],
                "type": "fraction"
            }
        else:
            # For feet patterns: (number, unit)
            return {
                "number": groups[0] if len(groups) >= 1 else "",
                "unit": groups[1] if len(groups) >= 2 else "",
                "fraction_type": "half",  # Default for feet patterns
                "type": "fraction"
            }
        
        # Fallback
        return {
            "number": groups[0] if len(groups) >= 1 else "",
            "unit": groups[-1] if groups else "",
            "fraction_type": "half",
            "type": "fraction"
        }
    
    def _extract_unicode_fraction_measurement_metadata(self, match: re.Match) -> Dict[str, Any]:
        """Extract metadata from measurements with Unicode fractions like 'X and ¾ liters'."""
        groups = match.groups()
        return {
            "number": groups[0] if len(groups) >= 1 else "",
            "unicode_fraction": groups[1] if len(groups) >= 2 else "",
            "unit": groups[2] if len(groups) >= 3 else "",
            "type": "unicode_fraction"
        }
    
    def _extract_height_metadata(self, match: re.Match) -> Dict[str, Any]:
        """Extract metadata from height measurements like '5 foot 10'."""
        return {
            "feet": match.group(1) if len(match.groups()) >= 1 else "",
            "inches": match.group(2) if len(match.groups()) >= 2 else "",
            "type": "height"
        }
    
    def _extract_general_unit_metadata(self, match: re.Match) -> Dict[str, Any]:
        """Extract metadata from general unit matches."""
        match_text = match.group().lower()
        
        # Find which unit was matched by checking all unit lists
        all_units = (
            self.resources.get("data_units", {}).get("storage", []) +
            self.resources.get("units", {}).get("frequency_units", []) +
            self.resources.get("units", {}).get("time_units", []) +
            self.resources.get("units", {}).get("percent_units", [])
        )
        
        unit = None
        for test_unit in all_units:
            if match_text.endswith(" " + test_unit.lower()):
                unit = test_unit
                break
        
        if unit:
            # Extract number part
            number_text = match_text[: -(len(unit) + 1)]  # Remove unit and space
            return {
                "number": number_text.strip(),
                "unit": unit
            }
        
        return {}
    
    def _extract_basic_metric_metadata(self, match: re.Match) -> Dict[str, Any]:
        """Extract metadata from basic metric unit matches."""
        # Now using capture groups: group(1) is the number, group(2) is the unit
        if len(match.groups()) >= 2:
            number_text = match.group(1).strip()
            unit = match.group(2).strip()
            
            return {
                "number": number_text,
                "unit": unit,
                "is_metric": True  # Flag to route to metric conversion
            }
        
        return {}
    
    def _extract_general_measurement_metadata(self, match: re.Match) -> Dict[str, Any]:
        """Extract metadata from general measurement matches."""
        match_text = match.group().lower()
        measurement_units = [
            "feet", "foot", "inches", "inch", "pounds", "pound", "lbs", "lb",
            "miles", "mile", "yards", "yard", "ounces", "ounce", "oz"
        ]
        
        unit = None
        for test_unit in measurement_units:
            if match_text.endswith(" " + test_unit.lower()):
                unit = test_unit
                break
        
        if unit:
            # Extract number part
            number_text = match_text[: -(len(unit) + 1)]  # Remove unit and space
            return {
                "number": number_text.strip(),
                "unit": unit
            }
        
        return {}
    
    def _extract_percentage_metadata(self, match: re.Match) -> Dict[str, Any]:
        """Extract metadata from percentage matches."""
        match_text = match.group().lower()
        percent_units = self.resources.get("units", {}).get("percent_units", [])
        
        unit = None
        for test_unit in percent_units:
            if match_text.endswith(" " + test_unit.lower()):
                unit = test_unit
                break
        
        if unit:
            # Extract number part
            number_text = match_text[: -(len(unit) + 1)]  # Remove unit and space
            return {
                "number": number_text.strip(),
                "unit": unit
            }
        
        return {}
    
    # Context filters
    
    def _filter_temperature_degrees_context(self, text: str, start: int, end: int) -> bool:
        """Filter temperature degrees based on context to avoid angle confusion."""
        match_text = text[start:end].lower()
        
        # Extract just the sign and unit from the match
        temp_match = re.match(
            r"(?:(minus|negative)\s+)?.*?\s+degrees?(?:\s+(celsius|centigrade|fahrenheit|c|f))?",
            match_text,
            re.IGNORECASE
        )
        
        if temp_match:
            sign = temp_match.group(1)
            unit = temp_match.group(2) if len(temp_match.groups()) >= 2 else None
            
            # Always include if has explicit temperature unit or is negative
            if unit or sign:
                return True
        
        # Check for angle context
        full_text_lower = text.lower()
        angle_keywords = self.resources.get("context_words", {}).get("angle_keywords", [])
        
        # Look for angle keywords in surrounding context
        context_start = max(0, start - 50)
        context_end = min(len(text), end + 50)
        context = full_text_lower[context_start:context_end]
        
        if any(keyword in context for keyword in angle_keywords):
            return False
            
        # Check for temperature context
        temp_context_pattern = re.compile(
            r"\b(temperature|temp|oven|heat|freezer|boiling|freezing)\b.*?" +
            re.escape(match_text[:20]),  # Match start of our text
            re.IGNORECASE | re.DOTALL
        )
        
        if temp_context_pattern.search(text):
            return True
            
        # If no clear context and no explicit unit/sign, filter out
        return unit is not None or sign is not None
    
    def _filter_angle_degrees_context(self, text: str, start: int, end: int) -> bool:
        """Filter to include only angle degrees in proper contexts."""
        # Get angle keywords from resources
        angle_keywords = self.resources.get("context_words", {}).get("angle_keywords", [])
        
        # Check for angle context in surrounding text
        full_text_lower = text.lower()
        context_start = max(0, start - 50)
        context_end = min(len(text), end + 50)
        context = full_text_lower[context_start:context_end]
        
        # Include if angle keywords are found in context
        return any(keyword in context for keyword in angle_keywords)
    
    # SpaCy-based detection methods
    
    def _detect_metric_units_with_spacy(self, doc, text: str, entities: List[Entity], 
                                       all_entities: Optional[List[Entity]] = None) -> None:
        """Detect metric units using SpaCy's grammar analysis."""
        # Get metric units from resources
        length_units = set(self.resources.get("units", {}).get("length_units", []))
        weight_units = set(self.resources.get("units", {}).get("weight_units", []))
        volume_units = set(self.resources.get("units", {}).get("volume_units", []))
        
        i = 0
        while i < len(doc):
            token = doc[i]
            
            # Check if this token is a number
            is_a_number = (
                token.like_num
                or (token.ent_type_ == "CARDINAL")
                or (token.lower_ in self.number_parser.all_number_words)
            )
            
            if is_a_number:
                # Collect all consecutive number tokens (including compound numbers)
                number_tokens = [token]
                j = i + 1
                
                # Keep collecting while we find more number-related tokens
                while j < len(doc):
                    next_token = doc[j]
                    is_next_number = (
                        next_token.like_num
                        or (next_token.ent_type_ == "CARDINAL")
                        or (next_token.lower_ in self.number_parser.all_number_words)
                        or next_token.lower_ in ["and", "point", "dot"]  # Handle decimals
                    )
                    
                    if is_next_number:
                        # Skip "and" in the collected tokens but continue looking
                        if next_token.lower_ != "and":
                            number_tokens.append(next_token)
                        j += 1
                    else:
                        break
                
                # Now check if the token after all numbers is a unit
                if j < len(doc):
                    unit_token = doc[j]
                    unit_lemma = unit_token.lemma_.lower()
                    unit_text = unit_token.text.lower()
                    
                    # Also check for compound units like "metric ton"
                    compound_unit = None
                    if j + 1 < len(doc):
                        next_unit = doc[j + 1]
                        compound = f"{unit_text} {next_unit.text.lower()}"
                        if compound in ["metric ton", "metric tons"]:
                            compound_unit = compound
                    
                    # Determine entity type based on unit
                    entity_type = None
                    actual_unit = compound_unit if compound_unit else unit_text
                    
                    if compound_unit in weight_units:
                        entity_type = EntityType.METRIC_WEIGHT
                    elif unit_lemma in length_units or unit_text in length_units:
                        entity_type = EntityType.METRIC_LENGTH
                    elif unit_lemma in weight_units or unit_text in weight_units:
                        entity_type = EntityType.METRIC_WEIGHT
                    elif unit_lemma in volume_units or unit_text in volume_units:
                        entity_type = EntityType.METRIC_VOLUME
                    
                    if entity_type:
                        # Create entity spanning all number tokens and unit
                        start_pos = number_tokens[0].idx
                        if compound_unit:
                            end_pos = doc[j + 1].idx + len(doc[j + 1].text)
                        else:
                            end_pos = unit_token.idx + len(unit_token.text)
                        entity_text = text[start_pos:end_pos]
                        
                        # Collect all number text for metadata
                        number_text = " ".join([t.text for t in number_tokens])
                        
                        check_entities = all_entities if all_entities is not None else entities
                        if not is_inside_entity(start_pos, end_pos, check_entities):
                            entities.append(
                                Entity(
                                    start=start_pos,
                                    end=end_pos,
                                    text=entity_text,
                                    type=entity_type,
                                    metadata={"number": number_text, "unit": actual_unit},
                                )
                            )
                        
                        # Skip past all the tokens we've processed
                        i = j + (2 if compound_unit else 1)
                        continue
            
            i += 1
    
    def _detect_general_units_with_spacy(self, doc, text: str, entities: List[Entity], 
                                        all_entities: Optional[List[Entity]] = None) -> None:
        """Detect general unit entities using SpaCy's grammar analysis."""
        # Define unit types (excluding currency and measurements which are handled by other detectors)
        percent_units = set(self.resources.get("units", {}).get("percent_units", []))
        data_units = set(self.resources.get("data_units", {}).get("storage", []))
        frequency_units = set(self.resources.get("units", {}).get("frequency_units", []))
        time_units = set(self.resources.get("units", {}).get("time_units", []))
        
        i = 0
        while i < len(doc):
            token = doc[i]
            
            # Find a number-like token (includes cardinals, digits, and number words)
            is_a_number = (
                (token.like_num and token.lower_ not in self.resources.get("technical", {}).get("ordinal_words", []))
                or (token.ent_type_ == "CARDINAL")
                or (token.lower_ in self.number_parser.all_number_words)
            )
            
            if is_a_number:
                number_tokens = [token]
                j = i + 1
                # Greedily consume all consecutive number-related words
                while j < len(doc) and (
                    doc[j].like_num
                    or doc[j].lower_ in self.number_parser.all_number_words
                    or doc[j].lower_ in {"and", "point", "dot"}
                ):
                    if doc[j].lower_ != "and":
                        number_tokens.append(doc[j])
                    j += 1
                
                # Now, check the very next token to see if it's a unit
                if j < len(doc):
                    unit_token = doc[j]
                    unit_lemma = unit_token.lemma_.lower()
                    
                    entity_type = None
                    # Determine entity type based on the unit found
                    if unit_lemma in percent_units:
                        entity_type = EntityType.PERCENT
                    elif unit_lemma in data_units:
                        entity_type = EntityType.DATA_SIZE
                    elif unit_lemma in frequency_units:
                        entity_type = EntityType.FREQUENCY
                    elif unit_lemma in time_units:
                        entity_type = EntityType.TIME_DURATION
                    
                    if entity_type:
                        start_pos = number_tokens[0].idx
                        end_pos = unit_token.idx + len(unit_token.text)
                        
                        # Use the entire span from the start of the number to the end of the unit
                        check_entities = all_entities if all_entities is not None else entities
                        if not is_inside_entity(start_pos, end_pos, check_entities):
                            number_text = " ".join([t.text for t in number_tokens])
                            entities.append(
                                Entity(
                                    start=start_pos,
                                    end=end_pos,
                                    text=text[start_pos:end_pos],
                                    type=entity_type,
                                    metadata={"number": number_text, "unit": unit_token.text},
                                )
                            )
                        i = j  # Move the main loop index past the consumed unit
                        continue
            i += 1
    
    def _detect_temperature_context_with_spacy(self, doc, text: str, entities: List[Entity], 
                                             all_entities: Optional[List[Entity]] = None) -> None:
        """Detect temperature context patterns where degrees doesn't have a unit but context suggests temperature."""
        number_words_pattern = "|".join(sorted(self.number_parser.all_number_words, key=len, reverse=True))
        
        temp_context_pattern = re.compile(
            r"\b(temperature|temp|oven|heat|freezer|boiling|freezing)\b.*?"
            r"\b((?:"
            + number_words_pattern
            + r")(?:\s+(?:and\s+)?(?:"
            + number_words_pattern
            + r"))*|\d+)\s+degrees?\b",
            re.IGNORECASE | re.DOTALL,
        )
        
        for match in temp_context_pattern.finditer(text):
            # Extract just the number + degrees part
            number_match = re.search(
                r"\b((?:"
                + number_words_pattern
                + r")(?:\s+(?:and\s+)?(?:"
                + number_words_pattern
                + r"))*|\d+)\s+degrees?\b",
                match.group(0),
                re.IGNORECASE,
            )
            if number_match:
                # Calculate correct position in original text
                start = text.find(number_match.group(0), match.start())
                if start != -1:
                    end = start + len(number_match.group(0))
                    check_entities = all_entities if all_entities is not None else entities
                    # Don't add if already covered by more specific pattern
                    already_covered = any(
                        e.type == EntityType.TEMPERATURE and e.start <= start and e.end >= end for e in entities
                    )
                    if not already_covered and not is_inside_entity(start, end, check_entities):
                        entities.append(
                            Entity(
                                start=start,
                                end=end,
                                text=number_match.group(0),
                                type=EntityType.TEMPERATURE,
                                metadata={
                                    "sign": None,
                                    "number": number_match.group(1),
                                    "unit": None,  # No unit specified
                                },
                            )
                        )
    
    # Conversion methods
    
    def convert_measurement(self, entity: Entity, full_text: str = "") -> str:
        """
        Convert measurements to use proper symbols.
        
        Examples:
        - "six feet" → "6′"
        - "twelve inches" → "12″"
        - "5 foot 10" → "5′10″"
        - "three and a half feet" → "3.5′"
        """
        if entity.metadata:
            # Check if this is a metric unit that should use metric conversion
            if entity.metadata.get("is_metric"):
                return self.convert_metric_unit(entity)
            
            measurement_type = entity.metadata.get("type")
            
            if measurement_type == "feet_inches":
                # Handle "X feet Y inches"
                feet_text = entity.metadata.get("feet", "")
                inches_text = entity.metadata.get("inches", "")
                
                parsed_feet = self.parse_number(feet_text)
                parsed_inches = self.parse_number(inches_text)
                
                if parsed_feet and parsed_inches:
                    return f"{parsed_feet}′{parsed_inches}″"
                    
            elif measurement_type == "fraction":
                # Handle "X and a half/quarter feet/inches/metric" or "X and three quarters Y"
                number_text = entity.metadata.get("number", "")
                unit = entity.metadata.get("unit", "")
                fraction_type = entity.metadata.get("fraction_type")
                fraction_numerator = entity.metadata.get("fraction_numerator")
                fraction_denominator = entity.metadata.get("fraction_denominator")
                
                parsed_num = self.parse_number(number_text)
                if parsed_num:
                    try:
                        if fraction_type:
                            # "a half" or "a quarter"
                            fraction_value = 0.5 if fraction_type == "half" else 0.25
                        elif fraction_numerator and fraction_denominator:
                            # "three quarters", etc.
                            parsed_numerator = self.parse_number(fraction_numerator)
                            if "quarter" in fraction_denominator.lower():
                                fraction_value = float(parsed_numerator) / 4.0
                            else:
                                fraction_value = 0.5  # Default fallback
                        else:
                            fraction_value = 0.5  # Default fallback
                            
                        num_value = float(parsed_num) + fraction_value
                        number_str = str(num_value).rstrip("0").rstrip(".")
                    except (ValueError, TypeError):
                        if fraction_type == "half":
                            fraction_str = "5"
                        elif fraction_type == "quarter":
                            fraction_str = "25"
                        elif fraction_numerator and "quarter" in (fraction_denominator or "").lower():
                            parsed_numerator = self.parse_number(fraction_numerator)
                            if parsed_numerator == "3":
                                fraction_str = "75"
                            else:
                                fraction_str = "25"
                        else:
                            fraction_str = "5"
                        number_str = f"{parsed_num}.{fraction_str}"
                    
                    # Use proper symbols
                    if "inch" in unit:
                        return f"{number_str}″"
                    if "foot" in unit or "feet" in unit:
                        return f"{number_str}′"
                    
                    # Handle metric units
                    unit_map = self.mapping_registry.get_measurement_unit_map()
                    for original, abbrev in unit_map.items():
                        if unit.lower().startswith(original.lower()) or unit.lower() == original.lower():
                            return f"{number_str} {abbrev}"
            
            elif measurement_type == "unicode_fraction":
                # Handle "X and ¾ unit" (Unicode fractions)
                number_text = entity.metadata.get("number", "")
                unit = entity.metadata.get("unit", "")
                unicode_fraction = entity.metadata.get("unicode_fraction", "")
                
                parsed_num = self.parse_number(number_text)
                if parsed_num and unicode_fraction:
                    try:
                        # Convert Unicode fraction to decimal
                        unicode_to_decimal = {
                            "½": 0.5, "¼": 0.25, "¾": 0.75,
                            "⅛": 0.125, "⅜": 0.375, "⅝": 0.625, "⅞": 0.875
                        }
                        fraction_value = unicode_to_decimal.get(unicode_fraction, 0.5)
                        num_value = float(parsed_num) + fraction_value
                        number_str = str(num_value).rstrip("0").rstrip(".")
                        
                        # Handle metric units
                        unit_map = self.mapping_registry.get_measurement_unit_map()
                        for original, abbrev in unit_map.items():
                            if unit.lower().startswith(original.lower()) or unit.lower() == original.lower():
                                return f"{number_str} {abbrev}"
                                
                    except (ValueError, TypeError):
                        pass
                        
            elif measurement_type == "height":
                # Handle "X foot Y" (height format)
                feet_text = entity.metadata.get("feet", "")
                inches_text = entity.metadata.get("inches", "")
                
                parsed_feet = self.parse_number(feet_text)
                parsed_inches = self.parse_number(inches_text)
                
                if parsed_feet and parsed_inches:
                    return f"{parsed_feet}′{parsed_inches}″"
            
            # Handle general measurements
            number_text = entity.metadata.get("number", "")
            unit = entity.metadata.get("unit", "")
            
            if number_text and unit:
                parsed_num = self.parse_number(number_text)
                if parsed_num:
                    # Check if this is an angle measurement
                    measurement_type = entity.metadata.get("type")
                    if measurement_type == "angle" or unit == "degrees":
                        return f"{parsed_num}°"
                    
                    # Use proper symbols for common units
                    if "inch" in unit:
                        return f"{parsed_num}″"
                    elif "foot" in unit or "feet" in unit:
                        return f"{parsed_num}′"
                    elif "pound" in unit or "lbs" in unit or "lb" == unit:
                        return f"{parsed_num} lbs"
                    elif "ounce" in unit or "oz" in unit:
                        return f"{parsed_num} oz"
                    elif "mile" in unit:
                        return f"{parsed_num} mi"
                    elif "yard" in unit:
                        return f"{parsed_num} yd"
                    else:
                        return f"{parsed_num} {unit}"
        
        # Fallback: try to parse from text
        text = entity.text.lower()
        
        # Try various measurement patterns
        patterns = [
            # "X and a half feet/inches"
            (r"(\w+)\s+and\s+a\s+half\s+(feet?|foot|inch(?:es)?)", "fraction"),
            # "X feet Y inches" (like "six feet two inches")
            (r"(\w+)\s+(feet?|foot)\s+(\w+)\s+(inch(?:es)?)", "feet_inches"),
            # "X foot Y" (like "5 foot 10" or "five foot ten")
            (r"(\w+)\s+foot\s+(\w+)", "height"),
            # Simple measurements
            (r"(\w+)\s+(feet?|foot|inch(?:es)?|pounds?|lbs?|miles?|yards?|ounces?|oz)", "simple"),
        ]
        
        for pattern, pattern_type in patterns:
            match = re.match(pattern, text, re.IGNORECASE)
            if match:
                if pattern_type == "fraction":
                    number_part = match.group(1)
                    unit = match.group(2)
                    
                    parsed_num = self.parse_number(number_part)
                    if parsed_num:
                        try:
                            num_value = float(parsed_num) + 0.5
                            number_str = str(num_value).rstrip("0").rstrip(".")
                        except (ValueError, TypeError):
                            number_str = f"{parsed_num}.5"
                    else:
                        return entity.text
                    
                    if "inch" in unit:
                        return f"{number_str}″"
                    if "foot" in unit or "feet" in unit:
                        return f"{number_str}′"
                        
                elif pattern_type == "simple":
                    number_part = match.group(1)
                    unit = match.group(2)
                    
                    parsed_num = self.parse_number(number_part)
                    if not parsed_num:
                        return entity.text
                    
                    # Use proper symbols
                    if "inch" in unit:
                        return f"{parsed_num}″"
                    if "foot" in unit or "feet" in unit:
                        return f"{parsed_num}′"
                    if "pound" in unit or "lbs" in unit:
                        return f"{parsed_num} lbs"
                    if "ounce" in unit or "oz" in unit:
                        return f"{parsed_num} oz"
                    if "mile" in unit:
                        return f"{parsed_num} mi"
                    if "yard" in unit:
                        return f"{parsed_num} yd"
                        
                elif pattern_type in ["feet_inches", "height"]:
                    if pattern_type == "feet_inches":
                        feet_part = match.group(1)
                        inches_part = match.group(3)
                    else:  # height
                        feet_part = match.group(1)
                        inches_part = match.group(2)
                    
                    parsed_feet = self.parse_number(feet_part)
                    parsed_inches = self.parse_number(inches_part)
                    
                    if parsed_feet and parsed_inches:
                        return f"{parsed_feet}′{parsed_inches}″"
                    
                break
        
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
        
        # Use the number parser to handle complex number expressions
        parsed_num = self.parse_number(number_text)
        
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
        
        # Use the number parser to handle complex number expressions
        parsed_num = self.parse_number(number_text)
        
        if not parsed_num:
            return entity.text
        
        # Get unit mappings from registry
        unit_map = self.mapping_registry.get_measurement_unit_map()
        standard_unit = unit_map.get(unit, unit.upper())
        return f"{parsed_num} {standard_unit}"
    
    def convert_data_size(self, entity: Entity) -> str:
        """Convert data size expressions."""
        if not entity.metadata:
            return entity.text
        
        number_text = entity.metadata.get("number", "")
        unit = entity.metadata.get("unit", "")
        
        parsed_num = self.parse_number(number_text)
        if not parsed_num:
            return entity.text
        
        # Standardize data size units
        unit_map = {
            "byte": "B", "bytes": "B",
            "kilobyte": "KB", "kilobytes": "KB",
            "megabyte": "MB", "megabytes": "MB", 
            "gigabyte": "GB", "gigabytes": "GB",
            "terabyte": "TB", "terabytes": "TB"
        }
        
        standard_unit = unit_map.get(unit.lower(), unit)
        return f"{parsed_num}{standard_unit}"
    
    def convert_frequency(self, entity: Entity) -> str:
        """Convert frequency expressions."""
        if not entity.metadata:
            return entity.text
        
        number_text = entity.metadata.get("number", "")
        unit = entity.metadata.get("unit", "")
        
        parsed_num = self.parse_number(number_text)
        if not parsed_num:
            return entity.text
        
        # Standardize frequency units
        unit_map = {
            "hertz": "Hz",
            "kilohertz": "kHz", "khz": "kHz",
            "megahertz": "MHz", "mhz": "MHz",
            "gigahertz": "GHz", "ghz": "GHz"
        }
        
        standard_unit = unit_map.get(unit.lower(), unit)
        return f"{parsed_num} {standard_unit}"
    
    def convert_time_duration(self, entity: Entity) -> str:
        """Convert time duration expressions."""
        if not entity.metadata:
            return entity.text
        
        number_text = entity.metadata.get("number", "")
        unit = entity.metadata.get("unit", "")
        
        parsed_num = self.parse_number(number_text)
        if not parsed_num:
            return entity.text
        
        # Get abbreviated unit from time duration mappings
        time_map = self.mapping_registry.get_time_duration_unit_map()
        abbrev = time_map.get(unit.lower(), unit)
        
        # Use compact formatting for durations (no space)
        return f"{parsed_num}{abbrev}"
    
    def convert_percent(self, entity: Entity) -> str:
        """Convert percentage expressions."""
        if not entity.metadata:
            # Fallback: parse from text if no metadata available
            text = entity.text.lower()
            match = re.search(r"(.+?)\s+percent", text)
            if match:
                number_text = match.group(1).strip()
                number = self.parse_number(number_text)
                if number is not None:
                    return f"{number}%"
            return entity.text
        
        # Handle groups metadata from format detector (for decimal percentages)
        if "groups" in entity.metadata and entity.metadata.get("is_percentage"):
            groups = entity.metadata["groups"]
            
            if len(groups) >= 2:
                # For decimal patterns like "nine point five" where group[0]="nine", group[1]="five"
                integer_part = groups[0]
                decimal_part = groups[1]
                
                # Parse the integer part
                integer_parsed = None
                if integer_part:
                    integer_parsed = self.parse_number(integer_part)
                    if not integer_parsed and integer_part.isdigit():
                        integer_parsed = integer_part
                
                # Parse the decimal part - handle as digits for true decimal representation
                decimal_parsed = None
                if decimal_part:
                    # For decimal parts, try to parse as a sequence of digits first
                    decimal_parsed = self.parse_as_digits(decimal_part)
                    if not decimal_parsed:
                        # Fallback to regular parsing
                        decimal_parsed = self.parse_number(decimal_part)
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
                    parsed = self.parse_number(group)
                    if parsed:
                        parts.append(parsed)
                    elif group and group.isdigit():
                        parts.append(group)

            if parts:
                # Join with dots for decimal percentages
                percent_str = ".".join(parts)
                return f"{percent_str}%"
        
        # Original handling for metadata with "number" field
        number_text = entity.metadata.get("number", "")
        
        # Parse the number text to convert words to digits
        parsed_number = self.parse_number(number_text)
        if parsed_number is not None:
            return f"{parsed_number}%"
        
        # Fallback to original if parsing fails
        return f"{number_text}%"