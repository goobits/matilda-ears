#!/usr/bin/env python3
"""Numeric, mathematical, time, and financial entity detection and conversion for Matilda transcriptions."""

import re
from typing import List, Optional, Dict, Any
from ..common import Entity, EntityType, NumberParser
from ..utils import is_inside_entity
from ...core.config import setup_logging
from .. import regex_patterns
from ..constants import get_resources

logger = setup_logging(__name__, log_filename="text_formatting.txt")

# Constants imported from constants.py


# Math expression parsing
try:
    from pyparsing import (
        Word,
        nums,
        alphas,
        alphanums,
        Optional as OptionalPP,
        oneOf,
        ParseException,
        infixNotation,
        opAssoc,
    )

    PYPARSING_AVAILABLE = True
except ImportError:
    PYPARSING_AVAILABLE = False


class MathExpressionParser:
    """Robust math expression parser using pyparsing"""

    def __init__(self):
        if not PYPARSING_AVAILABLE:
            raise ImportError("pyparsing is required but not available")

        try:
            # Define number words (comprehensive list)
            number_words = oneOf(
                [
                    "zero",
                    "one",
                    "two",
                    "three",
                    "four",
                    "five",
                    "six",
                    "seven",
                    "eight",
                    "nine",
                    "ten",
                    "eleven",
                    "twelve",
                    "thirteen",
                    "fourteen",
                    "fifteen",
                    "sixteen",
                    "seventeen",
                    "eighteen",
                    "nineteen",
                    "twenty",
                    "thirty",
                    "forty",
                    "fifty",
                    "sixty",
                    "seventy",
                    "eighty",
                    "ninety",
                    "hundred",
                    "thousand",
                    "million",
                    "billion",
                    "trillion",
                ]
            )

            # Define mathematical constants
            math_constants = oneOf(["pi", "e", "infinity", "inf"])
            math_constants.setParseAction(lambda t: t[0])  # Return the raw token

            # Define variables (order matters: longer matches first to avoid greedy single-char matching)
            variable = Word(alphanums + "_", min=2) | Word(alphas, exact=1)
            variable.setParseAction(lambda t: t[0])  # Return the raw token

            # Define numbers (digits or words)
            digit_number = Word(nums)
            word_number = number_words
            number = digit_number | word_number

            # Define operands (variables, numbers, constants, or expressions with powers)
            operand = math_constants | variable | number

            # Define power expressions (squared, cubed, etc.)
            power_word = oneOf(["squared", "cubed", "to the power of"])
            powered_expr = operand + OptionalPP(power_word + OptionalPP(number))

            # Define operators
            plus_op = oneOf(["plus", "+"])
            minus_op = oneOf(["minus", "-"])
            times_op = oneOf(["times", "multiplied by", "*", "×"])
            div_op = oneOf(["divided by", "over", "/", "÷"])  # Added "over"
            equals_op = oneOf(["equals", "is", "="])

            # Build expression grammar
            expr = infixNotation(
                powered_expr,
                [
                    (times_op | div_op, 2, opAssoc.LEFT),
                    (plus_op | minus_op, 2, opAssoc.LEFT),
                ],
            )

            # Full equation: expression equals expression
            equation = expr + equals_op + expr

            # Assignment: variable equals expression
            assignment = variable + equals_op + expr

            # Math statement (equation, assignment, or simple expression)
            simple_expr = expr
            self.parser = equation | assignment | simple_expr

            logger.info("Math expression parser initialized with pyparsing")

        except Exception as e:
            logger.error(f"Failed to initialize pyparsing math parser: {e}")
            raise

    def parse_expression(self, text: str) -> Optional[Dict[str, Any]]:
        """Parse math expression and return structured result"""
        try:
            # Clean the text but don't convert to lower
            cleaned = text.strip()

            # Try to parse
            result = self.parser.parseString(cleaned, parseAll=True)

            # Convert parse result to structured format
            return {"original": text, "parsed": list(result), "type": "MATH_EXPRESSION"}

        except ParseException:
            # Not a math expression - this is normal
            return None
        except (AttributeError, ValueError, TypeError) as e:
            logger.debug(f"Math parsing error for '{text}': {e}")
            return None


