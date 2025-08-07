#!/usr/bin/env python3
"""Numeric, mathematical, and time entity detection and conversion for Matilda transcriptions."""
from __future__ import annotations

from stt.core.config import setup_logging
from stt.text_formatting.common import Entity, NumberParser
from stt.text_formatting.constants import get_resources
from stt.text_formatting.detectors.numeric.basic_numbers import BasicNumberDetector
from stt.text_formatting.processors.mathematical_processor import MathematicalProcessor
from stt.text_formatting.detectors.numeric.temporal import TemporalDetector
from stt.text_formatting.detectors.numeric.financial import FinancialDetector
from stt.text_formatting.processors.measurement_processor import MeasurementProcessor
from stt.text_formatting.detectors.numeric.formats import FormatDetector

logger = setup_logging(__name__, log_filename="text_formatting.txt", include_console=False)


class NumericalEntityDetector:
    def __init__(self, nlp=None, language: str = "en"):
        """
        Initialize NumericalEntityDetector with dependency injection.

        Args:
            nlp: SpaCy NLP model instance. If None, will load from nlp_provider.
            language: Language code for resource loading (default: 'en')
        """
        if nlp is None:
            from stt.text_formatting.nlp_provider import get_nlp
            nlp = get_nlp()

        self.nlp = nlp
        self.language = language

        # Initialize all sub-detectors
        self.basic_detector = BasicNumberDetector(nlp=self.nlp, language=self.language)
        self.math_processor = MathematicalProcessor(nlp=self.nlp, language=self.language)
        self.temporal_detector = TemporalDetector(nlp=self.nlp, language=self.language)
        self.financial_detector = FinancialDetector(nlp=self.nlp, language=self.language)
        self.measurement_processor = MeasurementProcessor(nlp=self.nlp, language=self.language)
        self.format_detector = FormatDetector(language=self.language)

    def detect(self, text: str, entities: list[Entity]) -> list[Entity]:
        """Detects all numerical-related entities."""
        numerical_entities: list[Entity] = []

        # Detect version numbers and percentages first (before SpaCy processes them)
        all_entities = entities + numerical_entities
        self.format_detector.detect_version_numbers(text, numerical_entities, all_entities)

        # Pass all existing entities for overlap checking
        all_entities = entities + numerical_entities
        self._detect_numerical_entities(text, numerical_entities, all_entities)

        # Detect ordinal numbers early to prevent conflicts with time durations
        # (e.g., "thirty second" should be ordinal "32nd", not time duration "30s")
        all_entities = entities + numerical_entities
        self.basic_detector.detect_ordinal_numbers(text, numerical_entities, all_entities)

        # Fallback detection for basic number words when SpaCy is not available
        all_entities = entities + numerical_entities
        self.basic_detector.detect_cardinal_numbers(text, numerical_entities, all_entities)

        all_entities = entities + numerical_entities
        self.math_processor.detect_entities(text, numerical_entities, all_entities)

        # Detect temperatures before time expressions to prevent conflicts
        all_entities = entities + numerical_entities
        self.measurement_processor.detect_entities(text, numerical_entities, all_entities)

        all_entities = entities + numerical_entities
        self.temporal_detector.detect_time_expressions(text, numerical_entities, all_entities)

        all_entities = entities + numerical_entities
        self.format_detector.detect_phone_numbers(text, numerical_entities, all_entities)

        # Detect time durations after ordinals to prevent conflicts
        all_entities = entities + numerical_entities
        self.basic_detector.detect_time_durations(text, numerical_entities, all_entities)

        all_entities = entities + numerical_entities
        self.temporal_detector.detect_time_relative(text, numerical_entities, all_entities)

        all_entities = entities + numerical_entities
        self.basic_detector.detect_fractions(text, numerical_entities, all_entities)

        all_entities = entities + numerical_entities
        self.financial_detector.detect_dollar_cents(text, numerical_entities, all_entities)

        all_entities = entities + numerical_entities
        self.financial_detector.detect_cents_only(text, numerical_entities, all_entities)

        all_entities = entities + numerical_entities
        # Root expressions now handled by math processor

        all_entities = entities + numerical_entities
        # Mathematical constants now handled by math processor

        all_entities = entities + numerical_entities
        # Scientific notation now handled by math processor

        all_entities = entities + numerical_entities
        self.format_detector.detect_music_notation(text, numerical_entities, all_entities)

        all_entities = entities + numerical_entities
        self.format_detector.detect_spoken_emojis(text, numerical_entities, all_entities)

        return numerical_entities


    def _detect_numerical_entities(
        self, text: str, entities: list[Entity], all_entities: list[Entity] | None = None
    ) -> None:
        """Detect numerical entities with units using SpaCy's grammar analysis."""
        # First, handle patterns that don't need SpaCy
        self.basic_detector.detect_ranges(text, entities, all_entities)
        # Regex-based detection is handled by the measurement processor
        # self.measurement_processor.detect_general_units_with_regex(text, entities, all_entities)
        
        # Run currency detection BEFORE basic number detection to prevent conflicts
        # This ensures "ten dollars" is detected as currency before "ten" is detected as cardinal
        all_entities_current = entities + (all_entities if all_entities else [])
        self.financial_detector.detect_currency_with_regex(text, entities, all_entities_current)

        # Now run basic number detection - this should skip areas already covered by currency
        self.basic_detector.detect_number_words(text, entities, all_entities)

        if not self.nlp:
            return

        try:
            doc = self.nlp(text)
        except (AttributeError, ValueError, IndexError) as e:
            logger.warning(f"SpaCy numerical entity detection failed: {e}")
            return
        
        # Delegate SpaCy-based currency detection to the financial detector
        self.financial_detector.detect_currency_with_spacy(doc, text, entities, all_entities)
        
        # SpaCy-based detection is handled by the measurement processor
        # self.measurement_processor.detect_general_units_with_spacy(doc, text, entities, all_entities)
