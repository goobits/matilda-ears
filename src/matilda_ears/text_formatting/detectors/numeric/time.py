#!/usr/bin/env python3
"""Time expression detection for numeric entity detection."""

from typing import List, Optional
from ...common import Entity, EntityType
from ...utils import is_inside_entity
from ....core.config import setup_logging
from ... import regex_patterns

logger = setup_logging(__name__, log_filename="text_formatting.txt")


class TimeDetector:
    """Detector for time expressions and relative time."""

    def __init__(self, nlp=None, resources: dict = None):
        """Initialize TimeDetector.

        Args:
            nlp: SpaCy NLP model instance.
            resources: Language-specific resources dictionary.
        """
        self.nlp = nlp
        self.resources = resources or {}

    def detect_time_expressions(
        self, text: str, entities: List[Entity], all_entities: Optional[List[Entity]] = None
    ) -> None:
        """Detect time expressions in spoken form."""
        # Use centralized time expression patterns
        time_patterns = [
            (regex_patterns.TIME_EXPRESSION_PATTERNS[0], EntityType.TIME_CONTEXT),
            (regex_patterns.TIME_EXPRESSION_PATTERNS[1], EntityType.TIME_AMPM),
            (regex_patterns.TIME_EXPRESSION_PATTERNS[2], EntityType.TIME_AMPM),  # Spoken "a m"/"p m"
            (regex_patterns.TIME_EXPRESSION_PATTERNS[3], EntityType.TIME_AMPM),  # "at three PM"
            (regex_patterns.TIME_EXPRESSION_PATTERNS[4], EntityType.TIME_AMPM),  # "three PM"
        ]

        # Units that indicate this is NOT a time expression
        non_time_units = {
            "gigahertz",
            "megahertz",
            "kilohertz",
            "hertz",
            "ghz",
            "mhz",
            "khz",
            "hz",
            "gigabytes",
            "megabytes",
            "kilobytes",
            "bytes",
            "gb",
            "mb",
            "kb",
            "milliseconds",
            "microseconds",
            "nanoseconds",
            "ms",
            "us",
            "ns",
            "meters",
            "kilometers",
            "miles",
            "feet",
            "inches",
            "volts",
            "watts",
            "amps",
            "ohms",
        }

        for pattern, etype in time_patterns:
            for match in pattern.finditer(text):
                # Check if this is followed by a unit that indicates it's not a time
                match_end = match.end()
                following_text = text[match_end : match_end + 20].lower().strip()

                # Skip if followed by a non-time unit
                if any(following_text.startswith(unit) for unit in non_time_units):
                    logger.debug(f"Skipping time pattern '{match.group()}' - followed by non-time unit")
                    continue

                check_entities = all_entities if all_entities else entities
                if not is_inside_entity(match.start(), match.end(), check_entities):
                    entities.append(
                        Entity(
                            start=match.start(),
                            end=match.end(),
                            text=match.group(),
                            type=etype,
                            metadata={"groups": match.groups()},
                        )
                    )

    def detect_time_relative(
        self, text: str, entities: List[Entity], all_entities: Optional[List[Entity]] = None
    ) -> None:
        """Detect relative time expressions (quarter past three, half past two, etc.)."""
        for match in regex_patterns.SPOKEN_TIME_RELATIVE_PATTERN.finditer(text):
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

            # Add relative time if it doesn't overlap with high-priority entities
            if not overlaps_high_priority:
                entities.append(
                    Entity(
                        start=match.start(),
                        end=match.end(),
                        text=match.group(),
                        type=EntityType.TIME_RELATIVE,
                        metadata={"relative_expr": match.group(1), "hour_word": match.group(2)},
                    )
                )
