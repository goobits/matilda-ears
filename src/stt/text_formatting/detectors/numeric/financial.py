#!/usr/bin/env python3
"""Financial and currency entity detection for Matilda transcriptions."""
from __future__ import annotations

import re
from typing import Any

from stt.core.config import setup_logging
from stt.text_formatting.common import Entity, EntityType, NumberParser
from stt.text_formatting.constants import get_resources
from stt.text_formatting.utils import is_inside_entity

logger = setup_logging(__name__, log_filename="text_formatting.txt", include_console=False)


class FinancialDetector:
    """Detector for financial and currency entities."""
    
    def __init__(self, nlp=None, language: str = "en"):
        """
        Initialize FinancialDetector with dependency injection.

        Args:
            nlp: SpaCy NLP model instance. If None, will load from nlp_provider.
            language: Language code for resource loading (default: 'en')
        """
        if nlp is None:
            from stt.text_formatting.nlp_provider import get_nlp
            nlp = get_nlp()

        self.nlp = nlp
        self.language = language

        # Load language-specific resources
        self.resources = get_resources(language)

        # Initialize NumberParser for robust number word detection
        self.number_parser = NumberParser(language=self.language)

    def detect_currency_with_spacy(
        self, doc, text: str, entities: list[Entity], all_entities: list[Entity] | None = None
    ) -> None:
        """Detect currency entities using SpaCy's grammar analysis."""
        if not self.nlp or not doc:
            return

        # Define currency units
        currency_units = set(self.resources.get("currency", {}).get("units", []))

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

                # Now, check the very next token to see if it's a currency unit
                if j < len(doc):
                    unit_token = doc[j]
                    unit_lemma = unit_token.lemma_.lower()

                    if unit_lemma in currency_units:
                        # Special handling for "pounds" - check context
                        if unit_token.text.lower() in ["pound", "pounds"]:
                            prefix_context = text[: number_tokens[0].idx].lower()
                            currency_contexts = self.resources.get("context_words", {}).get("currency_contexts", [])
                            weight_contexts = self.resources.get("context_words", {}).get("weight_contexts", [])

                            # If it has clear weight context OR lacks currency context, skip (not currency).
                            if any(ctx in prefix_context for ctx in weight_contexts) or not any(
                                ctx in prefix_context for ctx in currency_contexts
                            ):
                                i += 1
                                continue
                            # It has currency context, so it's money - continue processing

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
                                    type=EntityType.CURRENCY,
                                    metadata={"number": number_text, "unit": unit_token.text},
                                )
                            )
                        i = j  # Move the main loop index past the consumed unit
                        continue
            i += 1

    def detect_currency_with_regex(
        self, text: str, entities: list[Entity], all_entities: list[Entity] | None = None
    ) -> None:
        """Detect currency patterns using regex for cases where SpaCy might fail."""
        # Build comprehensive pattern for all number words
        number_pattern = r"\b(?:" + "|".join(sorted(self.number_parser.all_number_words, key=len, reverse=True)) + r")"

        # Build currency unit patterns
        currency_units = self.resources.get("currency", {}).get("units", [])
        unit_pattern = r"(?:" + "|".join(sorted(currency_units, key=len, reverse=True)) + r")"

        # Pattern for compound numbers followed by currency units
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

                # Find which unit was matched
                for test_unit in currency_units:
                    if match_text.endswith(" " + test_unit.lower()):
                        unit = test_unit
                        
                        # Special handling for "pounds" - check context
                        if unit.lower() in ["pound", "pounds"]:
                            prefix_context = text[: match.start()].lower()
                            currency_contexts = self.resources.get("context_words", {}).get("currency_contexts", [])
                            weight_contexts = self.resources.get("context_words", {}).get("weight_contexts", [])

                            # If it has clear weight context OR lacks currency context, skip (not currency).
                            if any(ctx in prefix_context for ctx in weight_contexts) or not any(
                                ctx in prefix_context for ctx in currency_contexts
                            ):
                                break  # Skip this match, it's not currency
                        
                        # Extract number part
                        number_text = match_text[: -(len(unit) + 1)]  # Remove unit and space
                        entities.append(
                            Entity(
                                start=match.start(),
                                end=match.end(),
                                text=match.group(),
                                type=EntityType.CURRENCY,
                                metadata={"number": number_text, "unit": unit},
                            )
                        )
                        break

    def detect_dollar_cents(
        self, text: str, entities: list[Entity], all_entities: list[Entity] | None = None
    ) -> None:
        """Detect 'X dollars and Y cents' patterns and convert to DOLLAR_CENTS entities."""
        # Pattern to match "X dollars and Y cents"
        # Supports both word numbers and digits
        number_words = "|".join(re.escape(word) for word in self.number_parser.all_number_words)
        
        # Pattern for numbers (digits or words)
        number_pattern = rf"(?:\d+|(?:{number_words})(?:\s+(?:{number_words}))*)"
        
        # Complete pattern for "X dollars and Y cents"
        dollar_cents_pattern = re.compile(
            rf"\b({number_pattern})\s+dollars?\s+and\s+({number_pattern})\s+cents?\b",
            re.IGNORECASE
        )

        for match in dollar_cents_pattern.finditer(text):
            check_entities = all_entities if all_entities else entities
            if not is_inside_entity(match.start(), match.end(), check_entities):
                dollars_text = match.group(1).strip()
                cents_text = match.group(2).strip()
                
                # Parse the dollar and cent amounts
                dollars_value = self.number_parser.parse(dollars_text)
                cents_value = self.number_parser.parse(cents_text)
                
                # Only create entity if both parts parse successfully
                if dollars_value and cents_value:
                    entities.append(
                        Entity(
                            start=match.start(),
                            end=match.end(),
                            text=match.group(0),
                            type=EntityType.DOLLAR_CENTS,
                            metadata={
                                "dollars": dollars_value,
                                "cents": cents_value
                            },
                        )
                    )

    def detect_cents_only(
        self, text: str, entities: list[Entity], all_entities: list[Entity] | None = None
    ) -> None:
        """Detect 'X cents' patterns and convert to CENTS entities."""
        # Pattern to match "X cents"
        # Supports both word numbers and digits
        number_words = "|".join(re.escape(word) for word in self.number_parser.all_number_words)
        
        # Pattern for numbers (digits or words)
        number_pattern = rf"(?:\d+|(?:{number_words})(?:\s+(?:{number_words}))*)"
        
        # Complete pattern for "X cents"
        cents_pattern = re.compile(
            rf"\b({number_pattern})\s+cents?\b",
            re.IGNORECASE
        )

        for match in cents_pattern.finditer(text):
            check_entities = all_entities if all_entities else entities
            if not is_inside_entity(match.start(), match.end(), check_entities):
                cents_text = match.group(1).strip()
                
                # Parse the cent amount
                cents_value = self.number_parser.parse(cents_text)
                
                # Only create entity if parsing succeeds
                if cents_value:
                    entities.append(
                        Entity(
                            start=match.start(),
                            end=match.end(),
                            text=match.group(0),
                            type=EntityType.CENTS,
                            metadata={
                                "cents": cents_value
                            },
                        )
                    )