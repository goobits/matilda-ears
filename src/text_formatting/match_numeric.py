#!/usr/bin/env python3
"""Numeric, mathematical, time, and financial entity detection and conversion for Matilda transcriptions."""

import re
from typing import List, Optional, Dict, Any
from .common import Entity, EntityType, NumberParser
from .utils import is_inside_entity
from ..core.config import setup_logging
from . import regex_patterns
from .constants import get_resources

logger = setup_logging(__name__, log_filename="text_formatting.txt")

# Constants imported from constants.py


# Math expression parsing
try:
    from pyparsing import (
        Word,
        Literal,
        nums,
        alphas,
        alphanums,
        Optional as OptionalPP,
        oneOf,
        Suppress,
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
            from .nlp_provider import get_nlp

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
        numerical_entities = []

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

    def _detect_numerical_entities(self, text: str, entities: List[Entity], all_entities: List[Entity] = None) -> None:
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
                        if not is_inside_entity(start_pos, end_pos, all_entities):
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
        self, text: str, entities: List[Entity], all_entities: List[Entity] = None
    ) -> None:
        """Detect numeric range expressions (ten to twenty, etc.)."""
        for match in regex_patterns.SPOKEN_NUMERIC_RANGE_PATTERN.finditer(text):
            check_entities = all_entities if all_entities else entities
            if not is_inside_entity(match.start(), match.end(), check_entities):
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
                        end_pos = match.end() + len(text[match.end() :]) - len(remaining_text) + 7  # 7 = len("percent")

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
        self, text: str, entities: List[Entity], all_entities: List[Entity] = None
    ) -> None:
        """Detect number + unit patterns using regex for cases where SpaCy might fail."""
        # Build comprehensive pattern for all number words
        number_pattern = r"\b(?:" + "|".join(sorted(self.number_parser.all_number_words, key=len, reverse=True)) + r")"

        # Build unit patterns
        all_units = (
            (self.resources.get("currency", {}).get("units", []) + 
             self.resources.get("units", {}).get("percent_units", []) + 
             self.resources.get("data_units", {}).get("storage", []) + 
             self.resources.get("units", {}).get("frequency_units", []) + 
             self.resources.get("units", {}).get("time_units", []))
        )
        unit_pattern = r"(?:" + "|".join(sorted(all_units, key=len, reverse=True)) + r")"

        # Pattern for compound numbers followed by units
        compound_pattern = re.compile(
            number_pattern + r"(?:\s+" + number_pattern + r")*\s+" + unit_pattern + r"\b", re.IGNORECASE
        )

        for match in compound_pattern.finditer(text):
            check_entities = all_entities if all_entities else entities
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

                if entity_type:
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

    def _detect_math_expressions(self, text: str, entities: List[Entity], all_entities: List[Entity] = None) -> None:
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
                    converted_words.append("*")
                elif word.lower() == "plus":
                    converted_words.append("+")
                elif word.lower() == "minus":
                    converted_words.append("-")
                elif word.lower() in ["divided", "by"] and " ".join(words).lower().find("divided by") != -1:
                    # Handle "divided by" as a unit
                    if word.lower() == "divided":
                        converted_words.append("/")
                    # Skip "by" when it follows "divided"
                elif word.lower() == "by" and len(converted_words) > 0 and converted_words[-1] == "/":
                    continue  # Skip "by" in "divided by"
                else:
                    converted_words.append(word)
            preprocessed_expr = " ".join(converted_words)
            
            math_result = self.math_parser.parse_expression(preprocessed_expr)
            if math_result:
                # Context filter: Skip if "over" is used idiomatically (not mathematically)
                if self._is_idiomatic_over_expression(clean_expr, text, start_pos):
                    continue

                # Note: Idiomatic "plus" and "times" filtering is now handled at the CARDINAL detection stage
                # in formatter.py._should_skip_cardinal(), preventing these from being detected as entities in the first place

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
                            f"{'noun' if is_followed_by_noun else 'comparative'}: '{next_token.text}'"
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
            "game over", "over par", "it's over", "start over", "do over", "all over",
            "fight over", "argue over", "debate over", "think over", "over the", "over there",
            "over here", "over it", "over him", "over her", "over them", "get over",
            "be over", "i'm over", "i am over", "getting over"
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

    def _detect_time_expressions(self, text: str, entities: List[Entity], all_entities: List[Entity] = None) -> None:
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

    def _detect_phone_numbers(self, text: str, entities: List[Entity], all_entities: List[Entity] = None) -> None:
        """Detect phone numbers spoken as individual digits."""
        # Use centralized phone pattern
        for match in regex_patterns.SPOKEN_PHONE_PATTERN.finditer(text):
            check_entities = all_entities if all_entities else entities
            if not is_inside_entity(match.start(), match.end(), check_entities):
                entities.append(
                    Entity(start=match.start(), end=match.end(), text=match.group(), type=EntityType.PHONE_LONG)
                )

    def _detect_ordinals(self, text: str, entities: List[Entity], all_entities: List[Entity] = None) -> None:
        """Detect ordinal numbers (first, second, third, etc.)."""
        for match in regex_patterns.SPOKEN_ORDINAL_PATTERN.finditer(text):
            check_entities = all_entities if all_entities else entities

            # Check if this ordinal is part of an idiomatic phrase
            ordinal_text = match.group().lower()
            remaining_text = text[match.end() :].strip()

            # Skip ordinals that are likely part of idiomatic phrases
            if ordinal_text in ["sixth"] and remaining_text.startswith("sense"):
                logger.debug(f"Skipping ordinal '{ordinal_text}' - part of idiomatic phrase 'sixth sense'")
                continue
            if ordinal_text in ["first"] and (remaining_text.startswith("class") or remaining_text.startswith("rate")):
                logger.debug(f"Skipping ordinal '{ordinal_text}' - part of idiomatic phrase")
                continue
            if ordinal_text in ["second"] and remaining_text.startswith("nature"):
                logger.debug(f"Skipping ordinal '{ordinal_text}' - part of idiomatic phrase 'second nature'")
                continue

            # Allow ordinals to override low-priority entities like CARDINAL
            overlaps_high_priority = False
            for existing in check_entities:
                if not (match.end() <= existing.start or match.start() >= existing.end):
                    if existing.type not in [
                        EntityType.CARDINAL,
                        EntityType.DATE,  # e.g. "July first"
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
                        # Use group(0) to capture the full text of the ordinal, like "twenty third"
                        metadata={"ordinal_word": match.group(0)},
                    )
                )

    def _detect_time_relative(self, text: str, entities: List[Entity], all_entities: List[Entity] = None) -> None:
        """Detect relative time expressions (quarter past three, half past two, etc.)."""
        for match in regex_patterns.SPOKEN_TIME_RELATIVE_PATTERN.finditer(text):
            check_entities = all_entities if all_entities else entities

            # Check if this overlaps with only low-priority entities (CARDINAL, DATE, QUANTITY)
            overlaps_low_priority = False
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
                        overlaps_low_priority = True
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

    def _detect_fractions(self, text: str, entities: List[Entity], all_entities: List[Entity] = None) -> None:
        """Detect fraction expressions (one half, two thirds, etc.)."""
        for match in regex_patterns.SPOKEN_FRACTION_PATTERN.finditer(text):
            check_entities = all_entities if all_entities else entities

            # Check if this overlaps with only low-priority entities (CARDINAL, DATE, QUANTITY)
            overlaps_low_priority = False
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
                        overlaps_low_priority = True
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

    def _detect_version_numbers(self, text: str, entities: List[Entity], all_entities: List[Entity] = None) -> None:
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

                entity_type = EntityType.PERCENT if is_percentage else EntityType.VERSION_TWO

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

    def _detect_measurements(self, text: str, entities: List[Entity], all_entities: List[Entity] = None) -> None:
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

    def _detect_temperatures(self, text: str, entities: List[Entity], all_entities: List[Entity] = None) -> None:
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

    def _detect_metric_units(self, text: str, entities: List[Entity], all_entities: List[Entity] = None) -> None:
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

                    if compound_unit in WEIGHT_UNITS:
                        entity_type = EntityType.METRIC_WEIGHT
                    elif unit_lemma in LENGTH_UNITS or unit_text in LENGTH_UNITS:
                        entity_type = EntityType.METRIC_LENGTH
                    elif unit_lemma in WEIGHT_UNITS or unit_text in WEIGHT_UNITS:
                        entity_type = EntityType.METRIC_WEIGHT
                    elif unit_lemma in VOLUME_UNITS or unit_text in VOLUME_UNITS:
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
                if unit_text in LENGTH_UNITS:
                    entity_type = EntityType.METRIC_LENGTH
                elif unit_text in WEIGHT_UNITS:
                    entity_type = EntityType.METRIC_WEIGHT
                elif unit_text in VOLUME_UNITS:
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

    def _detect_root_expressions(self, text: str, entities: List[Entity], all_entities: List[Entity] = None) -> None:
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

    def _detect_math_constants(self, text: str, entities: List[Entity], all_entities: List[Entity] = None) -> None:
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

    def _detect_scientific_notation(self, text: str, entities: List[Entity], all_entities: List[Entity] = None) -> None:
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

    def _detect_music_notation(self, text: str, entities: List[Entity], all_entities: List[Entity] = None) -> None:
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

    def _detect_spoken_emojis(self, text: str, entities: List[Entity], all_entities: List[Entity] = None) -> None:
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
        self, text: str, entities: List[Entity], all_entities: List[Entity] = None
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


