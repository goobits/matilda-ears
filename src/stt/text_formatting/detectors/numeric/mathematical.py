#!/usr/bin/env python3
"""Mathematical expression detection and conversion for Matilda transcriptions.

This module contains specialized detectors for mathematical expressions, constants,
scientific notation, and root expressions extracted from the main numeric detector.
"""
from __future__ import annotations

import re
from typing import Any

from stt.core.config import setup_logging
from stt.text_formatting import regex_patterns
from stt.text_formatting.common import Entity, EntityType, NumberParser
from stt.text_formatting.utils import is_inside_entity
from stt.text_formatting.spacy_doc_cache import get_global_doc_processor
from stt.text_formatting.detectors.numeric.base import MathExpressionParser, is_idiomatic_over_expression
from stt.text_formatting.pattern_modules.basic_numeric_patterns import build_ordinal_pattern
from stt.text_formatting.constants import get_nested_resource

logger = setup_logging(__name__)


class MathematicalExpressionDetector:
    """Detector for mathematical expressions, constants, and scientific notation."""
    
    def __init__(self, nlp=None, language: str = "en"):
        """
        Initialize MathematicalExpressionDetector.

        Args:
            nlp: SpaCy NLP model instance. If None, will load from nlp_provider.
            language: Language code for resource loading (default: 'en')
        """
        if nlp is None:
            from stt.text_formatting.nlp_provider import get_nlp
            nlp = get_nlp()

        self.nlp = nlp
        self.language = language
        self.math_parser = MathExpressionParser(language=self.language)
        self.number_parser = NumberParser(language=self.language)
        
        # Cache for mathematical constants pattern
        self._constants_pattern = None

    def _get_math_constants_pattern(self) -> re.Pattern[str]:
        """Get mathematical constants pattern from resources with fallback."""
        if self._constants_pattern is not None:
            return self._constants_pattern
        
        try:
            constants_dict = get_nested_resource(self.language, "spoken_keywords", "mathematical", "constants")
            constants_list = list(constants_dict.keys())
            pattern_str = r"\b(" + "|".join(re.escape(c) for c in constants_list) + r")\b"
            self._constants_pattern = re.compile(pattern_str, re.IGNORECASE)
        except (KeyError, ValueError) as e:
            logger.debug(f"Failed to load math constants from resources for {self.language}: {e}")
            # Fallback to hardcoded pattern
            self._constants_pattern = re.compile(r"\b(pi|infinity|inf)\b", re.IGNORECASE)
        
        return self._constants_pattern

    def _get_ordinal_pattern_string(self) -> str:
        """Get ordinal pattern string for regex building (fallback pattern)."""
        # For regex building purposes, we need to fall back to a pattern string
        # The actual spaCy-based detection happens elsewhere in the pipeline
        return (
            r"twenty\s+first|twenty\s+second|twenty\s+third|twenty\s+fourth|twenty\s+fifth|"
            r"twenty\s+sixth|twenty\s+seventh|twenty\s+eighth|twenty\s+ninth|"
            r"thirty\s+first|thirty\s+second|thirty\s+third|thirty\s+fourth|thirty\s+fifth|"
            r"thirty\s+sixth|thirty\s+seventh|thirty\s+eighth|thirty\s+ninth|"
            r"first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth|"
            r"eleventh|twelfth|thirteenth|fourteenth|fifteenth|sixteenth|seventeenth|eighteenth|nineteenth|twentieth|"
            r"thirtieth|fortieth|fiftieth|sixtieth|seventieth|eightieth|ninetieth|hundredth"
        )

    def detect_math_expressions(
        self, text: str, entities: list[Entity], all_entities: list[Entity] | None = None
    ) -> None:
        """Detect and parse math expressions using SpaCy context analysis."""
        # Look for patterns that might be math expressions to avoid parsing every word
        # Match simple and complex math expressions, including optional trailing punctuation
        potential_math_matches = []

        # Use centralized complex math expression pattern
        for match in regex_patterns.COMPLEX_MATH_EXPRESSION_PATTERN.finditer(text):
            # Skip if this would conflict with increment/decrement operators already detected
            check_entities = all_entities if all_entities else entities
            if not is_inside_entity(match.start(), match.end(), check_entities):
                potential_math_matches.append((match.group(), match.start(), match.end()))

        # Use centralized simple math expression pattern
        for match in regex_patterns.SIMPLE_MATH_EXPRESSION_PATTERN.finditer(text):
            potential_math_matches.append((match.group(), match.start(), match.end()))

        # Use number + constant pattern (e.g., "two pi") - handle as special case
        for match in regex_patterns.NUMBER_CONSTANT_PATTERN.finditer(text):
            check_entities = all_entities if all_entities else entities
            if not is_inside_entity(match.start(), match.end(), check_entities):
                # These are valid math expressions that don't need pyparsing validation
                # Handle directly as implicit multiplication
                entities.append(
                    Entity(
                        start=match.start(),
                        end=match.end(),
                        text=match.group(),
                        type=EntityType.MATH_EXPRESSION,
                        metadata={"parsed": match.group().split(), "type": "NUMBER_CONSTANT"},
                    )
                )

        for potential_expr, start_pos, end_pos in potential_math_matches:
            # Skip if this looks like an increment/decrement operator
            if re.match(r"^\w+\s+plus\s+plus[.!?]?$", potential_expr, re.IGNORECASE) or re.match(
                r"^\w+\s+minus\s+minus[.!?]?$", potential_expr, re.IGNORECASE
            ):
                continue

            # Test if this is a valid math expression (pyparsing will handle the actual math part)
            clean_expr = potential_expr.rstrip(".!?")  # Remove punctuation for parsing

            # Pre-process number words and operators for better math parser compatibility
            words = clean_expr.split()
            converted_words = []
            for word in words:
                # Try to parse word as a number first
                parsed = self.number_parser.parse(word)
                if parsed:
                    converted_words.append(parsed)
                # Convert spoken operators to symbols
                elif word.lower() == "slash":
                    converted_words.append("/")
                elif word.lower() == "times":
                    converted_words.append("×")
                elif word.lower() == "plus":
                    converted_words.append("+")
                elif word.lower() == "minus":
                    converted_words.append("-")
                elif word.lower() in ["divided", "by"] and " ".join(words).lower().find("divided by") != -1:
                    # Handle "divided by" as a unit
                    if word.lower() == "divided":
                        converted_words.append("÷")
                    # Skip "by" when it follows "divided"
                elif word.lower() == "by" and len(converted_words) > 0 and converted_words[-1] == "÷":
                    continue  # Skip "by" in "divided by"
                else:
                    converted_words.append(word)
            preprocessed_expr = " ".join(converted_words)

            math_result = self.math_parser.parse_expression(preprocessed_expr)
            if math_result:
                # Context filter: Skip if "over" is used idiomatically (not mathematically)
                if is_idiomatic_over_expression(clean_expr, text, start_pos):
                    continue

                # Use the new SpaCy-based idiomatic check for "plus" and "times"
                if self._is_idiomatic_expression_spacy(clean_expr, text, start_pos, end_pos):
                    continue

                check_entities = all_entities if all_entities else entities
                if not is_inside_entity(start_pos, end_pos, check_entities):
                    entities.append(
                        Entity(
                            start=start_pos,
                            end=end_pos,
                            text=potential_expr,  # Include the punctuation in the entity
                            type=EntityType.MATH_EXPRESSION,
                            metadata=math_result,
                        )
                    )

    def _is_idiomatic_expression_spacy(self, expr: str, full_text: str, start_pos: int, end_pos: int) -> bool:
        """
        Use SpaCy POS tagging to determine if an expression is mathematical or idiomatic.

        This method uses grammatical analysis instead of hardcoded word lists to detect
        when 'plus' is used idiomatically (e.g., 'two plus years') rather than mathematically.
        It checks if 'plus' is preceded by a number and followed by a noun, which indicates
        idiomatic usage like 'five plus years of experience'.

        Args:
            expr: The expression text to analyze
            full_text: Complete text for context analysis
            start_pos: Start position of expression in full text
            end_pos: End position of expression in full text

        Returns:
            True if the expression is idiomatic (should not be converted to math)

        """
        # Use centralized document processor for better caching
        doc_processor = get_global_doc_processor()
        if not doc_processor:
            # No fallback needed - if SpaCy unavailable, assume mathematical
            return False
            
        doc = doc_processor.get_or_create_doc(full_text)
        if not doc:
            logger.warning("SpaCy idiomatic expression detection failed")
            return False

        try:

            # Find tokens corresponding to our expression
            expr_tokens = []
            for token in doc:
                # Check if token overlaps with our expression
                if token.idx >= start_pos and token.idx + len(token.text) <= end_pos:
                    expr_tokens.append(token)

            if not expr_tokens:
                return False

            # New logic: Check the POS tag of the word after "plus" or "times"
            for token in expr_tokens:
                if token.text.lower() in ["plus", "times"]:
                    # Check if token is preceded by a number
                    prev_token = doc[token.i - 1] if token.i > 0 else None
                    is_preceded_by_num = prev_token and prev_token.like_num

                    # Check if token is followed by a noun
                    next_token = doc[token.i + 1] if token.i < len(doc) - 1 else None
                    is_followed_by_noun = next_token and next_token.pos_ == "NOUN"

                    # Check if followed by comparative adjective/adverb (e.g., "better", "worse")
                    is_followed_by_comparative = (
                        next_token
                        and (next_token.pos_ in ["ADJ", "ADV"])
                        and next_token.tag_ in ["JJR", "RBR"]  # Comparative forms
                    )

                    if is_preceded_by_num and (is_followed_by_noun or is_followed_by_comparative):
                        logger.debug(
                            f"Skipping math for '{expr}' because '{token.text.lower()}' is followed by "
                            f"{'noun' if is_followed_by_noun else 'comparative'}: '{next_token.text if next_token else 'N/A'}'"
                        )
                        return True  # It's an idiomatic phrase, not math.

            # If the loop completes without finding an idiomatic pattern, it's likely mathematical.
            return False

        except (AttributeError, IndexError, ValueError):
            # SpaCy analysis failed, assume mathematical
            return False

    def detect_root_expressions(
        self, text: str, entities: list[Entity], all_entities: list[Entity] | None = None
    ) -> None:
        """
        Detect square root and cube root expressions.

        Examples:
        - "square root of sixteen" → "√16"
        - "cube root of twenty seven" → "∛27"
        - "square root of x plus one" → "√(x + 1)"

        """
        # Pattern for root expressions
        root_pattern = re.compile(r"\b(square|cube)\s+root\s+of\s+([\w\s+\-*/]+)\b", re.IGNORECASE)

        for match in root_pattern.finditer(text):
            check_entities = all_entities if all_entities else entities
            if not is_inside_entity(match.start(), match.end(), check_entities):
                root_type = match.group(1).lower()
                expression = match.group(2).strip()

                entities.append(
                    Entity(
                        start=match.start(),
                        end=match.end(),
                        text=match.group(0),
                        type=EntityType.ROOT_EXPRESSION,
                        metadata={"root_type": root_type, "expression": expression},
                    )
                )

    def detect_mathematical_constants(
        self, text: str, entities: list[Entity], all_entities: list[Entity] | None = None
    ) -> None:
        """
        Detect mathematical constants.

        Examples:
        - "pi" → "π"
        - "e" → "e" (Euler's number)
        - "infinity" → "∞"

        """
        # Pattern for math constants from resources
        constants_pattern = self._get_math_constants_pattern()

        for match in constants_pattern.finditer(text):
            check_entities = all_entities if all_entities else entities
            if not is_inside_entity(match.start(), match.end(), check_entities):
                constant = match.group(1).lower()

                entities.append(
                    Entity(
                        start=match.start(),
                        end=match.end(),
                        text=match.group(0),
                        type=EntityType.MATH_CONSTANT,
                        metadata={"constant": constant},
                    )
                )

    def detect_scientific_notation(
        self, text: str, entities: list[Entity], all_entities: list[Entity] | None = None
    ) -> None:
        """
        Detect scientific notation expressions.

        Examples:
        - "two point five times ten to the sixth" → "2.5 × 10⁶"
        - "three times ten to the negative four" → "3 × 10⁻⁴"
        - "six point zero two times ten to the twenty third" → "6.02 × 10²³"

        """
        # Pattern for scientific notation: number times ten to the power
        # Support for "to the", "to the power of", etc.
        # Use more specific pattern to avoid greedy matching
        number_pattern = r"(?:" + "|".join(sorted(self.number_parser.all_number_words, key=len, reverse=True)) + r")"

        # Pattern matches: [number with optional decimal] times ten to the [ordinal/number]
        # More flexible pattern that accepts both ordinals and regular numbers for exponents
        # Uses fallback pattern string for regex building (actual spaCy detection happens in pipeline)
        ordinal_pattern = self._get_ordinal_pattern_string()

        sci_pattern = re.compile(
            r"\b("
            + number_pattern
            + r"(?:\s+point\s+(?:"
            + number_pattern
            + r"|\d+)(?:\s+(?:"
            + number_pattern
            + r"|\d+))*)*|\d+(?:\.\d+)?)"
            r"\s+times\s+ten\s+to\s+the\s+"
            r"((?:negative\s+|minus\s+)?(?:"
            + ordinal_pattern
            + r"|"
            + number_pattern
            + r")(?:\s+(?:"
            + number_pattern
            + r"))*)",
            re.IGNORECASE,
        )

        for match in sci_pattern.finditer(text):
            check_entities = all_entities if all_entities else entities
            if not is_inside_entity(match.start(), match.end(), check_entities):
                base_number = match.group(1).strip()
                exponent = match.group(2).strip()

                entities.append(
                    Entity(
                        start=match.start(),
                        end=match.end(),
                        text=match.group(0),
                        type=EntityType.SCIENTIFIC_NOTATION,
                        metadata={"base": base_number, "exponent": exponent},
                    )
                )

    def detect_negative_numbers(
        self, text: str, entities: list[Entity], all_entities: list[Entity] | None = None
    ) -> None:
        """
        Detect negative number expressions.

        Examples:
        - "negative five" → "-5"
        - "minus ten" → "-10"

        """
        # Pattern for negative numbers
        number_pattern = r"(?:" + "|".join(sorted(self.number_parser.all_number_words, key=len, reverse=True)) + r")"
        
        negative_pattern = re.compile(
            r"\b(negative|minus)\s+(" + number_pattern + r")\b",
            re.IGNORECASE
        )

        for match in negative_pattern.finditer(text):
            check_entities = all_entities if all_entities else entities
            if not is_inside_entity(match.start(), match.end(), check_entities):
                sign = match.group(1).lower()
                number_text = match.group(2)

                entities.append(
                    Entity(
                        start=match.start(),
                        end=match.end(),
                        text=match.group(0),
                        type=EntityType.MATH_EXPRESSION,
                        metadata={"sign": sign, "number": number_text},
                    )
                )

    def detect_roots_and_powers(
        self, text: str, entities: list[Entity], all_entities: list[Entity] | None = None
    ) -> None:
        """
        Detect expressions involving roots and powers.

        Examples:
        - "x squared" → "x²"
        - "five cubed" → "5³"
        - "two to the fourth power" → "2⁴"

        """
        # Pattern for power expressions
        number_pattern = r"(?:" + "|".join(sorted(self.number_parser.all_number_words, key=len, reverse=True)) + r")"
        
        # Simple power expressions like "x squared", "five cubed"
        simple_power_pattern = re.compile(
            r"\b(" + number_pattern + r"|[a-zA-Z]+)\s+(squared|cubed)\b",
            re.IGNORECASE
        )

        # Complex power expressions like "two to the fourth power"
        complex_power_pattern = re.compile(
            r"\b(" + number_pattern + r"|[a-zA-Z]+)\s+to\s+the\s+(" + number_pattern + r")\s+power\b",
            re.IGNORECASE
        )

        for pattern in [simple_power_pattern, complex_power_pattern]:
            for match in pattern.finditer(text):
                check_entities = all_entities if all_entities else entities
                if not is_inside_entity(match.start(), match.end(), check_entities):
                    base = match.group(1)
                    if pattern == simple_power_pattern:
                        power_word = match.group(2).lower()
                        power = "2" if power_word == "squared" else "3"
                    else:
                        power = match.group(2)

                    entities.append(
                        Entity(
                            start=match.start(),
                            end=match.end(),
                            text=match.group(0),
                            type=EntityType.MATH_EXPRESSION,
                            metadata={"base": base, "power": power},
                        )
                    )

    def detect_all_mathematical(
        self, text: str, entities: list[Entity], all_entities: list[Entity] | None = None
    ) -> None:
        """Detect all types of mathematical expressions."""
        self.detect_math_expressions(text, entities, all_entities)
        
        all_entities = (all_entities or []) + entities
        self.detect_root_expressions(text, entities, all_entities)
        
        all_entities = (all_entities or []) + entities
        self.detect_mathematical_constants(text, entities, all_entities)
        
        all_entities = (all_entities or []) + entities
        self.detect_scientific_notation(text, entities, all_entities)
        
        all_entities = (all_entities or []) + entities
        self.detect_negative_numbers(text, entities, all_entities)
        
        all_entities = (all_entities or []) + entities
        self.detect_roots_and_powers(text, entities, all_entities)