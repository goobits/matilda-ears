"""
Temporal entity processor combining detection and conversion.

This module migrates TemporalDetector and TemporalConverter to the new
EntityProcessor pattern, eliminating code duplication and providing a
cleaner abstraction.
"""

# Standard library imports
import re
from typing import Dict, List, Any, Optional, Pattern

# Local imports - common data structures
from stt.text_formatting.common import Entity, EntityType

# Local imports - base processors and resources
from stt.text_formatting.entity_processor import BaseNumericProcessor, ProcessingRule
from stt.text_formatting.pattern_modules.numeric_patterns import TIME_EXPRESSION_PATTERNS
from stt.text_formatting.modern_pattern_cache import cached_pattern


class TemporalProcessor(BaseNumericProcessor):
    """Processor for temporal entities (time, duration, relative time)."""
    
    def __init__(self, nlp=None, language: str = "en"):
        """Initialize temporal processor."""
        super().__init__(nlp, language)
        
        # Initialize time word mappings
        self.time_word_mappings = self.mapping_registry.get_time_word_mappings()
        
        # Non-time units that indicate this is NOT a time expression
        self.non_time_units = {
            "gigahertz", "megahertz", "kilohertz", "hertz",
            "ghz", "mhz", "khz", "hz",
            "gigabytes", "megabytes", "kilobytes", "bytes",
            "gb", "mb", "kb",
            "milliseconds", "microseconds", "nanoseconds",
            "ms", "us", "ns",
            "meters", "kilometers", "miles", "feet", "inches",
            "volts", "watts", "amps", "ohms",
        }
    
    def _init_detection_rules(self) -> List[ProcessingRule]:
        """Initialize detection rules for temporal entities."""
        return [
            # Time expressions with context (e.g., "meet at three thirty")
            ProcessingRule(
                pattern=TIME_EXPRESSION_PATTERNS[0],
                entity_type=EntityType.TIME_CONTEXT,
                metadata_extractor=self._extract_time_metadata,
                context_filters=[self._filter_non_time_units],
                priority=100
            ),
            # AM/PM time expressions (e.g., "three thirty PM")
            ProcessingRule(
                pattern=TIME_EXPRESSION_PATTERNS[1],
                entity_type=EntityType.TIME_AMPM,
                metadata_extractor=self._extract_time_metadata,
                context_filters=[self._filter_non_time_units],
                priority=98
            ),
            # Spoken "a m"/"p m" pattern
            ProcessingRule(
                pattern=TIME_EXPRESSION_PATTERNS[2],
                entity_type=EntityType.TIME_AMPM,
                metadata_extractor=self._extract_time_metadata,
                context_filters=[self._filter_non_time_units],
                priority=95
            ),
            # "at three PM" pattern
            ProcessingRule(
                pattern=TIME_EXPRESSION_PATTERNS[3],
                entity_type=EntityType.TIME_AMPM,
                metadata_extractor=self._extract_time_metadata,
                context_filters=[self._filter_non_time_units],
                priority=92
            ),
            # Simple "three PM" pattern
            ProcessingRule(
                pattern=TIME_EXPRESSION_PATTERNS[4],
                entity_type=EntityType.TIME_AMPM,
                metadata_extractor=self._extract_time_metadata,
                context_filters=[self._filter_non_time_units],
                priority=89
            ),
            # Time duration pattern
            ProcessingRule(
                pattern=self._build_time_duration_pattern(),
                entity_type=EntityType.TIME_DURATION,
                metadata_extractor=self._extract_duration_metadata,
                priority=86
            ),
            # Compound duration pattern
            ProcessingRule(
                pattern=self._build_compound_duration_pattern(),
                entity_type=EntityType.TIME_DURATION,
                metadata_extractor=self._extract_compound_duration_metadata,
                priority=83
            ),
            # Relative time expressions (e.g., "quarter past three")
            ProcessingRule(
                pattern=self._build_relative_time_pattern(),
                entity_type=EntityType.TIME_RELATIVE,
                metadata_extractor=self._extract_relative_time_metadata,
                priority=80
            ),
            # Date expressions (e.g., "january first", "march third")
            ProcessingRule(
                pattern=self._build_date_pattern(),
                entity_type=EntityType.DATE,
                metadata_extractor=self._extract_date_metadata,
                priority=75
            ),
            # Time with seconds: "three thirty and twenty seconds PM"
            ProcessingRule(
                pattern=TIME_EXPRESSION_PATTERNS[6],
                entity_type=EntityType.TIME_AMPM,
                metadata_extractor=self._extract_time_metadata,
                priority=91
            ),
            # Special time expressions: "noon", "midnight", "twelve noon"
            ProcessingRule(
                pattern=TIME_EXPRESSION_PATTERNS[7],
                entity_type=EntityType.TIME_AMPM,
                metadata_extractor=self._extract_time_metadata,
                priority=90
            ),
        ]
    
    def _init_conversion_methods(self) -> Dict[EntityType, str]:
        """Initialize conversion methods for temporal types."""
        return {
            EntityType.TIME_DURATION: "convert_time_duration",
            EntityType.TIME: "convert_time_or_duration",  # SpaCy detected TIME entity
            EntityType.TIME_CONTEXT: "convert_time",
            EntityType.TIME_AMPM: "convert_time",
            EntityType.TIME_RELATIVE: "convert_time_relative",
            EntityType.DATE: "convert_date",
        }
    
    # Pattern builders
    
    @cached_pattern(category='temporal', language_aware=True)
    def _build_time_duration_pattern(self) -> Pattern[str]:
        """Build pattern for time duration expressions."""
        # Build number pattern from number parser words
        number_words = sorted(self.number_parser.all_number_words, key=len, reverse=True)
        number_pattern = r"\b(?:" + "|".join(re.escape(word) for word in number_words) + r"|\d+)"
        
        # Time units
        time_units = ["second", "minute", "hour", "day", "week", "month", "year"]
        unit_pattern = r"(?:" + "|".join(time_units) + r")s?"
        
        return re.compile(
            rf"({number_pattern}(?:\s+{number_pattern})*)\s+({unit_pattern})\b",
            re.IGNORECASE
        )
    
    @cached_pattern(category='temporal', language_aware=True)
    def _build_compound_duration_pattern(self) -> Pattern[str]:
        """Build pattern for compound durations like '5 hours 30 minutes'."""
        number_pattern = r"(?:\w+(?:\s+\w+)*)"  # Allow compound numbers
        time_units = ["second", "minute", "hour", "day", "week", "month", "year"]
        unit_pattern = r"(?:" + "|".join(time_units) + r")s?"
        
        return re.compile(
            rf"\b({number_pattern})\s+({unit_pattern})\s+({number_pattern})\s+({unit_pattern})\b",
            re.IGNORECASE
        )
    
    @cached_pattern(category='temporal', language_aware=True)
    def _build_relative_time_pattern(self) -> Pattern[str]:
        """Build pattern for relative time expressions."""
        relative_exprs = [
            "quarter past", "half past", "quarter to",
            "five past", "ten past", "twenty past", "twenty-five past",
            "five to", "ten to", "twenty to", "twenty-five to"
        ]
        expr_pattern = r"(?:" + "|".join(relative_exprs) + r")"
        
        # Hour words (one through twelve)
        hour_words = ["one", "two", "three", "four", "five", "six", 
                     "seven", "eight", "nine", "ten", "eleven", "twelve"]
        hour_pattern = r"(?:" + "|".join(hour_words) + r"|\d{1,2})"
        
        return re.compile(
            rf"\b({expr_pattern})\s+({hour_pattern})\b",
            re.IGNORECASE
        )
    
    @cached_pattern(category='temporal', language_aware=True)
    def _build_date_pattern(self) -> Pattern[str]:
        """Build pattern for date expressions."""
        temporal_resources = self.resources.get("temporal", {})
        months = temporal_resources.get("month_names", [])
        ordinals = temporal_resources.get("date_ordinals", [])
        
        # Build pattern for "month ordinal" format
        month_pattern = r"(?:" + "|".join(months) + r")"
        ordinal_pattern = r"(?:" + "|".join(ordinals) + r")"
        
        return re.compile(
            rf"\b({month_pattern})\s+({ordinal_pattern})\b",
            re.IGNORECASE
        )
    
    # Metadata extractors
    
    def _extract_time_metadata(self, match: re.Match) -> Dict[str, Any]:
        """Extract metadata from time matches."""
        return {"groups": match.groups()}
    
    def _extract_duration_metadata(self, match: re.Match) -> Dict[str, Any]:
        """Extract metadata from duration matches."""
        return {
            "number": match.group(1).strip(),
            "unit": match.group(2).strip()
        }
    
    def _extract_compound_duration_metadata(self, match: re.Match) -> Dict[str, Any]:
        """Extract metadata from compound duration matches."""
        return {
            "is_compound": True,
            "number1": match.group(1).strip(),
            "unit1": match.group(2).strip(),
            "number2": match.group(3).strip(),
            "unit2": match.group(4).strip()
        }
    
    def _extract_relative_time_metadata(self, match: re.Match) -> Dict[str, Any]:
        """Extract metadata from relative time matches."""
        return {
            "relative_expr": match.group(1).strip(),
            "hour_word": match.group(2).strip()
        }
    
    def _extract_date_metadata(self, match: re.Match) -> Dict[str, Any]:
        """Extract metadata from date matches."""
        return {
            "month": match.group(1).strip(),
            "ordinal": match.group(2).strip()
        }
    
    # Context filters
    
    def _filter_non_time_units(self, text: str, start: int, end: int) -> bool:
        """Filter out matches followed by non-time units."""
        # Check following text
        following_text = text[end:end + 20].lower().strip()
        
        # Skip if followed by a non-time unit
        if any(following_text.startswith(unit) for unit in self.non_time_units):
            return False
        
        return True
    
    # Conversion methods
    
    def convert_time_duration(self, entity: Entity) -> str:
        """Convert time duration entities."""
        if not entity.metadata:
            return entity.text
        
        # Check if the number part is an ordinal word
        if "number" in entity.metadata:
            number_text = entity.metadata["number"].lower()
            ordinal_words = self.resources.get("technical", {}).get("ordinal_words", [])
            if number_text in ordinal_words:
                # This is an ordinal + time unit (e.g., "fourth day")
                return entity.text
        
        # Check if this is a compound duration
        if entity.metadata.get("is_compound"):
            # Handle compound durations like "5 hours 30 minutes"
            number1 = entity.metadata.get("number1", "")
            unit1 = entity.metadata.get("unit1", "").lower()
            number2 = entity.metadata.get("number2", "")
            unit2 = entity.metadata.get("unit2", "").lower()
            
            # Convert number words to digits
            num1_str = self.number_parser.parse(number1) or number1
            num2_str = self.number_parser.parse(number2) or number2
            
            # Get abbreviated units
            time_map = self.mapping_registry.get_time_duration_unit_map()
            abbrev1 = time_map.get(unit1, unit1)
            abbrev2 = time_map.get(unit2, unit2)
            
            # Format as compact notation
            return f"{num1_str}{abbrev1} {num2_str}{abbrev2}"
        
        # Handle simple duration
        if "number" in entity.metadata and "unit" in entity.metadata:
            number_text = entity.metadata["number"]
            unit = entity.metadata["unit"].lower()
            
            # Parse the number
            number_str = self.number_parser.parse(number_text)
            
            # If that fails, try parsing individual words
            if number_str is None:
                words = number_text.split()
                for i, _word in enumerate(words):
                    remaining_text = " ".join(words[i:])
                    parsed = self.number_parser.parse(remaining_text)
                    if parsed:
                        number_str = parsed
                        break
            
            # Final fallback
            if number_str is None:
                number_str = number_text
            
            # Get abbreviated unit
            time_map = self.mapping_registry.get_time_duration_unit_map()
            abbrev = time_map.get(unit, unit)
            
            # Use compact formatting for durations
            return f"{number_str}{abbrev}"  # No space for units like h, s, d
        
        return entity.text
    
    def convert_time_or_duration(self, entity: Entity) -> str:
        """Convert TIME entities detected by SpaCy."""
        text = entity.text.lower().strip()
        
        # Check for special time expressions first
        units_resources = self.resources.get("units", {})
        time_expressions = units_resources.get("time_expressions", {})
        
        # Handle special time expressions like "noon", "midnight", "twelve noon"
        # First try exact matches
        for phrase, replacement in time_expressions.items():
            if text == phrase:
                return replacement
        
        # Check patterns from TIME_EXPRESSION_PATTERNS for SpaCy TIME entities
        # Use the same patterns as the temporal processor rules
        time_patterns = TIME_EXPRESSION_PATTERNS
        
        # Check pattern 7 (special time expressions: noon, midnight, twelve noon)
        if len(time_patterns) > 7:
            match = time_patterns[7].search(entity.text)
            if match:
                groups = match.groups()
                # For "twelve noon" -> groups: ('twelve ', 'noon')
                # For "noon" -> groups: (None, 'noon')
                time_word = groups[1].lower()  # "noon" or "midnight"
                if time_word in time_expressions:
                    # Replace the matched part while preserving the rest
                    replacement = time_expressions[time_word]
                    return entity.text.replace(match.group(0), replacement, 1)
        
        # Check pattern 6 (time with seconds)
        if len(time_patterns) > 6:
            match = time_patterns[6].search(entity.text)
            if match:
                groups = match.groups()
                # Groups: (hour, minutes, seconds, AM/PM)
                hour = self.time_word_mappings.get(groups[0].lower(), groups[0])
                minute_word = groups[1].lower()
                minute = self.time_word_mappings.get(minute_word, minute_word)
                seconds_word = groups[2].lower()
                seconds = self.time_word_mappings.get(seconds_word, seconds_word)
                ampm = groups[3].upper() if groups[3] else ""
                
                # Ensure minute and seconds are zero-padded
                if minute.isdigit():
                    minute = minute.zfill(2)
                if seconds.isdigit():
                    seconds = seconds.zfill(2)
                
                time_str = f"{hour}:{minute}:{seconds}"
                if ampm:
                    time_str += f" {ampm}"
                
                # Replace the matched part while preserving the rest
                return entity.text.replace(match.group(0), time_str, 1)
        
        # Check if this is a compound duration pattern
        compound_pattern = re.compile(
            r"\b((?:\w+\s+)*\w+)\s+(seconds?|minutes?|hours?|days?|weeks?|months?|years?)\s+"
            r"((?:\w+\s+)*\w+)\s+(seconds?|minutes?|hours?|days?|weeks?|months?|years?)\b",
            re.IGNORECASE,
        )
        
        match = compound_pattern.match(text)
        if match:
            # This is a compound duration
            number1 = self.number_parser.parse(match.group(1)) or match.group(1)
            unit1 = match.group(2)
            number2 = self.number_parser.parse(match.group(3)) or match.group(3)
            unit2 = match.group(4)
            
            # Get abbreviated units
            time_map = self.mapping_registry.get_time_duration_unit_map()
            abbrev1 = time_map.get(unit1.lower(), unit1)
            abbrev2 = time_map.get(unit2.lower(), unit2)
            
            return f"{number1}{abbrev1} {number2}{abbrev2}"
        
        # Check for simple duration pattern
        simple_pattern = re.compile(
            r"\b(\w+)\s+(seconds?|minutes?|hours?|days?|weeks?|months?|years?)\b", 
            re.IGNORECASE
        )
        
        match = simple_pattern.match(text)
        if match:
            number = self.number_parser.parse(match.group(1)) or match.group(1)
            unit = match.group(2)
            
            # Get abbreviated unit
            time_map = self.mapping_registry.get_time_duration_unit_map()
            abbrev = time_map.get(unit.lower(), unit)
            
            return f"{number}{abbrev}"
        
        # Not a duration pattern
        return entity.text
    
    def convert_time(self, entity: Entity) -> str:
        """Convert time expressions."""
        # Check for special time expressions first
        text_lower = entity.text.lower().strip()
        units_resources = self.resources.get("units", {})
        time_expressions = units_resources.get("time_expressions", {})
        
        # Handle special time expressions like "noon", "midnight", "twelve noon"
        for phrase, replacement in time_expressions.items():
            if text_lower == phrase:
                return replacement
                
        if entity.metadata and "groups" in entity.metadata:
            groups = entity.metadata["groups"]
            
            if entity.type == EntityType.TIME_CONTEXT:
                # Handle 'meet at three thirty'
                context = groups[0]  # 'meet at' or 'at'
                hour = self.time_word_mappings.get(groups[1].lower(), groups[1])
                minute_word = groups[3].lower() if groups[3] else "00"
                minute = self.time_word_mappings.get(minute_word, minute_word)
                if minute.isdigit():
                    minute = minute.zfill(2)
                ampm = groups[4].upper() if len(groups) > 4 and groups[4] else ""
                
                time_str = f"{hour}:{minute}"
                if ampm:
                    time_str += f" {ampm}"
                return f"{context} {time_str}"
            
            if entity.type == EntityType.TIME_AMPM:
                # Handle different TIME_AMPM patterns
                if len(groups) == 4:
                    # Pattern: "three thirty and twenty seconds PM"
                    hour = self.time_word_mappings.get(groups[0].lower(), groups[0])
                    minute_word = groups[1].lower()
                    minute = self.time_word_mappings.get(minute_word, minute_word)
                    seconds_word = groups[2].lower()
                    seconds = self.time_word_mappings.get(seconds_word, seconds_word)
                    ampm = groups[3].upper() if groups[3] else ""
                    
                    # Ensure minute and seconds are zero-padded
                    if minute.isdigit():
                        minute = minute.zfill(2)
                    if seconds.isdigit():
                        seconds = seconds.zfill(2)
                    
                    time_str = f"{hour}:{minute}:{seconds}"
                    if ampm:
                        time_str += f" {ampm}"
                    return time_str
                elif len(groups) == 3:
                    if groups[0].lower() == "at":
                        # Pattern: "at three PM"
                        hour = self.time_word_mappings.get(groups[1].lower(), groups[1])
                        ampm = groups[2].upper()
                        at_word = groups[0]
                        return f"{at_word} {hour} {ampm}"
                    if groups[2] in ["AM", "PM"]:
                        # Pattern: "three thirty PM"
                        hour = self.time_word_mappings.get(groups[0].lower(), groups[0])
                        minute_word = groups[1].lower()
                        minute = self.time_word_mappings.get(minute_word, minute_word)
                        if minute.isdigit():
                            minute = minute.zfill(2)
                        ampm = groups[2].upper()
                        return f"{hour}:{minute} {ampm}"
                elif len(groups) == 2:
                    if groups[1] in ["AM", "PM"]:
                        # Pattern: "three PM"
                        hour = self.time_word_mappings.get(groups[0].lower(), groups[0])
                        ampm = groups[1].upper()
                        return f"{hour} {ampm}"
                    if groups[1].lower() in ["a", "p"]:
                        # Pattern: "ten a m"
                        hour = self.time_word_mappings.get(groups[0].lower(), groups[0])
                        ampm = "AM" if groups[1].lower() == "a" else "PM"
                        return f"{hour} {ampm}"
        
        return entity.text
    
    def convert_time_relative(self, entity: Entity) -> str:
        """Convert relative time expressions (quarter past three -> 3:15)."""
        if not entity.metadata:
            return entity.text
        
        relative_expr = entity.metadata.get("relative_expr", "").lower()
        hour_word = entity.metadata.get("hour_word", "").lower()
        
        # Get hour mappings
        hour_mappings = self.mapping_registry.get_hour_mappings()
        
        # Convert hour word to number
        hour = hour_mappings.get(hour_word)
        if hour is None:
            # Try to parse as a number
            try:
                hour = int(hour_word)
            except (ValueError, TypeError):
                return entity.text
        
        # Convert relative expression to time
        time_mappings = {
            "quarter past": f"{hour}:15",
            "half past": f"{hour}:30",
            "quarter to": f"{hour - 1 if hour > 1 else 12}:45",
            "five past": f"{hour}:05",
            "ten past": f"{hour}:10",
            "twenty past": f"{hour}:20",
            "twenty-five past": f"{hour}:25",
            "five to": f"{hour - 1 if hour > 1 else 12}:55",
            "ten to": f"{hour - 1 if hour > 1 else 12}:50",
            "twenty to": f"{hour - 1 if hour > 1 else 12}:40",
            "twenty-five to": f"{hour - 1 if hour > 1 else 12}:35",
        }
        
        return time_mappings.get(relative_expr, entity.text)
    
    def convert_date(self, entity: Entity) -> str:
        """Convert date expressions (january first -> January 1st)."""
        # Check if this DATE entity is actually a mathematical expression that should be converted
        if not entity.metadata:
            # This might be a mathematical expression like "two plus years" that was incorrectly detected as DATE
            if self._is_mathematical_expression_in_date(entity):
                return self._convert_mathematical_date_expression(entity)
            return entity.text
            
        month = entity.metadata.get("month", "").lower()
        ordinal = entity.metadata.get("ordinal", "").lower()
        
        # Get temporal resources
        temporal_resources = self.resources.get("temporal", {})
        date_ordinal_mappings = temporal_resources.get("date_ordinal_mappings", {})
        
        # Convert ordinal word to number
        ordinal_number = date_ordinal_mappings.get(ordinal, ordinal)
        
        # Capitalize month name
        month_capitalized = month.capitalize()
        
        return f"{month_capitalized} {ordinal_number}"
    
    def _is_mathematical_expression_in_date(self, entity: Entity) -> bool:
        """Check if this DATE entity is actually a mathematical expression."""
        text = entity.text.lower()
        
        # Look for mathematical patterns that were incorrectly detected as dates
        math_patterns = [
            r'\b\w+\s+plus\s+(?:years?|months?|weeks?|days?)\b',  # "two plus years"
            r'\b\w+\s+minus\s+(?:years?|months?|weeks?|days?)\b',  # "two minus years"
            r'\b\w+\s+times\s+(?:years?|months?|weeks?|days?)\b',  # "two times years"
        ]
        
        for pattern in math_patterns:
            if re.search(pattern, text):
                return True
        
        return False
    
    def _convert_mathematical_date_expression(self, entity: Entity) -> str:
        """Convert mathematical expressions that were detected as dates."""
        import re
        from stt.text_formatting.common import NumberParser
        
        text = entity.text
        
        # Pattern for "number plus years" type expressions
        plus_pattern = r'\b(\w+)\s+plus\s+(years?|months?|weeks?|days?)\b'
        match = re.search(plus_pattern, text, re.IGNORECASE)
        
        if match:
            number_word = match.group(1)
            time_unit = match.group(2)
            
            # Convert number word to digit
            parser = NumberParser()
            number_digit = parser.parse(number_word)
            
            if number_digit:
                return text.replace(f"{number_word} plus", f"{number_digit} +")
        
        return entity.text