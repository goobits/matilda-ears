#!/usr/bin/env python3
"""Basic number detection functionality extracted from numeric_detector.py."""
from __future__ import annotations

import re
from typing import Any

from stt.core.config import setup_logging
from stt.text_formatting import regex_patterns
from stt.text_formatting.common import Entity, EntityType, NumberParser
from stt.text_formatting.constants import get_resources
from stt.text_formatting.utils import is_inside_entity

logger = setup_logging(__name__, log_filename="text_formatting.txt", include_console=False)


class BasicNumberDetector:
    """Handles basic number detection: cardinals, ordinals, fractions, ranges, number words."""
    
    def __init__(self, nlp=None, language: str = "en"):
        """
        Initialize BasicNumberDetector.

        Args:
            nlp: SpaCy NLP model instance. If None, will load from nlp_provider.
            language: Language code for resource loading (default: 'en')
        """
        if nlp is None:
            try:
                from stt.text_formatting.nlp_provider import get_nlp
                nlp = get_nlp()
            except ImportError:
                nlp = None

        self.nlp = nlp
        self.language = language

        # Load language-specific resources
        self.resources = get_resources(language)

        # Initialize NumberParser for robust number word detection
        self.number_parser = NumberParser(language=self.language)

    def detect_cardinal_numbers(self, text: str, entities: list[Entity], all_entities: list[Entity] | None = None) -> None:
        """Fallback detection for cardinal numbers when SpaCy is not available or for non-English languages."""
        # Run this if SpaCy failed to load OR if we're not using English
        # (SpaCy's multilingual support for number recognition is limited)
        if self.nlp and self.language == "en":
            return  # SpaCy is available and we're using English, let it handle CARDINAL detection

        # Build a comprehensive pattern for number words
        number_words = sorted(self.number_parser.all_number_words, key=len, reverse=True)
        number_pattern = "|".join(re.escape(word) for word in number_words)

        # Pattern for sequences of number words
        # Matches: "two thousand five hundred", "twenty three", "four", etc.
        cardinal_pattern = re.compile(
            rf"\b(?:{number_pattern})(?:\s+(?:and\s+)?(?:{number_pattern}))*\b", re.IGNORECASE
        )

        for match in cardinal_pattern.finditer(text):
            check_entities = all_entities if all_entities else entities
            if not is_inside_entity(match.start(), match.end(), check_entities):
                # Try to parse this number sequence
                number_text = match.group(0)
                parsed_number = self.number_parser.parse(number_text)

                # Only create entity if it parses to a valid number
                if parsed_number and parsed_number.isdigit():
                    entities.append(
                        Entity(
                            start=match.start(),
                            end=match.end(),
                            text=number_text,
                            type=EntityType.CARDINAL,
                            metadata={"parsed_value": parsed_number},
                        )
                    )

    def detect_ordinal_numbers(self, text: str, entities: list[Entity], all_entities: list[Entity] | None = None) -> None:
        """Detect ordinal numbers (first, second, third, etc.)."""
        # First, run the SpaCy analysis once if available.
        doc = None
        if self.nlp:
            try:
                doc = self.nlp(text)
            except Exception as e:
                logger.warning(f"SpaCy ordinal analysis failed: {e}")

        for match in regex_patterns.SPOKEN_ORDINAL_PATTERN.finditer(text):
            # If we have a SpaCy doc, use it for grammatical context checking.
            if doc:
                ordinal_token = None
                next_token = None
                for token in doc:
                    if token.idx == match.start():
                        ordinal_token = token
                        if token.i + 1 < len(doc):
                            next_token = doc[token.i + 1]
                        break

                # Check for specific idiomatic contexts
                if ordinal_token and next_token:
                    # Skip if it's an adjective followed by a specific idiomatic noun from our resources.
                    if ordinal_token.pos_ == "ADJ" and next_token.pos_ == "NOUN":
                        # This is the key: we check our i18n file for specific exceptions.
                        idiomatic_phrases = self.resources.get("technical", {}).get("idiomatic_phrases", {})
                        if (
                            ordinal_token.text.lower() in idiomatic_phrases
                            and next_token.text.lower() in idiomatic_phrases[ordinal_token.text.lower()]
                        ):
                            logger.debug(
                                f"Skipping ORDINAL '{match.group()}' due to idiomatic follower noun '{next_token.text}'."
                            )
                            continue

                    # Skip if it's at sentence start and followed by comma ("First, we...")
                    if (ordinal_token.i == 0 or ordinal_token.sent.start == ordinal_token.i) and next_token.text == ",":
                        logger.debug(f"Skipping ORDINAL '{match.group()}' - sentence starter with comma")
                        continue

            # Your existing logic for checking overlaps is good. Keep it.
            check_entities = all_entities if all_entities else entities
            overlaps_high_priority = False
            for existing in check_entities:
                if not (match.end() <= existing.start or match.start() >= existing.end):
                    if existing.type not in [
                        EntityType.CARDINAL,
                        EntityType.DATE,
                        EntityType.QUANTITY,
                    ]:
                        overlaps_high_priority = True
                        break

            if not overlaps_high_priority:
                entities.append(
                    Entity(
                        start=match.start(),
                        end=match.end(),
                        text=match.group(),
                        type=EntityType.ORDINAL,
                        metadata={"ordinal_word": match.group(0)},
                    )
                )

    def detect_fractions(self, text: str, entities: list[Entity], all_entities: list[Entity] | None = None) -> None:
        """Detect fraction expressions (one half, two thirds, etc.) and compound fractions (one and one half)."""
        # First detect compound fractions (they take priority)
        for match in regex_patterns.SPOKEN_COMPOUND_FRACTION_PATTERN.finditer(text):
            check_entities = all_entities if all_entities else entities
            if not is_inside_entity(match.start(), match.end(), check_entities):
                entities.append(
                    Entity(
                        start=match.start(),
                        end=match.end(),
                        text=match.group(),
                        type=EntityType.FRACTION,
                        metadata={
                            "whole_word": match.group(1),
                            "numerator_word": match.group(2),
                            "denominator_word": match.group(3),
                            "is_compound": True,
                        },
                    )
                )

        # Then detect simple fractions
        for match in regex_patterns.SPOKEN_FRACTION_PATTERN.finditer(text):
            check_entities = all_entities if all_entities else entities

            # Check if this overlaps with only low-priority entities (CARDINAL, DATE, QUANTITY)
            overlaps_high_priority = False

            for existing in check_entities:
                if not (match.end() <= existing.start or match.start() >= existing.end):
                    # There is overlap
                    if existing.type in [
                        EntityType.CARDINAL,
                        EntityType.DATE,
                        EntityType.QUANTITY,
                        EntityType.TIME,
                        EntityType.ORDINAL,
                    ]:
                        pass  # overlaps_low_priority = True
                    else:
                        overlaps_high_priority = True
                        break

            # Add fraction if it doesn't overlap with high-priority entities
            if not overlaps_high_priority:
                entities.append(
                    Entity(
                        start=match.start(),
                        end=match.end(),
                        text=match.group(),
                        type=EntityType.FRACTION,
                        metadata={"numerator_word": match.group(1), "denominator_word": match.group(2)},
                    )
                )

    def detect_ranges(self, text: str, entities: list[Entity], all_entities: list[Entity] | None = None) -> None:
        """Detect numeric range expressions (ten to twenty, etc.)."""
        for match in regex_patterns.SPOKEN_NUMERIC_RANGE_PATTERN.finditer(text):
            # Don't check for entity overlap here - let the priority system handle it
            # This allows ranges to be detected even if individual numbers are already detected as CARDINAL

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
                    percent_start = text.find("percent", end_pos)
                    if percent_start != -1:
                        end_pos = percent_start + 7  # 7 = len("percent")

                # Check for currency units
                currency_units = self.resources.get("currency", {}).get("units", [])
                for currency_unit in currency_units:
                    if remaining_text.lower().startswith(currency_unit.lower()):
                        unit_type = "currency"
                        unit_text = currency_unit
                        # Find the actual unit in the text (might be slightly different due to plural)
                        # Look for the unit in the remaining text
                        words = remaining_text.split()
                        if words and words[0].lower().startswith(currency_unit.lower()[:4]):
                            # Use the actual word from the text (handles plural forms)
                            actual_unit = words[0]
                            unit_text = actual_unit
                            unit_start = text.lower().find(actual_unit.lower(), end_pos)
                            if unit_start != -1:
                                end_pos = unit_start + len(actual_unit)
                        else:
                            # Fallback to exact match
                            unit_start = text.lower().find(currency_unit.lower(), end_pos)
                            if unit_start != -1:
                                end_pos = unit_start + len(currency_unit)
                        break

                # Check for other units (time, weight, etc.)
                if not unit_text:
                    # Time units
                    time_units = self.resources.get("units", {}).get("time_units", [])
                    for time_unit in time_units:
                        if remaining_text.lower().startswith(time_unit.lower()):
                            unit_type = "time"
                            unit_text = time_unit
                            unit_start = text.lower().find(time_unit.lower(), end_pos)
                            if unit_start != -1:
                                end_pos = unit_start + len(time_unit)
                            break

                if not unit_text:
                    # Weight units
                    weight_units = self.resources.get("units", {}).get("weight_units", [])
                    for weight_unit in weight_units:
                        if remaining_text.lower().startswith(weight_unit.lower()):
                            unit_type = "weight"
                            unit_text = weight_unit
                            unit_start = text.lower().find(weight_unit.lower(), end_pos)
                            if unit_start != -1:
                                end_pos = unit_start + len(weight_unit)
                            break

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

    def detect_number_words(self, text: str, entities: list[Entity], all_entities: list[Entity] | None = None) -> None:
        """Detect consecutive digit sequences like 'six four four' -> '644'."""
        # Build pattern for single digits (zero through nine)
        single_digits = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine"]
        digit_pattern = "|".join(single_digits)

        # Pattern for consecutive single digits (3 or more for specificity)
        consecutive_pattern = re.compile(
            rf"\b({digit_pattern})\s+({digit_pattern})\s+({digit_pattern})(?:\s+({digit_pattern}))?\b", re.IGNORECASE
        )

        for match in consecutive_pattern.finditer(text):
            check_entities = all_entities if all_entities else entities
            if not is_inside_entity(match.start(), match.end(), check_entities):
                # Extract the digit words and convert to digits
                digit_words = [g for g in match.groups() if g is not None]

                # Convert words to digits
                digit_map = {word: str(i) for i, word in enumerate(single_digits)}
                digits = [digit_map[word.lower()] for word in digit_words]

                entities.append(
                    Entity(
                        start=match.start(),
                        end=match.end(),
                        text=match.group(),
                        type=EntityType.CARDINAL,
                        metadata={"consecutive_digits": digits, "parsed_value": "".join(digits)},
                    )
                )