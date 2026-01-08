#!/usr/bin/env python3
"""Phone number detection for numeric entity detection."""

from ...common import Entity, EntityType
from ...utils import is_inside_entity
from ....core.config import setup_logging
from ... import regex_patterns

logger = setup_logging(__name__, log_filename="text_formatting.txt")


class PhoneDetector:
    """Detector for phone numbers spoken as individual digits."""

    def __init__(self, nlp=None, resources: dict = None):
        """Initialize PhoneDetector.

        Args:
            nlp: SpaCy NLP model instance.
            resources: Language-specific resources dictionary.

        """
        self.nlp = nlp
        self.resources = resources or {}

    def detect_phone_numbers(self, text: str, entities: list[Entity], all_entities: list[Entity] | None = None) -> None:
        """Detect phone numbers spoken as individual digits."""
        # Use centralized phone pattern
        for match in regex_patterns.SPOKEN_PHONE_PATTERN.finditer(text):
            check_entities = all_entities if all_entities else entities
            if not is_inside_entity(match.start(), match.end(), check_entities):
                entities.append(
                    Entity(start=match.start(), end=match.end(), text=match.group(), type=EntityType.PHONE_LONG)
                )
