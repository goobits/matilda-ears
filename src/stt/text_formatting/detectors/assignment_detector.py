#!/usr/bin/env python3
"""Assignment and operator-related entity detection for code transcriptions."""
from __future__ import annotations

import re

from stt.core.config import setup_logging
from stt.text_formatting.pattern_modules.code_patterns import get_assignment_pattern
from stt.text_formatting.common import Entity, EntityType
from stt.text_formatting.constants import get_resources, get_nested_resource
from stt.text_formatting.utils import is_inside_entity

logger = setup_logging(__name__)


class AssignmentDetector:
    """Detects assignment and operator-related entities."""

    def __init__(self, nlp=None, language: str = "en"):
        """
        Initialize AssignmentDetector.

        Args:
            nlp: SpaCy NLP model instance. If None, will load from nlp_provider.
            language: Language code for resource loading (default: 'en')
        """
        if nlp is None:
            from stt.text_formatting.nlp_provider import get_nlp

            nlp = get_nlp()

        self.nlp = nlp
        self.language = language
        self.resources = get_resources(language)

        # Build patterns dynamically for the specified language
        self.assignment_pattern = get_assignment_pattern(language)

    def detect_assignment_operators(
        self, text: str, entities: list[Entity], all_entities: list[Entity] | None = None
    ) -> None:
        """
        Detects assignment operators like 'x equals 5' -> 'x=5' or 'let x equals 5' -> 'let x=5'.

        This method identifies patterns where a variable name is followed by 'equals'
        and then a value, capturing the entire phrase until punctuation or end of line.
        The pattern allows for number words like 'twenty five' to be captured properly.
        Also supports variable declaration keywords like 'let', 'const', and 'var'.

        Args:
            text: The text to search for assignment patterns
            entities: List to append detected assignment entities to
            all_entities: Complete list of entities for overlap checking

        """
        # This pattern looks for optional keyword, variable name, 'equals', and then captures everything after
        assignment_pattern = self.assignment_pattern
        for match in assignment_pattern.finditer(text):
            check_entities = all_entities if all_entities else entities
            if not is_inside_entity(match.start(), match.end(), check_entities):
                entities.append(
                    Entity(
                        start=match.start(),
                        end=match.end(),
                        text=match.group(0),
                        type=EntityType.ASSIGNMENT,
                        metadata={
                            "keyword": match.group(1),  # Optional keyword (let, const, var)
                            "left": match.group(2),  # Variable name
                            "right": match.group(3),  # Value
                        },
                    )
                )

    def detect_spoken_operators(
        self, text: str, entities: list[Entity], all_entities: list[Entity] | None = None
    ) -> None:
        """
        Detect spoken operators using SpaCy token context analysis.

        This method detects patterns like "variable plus plus" or "count minus minus"
        using token analysis to ensure they're used in valid programming contexts.
        """
        if not self.nlp:
            logger.debug("SpaCy not available for spoken operator detection, using regex fallback")
            self._detect_spoken_operators_regex(text, entities, all_entities)
            return
        # Use shared document processor for optimal caching
        from ..spacy_doc_cache import get_or_create_shared_doc
        try:
            doc = get_or_create_shared_doc(text, nlp_model=self.nlp)
            if doc is None:
                raise ValueError("SpaCy document creation failed")
        except (AttributeError, ValueError, IndexError) as e:
            logger.warning(f"SpaCy operator detection failed: {e}")
            return
        logger.debug(f"Processing text for operators: '{text}'")

        # Setup operator patterns
        operator_patterns = self._setup_operator_patterns()

        # Detect two-word and three-word operators
        self._detect_two_word_operators(doc, operator_patterns, entities, all_entities, text)
        self._detect_three_word_operators(doc, operator_patterns, entities, all_entities, text)

    def _setup_operator_patterns(self):
        """Setup operator patterns from language resources."""
        # Get operator keywords for the current language
        operators = get_nested_resource(self.language, "spoken_keywords", "operators")

        # Build a map of operator patterns to their symbols
        operator_patterns = {}
        for pattern, symbol in operators.items():
            operator_patterns[pattern.lower()] = symbol
        
        return operator_patterns

    def _validate_variable_token(self, token):
        """Validate if a token can be a valid variable name."""
        # Check if the preceding token is a valid variable name
        # Include single letter pronouns like 'i' which SpaCy tags as PRON
        return (
            (
                token.pos_ in ["NOUN", "PROPN", "SYM", "VERB", "PUNCT"]  # Added PUNCT for single letters like 'x'
                or (token.pos_ == "PRON" and len(token.text) == 1)
            )  # Single letter like 'i'
            and token.text.isalpha()
            and token.text.lower() not in {"the", "a", "an", "this", "that"}
        )

    def _detect_two_word_operators(self, doc, operator_patterns, entities, all_entities, text):
        """Detect two-word operator patterns in the document."""
        for i, token in enumerate(doc):
            # Check for multi-word operators
            if i + 1 < len(doc):
                two_word_pattern = f"{token.text.lower()} {doc[i + 1].text.lower()}"
                if two_word_pattern in operator_patterns:
                    logger.debug(f"Found '{two_word_pattern}' pattern at token {i}")

                    # Check if there's a preceding token that could be a variable
                    if i > 0:
                        prev_token = doc[i - 1]
                        if self._validate_variable_token(prev_token):
                            symbol = operator_patterns[two_word_pattern]
                            
                            # For comparison operators, check if there's a following value
                            if symbol == "==":
                                # Check if there's a next token that could be a value
                                if i + 2 < len(doc):
                                    next_token = doc[i + 2]
                                    if (next_token.is_alpha and not next_token.is_stop) or next_token.like_num or next_token.text.lower() in ["true", "false", "null"]:
                                        # Create comparison entity spanning variable + operator + value
                                        start_pos = prev_token.idx
                                        end_pos = next_token.idx + len(next_token.text)
                                        entity_text = text[start_pos:end_pos]
                                        
                                        check_entities = all_entities if all_entities else entities
                                        if not is_inside_entity(start_pos, end_pos, check_entities):
                                            entities.append(
                                                Entity(
                                                    start=start_pos,
                                                    end=end_pos,
                                                    text=entity_text,
                                                    type=EntityType.COMPARISON,
                                                    metadata={
                                                        "left": prev_token.text,
                                                        "right": next_token.text,
                                                        "operator": symbol,
                                                    },
                                                )
                                            )
                                            logger.debug(f"SpaCy detected {symbol} comparison: '{entity_text}' at {start_pos}-{end_pos}")
                            else:
                                # For increment/decrement operators, create entity spanning variable and operator
                                start_pos = prev_token.idx
                                end_pos = doc[i + 1].idx + len(doc[i + 1].text)
                                entity_text = text[start_pos:end_pos]

                                check_entities = all_entities if all_entities else entities
                                if not is_inside_entity(start_pos, end_pos, check_entities):
                                    entities.append(
                                        Entity(
                                            start=start_pos,
                                            end=end_pos,
                                            text=entity_text,
                                            type=(
                                                EntityType.INCREMENT_OPERATOR
                                                if symbol == "++"
                                                else EntityType.DECREMENT_OPERATOR
                                            ),
                                            metadata={
                                                "variable": prev_token.text,
                                                "operator": symbol,
                                            },
                                    )
                                )

    def _detect_three_word_operators(self, doc, operator_patterns, entities, all_entities, text):
        """Detect three-word operator patterns in the document."""
        for i, token in enumerate(doc):
            # Check for three-word operators if present
            if i + 2 < len(doc):
                three_word_pattern = f"{token.text.lower()} {doc[i + 1].text.lower()} {doc[i + 2].text.lower()}"
                if three_word_pattern in operator_patterns:
                    # Handle comparison operators like "equals equals"
                    if i > 0 and i + 3 < len(doc):
                        prev_token = doc[i - 1]
                        next_token = doc[i + 3]

                        # Check for variable on left and value/variable on right
                        is_left_var = prev_token.is_alpha and not prev_token.is_stop
                        is_right_var = (
                            (next_token.is_alpha and not next_token.is_stop)
                            or next_token.like_num
                            or next_token.text.lower() in ["true", "false", "null"]
                        )

                        if is_left_var and is_right_var:
                            # Check if there's an "if" before the comparison
                            start_pos = prev_token.idx
                            if i > 1 and doc[i - 2].text.lower() == "if":
                                start_pos = doc[i - 2].idx

                            end_pos = next_token.idx + len(next_token.text)
                            entity_text = text[start_pos:end_pos]
                            check_entities = all_entities if all_entities else entities
                            if not is_inside_entity(start_pos, end_pos, check_entities):
                                entities.append(
                                    Entity(
                                        start=start_pos,
                                        end=end_pos,
                                        text=entity_text,
                                        type=EntityType.COMPARISON,
                                        metadata={
                                            "left": prev_token.text,
                                            "right": next_token.text,
                                            "operator": operator_patterns[three_word_pattern],
                                        },
                                    )
                                )

    def _detect_spoken_operators_regex(
        self, text: str, entities: list[Entity], all_entities: list[Entity] | None = None
    ) -> None:
        """Regex-based fallback for operator detection when spaCy is not available."""
        # Get operator keywords for the current language
        operators = get_nested_resource(self.language, "spoken_keywords", "operators")

        # Build patterns for all operators
        for operator_phrase, symbol in operators.items():
            if symbol in ["++", "--"]:
                # Build pattern: variable + operator phrase
                # Use word boundaries and allow for spaces in the operator phrase
                escaped_phrase = re.escape(operator_phrase)
                pattern = rf"\b([a-zA-Z_]\w*)\s+{escaped_phrase}\b"

                for match in re.finditer(pattern, text, re.IGNORECASE):
                    start_pos = match.start()
                    end_pos = match.end()
                    check_entities = all_entities if all_entities else entities

                    if not is_inside_entity(start_pos, end_pos, check_entities):
                        variable_name = match.group(1)
                        entity_type = EntityType.INCREMENT_OPERATOR if symbol == "++" else EntityType.DECREMENT_OPERATOR

                        entities.append(
                            Entity(
                                start=start_pos,
                                end=end_pos,
                                text=match.group(0),
                                type=entity_type,
                                metadata={"variable": variable_name, "operator": symbol},
                            )
                        )
                        logger.debug(f"Regex detected {symbol} operator: '{match.group(0)}' at {start_pos}-{end_pos}")

            elif symbol == "==":
                # Build pattern for comparison: variable + operator phrase + value
                escaped_phrase = re.escape(operator_phrase)
                pattern = rf"\b([a-zA-Z_]\w*)\s+{escaped_phrase}\s+(\w+)\b"

                for match in re.finditer(pattern, text, re.IGNORECASE):
                    start_pos = match.start()
                    end_pos = match.end()
                    check_entities = all_entities if all_entities else entities

                    if not is_inside_entity(start_pos, end_pos, check_entities):
                        left_var = match.group(1)
                        right_val = match.group(2)

                        entities.append(
                            Entity(
                                start=start_pos,
                                end=end_pos,
                                text=match.group(0),
                                type=EntityType.COMPARISON,
                                metadata={"left": left_var, "right": right_val, "operator": symbol},
                            )
                        )
                        logger.debug(f"Regex detected {symbol} comparison: '{match.group(0)}' at {start_pos}-{end_pos}")