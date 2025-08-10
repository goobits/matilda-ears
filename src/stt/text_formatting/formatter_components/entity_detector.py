#!/usr/bin/env python3
"""
EntityDetector class for detecting various entities using SpaCy and custom patterns.

Extracted from formatter.py for modular architecture.
Refactored to use modular components for better maintainability.
"""
from __future__ import annotations

from ...core.config import setup_logging

# Import common data structures
from ..common import Entity

# Import resource loader for i18n constants
from ..nlp_provider import get_nlp

# Import the modular components
from .spacy_detector import SpacyEntityProcessor
from .validation import EntityValidator

# Setup logging
logger = setup_logging(__name__)


class EntityDetector:
    """Detects various entities using SpaCy and custom patterns"""

    def __init__(self, nlp=None, language: str = "en"):
        """
        Initialize EntityDetector with dependency injection.

        Args:
            nlp: SpaCy NLP model instance. If None, will load from nlp_provider.
            language: Language code for resource loading (default: 'en')

        """
        if nlp is None:
            nlp = get_nlp()

        self.nlp = nlp
        self.language = language
        
        # Initialize modular components
        self.spacy_processor = SpacyEntityProcessor(nlp=nlp, language=language)
        self.validator = EntityValidator(nlp=nlp, language=language)

    def detect_entities(self, text: str, existing_entities: list[Entity], doc=None) -> list[Entity]:
        """Single pass entity detection"""
        entities: list[Entity] = []

        # Only process SpaCy entities in the base detector
        # Pass the existing_entities list for the overlap check
        self._process_spacy_entities(text, entities, existing_entities, doc=doc)

        # Sorting is no longer needed here as the main formatter will sort the final list.
        return entities

    def _process_spacy_entities(
        self, text: str, entities: list[Entity], existing_entities: list[Entity], doc=None
    ) -> None:
        """Process SpaCy-detected entities using the modular processor."""
        # Apply validation filters before processing entities
        if doc is None and self.nlp:
            try:
                doc = self.nlp(text)
            except (AttributeError, ValueError, IndexError) as e:
                logger.warning(f"SpaCy entity detection failed: {e}")
                return

        # Collect entities that should be skipped to avoid double processing
        skipped_entities = set()
        if doc:
            for ent in doc.ents:
                if ent.label_ in ["CARDINAL", "DATE", "TIME", "MONEY", "PERCENT", "QUANTITY", "ORDINAL"]:
                    # Apply validation filters
                    if self._should_skip_entity(ent, text):
                        skipped_entities.add((ent.start_char, ent.end_char, ent.text))

        # Use the modular SpaCy processor for the main processing logic
        self.spacy_processor.process_spacy_entities(text, entities, existing_entities, doc=doc, skip_entities=skipped_entities)

    def _should_skip_entity(self, ent, text: str) -> bool:
        """Determine if an entity should be skipped based on its type and context."""
        if ent.label_ == "CARDINAL":
            return self.validator.should_skip_cardinal(ent, text)
        elif ent.label_ == "QUANTITY":
            return self.validator.should_skip_quantity(ent, text)
        elif ent.label_ == "MONEY":
            return self.validator.should_skip_money(ent, text)
        elif ent.label_ == "DATE":
            return self.validator.should_skip_date(ent, text)
        elif ent.label_ == "PERCENT":
            return self.validator.should_skip_percent(ent, text)
        return False

    # Backward compatibility methods - delegate to validator
    def _should_skip_cardinal(self, ent, text: str) -> bool:
        """Backward compatibility method - delegate to validator."""
        return self.validator.should_skip_cardinal(ent, text)

    def _should_skip_quantity(self, ent, text: str) -> bool:
        """Backward compatibility method - delegate to validator."""
        return self.validator.should_skip_quantity(ent, text)

    def _should_skip_money(self, ent, text: str) -> bool:
        """Backward compatibility method - delegate to validator."""
        return self.validator.should_skip_money(ent, text)

    def _should_skip_date(self, ent, text: str) -> bool:
        """Backward compatibility method - delegate to validator."""
        return self.validator.should_skip_date(ent, text)

    def _should_skip_percent(self, ent, text: str) -> bool:
        """Backward compatibility method - delegate to validator."""
        return self.validator.should_skip_percent(ent, text)

    def _is_contextual_number_word(self, ent, text: str) -> bool:
        """Backward compatibility method - delegate to validator."""
        return self.validator._is_contextual_number_word(ent, text)