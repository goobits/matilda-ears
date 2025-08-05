#!/usr/bin/env python3
"""Numeric, mathematical, and time entity detection and conversion for Matilda transcriptions."""
from __future__ import annotations

from stt.core.config import setup_logging
from stt.text_formatting.common import Entity, NumberParser
from stt.text_formatting.constants import get_resources
from stt.text_formatting.detectors.numeric.basic_numbers import BasicNumberDetector
from stt.text_formatting.detectors.numeric.mathematical import MathematicalExpressionDetector
from stt.text_formatting.detectors.numeric.temporal import TemporalDetector
from stt.text_formatting.detectors.numeric.financial import FinancialDetector
from stt.text_formatting.detectors.numeric.measurements import MeasurementDetector
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
        self.math_detector = MathematicalExpressionDetector(nlp=self.nlp, language=self.language)
        self.temporal_detector = TemporalDetector(nlp=self.nlp, language=self.language)
        self.financial_detector = FinancialDetector(nlp=self.nlp, language=self.language)
        self.measurement_detector = MeasurementDetector(nlp=self.nlp, language=self.language)
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

        # Fallback detection for basic number words when SpaCy is not available
        all_entities = entities + numerical_entities
        self.basic_detector.detect_cardinal_numbers(text, numerical_entities, all_entities)

        all_entities = entities + numerical_entities
        self.math_detector.detect_math_expressions(text, numerical_entities, all_entities)

        # Detect temperatures before time expressions to prevent conflicts
        all_entities = entities + numerical_entities
        self.measurement_detector.detect_temperatures(text, numerical_entities, all_entities)

        all_entities = entities + numerical_entities
        self.temporal_detector.detect_time_expressions(text, numerical_entities, all_entities)

        all_entities = entities + numerical_entities
        self.format_detector.detect_phone_numbers(text, numerical_entities, all_entities)

        all_entities = entities + numerical_entities
        self.basic_detector.detect_ordinal_numbers(text, numerical_entities, all_entities)

        all_entities = entities + numerical_entities
        self.temporal_detector.detect_time_relative(text, numerical_entities, all_entities)

        all_entities = entities + numerical_entities
        self.basic_detector.detect_fractions(text, numerical_entities, all_entities)

        all_entities = entities + numerical_entities
        self.measurement_detector.detect_measurements(text, numerical_entities, all_entities)

        all_entities = entities + numerical_entities
        self.financial_detector.detect_dollar_cents(text, numerical_entities, all_entities)

        all_entities = entities + numerical_entities
        self.financial_detector.detect_cents_only(text, numerical_entities, all_entities)

        all_entities = entities + numerical_entities
        self.measurement_detector.detect_metric_units(text, numerical_entities, all_entities)

        all_entities = entities + numerical_entities
        self.math_detector.detect_root_expressions(text, numerical_entities, all_entities)

        all_entities = entities + numerical_entities
        self.math_detector.detect_mathematical_constants(text, numerical_entities, all_entities)

        all_entities = entities + numerical_entities
        self.math_detector.detect_scientific_notation(text, numerical_entities, all_entities)

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
        self.measurement_detector.detect_general_units_with_regex(text, entities, all_entities)
        self.basic_detector.detect_number_words(text, entities, all_entities)

        if not self.nlp:
            return

        try:
            doc = self.nlp(text)
        except (AttributeError, ValueError, IndexError) as e:
            logger.warning(f"SpaCy numerical entity detection failed: {e}")
            return
        
        # Delegate currency detection to the financial detector
        self.financial_detector.detect_currency_with_spacy(doc, text, entities, all_entities)
        
        # Delegate general unit detection to the measurement detector
        self.measurement_detector.detect_general_units_with_spacy(doc, text, entities, all_entities)
