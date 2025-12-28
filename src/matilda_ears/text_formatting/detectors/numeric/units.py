#!/usr/bin/env python3
"""Unit and measurement detection for numeric entity detection."""

import re
from typing import List, Optional, Tuple
from ...common import Entity, EntityType, NumberParser
from ...utils import is_inside_entity
from ....core.config import setup_logging
from ... import regex_patterns

logger = setup_logging(__name__, log_filename="text_formatting.txt")


class UnitsDetector:
    """Detector for numbers with units, ranges, measurements, and metric units."""

    def __init__(self, nlp=None, number_parser: NumberParser = None, resources: dict = None):
        """Initialize UnitsDetector.

        Args:
            nlp: SpaCy NLP model instance.
            number_parser: NumberParser instance for number word handling.
            resources: Language-specific resources dictionary.

        """
        self.nlp = nlp
        self.number_parser = number_parser
        self.resources = resources or {}

    def _find_unit_match(self, text: str, type_name: str, units_list: List[str]) -> Optional[Tuple[str, str, int]]:
        """Helper to find a matching unit at the start of text.

        Args:
            text: The text to search in (should be remaining text after a number)
            type_name: The unit type name (e.g. 'currency', 'time')
            units_list: List of unit strings to match

        Returns:
            Tuple of (type_name, matched_unit_text, match_length) or None

        """
        # Create a sorted copy to ensure longest matches first without modifying original list
        sorted_units = sorted(units_list, key=len, reverse=True)

        for unit in sorted_units:
            if re.match(rf"{re.escape(unit)}s?\b", text, re.IGNORECASE):
                match_unit = re.search(rf"({re.escape(unit)}s?)\b", text, re.IGNORECASE)
                if match_unit:
                    return (type_name, unit, match_unit.end())
        return None

    def detect_numerical_entities(
        self, text: str, entities: List[Entity], all_entities: Optional[List[Entity]] = None
    ) -> None:
        """Detect numerical entities with units using SpaCy's grammar analysis."""
        # First, handle patterns that don't need SpaCy
        self.detect_numeric_ranges_simple(text, entities, all_entities)
        self.detect_number_unit_patterns(text, entities, all_entities)

        if not self.nlp:
            return

        try:
            doc = self.nlp(text)
        except (AttributeError, ValueError, IndexError) as e:
            logger.warning(f"SpaCy numerical entity detection failed: {e}")
            return

        # Define all unit types in one place
        currency_units = set(self.resources.get("currency", {}).get("units", []))
        percent_units = set(self.resources.get("units", {}).get("percent_units", []))
        data_units = set(self.resources.get("data_units", {}).get("storage", []))
        frequency_units = set(self.resources.get("units", {}).get("frequency_units", []))
        time_units = set(self.resources.get("units", {}).get("time_units", []))

        i = 0
        while i < len(doc):
            token = doc[i]

            # Find a number-like token (includes cardinals, digits, and number words)
            # Check if token overlaps with an existing high-priority entity
            token_start = token.idx
            token_end = token.idx + len(token.text)
            if is_inside_entity(token_start, token_end, all_entities or []):
                i += 1
                continue

            is_a_number = (
                (token.like_num and token.lower_ not in self.resources.get("technical", {}).get("ordinal_words", []))
                or (token.ent_type_ == "CARDINAL")
                or (self.number_parser and token.lower_ in self.number_parser.all_number_words)
            )

            if is_a_number:
                number_tokens = [token]
                j = i + 1
                # Greedily consume all consecutive number-related words
                while j < len(doc) and (
                    doc[j].like_num
                    or (self.number_parser and doc[j].lower_ in self.number_parser.all_number_words)
                    or doc[j].lower_ in {"and", "point", "dot"}
                ):
                    # Check if this token overlaps with existing entities
                    token_start = doc[j].idx
                    token_end = doc[j].idx + len(doc[j].text)
                    if is_inside_entity(token_start, token_end, all_entities or []):
                        # If we hit an entity, stop consuming
                        break

                    if doc[j].lower_ != "and":
                        number_tokens.append(doc[j])
                    j += 1

                # Check if the token BEFORE the number is "approximately" or similar
                # If so, DO NOT include it in the number entity, but be aware
                # Some SpaCy models might include it in the CARDINAL entity, which we want to avoid
                # But here we are building our own entities based on tokens.
                # So if we just consume number tokens, we are safe from "approximately".

                # Now, check the very next token to see if it's a unit
                if j < len(doc):
                    unit_token = doc[j]
                    unit_lemma = unit_token.lemma_.lower()

                    entity_type = None
                    # Determine entity type based on the unit found
                    if unit_lemma in currency_units:
                        # Special handling for "pounds" - check context
                        if unit_token.text.lower() in ["pound", "pounds"]:
                            prefix_context = text[: number_tokens[0].idx].lower()
                            currency_contexts = self.resources.get("context_words", {}).get("currency_contexts", [])
                            weight_contexts = self.resources.get("context_words", {}).get("weight_contexts", [])

                            # If it has clear weight context OR lacks currency context, treat as weight.
                            if any(ctx in prefix_context for ctx in weight_contexts) or not any(
                                ctx in prefix_context for ctx in currency_contexts
                            ):
                                entity_type = EntityType.METRIC_WEIGHT  # Treat as weight, will be converted to 'lbs'
                            else:
                                entity_type = EntityType.CURRENCY  # It has currency context, so it's money
                        else:
                            entity_type = EntityType.CURRENCY
                    elif unit_lemma in percent_units:
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

    def detect_numeric_ranges_simple(
        self, text: str, entities: List[Entity], all_entities: Optional[List[Entity]] = None
    ) -> None:
        """Detect numeric range expressions (ten to twenty, etc.)."""
        for match in regex_patterns.SPOKEN_NUMERIC_RANGE_PATTERN.finditer(text):
            # Check for overlap with existing entities
            if is_inside_entity(match.start(), match.end(), all_entities or []):
                continue

            # Check if this is actually a time expression (e.g., "five to ten" meaning 9:55)
            # We'll skip if it looks like a time context
            if match.start() > 0:
                prefix = text[max(0, match.start() - 20) : match.start()].lower()
                if any(time_word in prefix for time_word in ["quarter", "half", "past", "at"]):
                    continue

            # Check if followed by a unit (e.g., "five to ten percent")
            end_pos = match.end()
            unit_type = None
            unit_text = None

            # Check for units after the range
            remaining_text = text[end_pos:].lstrip()
            if remaining_text:
                # Check for percent
                if remaining_text.lower().startswith("percent"):
                    unit_type = "percent"
                    unit_text = "percent"
                    # Calculate the correct end position: find "percent" start position + length
                    percent_start = text.lower().find("percent", end_pos)
                    if percent_start != -1:
                        end_pos = percent_start + 7  # 7 = len("percent")

                # Check for units using refactored helper
                if not unit_text:
                    unit_match = self._find_unit_match(
                        remaining_text, "currency", self.resources.get("currency", {}).get("units", [])
                    )
                    if unit_match:
                        unit_type, unit_text, unit_len = unit_match
                        spaces_len = len(text[end_pos:]) - len(remaining_text)
                        end_pos = end_pos + spaces_len + unit_len

                if not unit_text:
                    unit_match = self._find_unit_match(
                        remaining_text, "time", self.resources.get("units", {}).get("time_units", [])
                    )
                    if unit_match:
                        unit_type, unit_text, unit_len = unit_match
                        spaces_len = len(text[end_pos:]) - len(remaining_text)
                        end_pos = end_pos + spaces_len + unit_len

                if not unit_text:
                    unit_match = self._find_unit_match(
                        remaining_text, "weight", self.resources.get("units", {}).get("weight_units", [])
                    )
                    if unit_match:
                        unit_type, unit_text, unit_len = unit_match
                        spaces_len = len(text[end_pos:]) - len(remaining_text)
                        end_pos = end_pos + spaces_len + unit_len

                if not unit_text:
                    unit_match = self._find_unit_match(
                        remaining_text, "length", self.resources.get("units", {}).get("length_units", [])
                    )
                    if unit_match:
                        unit_type, unit_text, unit_len = unit_match
                        spaces_len = len(text[end_pos:]) - len(remaining_text)
                        end_pos = end_pos + spaces_len + unit_len

                if not unit_text:
                    unit_match = self._find_unit_match(
                        remaining_text, "volume", self.resources.get("units", {}).get("volume_units", [])
                    )
                    if unit_match:
                        unit_type, unit_text, unit_len = unit_match
                        spaces_len = len(text[end_pos:]) - len(remaining_text)
                        end_pos = end_pos + spaces_len + unit_len

            entities.append(
                Entity(
                    start=match.start(),
                    end=end_pos,
                    text=text[match.start() : end_pos],
                    type=EntityType.NUMERIC_RANGE,
                    metadata={
                        "start_word": match.group(1),
                        "end_word": match.group(2),
                        "unit_type": unit_type,
                        "unit": unit_text,
                    },
                )
            )

    def detect_number_unit_patterns(
        self, text: str, entities: List[Entity], all_entities: Optional[List[Entity]] = None
    ) -> None:
        """Detect number + unit patterns using regex for cases where SpaCy might fail."""
        if not self.number_parser:
            return

        # Build comprehensive pattern for all number words
        number_pattern = r"\b(?:" + "|".join(sorted(self.number_parser.all_number_words, key=len, reverse=True)) + r")"

        # Build unit patterns
        all_units = (
            self.resources.get("currency", {}).get("units", [])
            + self.resources.get("units", {}).get("percent_units", [])
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
                        currency_units = set(self.resources.get("currency", {}).get("units", []))
                        data_units = set(self.resources.get("data_units", {}).get("storage", []))
                        time_units = set(self.resources.get("units", {}).get("time_units", []))
                        percent_units = set(self.resources.get("units", {}).get("percent_units", []))
                        frequency_units = set(self.resources.get("units", {}).get("frequency_units", []))

                        if unit in currency_units:
                            # Special handling for "pounds" - check context
                            if unit.lower() in ["pound", "pounds"]:
                                prefix_context = text[: match.start()].lower()
                                currency_contexts = self.resources.get("context_words", {}).get("currency_contexts", [])
                                weight_contexts = self.resources.get("context_words", {}).get("weight_contexts", [])

                                # If it has clear weight context OR lacks currency context, treat as weight.
                                if any(ctx in prefix_context for ctx in weight_contexts) or not any(
                                    ctx in prefix_context for ctx in currency_contexts
                                ):
                                    entity_type = EntityType.METRIC_WEIGHT
                                else:
                                    entity_type = EntityType.CURRENCY
                            else:
                                entity_type = EntityType.CURRENCY
                        elif unit in percent_units:
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

    def detect_measurements(
        self, text: str, entities: List[Entity], all_entities: Optional[List[Entity]] = None
    ) -> None:
        """Detect measurement patterns that SpaCy might miss or misclassify.

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

    def detect_metric_units(
        self, text: str, entities: List[Entity], all_entities: Optional[List[Entity]] = None
    ) -> None:
        """Detect metric unit expressions.

        Examples:
        - "five kilometers" -> "5 km"
        - "two point five centimeters" -> "2.5 cm"
        - "ten kilograms" -> "10 kg"
        - "three liters" -> "3 L"

        """
        if not self.nlp:
            return
        try:
            doc = self.nlp(text)
        except (AttributeError, ValueError, IndexError) as e:
            logger.warning(f"SpaCy metric unit detection failed: {e}")
            return

        # Use metric units from constants

        # Iterate through tokens
        i = 0
        while i < len(doc):
            token = doc[i]

            # Check if this token is a number
            is_a_number = (
                token.like_num
                or (token.ent_type_ == "CARDINAL")
                or (self.number_parser and token.lower_ in self.number_parser.all_number_words)
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
                        or (self.number_parser and next_token.lower_ in self.number_parser.all_number_words)
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
        if not self.number_parser:
            return

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
