#!/usr/bin/env python3
"""Numeric, mathematical, time, and financial entity detection and conversion for Matilda transcriptions.

This module serves as the orchestrator for numeric entity detection, delegating to
specialized sub-detectors for different entity types.
"""

from typing import List
from ..common import Entity, NumberParser
from ..constants import get_resources
from ...core.config import setup_logging

# Import sub-detectors
from .numeric import (
    MathDetector,
    TimeDetector,
    PhoneDetector,
    UnitsDetector,
    FractionalDetector,
    SpecialDetector,
)

logger = setup_logging(__name__, log_filename="text_formatting.txt")


class NumericalEntityDetector:
    """Orchestrator for numerical entity detection.

    This class coordinates multiple specialized sub-detectors to identify various
    types of numeric entities in text, including:
    - Math expressions, constants, roots, scientific notation
    - Time expressions and relative time
    - Phone numbers
    - Numbers with units, ranges, measurements, metric units
    - Fractions, versions, decimals, temperatures
    - Ordinals, music notation, emojis
    """

    def __init__(self, nlp=None, language: str = "en"):
        """Initialize NumericalEntityDetector with dependency injection.

        Args:
            nlp: SpaCy NLP model instance. If None, will load from nlp_provider.
            language: Language code for resource loading (default: 'en')

        """
        if nlp is None:
            from ..nlp_provider import get_nlp

            nlp = get_nlp()

        self.nlp = nlp
        self.language = language

        # Load language-specific resources
        self.resources = get_resources(language)

        # Initialize NumberParser for robust number word detection
        self.number_parser = NumberParser(language=self.language)

        # Initialize sub-detectors with shared dependencies
        self.math_detector = MathDetector(
            nlp=self.nlp,
            number_parser=self.number_parser,
            resources=self.resources,
        )
        self.time_detector = TimeDetector(
            nlp=self.nlp,
            resources=self.resources,
        )
        self.phone_detector = PhoneDetector(
            nlp=self.nlp,
            resources=self.resources,
        )
        self.units_detector = UnitsDetector(
            nlp=self.nlp,
            number_parser=self.number_parser,
            resources=self.resources,
        )
        self.fractional_detector = FractionalDetector(
            nlp=self.nlp,
            number_parser=self.number_parser,
            resources=self.resources,
        )
        self.special_detector = SpecialDetector(
            nlp=self.nlp,
            number_parser=self.number_parser,
            resources=self.resources,
            language=self.language,
        )

        # Keep MathExpressionParser accessible for backward compatibility
        self.math_parser = self.math_detector.math_parser

    def detect(self, text: str, entities: List[Entity]) -> List[Entity]:
        """Detects all numerical-related entities.

        Args:
            text: The input text to analyze.
            entities: List of already-detected entities to avoid overlaps.

        Returns:
            List of newly detected numerical entities.

        """
        numerical_entities: list[Entity] = []

        # PRIORITY 1: Complex entities that consume numbers
        # Detect these first to prevent simple numbers from breaking them

        all_entities = entities + numerical_entities
        self.math_detector.detect_scientific_notation(text, numerical_entities, all_entities)

        all_entities = entities + numerical_entities
        self.math_detector.detect_math_expressions(text, numerical_entities, all_entities)

        all_entities = entities + numerical_entities
        self.math_detector.detect_math_constants(text, numerical_entities, all_entities)

        # PRIORITY 2: Specific numeric formats

        all_entities = entities + numerical_entities
        self.fractional_detector.detect_version_numbers(text, numerical_entities, all_entities)

        all_entities = entities + numerical_entities
        self.phone_detector.detect_phone_numbers(text, numerical_entities, all_entities)

        all_entities = entities + numerical_entities
        self.time_detector.detect_time_expressions(text, numerical_entities, all_entities)

        all_entities = entities + numerical_entities
        self.time_detector.detect_time_relative(text, numerical_entities, all_entities)

        all_entities = entities + numerical_entities
        self.fractional_detector.detect_fractions(text, numerical_entities, all_entities)

        all_entities = entities + numerical_entities
        self.fractional_detector.detect_temperatures(text, numerical_entities, all_entities)

        # PRIORITY 3: Measures and Units

        # Detect ranges before simple numbers
        all_entities = entities + numerical_entities
        self.units_detector.detect_numeric_ranges_simple(text, numerical_entities, all_entities)

        all_entities = entities + numerical_entities
        self.units_detector.detect_measurements(text, numerical_entities, all_entities)

        all_entities = entities + numerical_entities
        self.units_detector.detect_metric_units(text, numerical_entities, all_entities)

        all_entities = entities + numerical_entities
        self.units_detector.detect_numerical_entities(text, numerical_entities, all_entities)

        # PRIORITY 4: Fallbacks and simple types

        all_entities = entities + numerical_entities
        self.special_detector.detect_ordinals(text, numerical_entities, all_entities)

        all_entities = entities + numerical_entities
        self.math_detector.detect_root_expressions(text, numerical_entities, all_entities)

        all_entities = entities + numerical_entities
        self.special_detector.detect_music_notation(text, numerical_entities, all_entities)

        all_entities = entities + numerical_entities
        self.special_detector.detect_spoken_emojis(text, numerical_entities, all_entities)

        # Fallback detection for basic number words when SpaCy is not available
        # Or to catch sequences not caught by other detectors
        all_entities = entities + numerical_entities
        self.special_detector.detect_cardinal_numbers_fallback(text, numerical_entities, all_entities)

        return numerical_entities
