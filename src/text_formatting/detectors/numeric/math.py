#!/usr/bin/env python3
"""Math expression detection and parsing for numeric entity detection."""

import re
from typing import List, Optional, Dict, Any
from ...common import Entity, EntityType, NumberParser
from ...utils import is_inside_entity
from ....core.config import setup_logging
from ... import regex_patterns

logger = setup_logging(__name__, log_filename="text_formatting.txt")


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


class MathDetector:
    """Detector for math expressions, constants, roots, and scientific notation."""

    def __init__(self, nlp=None, number_parser: NumberParser = None, resources: dict = None):
        """Initialize MathDetector.

        Args:
            nlp: SpaCy NLP model instance.
            number_parser: NumberParser instance for number word handling.
            resources: Language-specific resources dictionary.
        """
        self.nlp = nlp
        self.number_parser = number_parser
        self.resources = resources or {}
        self.math_parser = MathExpressionParser()

    def detect_math_expressions(
        self, text: str, entities: List[Entity], all_entities: Optional[List[Entity]] = None
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
                parsed = self.number_parser.parse(word) if self.number_parser else None
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

    def detect_math_constants(
        self, text: str, entities: List[Entity], all_entities: Optional[List[Entity]] = None
    ) -> None:
        """Detect mathematical constants.

        Examples:
        - "pi" -> "pi" (will be converted to symbol by converter)
        - "infinity" -> "infinity"

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

    def detect_root_expressions(
        self, text: str, entities: List[Entity], all_entities: Optional[List[Entity]] = None
    ) -> None:
        """Detect square root and cube root expressions.

        Examples:
        - "square root of sixteen" -> "sqrt(16)"
        - "cube root of twenty seven" -> "cbrt(27)"

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

    def detect_scientific_notation(
        self, text: str, entities: List[Entity], all_entities: Optional[List[Entity]] = None
    ) -> None:
        """Detect scientific notation expressions.

        Examples:
        - "two point five times ten to the sixth" -> "2.5 x 10^6"
        - "three times ten to the negative four" -> "3 x 10^-4"

        """
        if not self.number_parser:
            return

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