class NumericalPatternConverter:
    def __init__(self, number_parser: NumberParser, language: str = "en"):
        self.number_parser = number_parser
        self.language = language
        
        # Load language-specific resources
        self.resources = get_resources(language)

        # Operator mappings
        self.operators = {
            "plus": "+",
            "minus": "-",
            "times": "×",
            "divided by": "÷",
            "over": "/",  # Re-enabled with contextual checking
            "equals": "=",
            "plus plus": "++",
            "minus minus": "--",
            "equals equals": "==",
        }

        self.converters = {
            EntityType.MATH_EXPRESSION: self.convert_math_expression,
            EntityType.CURRENCY: self.convert_currency,
            EntityType.MONEY: self.convert_currency,  # SpaCy detected money entity
            EntityType.DOLLAR_CENTS: self.convert_dollar_cents,
            EntityType.PERCENT: self.convert_percent,
            EntityType.DATA_SIZE: self.convert_data_size,
            EntityType.FREQUENCY: self.convert_frequency,
            EntityType.TIME_DURATION: self.convert_time_duration,
            EntityType.TIME: self.convert_time_or_duration,  # SpaCy detected TIME entity
            EntityType.TIME_CONTEXT: self.convert_time,
            EntityType.TIME_AMPM: self.convert_time,
            EntityType.PHONE_LONG: self.convert_phone_long,
            EntityType.CARDINAL: self.convert_cardinal,
            EntityType.ORDINAL: self.convert_ordinal,
            EntityType.TIME_RELATIVE: self.convert_time_relative,
            EntityType.FRACTION: self.convert_fraction,
            EntityType.NUMERIC_RANGE: self.convert_numeric_range,
            EntityType.VERSION_TWO: self.convert_version,
            EntityType.VERSION_THREE: self.convert_version,
            EntityType.QUANTITY: self.convert_measurement,
            EntityType.TEMPERATURE: self.convert_temperature,
            EntityType.METRIC_LENGTH: self.convert_metric_unit,
            EntityType.METRIC_WEIGHT: self.convert_metric_unit,
            EntityType.METRIC_VOLUME: self.convert_metric_unit,
            EntityType.ROOT_EXPRESSION: self.convert_root_expression,
            EntityType.MATH_CONSTANT: self.convert_math_constant,
            EntityType.SCIENTIFIC_NOTATION: self.convert_scientific_notation,
            EntityType.MUSIC_NOTATION: self.convert_music_notation,
            EntityType.SPOKEN_EMOJI: self.convert_spoken_emoji,
        }

    def convert_math_expression(self, entity: Entity) -> str:
        """Convert parsed math expressions to properly formatted text"""
        if not entity.metadata or "parsed" not in entity.metadata:
            return entity.text

        try:
            parsed = entity.metadata["parsed"]
            result_parts = []

            # Check for trailing punctuation
            text = entity.text
            trailing_punct = ""
            if text and text[-1] in ".!?":
                trailing_punct = text[-1]

            # Flatten the parsed tokens first for easier processing
            flat_tokens = []

            def flatten_tokens(tokens):
                for token in tokens:
                    if hasattr(token, "__iter__") and not isinstance(token, str):
                        flatten_tokens(token)
                    else:
                        flat_tokens.append(str(token))

            flatten_tokens(parsed)

            # Process tokens with lookahead for better conversion
            i = 0
            while i < len(flat_tokens):
                token = flat_tokens[i]
                # Check if next token is a power word
                if i + 1 < len(flat_tokens) and flat_tokens[i + 1].lower() in ["squared", "cubed"]:
                    # Convert the variable/number and its power together
                    converted = self._convert_math_token(token)
                    power = self._convert_math_token(flat_tokens[i + 1])
                    result_parts.append(converted + power)
                    i += 2  # Skip the power token
                else:
                    # Normal token conversion
                    converted = self._convert_math_token(token)
                    if converted:
                        result_parts.append(converted)
                    i += 1

            # Join and clean up spacing
            result = " ".join(result_parts)
            result = re.sub(r"\s+", " ", result).strip()

            # Ensure there is a single space around binary operators for readability
            result = re.sub(r"\s*([+\-*/=×÷])\s*", r" \1 ", result).strip()
            # Clean up potential double spaces that might result
            result = re.sub(r"\s+", " ", result)

            # Remove any question marks that may have crept in from pyparsing
            result = result.replace("?", "")

            # Fix spacing around powers (remove space before superscripts)
            result = re.sub(r"\s+([²³⁴⁵⁶⁷⁸⁹⁰¹])", r"\1", result)

            # Fix spacing between numbers and math constants (e.g., "2 π" → "2π")
            result = re.sub(r"(\d)\s+([π∞e])", r"\1\2", result)

            # Fix spacing for single-letter variables next to constants (e.g., "π × r²" not "π×r²")
            result = re.sub(r"([π∞e])×([a-zA-Z])", r"\1 × \2", result)

            # Special case: strip periods from physics equations like "E = MC²"
            # Physics equations ending with superscripts should not have trailing periods
            if trailing_punct == "." and re.search(r"[²³⁴⁵⁶⁷⁸⁹⁰¹]$", result):
                trailing_punct = ""

            # Add back trailing punctuation for math expressions
            return result + trailing_punct

        except (AttributeError, ValueError, TypeError, IndexError) as e:
            logger.debug(f"Error converting math expression: {e}")
            return entity.text

    def _convert_math_token(self, token: str) -> str:
        """Convert individual math tokens"""
        token_lower = str(token).lower()

        # Convert operators
        if token_lower in self.operators:
            return self.operators[token_lower]

        # Handle special math symbols
        if token_lower == "times":
            return "×"
        if token_lower == "over":  # Added handling for "over"
            return "/"

        # Convert number words
        parsed_num = self.number_parser.parse(token_lower)
        if parsed_num:
            return parsed_num

        # Convert powers
        if token_lower == "squared":
            return "²"
        if token_lower == "cubed":
            return "³"

        # Handle Greek letters
        if token_lower == "lambda":
            return "λ"
        if token_lower == "pi":
            return "π"
        if token_lower == "theta":
            return "θ"
        if token_lower == "alpha":
            return "α"
        if token_lower == "beta":
            return "β"
        if token_lower == "gamma":
            return "γ"
        if token_lower == "delta":
            return "δ"

        # Preserve case for variables
        if str(token).isalpha():
            # Keep variables as-is (preserve original case)
            # Single letters like 'r', 'x', 'y' stay lowercase in math
            # Multi-letter variables preserve their original case
            return str(token)

        # Return as-is (other tokens)
        return str(token)

    def convert_currency(self, entity: Entity, full_text: str = "") -> str:
        """Convert currency like 'twenty five dollars' -> '$25' or 'five thousand pounds' -> '£5000'"""
        import re

        text = entity.text

        # Use currency mappings from constants

        # Currencies that go after the amount (post-position)
        post_position_currencies = {"won"}

        post_position_currencies.update({"cent", "cents"})

        # If it's already in currency format (e.g., "25.99" from SpaCy MONEY)
        # Check if there's already a dollar sign before the entity
        if re.match(r"^\d+\.?\d*$", text.strip()):
            # Check if dollar sign precedes this entity in the full text
            if full_text and entity.start > 0 and full_text[entity.start - 1] == "$":
                # Dollar sign already present, just return the number
                return text.strip()
            # No dollar sign, add it
            return f"${text.strip()}"

        # Handle spoken currency (e.g., "twenty five dollars", "five thousand pounds")
        # Check for trailing punctuation in the entity text
        trailing_punct = ""
        if text and text[-1] in ".!?":
            trailing_punct = text[-1]

        # Extract currency unit from metadata or text
        unit = None
        if entity.metadata and "unit" in entity.metadata:
            unit = entity.metadata["unit"].lower()
        else:
            # Try to extract unit from text
            text_lower = text.lower()
            if text_lower and text_lower[-1] in ".!?":
                text_lower = text_lower[:-1]

            # Find which currency word is in the text
            currency_map = self.resources.get("units", {}).get("currency_map", {})
            for currency_word in currency_map:
                if currency_word in text_lower:
                    unit = currency_word
                    break

        # Get the currency symbol
        currency_map = self.resources.get("units", {}).get("currency_map", {})
        symbol = currency_map.get(unit, "$")  # Default to $ if not found

        # Extract and parse the number
        number_text = None
        if entity.metadata and "number" in entity.metadata:
            number_text = entity.metadata["number"]
        else:
            # Remove currency word and parse
            text_lower = text.lower()
            if text_lower and text_lower[-1] in ".!?":
                text_lower = text_lower[:-1]

            if unit:
                # Use regex to remove the currency word at word boundaries
                # Create pattern that matches the currency word at word boundaries
                pattern = r"\b" + re.escape(unit) + r"s?\b"  # Handle plural forms
                number_text = re.sub(pattern, "", text_lower).strip()
            else:
                # Try removing any known currency words
                currency_map = self.resources.get("units", {}).get("currency_map", {})
            for currency_word in currency_map:
                    if currency_word in text_lower:
                        # Use regex for proper word boundary matching
                        pattern = r"\b" + re.escape(currency_word) + r"s?\b"
                        number_text = re.sub(pattern, "", text_lower).strip()
                        unit = currency_word
                        break

        if number_text:
            amount = self.number_parser.parse(number_text)
            if amount:
                # Format based on currency position
                if unit in post_position_currencies:
                    return f"{amount}{symbol}{trailing_punct}"
                return f"{symbol}{amount}{trailing_punct}"

        return entity.text  # Fallback

    def convert_dollar_cents(self, entity: Entity) -> str:
        """Convert 'X dollars and Y cents' to '$X.Y'"""
        if entity.metadata:
            dollars = self.number_parser.parse(entity.metadata.get("dollars", "0"))
            cents = self.number_parser.parse(entity.metadata.get("cents", "0"))
            if dollars and cents:
                # Ensure cents is zero-padded to 2 digits
                cents_str = str(cents).zfill(2)
                return f"${dollars}.{cents_str}"
        return entity.text

    def convert_percent(self, entity: Entity) -> str:
        """Convert numerical percent entities"""
        # Handle new version number detection format
        if entity.metadata and "groups" in entity.metadata and entity.metadata.get("is_percentage"):
            groups = entity.metadata["groups"]
            # Convert the numeric parts
            parts = []
            for group in groups:
                if group:
                    parsed = self.number_parser.parse(group)
                    if parsed:
                        parts.append(parsed)
                    elif group and group.isdigit():
                        parts.append(group)

            if parts:
                # Join with dots for decimal percentages
                percent_str = ".".join(parts)
                return f"{percent_str}%"

        # Original handling for SpaCy-detected percentages
        if entity.metadata and "number" in entity.metadata:
            number_text = entity.metadata["number"]
            # Parse the number text to convert words to digits
            parsed_number = self.number_parser.parse(number_text)
            if parsed_number is not None:
                return f"{parsed_number}%"
            # Fallback to original if parsing fails
            return f"{number_text}%"

        # Fallback: parse from text if no metadata available
        text = entity.text.lower()
        # Try to extract number from text
        match = re.search(r"(.+?)\s+percent", text)
        if match:
            number_text = match.group(1).strip()
            # Use the number parser to convert words to numbers
            number = self.number_parser.parse(number_text)
            if number is not None:
                return f"{number}%"

        return entity.text

    def convert_data_size(self, entity: Entity) -> str:
        """Convert data size entities like 'five megabytes' -> '5MB'"""
        if entity.metadata and "number" in entity.metadata and "unit" in entity.metadata:
            number_text = entity.metadata["number"]
            unit = entity.metadata["unit"].lower()

            # Try to parse the entire number text first
            number_str = self.number_parser.parse(number_text)

            # If that fails, try parsing individual words from the number text
            if number_str is None:
                # Split and try to find valid number words
                words = number_text.split()
                for i, word in enumerate(words):
                    # Try parsing from this word onwards
                    remaining_text = " ".join(words[i:])
                    parsed = self.number_parser.parse(remaining_text)
                    if parsed:
                        number_str = parsed
                        break

            # Final fallback
            if number_str is None:
                number_str = number_text

            unit_map = {
                "byte": "B",
                "bytes": "B",
                "kilobyte": "KB",
                "kilobytes": "KB",
                "kb": "KB",
                "megabyte": "MB",
                "megabytes": "MB",
                "mb": "MB",
                "gigabyte": "GB",
                "gigabytes": "GB",
                "gb": "GB",
                "terabyte": "TB",
                "terabytes": "TB",
                "tb": "TB",
            }
            standard_unit = unit_map.get(unit, unit.upper())
            return f"{number_str}{standard_unit}"  # No space
        return entity.text

    def convert_frequency(self, entity: Entity) -> str:
        """Convert frequency entities like 'two megahertz' -> '2MHz'"""
        if entity.metadata and "number" in entity.metadata and "unit" in entity.metadata:
            number_text = entity.metadata["number"]
            unit = entity.metadata["unit"].lower()

            # Try to parse the entire number text first
            number_str = self.number_parser.parse(number_text)

            # If that fails, try parsing individual words from the number text
            if number_str is None:
                # Split and try to find valid number words
                words = number_text.split()
                for i, word in enumerate(words):
                    # Try parsing from this word onwards
                    remaining_text = " ".join(words[i:])
                    parsed = self.number_parser.parse(remaining_text)
                    if parsed:
                        number_str = parsed
                        break

            # Final fallback
            if number_str is None:
                number_str = number_text

            unit_map = {
                "hertz": "Hz",
                "hz": "Hz",
                "kilohertz": "kHz",
                "khz": "kHz",
                "megahertz": "MHz",
                "mhz": "MHz",
                "gigahertz": "GHz",
                "ghz": "GHz",
            }

            standard_unit = unit_map.get(unit, unit.upper())
            return f"{number_str}{standard_unit}"  # No space

        return entity.text

    def convert_time_duration(self, entity: Entity) -> str:
        """Convert time duration entities."""
        if not entity.metadata:
            return entity.text

        # Unit abbreviation map for compact formatting
        unit_map = {
            "second": "s",
            "seconds": "s",
            "minute": "min",
            "minutes": "min",
            "hour": "h",
            "hours": "h",
            "day": "d",
            "days": "d",
            "week": "w",
            "weeks": "w",
            "month": "mo",
            "months": "mo",
            "year": "y",
            "years": "y",
        }

        # Check if the number part is an ordinal word - if so, this shouldn't be a TIME_DURATION
        if "number" in entity.metadata:
            number_text = entity.metadata["number"].lower()
            # Check if it's an ordinal word
            ordinal_words = self.resources.get("technical", {}).get("ordinal_words", [])
            if number_text in ordinal_words:
                # This is an ordinal + time unit (e.g., "fourth day"), not a duration
                # Return the original text unchanged
                return entity.text

        # Check if this is a compound duration
        if entity.metadata.get("is_compound"):
            # Handle compound durations like "5 hours 30 minutes"
            number1 = entity.metadata.get("number1", "")
            unit1 = entity.metadata.get("unit1", "").lower()
            number2 = entity.metadata.get("number2", "")
            unit2 = entity.metadata.get("unit2", "").lower()

            # Convert number words to digits
            num1_str = self.number_parser.parse(number1)
            if num1_str is None:
                num1_str = number1
            num2_str = self.number_parser.parse(number2)
            if num2_str is None:
                num2_str = number2

            # Get abbreviated units
            abbrev1 = unit_map.get(unit1, unit1)
            abbrev2 = unit_map.get(unit2, unit2)

            # Format as compact notation
            return f"{num1_str}{abbrev1} {num2_str}{abbrev2}"

        # Handle simple duration
        if "number" in entity.metadata and "unit" in entity.metadata:
            number_text = entity.metadata["number"]
            unit = entity.metadata["unit"].lower()

            # Try to parse the entire number text first
            number_str = self.number_parser.parse(number_text)

            # If that fails, try parsing individual words from the number text
            if number_str is None:
                # Split and try to find valid number words
                words = number_text.split()
                for i, word in enumerate(words):
                    # Try parsing from this word onwards
                    remaining_text = " ".join(words[i:])
                    parsed = self.number_parser.parse(remaining_text)
                    if parsed:
                        number_str = parsed
                        break

            # Final fallback
            if number_str is None:
                number_str = number_text

            # Get abbreviated unit
            abbrev = unit_map.get(unit, unit)

            # Use compact formatting for durations
            return f"{number_str}{abbrev}"  # No space for units like h, s, d

        return entity.text

    def convert_time_or_duration(self, entity: Entity) -> str:
        """Convert TIME entities detected by SpaCy.

        This handles both regular time expressions and compound durations.
        SpaCy detects phrases like "five hours thirty minutes" as TIME entities.
        """
        text = entity.text.lower()

        # Check if this is a compound duration pattern
        # Pattern: number + time_unit + number + time_unit
        # Numbers can be compound like "twenty four"
        compound_pattern = re.compile(
            r"\b((?:\w+\s+)*\w+)\s+(seconds?|minutes?|hours?|days?|weeks?|months?|years?)\s+"
            r"((?:\w+\s+)*\w+)\s+(seconds?|minutes?|hours?|days?|weeks?|months?|years?)\b",
            re.IGNORECASE,
        )

        match = compound_pattern.match(text)
        if match:
            # This is a compound duration
            number1 = match.group(1)
            unit1 = match.group(2)
            number2 = match.group(3)
            unit2 = match.group(4)

            # Convert number words to digits
            num1_str = self.number_parser.parse(number1)
            if num1_str:
                number1 = num1_str
            num2_str = self.number_parser.parse(number2)
            if num2_str:
                number2 = num2_str

            # Unit abbreviation map
            unit_map = {
                "second": "s",
                "seconds": "s",
                "minute": "min",
                "minutes": "min",
                "hour": "h",
                "hours": "h",
                "day": "d",
                "days": "d",
                "week": "w",
                "weeks": "w",
                "month": "mo",
                "months": "mo",
                "year": "y",
                "years": "y",
            }

            # Get abbreviated units
            abbrev1 = unit_map.get(unit1.lower(), unit1)
            abbrev2 = unit_map.get(unit2.lower(), unit2)

            # Format as compact notation
            return f"{number1}{abbrev1} {number2}{abbrev2}"

        # Check for simple duration pattern
        simple_pattern = re.compile(
            r"\b(\w+)\s+(seconds?|minutes?|hours?|days?|weeks?|months?|years?)\b", re.IGNORECASE
        )

        match = simple_pattern.match(text)
        if match:
            number = match.group(1)
            unit = match.group(2)

            # Convert number words to digits
            num_str = self.number_parser.parse(number)
            if num_str:
                number = num_str

            # Unit abbreviation map
            unit_map = {
                "second": "s",
                "seconds": "s",
                "minute": "min",
                "minutes": "min",
                "hour": "h",
                "hours": "h",
                "day": "d",
                "days": "d",
                "week": "w",
                "weeks": "w",
                "month": "mo",
                "months": "mo",
                "year": "y",
                "years": "y",
            }

            # Get abbreviated unit
            abbrev = unit_map.get(unit.lower(), unit)

            # Use compact formatting
            return f"{number}{abbrev}"

        # Not a duration pattern, return as-is
        return entity.text

    def convert_time(self, entity: Entity) -> str:
        """Convert time expressions"""
        if entity.metadata and "groups" in entity.metadata:
            groups = entity.metadata["groups"]

            time_words = {
                "one": "1",
                "two": "2",
                "three": "3",
                "four": "4",
                "five": "5",
                "six": "6",
                "seven": "7",
                "eight": "8",
                "nine": "9",
                "ten": "10",
                "eleven": "11",
                "twelve": "12",
                "oh": "0",
                "fifteen": "15",
                "thirty": "30",
                "forty five": "45",
            }

            if entity.type == EntityType.TIME_CONTEXT:
                # Handle 'meet at three thirty'
                context = groups[0]  # 'meet at' or 'at'
                hour = time_words.get(groups[1].lower(), groups[1])
                minute_word = groups[3].lower() if groups[3] else "00"
                minute = time_words.get(minute_word, minute_word)
                if minute.isdigit():
                    minute = minute.zfill(2)
                ampm = groups[4].upper() if len(groups) > 4 and groups[4] else ""

                time_str = f"{hour}:{minute}"
                if ampm:
                    time_str += f" {ampm}"
                return f"{context} {time_str}"

            if entity.type == EntityType.TIME_AMPM:
                # Handle different TIME_AMPM patterns based on group structure
                if len(groups) == 3:
                    if groups[0].lower() == "at":
                        # Pattern: "at three PM" -> groups: ["at", "three", "PM"]
                        hour = time_words.get(groups[1].lower(), groups[1])
                        ampm = groups[2].upper()
                        # Preserve the original case of "at" (might be "At" at sentence start)
                        at_word = groups[0]
                        return f"{at_word} {hour} {ampm}"
                    if groups[2] in ["AM", "PM"]:
                        # Pattern: "three thirty PM" -> groups: ["three", "thirty", "PM"]
                        hour = time_words.get(groups[0].lower(), groups[0])
                        minute_word = groups[1].lower()
                        minute = time_words.get(minute_word, minute_word)
                        if minute.isdigit():
                            minute = minute.zfill(2)
                        ampm = groups[2].upper()
                        return f"{hour}:{minute} {ampm}"
                elif len(groups) == 2:
                    if groups[1] in ["AM", "PM"]:
                        # Pattern: "three PM" -> groups: ["three", "PM"]
                        hour = time_words.get(groups[0].lower(), groups[0])
                        ampm = groups[1].upper()
                        return f"{hour} {ampm}"
                    if groups[1].lower() in ["a", "p"]:
                        # Pattern: "ten a m" -> groups: ["ten", "a"]
                        hour = time_words.get(groups[0].lower(), groups[0])
                        ampm = "AM" if groups[1].lower() == "a" else "PM"
                        return f"{hour} {ampm}"

        return entity.text

    def convert_phone_long(self, entity: Entity) -> str:
        """Convert long form phone numbers"""
        # Extract digit words
        digit_words = {
            "zero": "0",
            "one": "1",
            "two": "2",
            "three": "3",
            "four": "4",
            "five": "5",
            "six": "6",
            "seven": "7",
            "eight": "8",
            "nine": "9",
        }

        words = entity.text.lower().split()
        digits = []
        for word in words:
            if word in digit_words:
                digits.append(digit_words[word])

        if len(digits) == 10:
            return f"({digits[0]}{digits[1]}{digits[2]}) {digits[3]}{digits[4]}{digits[5]}-{digits[6]}{digits[7]}{digits[8]}{digits[9]}"

        return entity.text

    def convert_cardinal(self, entity: Entity, full_text: str = "") -> str:
        """Convert cardinal numbers - only convert standalone clear numbers"""
        # Don't convert numbers that are part of hyphenated compounds
        # Check if this entity is immediately followed by a hyphen (like "One-on-one")
        if full_text:
            # Check character after entity end
            if entity.end < len(full_text) and full_text[entity.end] == "-":
                return entity.text
            # Check character before entity start
            if entity.start > 0 and full_text[entity.start - 1] == "-":
                return entity.text

        parsed = self.number_parser.parse_with_validation(entity.text)
        return parsed if parsed else entity.text

    def convert_ordinal(self, entity: Entity) -> str:
        """Convert ordinal numbers with context awareness (first -> 1st, but 1st -> first in conversational contexts)."""
        text_lower = entity.text.lower().replace("-", " ")
        original_text = entity.text

        # Check if input is already numeric (1st, 2nd, etc.)
        numeric_ordinal_pattern = re.compile(r"(\d+)(st|nd|rd|th)", re.IGNORECASE)
        numeric_match = numeric_ordinal_pattern.match(original_text)

        if numeric_match:
            # Input is already numeric - check context to see if we should convert to words
            if hasattr(entity, "parent_text") and entity.parent_text:
                # Context analysis for conversational vs positional usage
                context = entity.parent_text.lower()

                # Conversational patterns where numeric ordinals should become words
                conversational_patterns = [
                    r"\blet\'s\s+do\s+(?:this|that)\s+" + re.escape(original_text.lower()),
                    r"\bwe\s+(?:need|should)\s+(?:to\s+)?(?:handle|do)\s+(?:this|that)\s+"
                    + re.escape(original_text.lower()),
                    r"\b(?:first|1st)\s+(?:thing|step|priority|order|task)",
                    r"\bdo\s+(?:this|that)\s+" + re.escape(original_text.lower()),
                ]

                # Positional/ranking patterns where numeric ordinals should stay numeric
                positional_patterns = [
                    r"\bfinished\s+" + re.escape(original_text.lower()) + r"\s+place",
                    r"\bcame\s+in\s+" + re.escape(original_text.lower()),
                    r"\branked\s+" + re.escape(original_text.lower()),
                    r"\b" + re.escape(original_text.lower()) + r"\s+place",
                    r"\bin\s+the\s+" + re.escape(original_text.lower()),
                ]

                # Check for conversational patterns
                for pattern in conversational_patterns:
                    if re.search(pattern, context):
                        # Convert numeric to word form
                        num_str = numeric_match.group(1)
                        num = int(num_str)

                        # Reverse mapping from numbers to words
                        num_to_word = {
                            1: "first",
                            2: "second",
                            3: "third",
                            4: "fourth",
                            5: "fifth",
                            6: "sixth",
                            7: "seventh",
                            8: "eighth",
                            9: "ninth",
                            10: "tenth",
                            11: "eleventh",
                            12: "twelfth",
                            13: "thirteenth",
                            14: "fourteenth",
                            15: "fifteenth",
                            16: "sixteenth",
                            17: "seventeenth",
                            18: "eighteenth",
                            19: "nineteenth",
                            20: "twentieth",
                            30: "thirtieth",
                            40: "fortieth",
                            50: "fiftieth",
                            60: "sixtieth",
                            70: "seventieth",
                            80: "eightieth",
                            90: "ninetieth",
                            100: "hundredth",
                        }

                        if num in num_to_word:
                            return num_to_word[num]
                        break

                # Check for positional patterns - keep numeric
                for pattern in positional_patterns:
                    if re.search(pattern, context):
                        return original_text  # Keep numeric form

            # Default: keep numeric form if no clear context
            return original_text

        # Input is word form - convert to numeric (existing behavior)
        # First, try a direct lookup in a comprehensive map
        ordinal_map = {
            "first": "1st",
            "second": "2nd",
            "third": "3rd",
            "fourth": "4th",
            "fifth": "5th",
            "sixth": "6th",
            "seventh": "7th",
            "eighth": "8th",
            "ninth": "9th",
            "tenth": "10th",
            "eleventh": "11th",
            "twelfth": "12th",
            "thirteenth": "13th",
            "fourteenth": "14th",
            "fifteenth": "15th",
            "sixteenth": "16th",
            "seventeenth": "17th",
            "eighteenth": "18th",
            "nineteenth": "19th",
            "twentieth": "20th",
            "thirtieth": "30th",
            "fortieth": "40th",
            "fiftieth": "50th",
            "sixtieth": "60th",
            "seventieth": "70th",
            "eightieth": "80th",
            "ninetieth": "90th",
            "hundredth": "100th",
        }
        if text_lower in ordinal_map:
            return ordinal_map[text_lower]

        # If not found, parse the number and apply the suffix rule
        parsed_num_str = self.number_parser.parse_ordinal(text_lower)
        if parsed_num_str:
            num = int(parsed_num_str)
            if 11 <= num % 100 <= 13:
                suffix = "th"
            else:
                suffix = {1: "st", 2: "nd", 3: "rd"}.get(num % 10, "th")
            return f"{parsed_num_str}{suffix}"

        return entity.text

    def convert_time_relative(self, entity: Entity) -> str:
        """Convert relative time expressions (quarter past three -> 3:15)."""
        if not entity.metadata:
            return entity.text

        relative_expr = entity.metadata.get("relative_expr", "").lower()
        hour_word = entity.metadata.get("hour_word", "").lower()

        # Convert hour word to number
        hour_map = {
            "one": 1,
            "two": 2,
            "three": 3,
            "four": 4,
            "five": 5,
            "six": 6,
            "seven": 7,
            "eight": 8,
            "nine": 9,
            "ten": 10,
            "eleven": 11,
            "twelve": 12,
        }

        hour = hour_map.get(hour_word)
        if hour is None:
            # Try to parse as a number
            try:
                hour = int(hour_word)
            except:
                return entity.text

        # Convert relative expression to time
        if relative_expr == "quarter past":
            return f"{hour}:15"
        if relative_expr == "half past":
            return f"{hour}:30"
        if relative_expr == "quarter to":
            # Quarter to the next hour = current hour minus 15 minutes
            prev_hour = hour - 1 if hour > 1 else 12
            return f"{prev_hour}:45"
        if relative_expr == "five past":
            return f"{hour}:05"
        if relative_expr == "ten past":
            return f"{hour}:10"
        if relative_expr == "twenty past":
            return f"{hour}:20"
        if relative_expr == "twenty-five past":
            return f"{hour}:25"
        if relative_expr == "five to":
            # Five to the next hour = current hour minus 5 minutes
            prev_hour = hour - 1 if hour > 1 else 12
            return f"{prev_hour}:55"
        if relative_expr == "ten to":
            # Ten to the next hour = current hour minus 10 minutes
            prev_hour = hour - 1 if hour > 1 else 12
            return f"{prev_hour}:50"
        if relative_expr == "twenty to":
            # Twenty to the next hour = current hour minus 20 minutes
            prev_hour = hour - 1 if hour > 1 else 12
            return f"{prev_hour}:40"
        if relative_expr == "twenty-five to":
            # Twenty-five to the next hour = current hour minus 25 minutes
            prev_hour = hour - 1 if hour > 1 else 12
            return f"{prev_hour}:35"

        return entity.text

    def convert_fraction(self, entity: Entity) -> str:
        """Convert fraction expressions (one half -> ½) and decimal numbers (three point one four -> 3.14)."""
        if not entity.metadata:
            return entity.text

        # Handle decimal numbers (e.g., "three point one four" -> "3.14")
        if entity.metadata.get("is_decimal"):
            return self.number_parser.parse(entity.text) or entity.text

        numerator_word = entity.metadata.get("numerator_word", "").lower()
        denominator_word = entity.metadata.get("denominator_word", "").lower()

        # Map number words to digits
        num_map = {
            "one": "1",
            "two": "2",
            "three": "3",
            "four": "4",
            "five": "5",
            "six": "6",
            "seven": "7",
            "eight": "8",
            "nine": "9",
            "ten": "10",
        }

        # Map denominator words to numbers
        denom_map = {
            "half": "2",
            "halves": "2",
            "third": "3",
            "thirds": "3",
            "quarter": "4",
            "quarters": "4",
            "fourth": "4",
            "fourths": "4",
            "fifth": "5",
            "fifths": "5",
            "sixth": "6",
            "sixths": "6",
            "seventh": "7",
            "sevenths": "7",
            "eighth": "8",
            "eighths": "8",
            "ninth": "9",
            "ninths": "9",
            "tenth": "10",
            "tenths": "10",
        }

        numerator = num_map.get(numerator_word)
        denominator = denom_map.get(denominator_word)

        if numerator and denominator:
            # Create the x/y format first
            fraction_str = f"{numerator}/{denominator}"

            # Map common fractions to Unicode equivalents
            unicode_fractions = {
                "1/2": "½",
                "1/3": "⅓",
                "2/3": "⅔",
                "1/4": "¼",
                "3/4": "¾",
                "1/5": "⅕",
                "2/5": "⅖",
                "3/5": "⅗",
                "4/5": "⅘",
                "1/6": "⅙",
                "5/6": "⅚",
                "1/7": "⅐",
                "1/8": "⅛",
                "3/8": "⅜",
                "5/8": "⅝",
                "7/8": "⅞",
                "1/9": "⅑",
                "1/10": "⅒",
            }

            # Return Unicode character if available, otherwise return x/y format
            return unicode_fractions.get(fraction_str, fraction_str)

        return entity.text

    def convert_numeric_range(self, entity: Entity) -> str:
        """Convert numeric range expressions (ten to twenty -> 10-20)."""
        if not entity.metadata:
            return entity.text

        start_word = entity.metadata.get("start_word", "").lower()
        end_word = entity.metadata.get("end_word", "").lower()

        # Use the number parser to convert words to numbers
        start_num = self.number_parser.parse(start_word)
        end_num = self.number_parser.parse(end_word)

        if start_num and end_num:
            result = f"{start_num}-{end_num}"

            # Add unit if present
            unit_type = entity.metadata.get("unit_type")
            if unit_type == "percent":
                result += "%"

            return result

        return entity.text

    def convert_version(self, entity: Entity) -> str:
        """Convert version numbers from spoken form to numeric form."""
        # Handle VERSION_THREE (keyword-only capitalization)
        if entity.type == EntityType.VERSION_THREE and entity.metadata and "capitalized" in entity.metadata:
            return entity.metadata["capitalized"]

        text = entity.text

        # Extract the prefix (version, python, etc.)
        prefix_match = re.match(r"^(\w+)\s+", text, re.IGNORECASE)
        if prefix_match:
            prefix = prefix_match.group(1)
            # Capitalize the prefix appropriately
            if prefix.lower() in ["v", "version", "python", "java", "node", "ruby", "php", "go", "rust", "dotnet", "gcc"]:
                if prefix.lower() in ["v", "version"]:
                    prefix = prefix.lower()  # Keep lowercase for version and v
                elif prefix.lower() in ["php", "gcc"]:
                    prefix = prefix.upper()
                else:
                    prefix = prefix.capitalize()
        else:
            prefix = ""

        # Get the groups from metadata
        if entity.metadata and "groups" in entity.metadata:
            groups = entity.metadata["groups"]

            # Convert each component
            parts = []
            for i, group in enumerate(groups):
                if group:
                    # Handle multi-word decimals like "one four" -> "14"
                    if " " in group and i > 0:  # This is a decimal part
                        decimal_digits = []
                        for word in group.split():
                            digit = self.number_parser.parse(word)
                            if digit and len(digit) <= 2 and digit.isdigit():  # Single or double digit
                                decimal_digits.append(digit)
                        if decimal_digits:
                            parts.append("".join(decimal_digits))
                        else:
                            # Fallback to regular parsing
                            parsed = self.number_parser.parse(group)
                            if parsed:
                                parts.append(parsed)
                    else:
                        # Try to parse the number normally
                        parsed = self.number_parser.parse(group)
                        if parsed:
                            parts.append(parsed)
                        elif group.isdigit():
                            parts.append(group)

            # Join with dots
            if parts:
                version_str = ".".join(parts)
                if prefix:
                    # No space for "v" prefix, space for others
                    separator = "" if prefix.lower() == "v" else " "
                    return f"{prefix}{separator}{version_str}"
                else:
                    return version_str

        # Fallback
        return entity.text

    def convert_measurement(self, entity: Entity, full_text: str = "") -> str:
        """Convert measurements to use proper symbols.

        Examples:
        - "six feet" → "6′"
        - "twelve inches" → "12″"
        - "5 foot 10" → "5′10″"
        - "three and a half feet" → "3.5′"
        - Also handles metric units and temperatures detected as QUANTITY

        """
        text = entity.text.lower()

        # First check if this is actually a temperature
        if "degrees" in text:
            # Check if this is an angle context (rotate, turn, angle, etc.) in the full text
            full_text_lower = full_text.lower() if full_text else ""
            angle_keywords = self.resources.get("context_words", {}).get("angle_keywords", [])
            if any(keyword in full_text_lower for keyword in angle_keywords):
                # This is an angle, not a temperature - return unchanged
                return entity.text
            # Also skip if there's no explicit unit (could be angle)
            if (
                not any(unit in text for unit in ["celsius", "centigrade", "fahrenheit", "c", "f"])
                and not full_text_lower
            ):
                return entity.text

            # Extract temperature parts
            import re

            temp_match = re.match(
                r"(?:(minus|negative)\s+)?"  # Optional sign
                r"(.*?)\s+degrees?"  # Number + degrees
                r"(?:\s+(celsius|centigrade|fahrenheit|c|f))?",  # Optional unit
                text,
                re.IGNORECASE,
            )
            if temp_match:
                sign = temp_match.group(1)
                number_text = temp_match.group(2)
                unit = temp_match.group(3)

                # Parse the number
                parsed_num = self.number_parser.parse(number_text)
                if parsed_num:
                    if sign:
                        parsed_num = f"-{parsed_num}"

                    if unit:
                        unit_lower = unit.lower()
                        if unit_lower in ["celsius", "centigrade", "c"]:
                            return f"{parsed_num}°C"
                        if unit_lower in ["fahrenheit", "f"]:
                            return f"{parsed_num}°F"

                    # No unit specified, just degrees symbol
                    return f"{parsed_num}°"

        # Check if this is a metric unit
        import re

        metric_match = re.match(
            r"(.*?)\s+(millimeters?|millimetres?|centimeters?|centimetres?|meters?|metres?|"
            r"kilometers?|kilometres?|milligrams?|grams?|kilograms?|metric\s+tons?|tonnes?|"
            r"milliliters?|millilitres?|liters?|litres?)",
            text,
            re.IGNORECASE,
        )
        if metric_match:
            number_text = metric_match.group(1)
            unit_text = metric_match.group(2).lower()

            # Handle decimal numbers
            decimal_match = re.match(r"(\w+)\s+point\s+(\w+)", number_text, re.IGNORECASE)
            if decimal_match:
                whole_part = self.number_parser.parse(decimal_match.group(1))
                decimal_part = self.number_parser.parse(decimal_match.group(2))
                if whole_part and decimal_part:
                    parsed_num = f"{whole_part}.{decimal_part}"
                else:
                    parsed_num = self.number_parser.parse(number_text)
            else:
                parsed_num = self.number_parser.parse(number_text)

            if parsed_num:
                # Map to standard abbreviations
                unit_map = {
                    # Length
                    "millimeter": "mm",
                    "millimeters": "mm",
                    "millimetre": "mm",
                    "millimetres": "mm",
                    "centimeter": "cm",
                    "centimeters": "cm",
                    "centimetre": "cm",
                    "centimetres": "cm",
                    "meter": "m",
                    "meters": "m",
                    "metre": "m",
                    "metres": "m",
                    "kilometer": "km",
                    "kilometers": "km",
                    "kilometre": "km",
                    "kilometres": "km",
                    # Weight
                    "milligram": "mg",
                    "milligrams": "mg",
                    "gram": "g",
                    "grams": "g",
                    "kilogram": "kg",
                    "kilograms": "kg",
                    "metric ton": "t",
                    "metric tons": "t",
                    "tonne": "t",
                    "tonnes": "t",
                    # Volume
                    "milliliter": "mL",
                    "milliliters": "mL",
                    "millilitre": "mL",
                    "millilitres": "mL",
                    "liter": "L",
                    "liters": "L",
                    "litre": "L",
                    "litres": "L",
                }

                standard_unit = unit_map.get(unit_text, unit_text.upper())
                return f"{parsed_num} {standard_unit}"

        # Original measurement conversion code continues...
        text = entity.text.lower()

        # Extract number and unit
        import re

        # Pattern for measurements with numbers (digits or words)
        # Match patterns like "six feet", "5 foot", "three and a half inches"
        patterns = [
            # "X and a half feet/inches"
            (r"(\w+)\s+and\s+a\s+half\s+(feet?|foot|inch(?:es)?)", "fraction"),
            # "X feet Y inches" (like "six feet two inches")
            (r"(\w+)\s+(feet?|foot)\s+(\w+)\s+(inch(?:es)?)", "feet_inches"),
            # "X foot Y" (like "5 foot 10" or "five foot ten")
            (r"(\w+)\s+foot\s+(\w+)", "height"),
            # "X miles/yards" (distance measurements)
            (r"(\w+)\s+(miles?|yards?)", "distance"),
            # "X pounds/ounces/lbs" (weight measurements)
            (r"(\w+)\s+(pounds?|lbs?|ounces?|oz)", "weight"),
            # "X feet/foot/inches/inch" (must come after compound patterns)
            (r"(\w+)\s+(feet?|foot|inch(?:es)?)", "simple"),
        ]

        for pattern, pattern_type in patterns:
            match = re.match(pattern, text, re.IGNORECASE)
            if match:
                if pattern_type == "fraction":
                    number_part = match.group(1)
                    unit = match.group(2)

                    # Parse the number
                    parsed_num = self.number_parser.parse(number_part)
                    if parsed_num:
                        # Add 0.5 for "and a half"
                        try:
                            num_value = float(parsed_num) + 0.5
                            number_str = str(num_value).rstrip("0").rstrip(".")
                        except:
                            number_str = f"{parsed_num}.5"
                    else:
                        return entity.text  # Fallback if can't parse

                    # Use proper symbols
                    if "inch" in unit:
                        return f"{number_str}″"
                    if "foot" in unit or "feet" in unit:
                        return f"{number_str}′"

                elif pattern_type == "simple":
                    number_part = match.group(1)
                    unit = match.group(2)

                    # Parse the number
                    parsed_num = self.number_parser.parse(number_part)
                    if not parsed_num:
                        return entity.text  # Fallback if can't parse

                    # Use proper symbols
                    if "inch" in unit:
                        return f"{parsed_num}″"
                    if "foot" in unit or "feet" in unit:
                        return f"{parsed_num}′"

                elif pattern_type == "feet_inches":
                    feet_part = match.group(1)
                    feet_unit = match.group(2)  # "feet" or "foot"
                    inches_part = match.group(3)
                    inches_unit = match.group(4)  # "inches" or "inch"

                    # Parse both parts
                    parsed_feet = self.number_parser.parse(feet_part)
                    parsed_inches = self.number_parser.parse(inches_part)

                    if parsed_feet and parsed_inches:
                        return f"{parsed_feet}′{parsed_inches}″"
                    return entity.text  # Fallback if can't parse

                elif pattern_type == "distance":
                    number_part = match.group(1)
                    unit = match.group(2)

                    # Parse the number
                    parsed_num = self.number_parser.parse(number_part)
                    if not parsed_num:
                        return entity.text  # Fallback if can't parse

                    # Convert to abbreviations
                    if "mile" in unit:
                        return f"{parsed_num} mi"
                    if "yard" in unit:
                        return f"{parsed_num} yd"

                elif pattern_type == "weight":
                    number_part = match.group(1)
                    unit = match.group(2)

                    # Parse the number
                    parsed_num = self.number_parser.parse(number_part)
                    if not parsed_num:
                        return entity.text  # Fallback if can't parse

                    # Convert to abbreviations (avoiding currency symbols)
                    if "pound" in unit or "lbs" in unit:
                        return f"{parsed_num} lbs"
                    if "ounce" in unit or "oz" in unit:
                        return f"{parsed_num} oz"

                elif pattern_type == "height":
                    feet_part = match.group(1)
                    inches_part = match.group(2)

                    # Parse both parts
                    parsed_feet = self.number_parser.parse(feet_part)
                    parsed_inches = self.number_parser.parse(inches_part)

                    if parsed_feet and parsed_inches:
                        return f"{parsed_feet}′{parsed_inches}″"
                    return entity.text  # Fallback if can't parse

        # Fallback
        return entity.text

    def convert_temperature(self, entity: Entity) -> str:
        """Convert temperature expressions to proper format.

        Examples:
        - "twenty degrees celsius" → "20°C"
        - "thirty two degrees fahrenheit" → "32°F"
        - "minus ten degrees" → "-10°"

        """
        if not entity.metadata:
            return entity.text

        sign = entity.metadata.get("sign")
        number_text = entity.metadata.get("number", "")
        unit = entity.metadata.get("unit")

        # Use the improved number parser that handles decimals automatically
        parsed_num = self.number_parser.parse(number_text)

        if not parsed_num:
            return entity.text

        # Add sign if present
        if sign:
            parsed_num = f"-{parsed_num}"

        # Format based on unit
        if unit:
            unit_lower = unit.lower()
            if unit_lower in ["celsius", "centigrade", "c"]:
                return f"{parsed_num}°C"
            if unit_lower in ["fahrenheit", "f"]:
                return f"{parsed_num}°F"

        # No unit specified, just degrees
        return f"{parsed_num}°"

    def convert_metric_unit(self, entity: Entity) -> str:
        """Convert metric units to standard abbreviations.

        Examples:
        - "five kilometers" → "5 km"
        - "two point five centimeters" → "2.5 cm"
        - "ten kilograms" → "10 kg"
        - "three liters" → "3 L"

        """
        if not entity.metadata:
            return entity.text

        number_text = entity.metadata.get("number", "")
        unit = entity.metadata.get("unit", "").lower()

        # Use the improved number parser that handles decimals automatically
        parsed_num = self.number_parser.parse(number_text)

        if not parsed_num:
            return entity.text

        # Unit mappings
        unit_map = {
            # Length
            "millimeter": "mm",
            "millimeters": "mm",
            "millimetre": "mm",
            "millimetres": "mm",
            "mm": "mm",
            "centimeter": "cm",
            "centimeters": "cm",
            "centimetre": "cm",
            "centimetres": "cm",
            "cm": "cm",
            "meter": "m",
            "meters": "m",
            "metre": "m",
            "metres": "m",
            "m": "m",
            "kilometer": "km",
            "kilometers": "km",
            "kilometre": "km",
            "kilometres": "km",
            "km": "km",
            # Weight
            "milligram": "mg",
            "milligrams": "mg",
            "mg": "mg",
            "gram": "g",
            "grams": "g",
            "g": "g",
            "kilogram": "kg",
            "kilograms": "kg",
            "kg": "kg",
            "metric ton": "t",
            "metric tons": "t",
            "tonne": "t",
            "tonnes": "t",
            # Volume
            "milliliter": "mL",
            "milliliters": "mL",
            "millilitre": "mL",
            "millilitres": "mL",
            "ml": "mL",
            "liter": "L",
            "liters": "L",
            "litre": "L",
            "litres": "L",
            "l": "L",
        }

        standard_unit = unit_map.get(unit, unit.upper())
        return f"{parsed_num} {standard_unit}"

    def convert_root_expression(self, entity: Entity) -> str:
        """Convert root expressions to mathematical notation.

        Examples:
        - "square root of sixteen" → "√16"
        - "cube root of twenty seven" → "∛27"
        - "square root of x plus one" → "√(x + 1)"

        """
        if not entity.metadata:
            return entity.text

        root_type = entity.metadata.get("root_type", "")
        expression = entity.metadata.get("expression", "")

        # Process the expression
        # First, try to parse it as a number
        parsed_num = self.number_parser.parse(expression)
        if parsed_num:
            # Simple number
            if root_type == "square":
                return f"√{parsed_num}"
            if root_type == "cube":
                return f"∛{parsed_num}"

        # Otherwise, it might be a more complex expression
        # Convert any number words in the expression
        words = expression.split()
        converted_words = []
        for word in words:
            # Try to parse as number
            num = self.number_parser.parse(word)
            if num:
                converted_words.append(num)
            # Convert operators
            elif word.lower() == "plus":
                converted_words.append("+")
            elif word.lower() == "minus":
                converted_words.append("-")
            elif word.lower() == "times":
                converted_words.append("×")
            elif word.lower() == "over":
                converted_words.append("/")
            else:
                converted_words.append(word)

        # Join the converted expression
        converted_expr = " ".join(converted_words)

        # Add parentheses if expression contains operators
        if any(op in converted_expr for op in ["+", "-", "×", "/"]):
            if root_type == "square":
                return f"√({converted_expr})"
            if root_type == "cube":
                return f"∛({converted_expr})"
        elif root_type == "square":
            return f"√{converted_expr}"
        elif root_type == "cube":
            return f"∛{converted_expr}"

        # Fallback
        return entity.text

    def convert_math_constant(self, entity: Entity) -> str:
        """Convert mathematical constants to their symbols.

        Examples:
        - "pi" → "π"
        - "infinity" → "∞"

        """
        if not entity.metadata:
            return entity.text

        constant = entity.metadata.get("constant", "").lower()

        # Constant mappings
        constant_map = {
            "pi": "π",
            "infinity": "∞",
            "inf": "∞",
        }

        return constant_map.get(constant, entity.text)

    def convert_scientific_notation(self, entity: Entity) -> str:
        """Convert scientific notation to proper format.

        Examples:
        - "two point five times ten to the sixth" → "2.5 × 10⁶"
        - "three times ten to the negative four" → "3 × 10⁻⁴"

        """
        if not entity.metadata:
            return entity.text

        base = entity.metadata.get("base", "")
        exponent = entity.metadata.get("exponent", "")

        # Parse the base number
        parsed_base = self.number_parser.parse(base)
        if not parsed_base:
            # Try handling "point" for decimals
            if "point" in base.lower():
                parts = base.lower().split("point")
                if len(parts) == 2:
                    whole = self.number_parser.parse(parts[0].strip())
                    # Handle decimal part that might be multiple digits like "zero two"
                    decimal_part = parts[1].strip()
                    decimal_digits = []
                    for word in decimal_part.split():
                        digit = self.number_parser.parse(word)
                        if digit:
                            decimal_digits.append(digit)
                    if whole and decimal_digits:
                        parsed_base = f"{whole}.{''.join(decimal_digits)}"

            if not parsed_base:
                return entity.text

        # Parse the exponent
        is_negative = False
        exp_text = exponent.lower()

        # Check for negative exponent
        if "negative" in exp_text or "minus" in exp_text:
            is_negative = True
            exp_text = exp_text.replace("negative", "").replace("minus", "").strip()

        # Parse the exponent number
        parsed_exp = self.number_parser.parse(exp_text)

        # If number parser fails, try ordinal parsing
        if not parsed_exp:
            parsed_exp = self.number_parser.parse_ordinal(exp_text)

        if not parsed_exp:
            return entity.text

        # Convert to superscript
        superscript_map = {
            "0": "⁰",
            "1": "¹",
            "2": "²",
            "3": "³",
            "4": "⁴",
            "5": "⁵",
            "6": "⁶",
            "7": "⁷",
            "8": "⁸",
            "9": "⁹",
            "-": "⁻",
        }

        # Build superscript exponent
        superscript_exp = ""
        if is_negative:
            superscript_exp = "⁻"

        for digit in str(parsed_exp):
            superscript_exp += superscript_map.get(digit, digit)

        # Format the result
        return f"{parsed_base} × 10{superscript_exp}"

    def convert_music_notation(self, entity: Entity) -> str:
        """Convert music notation to symbols.

        Examples:
        - "C sharp" → "C♯"
        - "B flat" → "B♭"
        - "E natural" → "E♮"

        """
        if not entity.metadata:
            return entity.text

        note = entity.metadata.get("note", "")
        accidental = entity.metadata.get("accidental", "")

        accidental_map = {"sharp": "♯", "flat": "♭", "natural": "♮"}

        symbol = accidental_map.get(accidental, "")
        if symbol:
            return f"{note}{symbol}"

        return entity.text

    def convert_spoken_emoji(self, entity: Entity) -> str:
        """Convert spoken emoji expressions to emoji characters.

        Examples:
        - "smiley face" → "🙂"
        - "rocket emoji" → "🚀"

        """
        if not entity.metadata:
            return entity.text

        emoji_key = entity.metadata.get("emoji_key", "").lower()
        is_implicit = entity.metadata.get("is_implicit", False)

        if is_implicit:
            # Look up in implicit map
            emoji = regex_patterns.SPOKEN_EMOJI_IMPLICIT_MAP.get(emoji_key)
        else:
            # Look up in explicit map
            emoji = regex_patterns.SPOKEN_EMOJI_EXPLICIT_MAP.get(emoji_key)

        if emoji:
            # The detection regex now captures trailing punctuation in the entity text
            # Preserve it after conversion.
            trailing_punct = re.search(r"([.!?]*)$", entity.text).group(1)
            return emoji + trailing_punct

        return entity.text
