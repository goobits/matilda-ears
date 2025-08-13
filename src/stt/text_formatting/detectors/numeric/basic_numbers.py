#!/usr/bin/env python3
"""Basic number detection functionality extracted from numeric_detector.py."""
from __future__ import annotations

import re
from typing import Any

from stt.core.config import setup_logging
from stt.text_formatting.pattern_modules.numeric_patterns import (
    SPOKEN_ORDINAL_PATTERN,
    SPOKEN_COMPOUND_FRACTION_PATTERN,
    SPOKEN_FRACTION_PATTERN,
    SPOKEN_NUMERIC_RANGE_PATTERN,
)
from stt.text_formatting.common import Entity, EntityType, NumberParser
from stt.text_formatting.constants import get_resources
from stt.text_formatting.utils import is_inside_entity, overlaps_with_entity
from stt.text_formatting.number_word_context import NumberWordContextAnalyzer, NumberWordDecision

logger = setup_logging(__name__)


class BasicNumberDetector:
    """Handles basic number detection: cardinals, ordinals, fractions, ranges, number words."""
    
    def __init__(self, nlp=None, language: str = "en"):
        """
        Initialize BasicNumberDetector.

        Args:
            nlp: SpaCy NLP model instance. If None, will load from nlp_provider.
            language: Language code for resource loading (default: 'en')
        """
        if nlp is None:
            try:
                from stt.text_formatting.nlp_provider import get_nlp
                nlp = get_nlp()
            except ImportError:
                nlp = None

        self.nlp = nlp
        self.language = language

        # Load language-specific resources
        self.resources = get_resources(language)

        # Initialize NumberParser for robust number word detection
        self.number_parser = NumberParser(language=self.language)
        
        # Initialize context analyzer for better number word detection
        self.context_analyzer = NumberWordContextAnalyzer(nlp=self.nlp)

    def detect_cardinal_numbers(self, text: str, entities: list[Entity], all_entities: list[Entity] | None = None) -> None:
        """Detect cardinal numbers including compound numbers that SpaCy might miss."""
        # Note: Always run this detection to catch compound numbers like "twenty one" that SpaCy might not detect
        # We'll check for overlaps with existing entities to avoid duplicates

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
            # Check for overlaps with existing entities (including SpaCy-detected ones)
            if not overlaps_with_entity(match.start(), match.end(), check_entities):
                # Try to parse this number sequence
                number_text = match.group(0)
                parsed_number = self.number_parser.parse(number_text)

                # Only create entity if it parses to a valid number
                if parsed_number and parsed_number.isdigit():
                    # Check if this might be a time duration (number + time unit)
                    # Skip creating CARDINAL entity to let time duration processing handle it
                    remaining_text = text[match.end():].lstrip()
                    time_units = ['second', 'seconds', 'minute', 'minutes', 'hour', 'hours', 
                                 'day', 'days', 'week', 'weeks', 'month', 'months', 'year', 'years']
                    
                    is_time_duration = any(remaining_text.lower().startswith(unit) for unit in time_units)
                    if is_time_duration:
                        # Skip creating CARDINAL entity for time durations
                        continue
                    
                    # Compound numbers (with spaces or scale words) are always numeric
                    if ' ' in number_text or any(scale in number_text.lower() 
                                                  for scale in ['hundred', 'thousand', 'million', 'billion']):
                        # Compound number - always convert
                        decision = NumberWordDecision.CONVERT_DIGIT
                    else:
                        # Single word - check context
                        decision = self.context_analyzer.should_convert_number_word(
                            text, match.start(), match.end()
                        )
                    
                    # Only create entity if context analysis says to convert
                    if decision == NumberWordDecision.CONVERT_DIGIT:
                        entities.append(
                            Entity(
                                start=match.start(),
                                end=match.end(),
                                text=number_text,
                                type=EntityType.CARDINAL,
                                metadata={"parsed_value": parsed_number},
                            )
                        )

    def _detect_compound_ordinals(self, text: str, entities: list[Entity], all_entities: list[Entity] | None = None, doc=None) -> None:
        """Detect compound ordinals like 'one hundred first', 'twenty third', etc."""
        # Simple ordinal endings that can be combined with cardinal numbers
        ordinal_endings = ["first", "second", "third", "fourth", "fifth", "sixth", "seventh", "eighth", "ninth"]
        
        # Build pattern to match: [cardinal numbers] + [ordinal ending]
        number_words = sorted(self.number_parser.all_number_words, key=len, reverse=True)
        number_pattern = "|".join(re.escape(word) for word in number_words)
        ordinal_ending_pattern = "|".join(ordinal_endings)
        
        # Pattern for compound ordinals: number words + ordinal ending
        compound_ordinal_pattern = re.compile(
            rf"\b({number_pattern}(?:\s+(?:and\s+)?(?:{number_pattern}))*)\s+({ordinal_ending_pattern})\b", 
            re.IGNORECASE
        )
        
        for match in compound_ordinal_pattern.finditer(text):
            check_entities = all_entities if all_entities else entities
            if not overlaps_with_entity(match.start(), match.end(), check_entities):
                cardinal_part = match.group(1)
                ordinal_part = match.group(2)
                full_ordinal = match.group(0)
                
                # Try to parse the compound ordinal
                parsed_ordinal = self.number_parser.parse_ordinal(full_ordinal)
                if parsed_ordinal and parsed_ordinal != full_ordinal:  # Only if it actually converted something
                    # For compound ordinals, apply simplified context filtering
                    should_skip = False
                    
                    # Only skip if it's clearly an idiomatic sentence starter like "Twenty first, we need to..."
                    if match.start() == 0:  # Starts at beginning of text
                        # Find what follows the compound ordinal
                        remaining_text = text[match.end():].strip()
                        if remaining_text.startswith(','):
                            should_skip = True
                    
                    # Don't apply the complex idiomatic filtering to compound ordinals
                    # because they are inherently more specific and technical in nature
                    
                    if not should_skip:
                        entities.append(
                            Entity(
                                start=match.start(),
                                end=match.end(),
                                text=full_ordinal,
                                type=EntityType.ORDINAL,
                                metadata={"cardinal_part": cardinal_part, "ordinal_part": ordinal_part},
                            )
                        )

    def detect_ordinal_numbers(self, text: str, entities: list[Entity], all_entities: list[Entity] | None = None) -> None:
        """Detect ordinal numbers (first, second, third, etc.)."""
        # First, run the SpaCy analysis once if available.
        doc = None
        if self.nlp:
            # Use shared document processor for optimal caching
            from ...spacy_doc_cache import get_or_create_shared_doc
            try:
                doc = get_or_create_shared_doc(text, nlp_model=self.nlp)
            except Exception as e:
                logger.warning(f"SpaCy ordinal analysis failed: {e}")
                doc = None

        # First, detect compound ordinals like "one hundred first", "twenty first", etc.
        self._detect_compound_ordinals(text, entities, all_entities, doc)
        
        # Then detect simple ordinals that aren't already covered
        for match in SPOKEN_ORDINAL_PATTERN.finditer(text):
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
                    # Skip if it's an adjective followed by a specific idiomatic word from our resources.
                    # Extended to include not just nouns but also prepositions, pronouns, etc.
                    if ordinal_token.pos_ == "ADJ" and next_token.pos_ in ["NOUN", "ADP", "PRON", "DET", "PART", "VERB"]:
                        # This is the key: we check our i18n file for specific exceptions.
                        idiomatic_phrases = self.resources.get("technical", {}).get("idiomatic_phrases", {})
                        if (
                            ordinal_token.text.lower() in idiomatic_phrases
                            and next_token.text.lower() in idiomatic_phrases[ordinal_token.text.lower()]
                        ):
                            # Check for technical/formal context that should override idiomatic detection
                            full_context = text.lower()
                            technical_indicators = [
                                'software', 'technology', 'generation', 'quarter', 'earnings', 
                                'report', 'century', 'winner', 'performance', 'meeting',
                                'deadline', 'conference', 'agenda', 'process', 'option',
                                'item', 'step', 'iphone', 'competition', 'race', 'contest',
                                'ranking', 'leaderboard', 'score', 'match', 'tournament',
                                'came in', 'finished', 'placed', 'ranked', 'position',
                                'this is the', 'that was the', 'it was the', 'attempt', 'try', 'iteration',
                                'contractor', 'vendor', 'supplier', 'developer', 'provider'
                            ]
                            
                            # If we find technical indicators, convert to numeric ordinal (don't skip)
                            if any(indicator in full_context for indicator in technical_indicators):
                                logger.debug(f"Technical context override: allowing ORDINAL '{match.group()}' despite idiomatic pattern")
                            else:
                                logger.debug(
                                    f"Skipping ORDINAL '{match.group()}' due to idiomatic follower word '{next_token.text}' (POS: {next_token.pos_})."
                                )
                                continue

                    # Skip if it's at sentence start and followed by comma ("First, we...")
                    if (ordinal_token.i == 0 or ordinal_token.sent.start == ordinal_token.i) and next_token.text == ",":
                        logger.debug(f"Skipping ORDINAL '{match.group()}' - sentence starter with comma")
                        continue

            # Fallback check for idiomatic phrases when SpaCy is not available
            if not doc:
                # Simple pattern-based check for common idiomatic patterns
                ordinal_word = match.group().lower()
                remaining_text = text[match.end():].strip().lower()
                
                # Check if the ordinal is followed by any idiomatic words from our resources
                idiomatic_phrases = self.resources.get("technical", {}).get("idiomatic_phrases", {})
                
                # Special check for multi-word idioms with repeated words
                if ordinal_word == "first" and "things first" in text.lower():
                    logger.debug(f"Skipping ORDINAL '{match.group()}' - part of 'first things first' idiom")
                    continue
                if ordinal_word == "first" and "come first served" in text.lower():
                    logger.debug(f"Skipping ORDINAL '{match.group()}' - part of 'first come first served' idiom")
                    continue
                
                if ordinal_word in idiomatic_phrases:
                    # Get the next word after the ordinal
                    words_after = remaining_text.split()
                    if words_after and words_after[0] in idiomatic_phrases[ordinal_word]:
                        # Check for technical/formal context that should override idiomatic detection
                        full_context = text.lower()
                        technical_indicators = [
                            'software', 'technology', 'generation', 'quarter', 'earnings', 
                            'report', 'century', 'winner', 'performance', 'meeting',
                            'deadline', 'conference', 'agenda', 'process', 'option',
                            'item', 'step', 'iphone', 'competition', 'race', 'contest',
                            'ranking', 'leaderboard', 'score', 'match', 'tournament',
                            'came in', 'finished', 'placed', 'ranked', 'position',
                            'this is the', 'that was the', 'it was the', 'attempt', 'try', 'iteration',
                            'contractor', 'vendor', 'supplier', 'developer', 'provider'
                        ]
                        
                        # If we find technical indicators, convert to numeric ordinal
                        if any(indicator in full_context for indicator in technical_indicators):
                            # Don't skip - let it convert to numeric ordinal
                            pass
                        else:
                            logger.debug(f"Skipping ORDINAL '{match.group()}' due to idiomatic pattern (no SpaCy)")
                            continue
                
                # Also check for sentence-start patterns with comma
                if (match.start() == 0 or text[match.start()-1] in '.!?') and remaining_text.startswith(','):
                    logger.debug(f"Skipping ORDINAL '{match.group()}' - sentence starter with comma (no SpaCy)")
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

    def detect_fractions(self, text: str, entities: list[Entity], all_entities: list[Entity] | None = None) -> None:
        """Detect fraction expressions (one half, two thirds, etc.) and compound fractions (one and one half)."""
        # First detect compound fractions (they take priority)
        for match in SPOKEN_COMPOUND_FRACTION_PATTERN.finditer(text):
            check_entities = all_entities if all_entities else entities
            if not overlaps_with_entity(match.start(), match.end(), check_entities):
                entities.append(
                    Entity(
                        start=match.start(),
                        end=match.end(),
                        text=match.group(),
                        type=EntityType.FRACTION,
                        metadata={
                            "whole_word": match.group(1),
                            "numerator_word": match.group(2),
                            "denominator_word": match.group(3),
                            "is_compound": True,
                        },
                    )
                )

        # Then detect simple fractions
        for match in SPOKEN_FRACTION_PATTERN.finditer(text):
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

    def detect_ranges(self, text: str, entities: list[Entity], all_entities: list[Entity] | None = None) -> None:
        """Detect numeric range expressions (ten to twenty, etc.)."""
        for match in SPOKEN_NUMERIC_RANGE_PATTERN.finditer(text):
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

                # Check for currency units - sort by length descending to prioritize longer matches
                currency_units = self.resources.get("currency", {}).get("units", [])
                currency_units = sorted(currency_units, key=len, reverse=True)
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
                    # Time units - sort by length descending to prioritize longer matches
                    time_units = self.resources.get("units", {}).get("time_units", [])
                    time_units = sorted(time_units, key=len, reverse=True)
                    for time_unit in time_units:
                        if remaining_text.lower().startswith(time_unit.lower()):
                            unit_type = "time"
                            unit_text = time_unit
                            unit_start = text.lower().find(time_unit.lower(), end_pos)
                            if unit_start != -1:
                                end_pos = unit_start + len(time_unit)
                            break

                if not unit_text:
                    # Weight units - sort by length descending to prioritize longer matches (e.g., "kilograms" over "kilogram")
                    weight_units = self.resources.get("units", {}).get("weight_units", [])
                    weight_units = sorted(weight_units, key=len, reverse=True)
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

    def detect_time_durations(self, text: str, entities: list[Entity], all_entities: list[Entity] | None = None) -> None:
        """Detect time duration patterns when SpaCy is unavailable."""
        if self.nlp:
            # If SpaCy is available, let the MeasurementDetector handle this
            return
        
        # Simple regex-based time duration detection for fallback
        time_units = ['second', 'seconds', 'minute', 'minutes', 'hour', 'hours', 
                     'day', 'days', 'week', 'weeks', 'month', 'months', 'year', 'years']
        unit_pattern = '|'.join(time_units)
        
        # Pattern: number words + time units
        number_words = sorted(self.number_parser.all_number_words, key=len, reverse=True)
        number_pattern = "|".join(re.escape(word) for word in number_words)
        
        duration_pattern = re.compile(
            rf"\b(?:{number_pattern})\s+(?:{unit_pattern})\b", re.IGNORECASE
        )
        
        for match in duration_pattern.finditer(text):
            check_entities = all_entities if all_entities else entities
            if not overlaps_with_entity(match.start(), match.end(), check_entities):
                # Parse the duration
                words = match.group(0).split()
                number_text = words[0]
                unit_text = ' '.join(words[1:])
                
                parsed_number = self.number_parser.parse(number_text)
                if parsed_number and parsed_number.isdigit():
                    entities.append(
                        Entity(
                            start=match.start(),
                            end=match.end(),
                            text=match.group(0),
                            type=EntityType.TIME_DURATION,
                            metadata={
                                "number": number_text,
                                "unit": unit_text,
                                "parsed_value": parsed_number
                            },
                        )
                    )

    def detect_number_words(self, text: str, entities: list[Entity], all_entities: list[Entity] | None = None) -> None:
        """Detect consecutive digit sequences like 'six four four' -> '644'."""
        # Build pattern for single digits (zero through nine)
        single_digits = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine"]
        digit_pattern = "|".join(single_digits)

        # Pattern for consecutive single digits (3 or more for specificity)
        consecutive_pattern = re.compile(
            rf"\b({digit_pattern})\s+({digit_pattern})\s+({digit_pattern})(?:\s+({digit_pattern}))?\b", re.IGNORECASE
        )

        for match in consecutive_pattern.finditer(text):
            check_entities = all_entities if all_entities else entities
            if not overlaps_with_entity(match.start(), match.end(), check_entities):
                # Extract the digit words and convert to digits
                digit_words = [g for g in match.groups() if g is not None]

                # Convert words to digits
                digit_map = {word: str(i) for i, word in enumerate(single_digits)}
                digits = [digit_map[word.lower()] for word in digit_words]

                entities.append(
                    Entity(
                        start=match.start(),
                        end=match.end(),
                        text=match.group(),
                        type=EntityType.CARDINAL,
                        metadata={"consecutive_digits": digits, "parsed_value": "".join(digits)},
                    )
                )