#!/usr/bin/env python3
"""Fraction, version, and temperature detection for numeric entity detection."""

import re
from ....common import Entity, EntityType, NumberParser
from ....utils import is_inside_entity
from .....core.config import setup_logging
from .... import regex_patterns

logger = setup_logging(__name__, log_filename="text_formatting.txt")


class FractionalDetector:
    """Detector for fractions, versions, decimals, and temperatures."""

    def __init__(self, nlp=None, number_parser: NumberParser = None, resources: dict = None):
        """Initialize FractionalDetector.

        Args:
            nlp: SpaCy NLP model instance.
            number_parser: NumberParser instance for number word handling.
            resources: Language-specific resources dictionary.

        """
        self.nlp = nlp
        self.number_parser = number_parser
        self.resources = resources or {}

    def detect_fractions(self, text: str, entities: list[Entity], all_entities: list[Entity] | None = None) -> None:
        """Detect fraction expressions (one half, two thirds, etc.)."""
        # First, detect mixed fractions ("one and one half")
        for match in regex_patterns.SPOKEN_MIXED_FRACTION_PATTERN.finditer(text):
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
                            "is_mixed": True,
                        },
                    )
                )

        # Then, detect regular fractions
        for match in regex_patterns.SPOKEN_FRACTION_PATTERN.finditer(text):
            check_entities = all_entities if all_entities else entities

            # Check if this overlaps with any existing entities
            # We want mixed fractions (detected above) to take precedence
            # Also skip if overlaps with high priority entities
            if is_inside_entity(match.start(), match.end(), check_entities):
                continue

            # Add fraction
            entities.append(
                Entity(
                    start=match.start(),
                    end=match.end(),
                    text=match.group(),
                    type=EntityType.FRACTION,
                    metadata={"numerator_word": match.group(1), "denominator_word": match.group(2)},
                )
            )

    def detect_version_numbers(
        self, text: str, entities: list[Entity], all_entities: list[Entity] | None = None
    ) -> None:
        """Detect version numbers in spoken form (e.g., 'version two point five')."""
        if not self.number_parser:
            return

        # Skip if text already contains properly formatted version numbers (e.g., "2.0.1")
        if re.search(r"\b\d+\.\d+(?:\.\d+)*\b", text):
            # Don't process - leave as is
            return

        # Pattern for version numbers with "version" prefix
        version_pattern = re.compile(
            r"\b(?:v|V|version|Version|python|Python|java|Java|node|Node|ruby|Ruby|php|PHP|go|Go|rust|Rust|dotnet|DotNet|gcc|GCC)\s+"
            r"(" + "|".join(self.number_parser.all_number_words) + r")"
            r"(?:\s+(?:point|dot)\s+"
            r"(" + "|".join(self.number_parser.all_number_words) + r"))?"
            r"(?:\s+(?:point|dot)\s+"
            r"(" + "|".join(self.number_parser.all_number_words) + r"))?"
            r"(?:\s+(?:percent|percentage))?"
            r"\b",
            re.IGNORECASE,
        )

        for match in version_pattern.finditer(text):
            check_entities = all_entities if all_entities else entities
            if not is_inside_entity(match.start(), match.end(), check_entities):
                # Extract the components
                full_match = match.group(0)
                groups = match.groups()

                # Check if this is a percentage (e.g., "rate is zero point five percent")
                is_percentage = "percent" in full_match.lower()

                entity_type = EntityType.PERCENT if is_percentage else EntityType.VERSION

                entities.append(
                    Entity(
                        start=match.start(),
                        end=match.end(),
                        text=full_match,
                        type=entity_type,
                        metadata={"groups": groups, "is_percentage": is_percentage},
                    )
                )

        # Also detect standalone decimal numbers that might be versions or percentages
        # Pattern for spoken decimal numbers like "three point one four"
        decimal_pattern = re.compile(
            r"\b(" + "|".join(self.number_parser.all_number_words) + r"|\d+)"
            r"\s+(?:point|dot)\s+"
            r"((?:"
            + "|".join(self.number_parser.all_number_words)
            + r"|\d+)(?:\s+(?:"
            + "|".join(self.number_parser.all_number_words)
            + r"|\d+))*)"
            r"(?:\s+(?:percent|percentage))?"
            r"\b",
            re.IGNORECASE,
        )

        for match in decimal_pattern.finditer(text):
            check_entities = all_entities if all_entities else entities
            if not is_inside_entity(match.start(), match.end(), check_entities):
                # Check context to determine if this is likely a version number
                prefix_context = text[max(0, match.start() - 20) : match.start()].lower()

                # Skip if already captured by version pattern
                if any(
                    word in prefix_context
                    for word in ["version", "python", "java", "node", "ruby", "php", "go", "rust", "dotnet", "gcc"]
                ):
                    continue

                # This is a standalone decimal, check if it's a percentage
                full_match = match.group(0)
                is_percentage = "percent" in full_match.lower()

                if is_percentage:
                    entities.append(
                        Entity(
                            start=match.start(),
                            end=match.end(),
                            text=full_match,
                            type=EntityType.PERCENT,
                            metadata={"groups": match.groups(), "is_percentage": True},
                        )
                    )
                else:
                    # Create a FRACTION entity for decimal numbers
                    entities.append(
                        Entity(
                            start=match.start(),
                            end=match.end(),
                            text=full_match,
                            type=EntityType.FRACTION,
                            metadata={"groups": match.groups(), "is_decimal": True},
                        )
                    )

    def detect_temperatures(self, text: str, entities: list[Entity], all_entities: list[Entity] | None = None) -> None:
        """Detect temperature expressions.

        Examples:
        - "twenty degrees celsius" -> "20C"
        - "thirty two degrees fahrenheit" -> "32F"
        - "minus ten degrees" -> "-10 degrees"
        - "negative five celsius" -> "-5C"

        """
        if not self.number_parser:
            return

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