class NumericalEntityDetector:
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

        self.math_parser = MathExpressionParser()
        # Initialize NumberParser for robust number word detection
        self.number_parser = NumberParser(language=self.language)

    def detect(self, text: str, entities: List[Entity]) -> List[Entity]:
        """Detects all numerical-related entities."""
        numerical_entities: list[Entity] = []

        # Detect version numbers and percentages first (before SpaCy processes them)
        all_entities = entities + numerical_entities
        self._detect_version_numbers(text, numerical_entities, all_entities)

        # Pass all existing entities for overlap checking
        all_entities = entities + numerical_entities
        self._detect_numerical_entities(text, numerical_entities, all_entities)

        # Fallback detection for basic number words when SpaCy is not available
        all_entities = entities + numerical_entities
        self._detect_cardinal_numbers_fallback(text, numerical_entities, all_entities)

        all_entities = entities + numerical_entities
        self._detect_math_expressions(text, numerical_entities, all_entities)

        # Detect temperatures before time expressions to prevent conflicts
        all_entities = entities + numerical_entities
        self._detect_temperatures(text, numerical_entities, all_entities)

        all_entities = entities + numerical_entities
        self._detect_time_expressions(text, numerical_entities, all_entities)

        all_entities = entities + numerical_entities
        self._detect_phone_numbers(text, numerical_entities, all_entities)

        all_entities = entities + numerical_entities
        self._detect_ordinals(text, numerical_entities, all_entities)

        all_entities = entities + numerical_entities
        self._detect_time_relative(text, numerical_entities, all_entities)

        all_entities = entities + numerical_entities
        self._detect_fractions(text, numerical_entities, all_entities)

        all_entities = entities + numerical_entities
        self._detect_measurements(text, numerical_entities, all_entities)

        all_entities = entities + numerical_entities
        self._detect_metric_units(text, numerical_entities, all_entities)

        all_entities = entities + numerical_entities
        self._detect_root_expressions(text, numerical_entities, all_entities)

        all_entities = entities + numerical_entities
        self._detect_math_constants(text, numerical_entities, all_entities)

        all_entities = entities + numerical_entities
        self._detect_scientific_notation(text, numerical_entities, all_entities)

        all_entities = entities + numerical_entities
        self._detect_music_notation(text, numerical_entities, all_entities)

        all_entities = entities + numerical_entities
        self._detect_spoken_emojis(text, numerical_entities, all_entities)

        return numerical_entities

    def _detect_numerical_entities(self, text: str, entities: List[Entity], all_entities: Optional[List[Entity]] = None) -> None:
        """Detect numerical entities with units using SpaCy's grammar analysis."""
        # First, handle patterns that don't need SpaCy
        self._detect_numeric_ranges_simple(text, entities, all_entities)
        self._detect_number_unit_patterns(text, entities, all_entities)

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
            is_a_number = (
                (token.like_num and token.lower_ not in self.resources.get("technical", {}).get("ordinal_words", []))
                or (token.ent_type_ == "CARDINAL")
                or (token.lower_ in self.number_parser.all_number_words)
            )

            if is_a_number:
                number_tokens = [token]
                j = i + 1
                # Greedily consume all consecutive number-related words
                while j < len(doc) and (
                    doc[j].like_num
                    or doc[j].lower_ in self.number_parser.all_number_words
                    or doc[j].lower_ in {"and", "point", "dot"}
                ):
                    if doc[j].lower_ != "and":
                        number_tokens.append(doc[j])
                    j += 1

                # Now, check the very next token to see if it's a unit
                if j < len(doc):
                    unit_token = doc[j]
                    unit_lemma = unit_token.lemma_.lower()

                    entity_type = None
                    # Determine entity type based on the unit found
                    if unit_lemma in currency_units:
                        # Special handling for "pounds" - check context
                        if unit_token.text.lower() in ["pound", "pounds"]:
                            prefix_context = text[:number_tokens[0].idx].lower()
                            currency_contexts = self.resources.get("context_words", {}).get("currency_contexts", [])
                            weight_contexts = self.resources.get("context_words", {}).get("weight_contexts", [])
                            
                            # If it has clear weight context OR lacks currency context, treat as weight.
                            if any(ctx in prefix_context for ctx in weight_contexts) or not any(ctx in prefix_context for ctx in currency_contexts):
                                entity_type = EntityType.METRIC_WEIGHT # Treat as weight, will be converted to 'lbs'
                            else:
                                entity_type = EntityType.CURRENCY # It has currency context, so it's money
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

    def _detect_numeric_ranges_simple(
        self, text: str, entities: List[Entity], all_entities: Optional[List[Entity]] = None
    ) -> None:
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

    def _detect_number_unit_patterns(
        self, text: str, entities: List[Entity], all_entities: Optional[List[Entity]] = None
    ) -> None:
        """Detect number + unit patterns using regex for cases where SpaCy might fail."""
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
                                prefix_context = text[:match.start()].lower()
                                currency_contexts = self.resources.get("context_words", {}).get("currency_contexts", [])
                                weight_contexts = self.resources.get("context_words", {}).get("weight_contexts", [])
                                
                                # If it has clear weight context OR lacks currency context, treat as weight.
                                if any(ctx in prefix_context for ctx in weight_contexts) or not any(ctx in prefix_context for ctx in currency_contexts):
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

    def _detect_math_expressions(self, text: str, entities: List[Entity], all_entities: Optional[List[Entity]] = None) -> None:
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
                if self._is_idiomatic_over_expression(clean_expr, text, start_pos):
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
        """Use SpaCy POS tagging to determine if an expression is mathematical or idiomatic.

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
        if not self.nlp:
            # No fallback needed - if SpaCy unavailable, assume mathematical
            return False
        try:
            doc = self.nlp(full_text)
        except (AttributeError, ValueError, IndexError) as e:
            logger.warning(f"SpaCy idiomatic expression detection failed: {e}")
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

    def _is_idiomatic_over_expression(self, expr: str, full_text: str, start_pos: int) -> bool:
        """Check if 'over' is used idiomatically rather than mathematically."""
        if " over " not in expr.lower():
            return False

        expr_lower = expr.lower()

        # Get context before the expression
        preceding_text = full_text[:start_pos].lower().strip()
        preceding_words = preceding_text.split()[-3:] if preceding_text else []
        preceding_context = " ".join(preceding_words)

        # Common idiomatic uses of "over"
        # Check the expression itself and preceding context
        idiomatic_over_patterns = [
            "game over",
            "over par",
            "it's over",
            "start over",
            "do over",
            "all over",
            "fight over",
            "argue over",
            "debate over",
            "think over",
            "over the",
            "over there",
            "over here",
            "over it",
            "over him",
            "over her",
            "over them",
            "get over",
            "be over",
            "i'm over",
            "i am over",
            "getting over",
        ]
        for pattern in idiomatic_over_patterns:
            if pattern in expr_lower or pattern in (preceding_context + " " + expr_lower).lower():
                return True

        # Additional check: if the left operand in expr is a pronoun or common word, it's likely idiomatic
        parts = expr_lower.split(" over ")
        if parts:
            left_part = parts[0].strip()
            if left_part in ["i", "i'm", "i am", "you", "we", "they", "he", "she", "it", "that", "this"]:
                return True

        return False

    def _detect_time_expressions(self, text: str, entities: List[Entity], all_entities: Optional[List[Entity]] = None) -> None:
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

    def _detect_phone_numbers(self, text: str, entities: List[Entity], all_entities: Optional[List[Entity]] = None) -> None:
        """Detect phone numbers spoken as individual digits."""
        # Use centralized phone pattern
        for match in regex_patterns.SPOKEN_PHONE_PATTERN.finditer(text):
            check_entities = all_entities if all_entities else entities
            if not is_inside_entity(match.start(), match.end(), check_entities):
                entities.append(
                    Entity(start=match.start(), end=match.end(), text=match.group(), type=EntityType.PHONE_LONG)
                )

    def _detect_ordinals(self, text: str, entities: List[Entity], all_entities: Optional[List[Entity]] = None) -> None:
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
                        if ordinal_token.text.lower() in idiomatic_phrases and next_token.text.lower() in idiomatic_phrases[ordinal_token.text.lower()]:
                            logger.debug(f"Skipping ORDINAL '{match.group()}' due to idiomatic follower noun '{next_token.text}'.")
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

    def _detect_time_relative(self, text: str, entities: List[Entity], all_entities: Optional[List[Entity]] = None) -> None:
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

    def _detect_fractions(self, text: str, entities: List[Entity], all_entities: Optional[List[Entity]] = None) -> None:
        """Detect fraction expressions (one half, two thirds, etc.)."""
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

    def _detect_version_numbers(self, text: str, entities: List[Entity], all_entities: Optional[List[Entity]] = None) -> None:
        """Detect version numbers in spoken form (e.g., 'version two point five')."""
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

    def _detect_measurements(self, text: str, entities: List[Entity], all_entities: Optional[List[Entity]] = None) -> None:
        """Detect measurement patterns that SpaCy might miss or misclassify.

        This catches patterns like:
        - "three and a half feet"
        - "X foot Y inches"
        """
        import re

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

    def _detect_temperatures(self, text: str, entities: List[Entity], all_entities: Optional[List[Entity]] = None) -> None:
        """Detect temperature expressions.

        Examples:
        - "twenty degrees celsius" → "20°C"
        - "thirty two degrees fahrenheit" → "32°F"
        - "minus ten degrees" → "-10°"
        - "negative five celsius" → "-5°C"

        """
        import re

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

    def _detect_metric_units(self, text: str, entities: List[Entity], all_entities: Optional[List[Entity]] = None) -> None:
        """Detect metric unit expressions.

        Examples:
        - "five kilometers" → "5 km"
        - "two point five centimeters" → "2.5 cm"
        - "ten kilograms" → "10 kg"
        - "three liters" → "3 L"

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
                or (token.lower_ in self.number_parser.all_number_words)
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
                        or (next_token.lower_ in self.number_parser.all_number_words)
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

    def _detect_root_expressions(self, text: str, entities: List[Entity], all_entities: Optional[List[Entity]] = None) -> None:
        """Detect square root and cube root expressions.

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

    def _detect_math_constants(self, text: str, entities: List[Entity], all_entities: Optional[List[Entity]] = None) -> None:
        """Detect mathematical constants.

        Examples:
        - "pi" → "π"
        - "e" → "e" (Euler's number)
        - "infinity" → "∞"

        """
        # Pattern for math constants - only match standalone words
        constants_pattern = re.compile(r"\b(pi|infinity|inf)\b", re.IGNORECASE)

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

    def _detect_scientific_notation(self, text: str, entities: List[Entity], all_entities: Optional[List[Entity]] = None) -> None:
        """Detect scientific notation expressions.

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
        ordinal_pattern = (
            r"twenty\s+first|twenty\s+second|twenty\s+third|twenty\s+fourth|twenty\s+fifth|"
            r"twenty\s+sixth|twenty\s+seventh|twenty\s+eighth|twenty\s+ninth|"
            r"thirty\s+first|thirty\s+second|thirty\s+third|thirty\s+fourth|thirty\s+fifth|"
            r"thirty\s+sixth|thirty\s+seventh|thirty\s+eighth|thirty\s+ninth|"
            r"first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth|"
            r"eleventh|twelfth|thirteenth|fourteenth|fifteenth|sixteenth|seventeenth|eighteenth|nineteenth|twentieth|"
            r"thirtieth|fortieth|fiftieth|sixtieth|seventieth|eightieth|ninetieth|hundredth"
        )

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

    def _detect_music_notation(self, text: str, entities: List[Entity], all_entities: Optional[List[Entity]] = None) -> None:
        """Detect music notation expressions.

        Examples:
        - "C sharp" → "C♯"
        - "B flat" → "B♭"
        - "E natural" → "E♮"

        """
        import re

        # Pattern for music notes with accidentals - supports both space and hyphen separation
        music_pattern = re.compile(r"\b([A-G])[-\s]+(sharp|flat|natural)\b", re.IGNORECASE)

        for match in music_pattern.finditer(text):
            check_entities = all_entities if all_entities else entities
            if not is_inside_entity(match.start(), match.end(), check_entities):
                note = match.group(1).upper()  # Capitalize the note
                accidental = match.group(2).lower()

                entities.append(
                    Entity(
                        start=match.start(),
                        end=match.end(),
                        text=match.group(0),
                        type=EntityType.MUSIC_NOTATION,
                        metadata={"note": note, "accidental": accidental},
                    )
                )

    def _detect_spoken_emojis(self, text: str, entities: List[Entity], all_entities: Optional[List[Entity]] = None) -> None:
        """Detect spoken emoji expressions using a tiered system.

        Tier 1 (Implicit): Can be used without "emoji" trigger
        - "smiley face" → 🙂

        Tier 2 (Explicit): Must be followed by "emoji", "icon", or "emoticon"
        - "rocket emoji" → 🚀
        """
        # Build patterns from the emoji mappings
        implicit_keys = list(regex_patterns.SPOKEN_EMOJI_IMPLICIT_MAP.keys())
        explicit_keys = list(regex_patterns.SPOKEN_EMOJI_EXPLICIT_MAP.keys())

        # Sort keys by length (longest first) to avoid greedy matching issues
        explicit_keys.sort(key=len, reverse=True)

        # Pattern for explicit emojis (must have trigger word)
        if explicit_keys:
            explicit_pattern = re.compile(
                r"(\b(?:"
                + "|".join(re.escape(key) for key in explicit_keys)
                + r")\s+(?:emoji|icon|emoticon)\b)([.!?]*)",
                re.IGNORECASE,
            )

            for match in explicit_pattern.finditer(text):
                check_entities = all_entities if all_entities else entities
                if not is_inside_entity(match.start(), match.end(), check_entities):
                    # Get the emoji key (group 1) and the full text including punctuation (group 0)
                    emoji_key_full = match.group(1).lower().strip()
                    # Remove the trigger word from the key
                    emoji_key = re.sub(r"\s+(?:emoji|icon|emoticon)$", "", emoji_key_full)

                    entities.append(
                        Entity(
                            start=match.start(),
                            end=match.end(),
                            text=match.group(0),
                            type=EntityType.SPOKEN_EMOJI,
                            metadata={"emoji_key": emoji_key, "is_implicit": False},
                        )
                    )

        # Pattern for implicit emojis (no trigger word needed)
        implicit_keys.sort(key=len, reverse=True)
        if implicit_keys:
            implicit_pattern = re.compile(
                r"(\b(?:" + "|".join(re.escape(key) for key in implicit_keys) + r")\b)([.!?]*)", re.IGNORECASE
            )

            for match in implicit_pattern.finditer(text):
                check_entities = all_entities if all_entities else entities
                if not is_inside_entity(match.start(), match.end(), check_entities):
                    entities.append(
                        Entity(
                            start=match.start(),
                            end=match.end(),
                            text=match.group(0),
                            type=EntityType.SPOKEN_EMOJI,
                            metadata={"emoji_key": match.group(1).lower(), "is_implicit": True},
                        )
                    )

    def _detect_cardinal_numbers_fallback(
        self, text: str, entities: List[Entity], all_entities: Optional[List[Entity]] = None
    ) -> None:
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


