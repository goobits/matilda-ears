#!/usr/bin/env python3
"""Measurement detection functionality for temperature, metric units, and quantity measurements."""
from __future__ import annotations

import re
from typing import Any

from stt.core.config import setup_logging
from stt.text_formatting.common import Entity, EntityType, NumberParser
from stt.text_formatting.constants import get_resources
from stt.text_formatting.utils import is_inside_entity

logger = setup_logging(__name__, log_filename="text_formatting.txt", include_console=False)


class MeasurementDetector:
    """Detector for temperature, metric units, and quantity measurements."""
    
    def __init__(self, nlp=None, language: str = "en"):
        """
        Initialize MeasurementDetector.

        Args:
            nlp: SpaCy NLP model instance. If None, will load from nlp_provider.
            language: Language code for resource loading (default: 'en')
        """
        if nlp is None:
            from stt.text_formatting.nlp_provider import get_nlp
            nlp = get_nlp()

        self.nlp = nlp
        self.language = language

        # Load language-specific resources
        self.resources = get_resources(language)

        # Initialize NumberParser for robust number word detection
        self.number_parser = NumberParser(language=self.language)

    def detect_measurements(self, text: str, entities: list[Entity], all_entities: list[Entity] | None = None) -> None:
        """
        Detect measurement patterns that SpaCy might miss or misclassify.

        This catches patterns like:
        - "three and a half feet"
        - "X foot Y inches"
        """
        # Patterns for measurements that SpaCy might miss
        patterns = [
            # "X and a half feet/inches" - often misclassified as DATE
            (r"(\w+)\s+and\s+a\s+half\s+(feet?|foot|inch(?:es)?)", EntityType.QUANTITY),
            # "X foot Y inches" pattern
            (r"(\w+)\s+foot\s+(\w+)(?:\s+inch(?:es)?)?", EntityType.QUANTITY),
        ]

        for pattern, entity_type in patterns:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                check_entities = all_entities if all_entities else entities
                if not is_inside_entity(match.start(), match.end(), check_entities):
                    entities.append(Entity(start=match.start(), end=match.end(), text=match.group(), type=entity_type))

    def detect_temperatures(self, text: str, entities: list[Entity], all_entities: list[Entity] | None = None) -> None:
        """
        Detect temperature expressions.

        Examples:
        - "twenty degrees celsius" → "20°C"
        - "thirty two degrees fahrenheit" → "32°F"
        - "minus ten degrees" → "-10°"
        - "negative five celsius" → "-5°C"
        """
        # Build pattern for temperature expressions
        number_words_pattern = "|".join(sorted(self.number_parser.all_number_words, key=len, reverse=True))

        # Pattern for temperatures with explicit units
        # This pattern needs to handle compound numbers like "thirty two", decimals like "thirty six point five"
        temp_pattern = re.compile(
            r"\b(?:(minus|negative)\s+)?"  # Optional minus/negative
            r"((?:" + number_words_pattern + r")(?:\s+(?:and\s+)?(?:" + number_words_pattern + r"))*"  # Numbers
            r"(?:\s+point\s+(?:"  # Optional decimal point
            + number_words_pattern
            + r")(?:\s+(?:"
            + number_words_pattern
            + r"))*)?|\d+(?:\.\d+)?)"  # Numbers with optional decimal or digit with decimal
            r"(?:\s+degrees?)?"  # Optional "degree" or "degrees"
            r"\s+(celsius|centigrade|fahrenheit|c|f)"  # Required unit for non-degree temperatures
            r"\b",
            re.IGNORECASE,
        )

        # Pattern for temperatures with degrees but optional units
        temp_degrees_pattern = re.compile(
            r"\b(?:(minus|negative)\s+)?"  # Optional minus/negative
            r"((?:" + number_words_pattern + r")(?:\s+(?:and\s+)?(?:" + number_words_pattern + r"))*"  # Numbers
            r"(?:\s+point\s+(?:"  # Optional decimal point
            + number_words_pattern
            + r")(?:\s+(?:"
            + number_words_pattern
            + r"))*)?|\d+(?:\.\d+)?)"  # Numbers with optional decimal or digit with decimal
            r"\s+degrees?"  # Required "degree" or "degrees"
            r"(?:\s+(celsius|centigrade|fahrenheit|c|f))?"  # Optional unit
            r"\b",
            re.IGNORECASE,
        )

        # Check both temperature patterns
        for pattern in [temp_pattern, temp_degrees_pattern]:
            for match in pattern.finditer(text):
                check_entities = all_entities if all_entities else entities
                if not is_inside_entity(match.start(), match.end(), check_entities):
                    sign = match.group(1)  # minus/negative
                    number_text = match.group(2)
                    unit = match.group(3) if len(match.groups()) >= 3 else None

                    # For temp_pattern (unit required), always create entity
                    # For temp_degrees_pattern, only create if it has a unit OR is negative
                    # This prevents "rotate ninety degrees" from being converted
                    if pattern == temp_pattern or unit or sign:
                        entities.append(
                            Entity(
                                start=match.start(),
                                end=match.end(),
                                text=match.group(0),
                                type=EntityType.TEMPERATURE,
                                metadata={"sign": sign, "number": number_text, "unit": unit},
                            )
                        )

        # Also check for temperature context patterns where "degrees" doesn't have a unit
        # but context suggests temperature (e.g., "temperature reached 100 degrees", "set oven to 350 degrees")
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
                    check_entities = all_entities if all_entities else entities
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

    def detect_metric_units(self, text: str, entities: list[Entity], all_entities: list[Entity] | None = None) -> None:
        """
        Detect metric unit expressions.

        Examples:
        - "five kilometers" → "5 km"
        - "two point five centimeters" → "2.5 cm"
        - "ten kilograms" → "10 kg"
        - "three liters" → "3 L"
        """
        if not self.nlp:
            return
        try:
            doc = self.nlp(text)
        except (AttributeError, ValueError, IndexError) as e:
            logger.warning(f"SpaCy metric unit detection failed: {e}")
            return

        # Iterate through tokens
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

                    # Get units from resources
                    weight_units = self.resources.get("units", {}).get("weight_units", [])
                    length_units = self.resources.get("units", {}).get("length_units", [])
                    volume_units = self.resources.get("units", {}).get("volume_units", [])

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

                        check_entities = all_entities if all_entities else entities
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

        # Fallback: Use regex pattern for cases SpaCy misses
        # Build pattern for metric units with number words
        number_words_pattern = "|".join(sorted(self.number_parser.all_number_words, key=len, reverse=True))
        metric_pattern = re.compile(
            r"\b((?:" + number_words_pattern + r")(?:\s+(?:and\s+)?(?:" + number_words_pattern + r"))*"
            r"(?:\s+point\s+(?:" + number_words_pattern + r"))?|\d+(?:\.\d+)?)"  # Number with optional decimal
            r"\s+("  # Followed by a unit
            r"(?:millimeters?|millimetres?|centimeters?|centimetres?|meters?|metres?|kilometers?|kilometres?|"
            r"milligrams?|grams?|kilograms?|metric\s+tons?|tonnes?|"
            r"milliliters?|millilitres?|liters?|litres?)"
            r")\b",
            re.IGNORECASE,
        )

        for match in metric_pattern.finditer(text):
            check_entities = all_entities if all_entities else entities
            # Check if already detected
            already_exists = any(
                (
                    e.type in [EntityType.METRIC_LENGTH, EntityType.METRIC_WEIGHT, EntityType.METRIC_VOLUME]
                    and e.start == match.start()
                    and e.end == match.end()
                )
                for e in entities
            )
            if not already_exists and not is_inside_entity(match.start(), match.end(), check_entities):
                number_text = match.group(1)
                unit_text = match.group(2).lower()

                # Determine entity type
                # Get units from resources
                length_units = self.resources.get("units", {}).get("length_units", [])
                weight_units = self.resources.get("units", {}).get("weight_units", [])
                volume_units = self.resources.get("units", {}).get("volume_units", [])

                if unit_text in length_units:
                    entity_type = EntityType.METRIC_LENGTH
                elif unit_text in weight_units:
                    entity_type = EntityType.METRIC_WEIGHT
                elif unit_text in volume_units:
                    entity_type = EntityType.METRIC_VOLUME
                else:
                    continue

                entities.append(
                    Entity(
                        start=match.start(),
                        end=match.end(),
                        text=match.group(0),
                        type=entity_type,
                        metadata={"number": number_text, "unit": unit_text},
                    )
                )

    def detect_general_units_with_spacy(
        self, doc, text: str, entities: list[Entity], all_entities: list[Entity] | None = None
    ) -> None:
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
                        if not is_inside_entity(start_pos, end_pos, all_entities or []):
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

    def detect_general_units_with_regex(
        self, text: str, entities: list[Entity], all_entities: list[Entity] | None = None
    ) -> None:
        """Detect general unit patterns using regex for cases where SpaCy might fail."""
        # Build comprehensive pattern for all number words
        number_pattern = r"\b(?:" + "|".join(sorted(self.number_parser.all_number_words, key=len, reverse=True)) + r")"

        # Build unit patterns (excluding currency and measurements which are handled by other detectors)
        all_units = (
            self.resources.get("units", {}).get("percent_units", [])
            + self.resources.get("data_units", {}).get("storage", [])
            + self.resources.get("units", {}).get("frequency_units", [])
            + self.resources.get("units", {}).get("time_units", [])
        )
        unit_pattern = r"(?:" + "|".join(sorted(all_units, key=len, reverse=True)) + r")"

        # Pattern for compound numbers followed by units
        compound_pattern = re.compile(
            number_pattern + r"(?:\s+" + number_pattern + r")*\s+" + unit_pattern + r"\b", re.IGNORECASE
        )

        for match in compound_pattern.finditer(text):
            # Check against both existing entities and entities being built in this detector
            check_entities = (all_entities if all_entities else []) + entities
            if not is_inside_entity(match.start(), match.end(), check_entities):
                # Extract the unit from the match
                match_text = match.group().lower()
                unit = None
                entity_type = None

                # Find which unit was matched
                for test_unit in all_units:
                    if match_text.endswith(" " + test_unit.lower()):
                        unit = test_unit
                        # Determine entity type based on unit
                        data_units = set(self.resources.get("data_units", {}).get("storage", []))
                        time_units = set(self.resources.get("units", {}).get("time_units", []))
                        percent_units = set(self.resources.get("units", {}).get("percent_units", []))
                        frequency_units = set(self.resources.get("units", {}).get("frequency_units", []))

                        if unit in percent_units:
                            entity_type = EntityType.PERCENT
                        elif unit in data_units:
                            entity_type = EntityType.DATA_SIZE
                        elif unit in frequency_units:
                            entity_type = EntityType.FREQUENCY
                        elif unit in time_units:
                            entity_type = EntityType.TIME_DURATION
                        break

                if entity_type and unit:
                    # Extract number part
                    number_text = match_text[: -(len(unit) + 1)]  # Remove unit and space
                    entities.append(
                        Entity(
                            start=match.start(),
                            end=match.end(),
                            text=match.group(),
                            type=entity_type,
                            metadata={"number": number_text, "unit": unit},
                        )
                    )