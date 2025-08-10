#!/usr/bin/env python3
"""
SpaCy-based entity detection module.

This module handles the core SpaCy entity detection logic, extracted from entity_detector.py
for better modularity and maintainability.
"""
from __future__ import annotations

from ...core.config import setup_logging
from stt.text_formatting.common import Entity, EntityType, NumberParser
from ..constants import get_resources
from ..utils import is_inside_entity
from ..number_word_context import NumberWordContextAnalyzer, NumberWordDecision

# Setup logging
logger = setup_logging(__name__)


class SpacyEntityProcessor:
    """Handles SpaCy-based entity detection and processing."""

    def __init__(self, nlp, language: str = "en"):
        """
        Initialize SpacyEntityProcessor.

        Args:
            nlp: SpaCy NLP model instance
            language: Language code for resource loading (default: 'en')
        """
        self.nlp = nlp
        self.language = language
        self.resources = get_resources(language)
        
        # Initialize context analyzer for better number word detection
        self.context_analyzer = NumberWordContextAnalyzer(nlp=self.nlp)

    def process_spacy_entities(
        self, text: str, entities: list[Entity], existing_entities: list[Entity], doc=None, skip_entities=None
    ) -> None:
        """
        Process SpaCy-detected entities and add them to the entities list.

        Args:
            text: Input text to process
            entities: List to add detected entities to
            existing_entities: List of already detected entities to check for overlaps
            doc: Pre-computed SpaCy doc object (optional)
            skip_entities: Set of (start, end, text) tuples to skip
        """
        if not self.nlp:
            return

        if skip_entities is None:
            skip_entities = set()

        if doc is None:
            try:
                doc = self.nlp(text)
            except (AttributeError, ValueError, IndexError) as e:
                logger.warning(f"SpaCy entity detection failed: {e}")
                return

        try:
            # Map SpaCy labels to EntityType enums
            label_to_type = {
                "CARDINAL": EntityType.CARDINAL,
                "DATE": EntityType.DATE,
                "TIME": EntityType.TIME,
                "MONEY": EntityType.MONEY,
                "PERCENT": EntityType.PERCENT,
                "QUANTITY": EntityType.QUANTITY,
                "ORDINAL": EntityType.ORDINAL,
            }

            for ent in doc.ents:
                if ent.label_ in label_to_type:
                    # Check if this entity was pre-filtered and should be skipped
                    if (ent.start_char, ent.end_char, ent.text) in skip_entities:
                        continue
                        
                    if not is_inside_entity(ent.start_char, ent.end_char, existing_entities):
                        # Get the entity type, potentially reclassifying it
                        entity_type = self._get_entity_type(ent, text, label_to_type)
                        if entity_type is None:
                            continue  # Skip this entity

                        # Get metadata for the entity
                        metadata = self._get_entity_metadata(ent, entity_type)

                        entities.append(
                            Entity(
                                start=ent.start_char,
                                end=ent.end_char,
                                text=ent.text,
                                type=entity_type,
                                metadata=metadata,
                            )
                        )
        except (AttributeError, ValueError, IndexError) as e:
            logger.warning(f"SpaCy entity detection failed: {e}")

    def _get_entity_type(self, ent, text: str, label_to_type: dict) -> EntityType | None:
        """
        Determine the correct entity type for a SpaCy entity, potentially reclassifying it.

        Args:
            ent: SpaCy entity object
            text: Full text being processed
            label_to_type: Mapping from SpaCy labels to EntityType enums

        Returns:
            EntityType if the entity should be kept, None if it should be skipped
        """
        entity_type = label_to_type[ent.label_]

        # Handle CARDINAL entities with context analysis
        if ent.label_ == "CARDINAL":
            decision = self.context_analyzer.should_convert_number_word(
                text, ent.start_char, ent.end_char
            )
            if decision == NumberWordDecision.KEEP_WORD:
                return None  # Skip this entity - keep as words
        
        # Handle ORDINAL entities with special processing
        if ent.label_ == "ORDINAL":
            if self._should_skip_ordinal(ent, text):
                return None
        
        # Reclassify DATE entities that are actually number sequences
        if entity_type == EntityType.DATE:
            entity_type = self._reclassify_date_entity(ent, text, entity_type)

        return entity_type

    def _should_skip_ordinal(self, ent, text: str) -> bool:
        """
        Check if an ORDINAL entity should be skipped due to idiomatic usage.

        Args:
            ent: SpaCy entity object
            text: Full text being processed

        Returns:
            True if the entity should be skipped, False otherwise
        """
        logger.debug(f"Processing ORDINAL entity: '{ent.text}' at {ent.start_char}-{ent.end_char}")
        
        # Find the corresponding token and next token
        ordinal_token = None
        next_token = None
        doc = ent.doc if hasattr(ent, 'doc') else self.nlp(text)
        
        for token in doc:
            if token.idx == ent.start_char:
                ordinal_token = token
                if token.i + 1 < len(doc):
                    next_token = doc[token.i + 1]
                break
        
        if ordinal_token and next_token:
            logger.debug(f"Found tokens: '{ordinal_token.text}' ({ordinal_token.pos_}) -> '{next_token.text}' ({next_token.pos_})")

        # Check for specific idiomatic contexts using POS tags
        if ordinal_token and next_token:
            # RULE 1: Skip if it's an adjective followed by a specific idiomatic word from our resources.
            # Extended to include not just nouns but also prepositions, pronouns, etc.
            if ordinal_token.pos_ == "ADJ" and next_token.pos_ in ["NOUN", "ADP", "PRON", "DET", "PART", "VERB"]:
                # This is the key: we check our i18n file for specific exceptions.
                idiomatic_phrases = self.resources.get("technical", {}).get("idiomatic_phrases", {})
                if (
                    ordinal_token.text.lower() in idiomatic_phrases
                    and next_token.text.lower() in idiomatic_phrases[ordinal_token.text.lower()]
                ):
                    logger.debug(
                        f"Skipping ORDINAL '{ent.text}' due to idiomatic follower word '{next_token.text}' (POS: {next_token.pos_})."
                    )
                    return True

            # RULE 2: Skip if it's at sentence start and followed by comma ("First, we...")
            if (
                ordinal_token.i == 0 or ordinal_token.sent.start == ordinal_token.i
            ) and next_token.text == ",":
                logger.debug(f"Skipping ORDINAL '{ent.text}' - sentence starter with comma")
                return True

        # RULE 3: Check the i18n resource file for specific phrases as fallback
        ordinal_text = ent.text.lower()
        following_text = ""
        if next_token:
            following_text = next_token.text.lower()

        idiomatic_phrases = self.resources.get("technical", {}).get("idiomatic_phrases", {})
        if ordinal_text in idiomatic_phrases and following_text in idiomatic_phrases[ordinal_text]:
            # Check for technical/formal context that should override idiomatic detection
            full_context = text.lower()
            technical_indicators = [
                'software', 'technology', 'generation', 'quarter', 'earnings', 
                'report', 'century', 'winner', 'performance', 'meeting',
                'deadline', 'conference', 'agenda', 'process', 'option',
                'item', 'step', 'iphone', 'competition', 'race', 'contest',
                'ranking', 'leaderboard', 'score', 'match', 'tournament'
            ]
            
            # If we find technical indicators, don't skip - let it convert to numeric ordinal
            if any(indicator in full_context for indicator in technical_indicators):
                logger.debug(f"Found technical context for ORDINAL '{ordinal_text} {following_text}' - allowing numeric conversion")
                return False
            else:
                logger.debug(
                    f"Skipping ORDINAL '{ordinal_text} {following_text}' - idiomatic phrase from resources"
                )
                return True
        
        # RULE 4: Additional fallback - check for sentence-start patterns with comma (even without proper POS analysis)
        ordinal_text = ent.text.lower()
        remaining_text = text[ent.end_char:].strip().lower()
        
        # Check for sentence-start patterns with comma when POS analysis didn't catch it
        if (ent.start_char == 0 or text[ent.start_char-1] in '.!?') and remaining_text.startswith(','):
            logger.debug(f"Skipping ORDINAL '{ent.text}' - sentence starter with comma (fallback)")
            return True

        return False

    def _reclassify_date_entity(self, ent, text: str, entity_type: EntityType) -> EntityType:
        """
        Reclassify DATE entities that are actually number sequences.

        Args:
            ent: SpaCy entity object
            text: Full text being processed
            entity_type: Current entity type

        Returns:
            Potentially reclassified EntityType
        """
        if entity_type == EntityType.DATE:
            number_parser = NumberParser(language=self.language)
            parsed_number = number_parser.parse(ent.text.lower())

            if parsed_number and parsed_number.isdigit():
                # This is a number sequence misclassified as a date, treat as CARDINAL
                entity_type = EntityType.CARDINAL
                logger.debug(
                    f"Reclassifying DATE '{ent.text}' as CARDINAL (number sequence: {parsed_number})"
                )

        return entity_type

    def _get_entity_metadata(self, ent, entity_type: EntityType) -> dict:
        """
        Generate metadata for an entity based on its type.

        Args:
            ent: SpaCy entity object
            entity_type: The determined entity type

        Returns:
            Dictionary containing entity metadata
        """
        metadata = {}
        
        # For PERCENT entities, add metadata for conversion
        if entity_type == EntityType.PERCENT:
            import re

            # Handle decimal percentages like "zero point one percent"
            if "point" in ent.text.lower():
                decimal_match = re.search(r"(\w+)\s+point\s+(\w+)", ent.text, re.IGNORECASE)
                if decimal_match:
                    metadata = {"groups": decimal_match.groups(), "is_percentage": True}
            else:
                # Handle simple percentages like "ten percent"
                # Try multiple patterns to match different spaCy outputs
                percent_match = re.search(r"^(.+?)\s*percent$", ent.text, re.IGNORECASE)
                if not percent_match:
                    percent_match = re.search(
                        r"^(.+?)$", ent.text.replace(" percent", ""), re.IGNORECASE
                    )
                if percent_match:
                    number_text = percent_match.group(1).strip()
                    metadata = {"number": number_text, "unit": "percent"}

        return metadata