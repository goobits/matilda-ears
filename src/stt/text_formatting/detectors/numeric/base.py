#!/usr/bin/env python3
"""Base classes and utilities for numeric entity detection."""
from __future__ import annotations

import re
from typing import Any

from stt.core.config import setup_logging
from stt.text_formatting.constants import get_nested_resource

logger = setup_logging(__name__)

# Math expression parsing
try:
    from pyparsing import (
        Optional as OptionalPP,
    )
    from pyparsing import (
        ParseException,
        Word,
        alphanums,
        alphas,
        infixNotation,
        nums,
        oneOf,
        opAssoc,
    )

    PYPARSING_AVAILABLE = True
except ImportError:
    PYPARSING_AVAILABLE = False


class MathExpressionParser:
    """Robust math expression parser using pyparsing"""

    def __init__(self, language: str = "en"):
        if not PYPARSING_AVAILABLE:
            raise ImportError("pyparsing is required but not available")
        
        self.language = language
        
        # Cache for loaded mathematical terms
        self._math_constants_cache = None
        self._power_expressions_cache = None
        self._operators_cache = None

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

            # Define mathematical constants (from resources)
            constants_list = self._get_math_constants()
            math_constants = oneOf(constants_list)
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

            # Define power expressions (from resources)
            power_expressions = self._get_power_expressions()
            power_word = oneOf(power_expressions)
            powered_expr = operand + OptionalPP(power_word + OptionalPP(number))

            # Define operators (from resources)
            operators = self._get_math_operators()
            plus_op = oneOf(operators["plus"])
            minus_op = oneOf(operators["minus"])
            times_op = oneOf(operators["times"])
            div_op = oneOf(operators["div"])
            equals_op = oneOf(operators["equals"])

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
    
    def _get_math_constants(self) -> list[str]:
        """Get mathematical constants from resources with fallback."""
        if self._math_constants_cache is not None:
            return self._math_constants_cache
        
        try:
            constants_dict = get_nested_resource(self.language, "spoken_keywords", "mathematical", "constants")
            constants = list(constants_dict.keys())
            self._math_constants_cache = constants
            return constants
        except (KeyError, ValueError) as e:
            logger.debug(f"Failed to load math constants from resources for {self.language}: {e}")
            # Fallback to hardcoded constants
            fallback = ["pi", "e", "infinity", "inf"]
            self._math_constants_cache = fallback
            return fallback
    
    def _get_power_expressions(self) -> list[str]:
        """Get power expressions from resources with fallback."""
        if self._power_expressions_cache is not None:
            return self._power_expressions_cache
        
        try:
            operations_dict = get_nested_resource(self.language, "spoken_keywords", "mathematical", "operations")
            # Extract power-related operations
            power_ops = []
            for key, value in operations_dict.items():
                if value in ["²", "³", "^"]:
                    power_ops.append(key)
            self._power_expressions_cache = power_ops
            return power_ops
        except (KeyError, ValueError) as e:
            logger.debug(f"Failed to load power expressions from resources for {self.language}: {e}")
            # Fallback to hardcoded expressions
            fallback = ["squared", "cubed", "to the power of"]
            self._power_expressions_cache = fallback
            return fallback
    
    def _get_math_operators(self) -> dict[str, list[str]]:
        """Get mathematical operators from resources with fallback."""
        if self._operators_cache is not None:
            return self._operators_cache
        
        try:
            operations_dict = get_nested_resource(self.language, "spoken_keywords", "mathematical", "operations")
            
            # Group operators by type
            operators = {
                "plus": [],
                "minus": [],
                "times": [],
                "div": [],
                "equals": []
            }
            
            for key, value in operations_dict.items():
                if value == "+":
                    operators["plus"].append(key)
                elif value == "-":
                    operators["minus"].append(key)
                elif value == "×":
                    operators["times"].append(key)
                elif value in ["/", "÷"]:
                    operators["div"].append(key)
                elif value == "=":
                    operators["equals"].append(key)
            
            # Add symbol fallbacks
            operators["plus"].extend(["+"])
            operators["minus"].extend(["-"])
            operators["times"].extend(["*", "×"])
            operators["div"].extend(["/", "÷"])
            operators["equals"].extend(["="])
            
            self._operators_cache = operators
            return operators
        except (KeyError, ValueError) as e:
            logger.debug(f"Failed to load math operators from resources for {self.language}: {e}")
            # Fallback to hardcoded operators
            fallback = {
                "plus": ["plus", "+"],
                "minus": ["minus", "-"],
                "times": ["times", "multiplied by", "*", "×"],
                "div": ["divided by", "over", "/", "÷"],
                "equals": ["equals", "is", "="]
            }
            self._operators_cache = fallback
            return fallback

    def parse_expression(self, text: str) -> dict[str, Any] | None:
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


def is_idiomatic_over_expression(expr: str, full_text: str, start_pos: int) -> bool:
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