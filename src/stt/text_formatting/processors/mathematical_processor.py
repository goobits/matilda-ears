"""
Mathematical entity processor combining detection and conversion.

This module migrates MathematicalExpressionDetector and MathematicalConverter 
to the new EntityProcessor pattern, providing a unified abstraction for 
mathematical expression handling including math expressions, root expressions,
mathematical constants, scientific notation, negative numbers, and powers.
"""

import re
from typing import Dict, List, Any, Optional, Pattern

from stt.text_formatting.entity_processor import BaseNumericProcessor, ProcessingRule
from stt.text_formatting.common import Entity, EntityType
from stt.text_formatting.spacy_doc_cache import get_global_doc_processor
from stt.text_formatting.utils import is_inside_entity
from stt.text_formatting.detectors.numeric.base import MathExpressionParser, is_idiomatic_over_expression
from stt.text_formatting import pattern_modules
from stt.text_formatting.pattern_modules.basic_numeric_patterns import build_ordinal_pattern
from stt.text_formatting.priority_config import ProcessorType, get_current_config
from stt.text_formatting.constants import get_nested_resource
from stt.core.config import setup_logging

logger = setup_logging(__name__)


class MathematicalProcessor(BaseNumericProcessor):
    """Processor for mathematical entities (expressions, roots, constants, scientific notation)."""
    
    def __init__(self, nlp=None, language: str = "en"):
        """Initialize mathematical processor."""
        super().__init__(nlp, language)
        
        # Initialize math expression parser
        try:
            self.math_parser = MathExpressionParser(language=language)
        except ImportError:
            self.math_parser = None
        
        # Apply priority configuration
        config = get_current_config()
        config.apply_to_processor(self, ProcessorType.MATHEMATICAL)
    
    def _init_detection_rules(self) -> List[ProcessingRule]:
        """Initialize detection rules for mathematical entities."""
        rules = []
        
        # Build number pattern for reuse
        number_pattern = self._build_number_pattern()
        
        # 1. Math expressions (with pyparsing validation) - Highest priority
        rules.append(ProcessingRule(
            pattern=pattern_modules.get_complex_math_expression_pattern(self.language),
            entity_type=EntityType.MATH_EXPRESSION,
            metadata_extractor=self._extract_complex_math_metadata,
            context_filters=[self._filter_idiomatic_over, self._filter_idiomatic_spacy],
            priority=120
        ))
        
        rules.append(ProcessingRule(
            pattern=pattern_modules.get_simple_math_expression_pattern(self.language),
            entity_type=EntityType.MATH_EXPRESSION,
            metadata_extractor=self._extract_simple_math_metadata,
            context_filters=[self._filter_increment_decrement],
            priority=118
        ))
        
        # Special case: number + constant pattern (e.g., "two pi")
        rules.append(ProcessingRule(
            pattern=pattern_modules.get_number_constant_pattern(self.language),
            entity_type=EntityType.MATH_EXPRESSION,
            metadata_extractor=self._extract_number_constant_metadata,
            priority=115
        ))
        
        # 2. Root expressions (square/cube root)
        rules.append(ProcessingRule(
            pattern=re.compile(r"\b(square|cube)\s+root\s+of\s+([\w\s+\-*/]+)\b", re.IGNORECASE),
            entity_type=EntityType.ROOT_EXPRESSION,
            metadata_extractor=self._extract_root_metadata,
            priority=113
        ))
        
        # 3. Mathematical constants (from resources)
        rules.append(ProcessingRule(
            pattern=self._build_math_constants_pattern(),
            entity_type=EntityType.MATH_CONSTANT,
            metadata_extractor=self._extract_constant_metadata,
            priority=110
        ))
        
        # 4. Scientific notation
        rules.append(ProcessingRule(
            pattern=self._build_scientific_notation_pattern(),
            entity_type=EntityType.SCIENTIFIC_NOTATION,
            metadata_extractor=self._extract_scientific_metadata,
            priority=108
        ))
        
        # 5. Negative numbers
        rules.append(ProcessingRule(
            pattern=re.compile(
                r"\b(negative|minus)\s+(" + number_pattern + r")\b",
                re.IGNORECASE
            ),
            entity_type=EntityType.MATH_EXPRESSION,
            metadata_extractor=self._extract_negative_metadata,
            priority=105
        ))
        
        # 6. Roots and powers (x squared, etc.)
        # Simple power expressions like "x squared", "five cubed"
        rules.append(ProcessingRule(
            pattern=re.compile(
                r"\b(" + number_pattern + r"|[a-zA-Z]+)\s+(squared|cubed)\b",
                re.IGNORECASE
            ),
            entity_type=EntityType.MATH_EXPRESSION,
            metadata_extractor=self._extract_simple_power_metadata,
            priority=103
        ))
        
        # Complex power expressions like "two to the fourth power"
        # Include ordinals for power expressions - get from mapping registry directly
        ordinal_mappings = self.mapping_registry.get_ordinal_word_to_numeric()
        ordinal_words = list(ordinal_mappings.keys())
        ordinal_pattern = r"(?:" + "|".join(sorted(ordinal_words, key=len, reverse=True)) + r")"
        power_number_pattern = f"(?:{number_pattern}|{ordinal_pattern})"
        
        rules.append(ProcessingRule(
            pattern=re.compile(
                r"\b(" + number_pattern + r"|[a-zA-Z]+)\s+to\s+the\s+(" + power_number_pattern + r")\s+power\b",
                re.IGNORECASE
            ),
            entity_type=EntityType.MATH_EXPRESSION,
            metadata_extractor=self._extract_complex_power_metadata,
            priority=100
        ))
        
        return rules
    
    def _init_conversion_methods(self) -> Dict[EntityType, str]:
        """Initialize conversion methods for mathematical types."""
        return {
            EntityType.MATH_EXPRESSION: "convert_math_expression",
            EntityType.ROOT_EXPRESSION: "convert_root_expression",
            EntityType.MATH_CONSTANT: "convert_math_constant",
            EntityType.SCIENTIFIC_NOTATION: "convert_scientific_notation",
        }
    
    # Pattern builders
    
    def _build_math_constants_pattern(self) -> Pattern[str]:
        """Build pattern for mathematical constants from resources."""
        try:
            constants_dict = get_nested_resource(self.language, "spoken_keywords", "mathematical", "constants")
            constants_list = list(constants_dict.keys())
            pattern_str = r"\b(" + "|".join(re.escape(c) for c in constants_list) + r")\b"
            return re.compile(pattern_str, re.IGNORECASE)
        except (KeyError, ValueError) as e:
            logger.debug(f"Failed to load math constants from resources for {self.language}: {e}")
            # Fallback to hardcoded pattern
            return re.compile(r"\b(pi|infinity|inf)\b", re.IGNORECASE)
    
    def _build_number_pattern(self) -> str:
        """Build pattern for number words."""
        return r"(?:" + "|".join(sorted(self.number_parser.all_number_words, key=len, reverse=True)) + r")"
    
    def _get_ordinal_pattern_string(self) -> str:
        """Get ordinal pattern string, with fallback to hardcoded pattern for regex building."""
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
    
    def _build_scientific_notation_pattern(self) -> Pattern[str]:
        """Build pattern for scientific notation expressions."""
        number_pattern = self._build_number_pattern()
        
        # Pattern for ordinals in exponents (uses fallback pattern for regex building)
        ordinal_pattern = self._get_ordinal_pattern_string()
        
        return re.compile(
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
    
    # Metadata extractors
    
    def _extract_complex_math_metadata(self, match: re.Match) -> Dict[str, Any]:
        """Extract metadata from complex math expression matches using pyparsing."""
        if not self.math_parser:
            return {"parsed": match.group().split(), "type": "COMPLEX_MATH"}
        
        potential_expr = match.group()
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
            return math_result
        else:
            # Fallback for when pyparsing fails
            return {"parsed": words, "type": "COMPLEX_MATH"}
    
    def _extract_simple_math_metadata(self, match: re.Match) -> Dict[str, Any]:
        """Extract metadata from simple math expression matches."""
        if not self.math_parser:
            return {"parsed": match.group().split(), "type": "SIMPLE_MATH"}
        
        potential_expr = match.group()
        clean_expr = potential_expr.rstrip(".!?")
        
        # Pre-process for math parser
        words = clean_expr.split()
        converted_words = []
        for word in words:
            parsed = self.number_parser.parse(word)
            if parsed:
                converted_words.append(parsed)
            elif word.lower() == "slash":
                converted_words.append("/")
            elif word.lower() == "times":
                converted_words.append("×")
            elif word.lower() == "over":
                converted_words.append("/")
            else:
                converted_words.append(word)
        
        preprocessed_expr = " ".join(converted_words)
        math_result = self.math_parser.parse_expression(preprocessed_expr)
        
        if math_result:
            return math_result
        else:
            return {"parsed": words, "type": "SIMPLE_MATH"}
    
    def _extract_number_constant_metadata(self, match: re.Match) -> Dict[str, Any]:
        """Extract metadata from number + constant matches."""
        return {"parsed": match.group().split(), "type": "NUMBER_CONSTANT"}
    
    def _extract_root_metadata(self, match: re.Match) -> Dict[str, Any]:
        """Extract metadata from root expression matches."""
        root_type = match.group(1).lower()
        expression = match.group(2).strip()
        
        return {"root_type": root_type, "expression": expression}
    
    def _extract_constant_metadata(self, match: re.Match) -> Dict[str, Any]:
        """Extract metadata from mathematical constant matches."""
        constant = match.group(1).lower()
        return {"constant": constant}
    
    def _extract_scientific_metadata(self, match: re.Match) -> Dict[str, Any]:
        """Extract metadata from scientific notation matches."""
        base_number = match.group(1).strip()
        exponent = match.group(2).strip()
        
        return {"base": base_number, "exponent": exponent}
    
    def _extract_negative_metadata(self, match: re.Match) -> Dict[str, Any]:
        """Extract metadata from negative number matches."""
        sign = match.group(1).lower()
        number_text = match.group(2)
        
        return {"sign": sign, "number": number_text}
    
    def _extract_simple_power_metadata(self, match: re.Match) -> Dict[str, Any]:
        """Extract metadata from simple power matches (x squared, five cubed)."""
        base = match.group(1)
        power_word = match.group(2).lower()
        power = "2" if power_word == "squared" else "3"
        
        return {"base": base, "power": power}
    
    def _extract_complex_power_metadata(self, match: re.Match) -> Dict[str, Any]:
        """Extract metadata from complex power matches (two to the fourth power)."""
        base = match.group(1)
        power = match.group(2)
        
        return {"base": base, "power": power}
    
    # Context filters
    
    def _filter_idiomatic_over(self, text: str, start: int, end: int) -> bool:
        """Filter expressions with idiomatic use of 'over'."""
        expr = text[start:end]
        return not is_idiomatic_over_expression(expr, text, start)
    
    def _filter_idiomatic_spacy(self, text: str, start: int, end: int) -> bool:
        """Filter expressions based on SpaCy grammatical analysis."""
        if not self.nlp:
            return True  # No filtering if SpaCy unavailable
        
        expr = text[start:end]
        return not self._is_idiomatic_expression_spacy(expr, text, start, end)
    
    def _filter_increment_decrement(self, text: str, start: int, end: int) -> bool:
        """Filter increment/decrement operators (word++ / word--)."""
        potential_expr = text[start:end]
        
        # Skip if this looks like an increment/decrement operator
        if re.match(r"^\w+\s+plus\s+plus[.!?]?$", potential_expr, re.IGNORECASE) or re.match(
            r"^\w+\s+minus\s+minus[.!?]?$", potential_expr, re.IGNORECASE
        ):
            return False
        
        return True
    
    def _is_idiomatic_expression_spacy(self, expr: str, full_text: str, start_pos: int, end_pos: int) -> bool:
        """
        Use SpaCy POS tagging to determine if an expression is mathematical or idiomatic.

        This method uses grammatical analysis instead of hardcoded word lists to detect
        when 'plus' is used idiomatically (e.g., 'two plus years') rather than mathematically.
        It checks if 'plus' is preceded by a number and followed by a noun, which indicates
        idiomatic usage like 'five plus years of experience'.
        """
        # Use centralized document processor for better caching
        doc_processor = get_global_doc_processor()
        if not doc_processor:
            return False
        
        doc = doc_processor.get_or_create_doc(full_text)
        if not doc:
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

            # Check the POS tag of the word after "plus" or "times"
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
                        return True  # It's an idiomatic phrase, not math.

            return False

        except (AttributeError, IndexError, ValueError):
            # SpaCy analysis failed, assume mathematical
            return False
    
    # Conversion methods
    
    def convert_math_expression(self, entity: Entity, full_text: str = "") -> str:
        """Convert parsed math expressions to properly formatted text."""
        if not entity.metadata:
            return entity.text
        
        # Handle negative numbers special case
        if "sign" in entity.metadata and "number" in entity.metadata:
            sign = entity.metadata["sign"]
            number = entity.metadata["number"]
            parsed_num = self.number_parser.parse(number)
            if parsed_num:
                return f"-{parsed_num}"
            else:
                return entity.text
        
        # Handle power expressions
        if "base" in entity.metadata and "power" in entity.metadata:
            base = entity.metadata["base"]
            power = entity.metadata["power"]
            
            # Try to parse base as number
            parsed_base = self.number_parser.parse(base)
            if not parsed_base:
                parsed_base = base  # Keep as variable
            
            # Convert power to superscript
            if power == "2":
                return f"{parsed_base}²"
            elif power == "3":
                return f"{parsed_base}³"
            else:
                parsed_power = self.number_parser.parse(power)
                if not parsed_power:
                    # Try parsing as ordinal
                    parsed_power = self.number_parser.parse_ordinal(power)
                
                if parsed_power:
                    superscript_power = self.convert_to_superscript(parsed_power)
                    return f"{parsed_base}{superscript_power}"
        
        # Standard parsed expression handling
        if "parsed" not in entity.metadata:
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
            # but not for division operator when it's a simple expression
            if "/" in result and len(result_parts) == 3:  # Simple division like "10 / 5"
                result = re.sub(r"\s*/\s*", "/", result).strip()
            else:
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
            return entity.text
    
    def _convert_math_token(self, token: str) -> str:
        """Convert individual math tokens."""
        token_lower = str(token).lower()

        # Convert operators from resources first
        try:
            operations_dict = get_nested_resource(self.language, "spoken_keywords", "mathematical", "operations")
            if token_lower in operations_dict:
                return operations_dict[token_lower]
        except (KeyError, ValueError):
            logger.debug(f"Failed to load math operations from resources for {self.language}")
        
        # Fallback to hardcoded operator mappings
        if token_lower in self.operator_mappings:
            return self.operator_mappings[token_lower]

        # Convert number words
        parsed_num = self.number_parser.parse(token_lower)
        if parsed_num:
            return parsed_num

        # Handle math constants from resources first
        try:
            constants_dict = get_nested_resource(self.language, "spoken_keywords", "mathematical", "constants")
            if token_lower in constants_dict:
                return constants_dict[token_lower]
        except (KeyError, ValueError):
            logger.debug(f"Failed to load math constants from resources for {self.language}")
        
        # Fallback to hardcoded math constant mappings
        if token_lower in self.math_constant_mappings:
            return self.math_constant_mappings[token_lower]

        # Preserve case for variables
        if str(token).isalpha():
            # Keep variables as-is (preserve original case)
            # Single letters like 'r', 'x', 'y' stay lowercase in math
            # Multi-letter variables preserve their original case
            return str(token)

        # Return as-is (other tokens)
        return str(token)
    
    def convert_root_expression(self, entity: Entity, full_text: str = "") -> str:
        """
        Convert root expressions to mathematical notation.

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
    
    def convert_math_constant(self, entity: Entity, full_text: str = "") -> str:
        """
        Convert mathematical constants to their symbols.

        Examples:
        - "pi" → "π"
        - "infinity" → "∞"
        """
        if not entity.metadata:
            return entity.text

        constant = entity.metadata.get("constant", "").lower()

        # Try to get the constant from resources first
        try:
            constants_dict = get_nested_resource(self.language, "spoken_keywords", "mathematical", "constants")
            if constant in constants_dict:
                return constants_dict[constant]
        except (KeyError, ValueError):
            logger.debug(f"Failed to load math constants from resources for {self.language}")
        
        # Fallback to hardcoded mappings, then original text
        return self.math_constant_mappings.get(constant, entity.text)
    
    def convert_scientific_notation(self, entity: Entity, full_text: str = "") -> str:
        """
        Convert scientific notation to proper format.

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

        # Build superscript exponent
        superscript_exp = ""
        if is_negative:
            superscript_exp = "⁻"

        superscript_exp += self.convert_to_superscript(str(parsed_exp))

        # Format the result
        return f"{parsed_base} × 10{superscript_exp}"