#!/usr/bin/env python3
"""Context analysis for smart capitalization decisions."""
from __future__ import annotations

import re
from typing import TYPE_CHECKING

from ..core.config import setup_logging
from .utils import is_inside_entity

if TYPE_CHECKING:
    from .common import Entity
    from .capitalizer_rules import CapitalizationRules

# Setup logging
logger = setup_logging(__name__, log_filename="text_formatting.txt", include_console=False)


class ContextAnalyzer:
    """Analyzes text context for intelligent capitalization decisions."""

    def __init__(self, rules: 'CapitalizationRules', nlp=None):
        """Initialize context analyzer.
        
        Args:
            rules: CapitalizationRules instance
            nlp: SpaCy NLP model (optional)
        """
        self.rules = rules
        self.nlp = nlp

    def is_technical_term(self, entity_text: str, full_text: str) -> bool:
        """Check if a PERSON entity is actually a technical term that shouldn't be capitalized.
        
        Args:
            entity_text: The entity text to analyze
            full_text: The full text context
            
        Returns:
            True if the entity is likely a technical term
        """
        # Check exact match for multi-word terms
        multi_word_technical = set(self.rules.resources.get("context_words", {}).get("multi_word_commands", []))
        if entity_text.lower() in multi_word_technical:
            return True

        # Check single words in the entity
        entity_words = entity_text.lower().split()
        technical_terms = set(self.rules.resources.get("technical", {}).get("terms", []))
        if any(word in technical_terms for word in entity_words):
            return True

        # Check context - if surrounded by technical keywords, likely technical
        full_text_lower = full_text.lower()
        words = full_text_lower.split()

        try:
            entity_index = words.index(entity_text)
            # Check 2 words before and after
            context_start = max(0, entity_index - 2)
            context_end = min(len(words), entity_index + 3)
            context_words = words[context_start:context_end]

            technical_context_words = set(self.rules.resources.get("context_words", {}).get("technical_context", []))
            if any(word in technical_context_words for word in context_words):
                return True
        except ValueError:
            # Entity not found as single word, might be multi-word
            pass

        return False

    def is_variable_context_for_i(self, text: str, position: int) -> bool:
        """Check if 'i' at given position is in a variable context.
        
        Args:
            text: Full text
            position: Position of 'i' in text
            
        Returns:
            True if 'i' appears to be a variable rather than pronoun
        """
        # Check preceding text for variable indicators
        preceding_text = text[max(0, position - 25):position].lower()
        variable_indicators = [
            "variable is", "counter is", "iterator is", "for i in", 
            "variable i", "letter i"
        ]
        return any(keyword in preceding_text for keyword in variable_indicators)

    def is_part_of_identifier(self, text: str, start: int, end: int) -> bool:
        """Check if a text span is part of an identifier (connected by _ or -).
        
        Args:
            text: Full text
            start: Start position of span
            end: End position of span
            
        Returns:
            True if the span is part of an identifier
        """
        return ((start > 0 and text[start - 1] in "_-") or 
                (end < len(text) and text[end] in "_-"))

    def should_skip_spacy_entity_for_technical_context(
        self, 
        entity_text: str, 
        entity_label: str, 
        full_text: str
    ) -> bool:
        """Determine if a SpaCy entity should be skipped due to technical context.
        
        Args:
            entity_text: The entity text
            entity_label: SpaCy entity label (PERSON, ORG, etc.)
            full_text: Full text context
            
        Returns:
            True if the entity should be skipped
        """
        # Skip pi constant to prevent capitalization
        if entity_text.lower() == "pi":
            logger.debug(f"Skipping pi constant '{entity_text}' to allow MATH_CONSTANT converter to handle it")
            return True

        # Skip PERSON entities that are likely technical terms in coding contexts
        if entity_label == "PERSON" and self.is_technical_term(entity_text.lower(), full_text):
            logger.debug(f"Skipping PERSON entity '{entity_text}' - detected as technical term")
            return True

        # Skip PERSON or ORG entities that are technical verbs (let, const, var, etc.)
        technical_verbs = self.rules.get_technical_verbs()
        if (entity_label in ["PERSON", "ORG"] and 
            entity_text.lower() in technical_verbs):
            logger.debug(f"Skipping capitalization for technical verb: '{entity_text}'")
            return True

        return False

    def should_handle_technical_verb_capitalization(
        self, 
        entity_text: str, 
        entity_label: str
    ) -> tuple[bool, str | None]:
        """Check if entity needs technical verb handling and return replacement.
        
        Args:
            entity_text: The entity text
            entity_label: SpaCy entity label
            
        Returns:
            Tuple of (should_replace, replacement_text)
        """
        technical_verbs = self.rules.get_technical_verbs()
        
        if (entity_label in ["PERSON", "ORG"] and 
            entity_text.isupper() and 
            entity_text.lower() in technical_verbs):
            # It's an all-caps technical term, replace with lowercase version
            return True, entity_text.lower()
            
        return False, None

    def get_sentence_capitalization_context(
        self, 
        text: str, 
        match_start: int
    ) -> dict:
        """Get context information for sentence capitalization decisions.
        
        Args:
            text: Full text
            match_start: Start position of potential capitalization
            
        Returns:
            Dictionary with context information
        """
        # Check the text before the match to see if it's an abbreviation
        preceding_text = text[:match_start].lower()
        common_abbreviations = self.rules.resources.get("technical", {}).get("common_abbreviations", [])
        
        return {
            "follows_abbreviation": any(
                preceding_text.endswith(abbrev) for abbrev in common_abbreviations
            ),
            "preceding_text": preceding_text[-50:] if len(preceding_text) > 50 else preceding_text
        }

    def analyze_proper_noun_entities(
        self, 
        doc, 
        text: str, 
        entities: list['Entity'] | None = None
    ) -> list[tuple[int, int, str]]:
        """Analyze SpaCy entities and return those suitable for capitalization.
        
        Args:
            doc: SpaCy document object
            text: Original text
            entities: List of existing entities for overlap checking
            
        Returns:
            List of tuples (start, end, entity_text) for capitalization
        """
        entities_to_capitalize = []

        for ent in doc.ents:
            logger.debug(f"SpaCy found entity: '{ent.text}' ({ent.label_}) at {ent.start_char}-{ent.end_char}")
            
            # Only process certain entity types
            if ent.label_ not in ["PERSON", "ORG", "GPE", "NORP", "LANGUAGE", "EVENT"]:
                continue

            # Skip if should be skipped due to technical context
            if self.should_skip_spacy_entity_for_technical_context(ent.text, ent.label_, text):
                continue

            # Skip if this SpaCy entity is inside a final filtered entity
            if entities and is_inside_entity(ent.start_char, ent.end_char, entities):
                logger.debug(
                    f"Skipping SpaCy-detected entity '{ent.text}' because it is inside a final filtered entity."
                )
                continue

            # Handle technical verb replacement
            should_replace, replacement = self.should_handle_technical_verb_capitalization(
                ent.text, ent.label_
            )
            if should_replace:
                # Return the replacement info but don't add to capitalize list
                continue

            logger.debug(f"Adding '{ent.text}' to capitalize list (type: {ent.label_})")
            entities_to_capitalize.append((ent.start_char, ent.end_char, ent.text))

        return entities_to_capitalize