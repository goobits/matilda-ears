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
logger = setup_logging(__name__)


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
        
        # Load language-specific capitalization context
        self.capitalization_context = rules.resources.get("capitalization_context", {})
        self.continuation_words = set(self.capitalization_context.get("continuation_words", []))
        self.entity_rules = self.capitalization_context.get("entity_capitalization_rules", {})
        self.spanish_lowercase_after_entities = set(
            self.capitalization_context.get("spanish_lowercase_after_entities", [])
        )

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
        # Check preceding text for variable indicators (expanded to catch more contexts)
        preceding_text = text[max(0, position - 30):position].lower()
        
        # Enhanced variable detection with position awareness
        variable_indicators = [
            "variable is", "counter is", "iterator is", "for i in", 
            "variable i", "letter i", "the variable is", "variable called",
            "the counter is", "the iterator is", "set i to", "set i equals",
            "i equals", "i is equal"
        ]
        
        # Special case: "when i write i" - only the second 'i' should be treated as variable
        # Check if this is the second 'i' in the "write i" pattern
        if "write i" in preceding_text and position > 0:
            # Look backwards to see if there's "write" immediately before this 'i'
            write_pattern_start = max(0, position - 10)
            write_context = text[write_pattern_start:position + 1].lower()
            if write_context.endswith("write i"):
                return True
        
        # Also check if 'i' comes after mathematical/assignment operators
        following_text = text[position + 1:position + 10].lower()
        if any(op in following_text for op in [" equals", " =", " +", " -", " *", " /"]):
            return True
            
        # Check for explicit variable context indicators
        if any(keyword in preceding_text for keyword in variable_indicators):
            return True
            
        # Enhanced check for assignment contexts
        # Look for "set i", "let i", etc.
        if any(pattern in preceding_text for pattern in ["set i", "let i", "declare i"]):
            return True
            
        return False

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

            # For Spanish, check if this entity contains continuation words that shouldn't be capitalized
            if self.rules.language == "es" and self._should_skip_spanish_entity(ent.text, ent.label_, text):
                logger.debug(f"Skipping Spanish entity '{ent.text}' due to continuation word context")
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

    def should_capitalize_after_entity(
        self, 
        entity_type: str, 
        following_word: str, 
        full_context: str = ""
    ) -> bool:
        """Determine if a word should be capitalized after a specific entity type.
        
        Args:
            entity_type: The type of entity (e.g., "SLASH_COMMAND", "COMMAND_FLAG")
            following_word: The word that follows the entity
            full_context: Full text context for additional analysis
            
        Returns:
            True if the word should be capitalized, False otherwise
        """
        # For Spanish language, check entity-specific rules
        if self.rules.language == "es":
            return self._should_capitalize_after_entity_spanish(
                entity_type, following_word, full_context
            )
        
        # For other languages, use default behavior (usually capitalize)
        return True

    def _should_capitalize_after_entity_spanish(
        self, 
        entity_type: str, 
        following_word: str, 
        full_context: str
    ) -> bool:
        """Spanish-specific logic for capitalization after entities.
        
        Args:
            entity_type: The type of entity
            following_word: The word that follows the entity
            full_context: Full text context
            
        Returns:
            True if the word should be capitalized
        """
        # Get entity-specific rules
        entity_rule = self.entity_rules.get(entity_type, {})
        
        # Default behavior from entity rules
        capitalize_after = entity_rule.get("capitalize_after", True)
        
        # Check if word is in continuation words (should not be capitalized)
        if following_word.lower() in self.continuation_words:
            logger.debug(f"Word '{following_word}' is a Spanish continuation word - not capitalizing")
            return False
        
        # Check if word is in Spanish lowercase after entities list
        if following_word.lower() in self.spanish_lowercase_after_entities:
            logger.debug(f"Word '{following_word}' should remain lowercase after Spanish entities")
            return False
        
        # Check for exception patterns (words that should always be capitalized)
        exception_patterns = entity_rule.get("exception_patterns", [])
        for pattern in exception_patterns:
            import re
            if re.match(pattern, following_word):
                logger.debug(f"Word '{following_word}' matches exception pattern '{pattern}' - capitalizing")
                return True
        
        # For technical entities in Spanish, default to not capitalizing unless at sentence start
        if entity_type in ["SLASH_COMMAND", "COMMAND_FLAG", "SIMPLE_UNDERSCORE_VARIABLE", "UNDERSCORE_DELIMITER"]:
            # Check if we're at the start of a sentence
            if self._is_sentence_start_context(full_context, following_word):
                return True
            return capitalize_after
        
        return capitalize_after

    def _is_sentence_start_context(self, full_context: str, word: str) -> bool:
        """Check if a word appears at the start of a sentence.
        
        Args:
            full_context: Full text context
            word: The word to check
            
        Returns:
            True if the word is at sentence start
        """
        if not full_context or not word:
            return False
        
        word_pos = full_context.lower().find(word.lower())
        if word_pos <= 0:
            return True  # Word is at the very beginning
        
        # Check if preceded by sentence-ending punctuation
        preceding_text = full_context[:word_pos].strip()
        if not preceding_text:
            return True
        
        # Look for sentence endings
        sentence_endings = ['.', '!', '?']
        if any(preceding_text.endswith(ending) for ending in sentence_endings):
            return True
        
        return False

    def get_spanish_capitalization_decision(
        self, 
        word: str, 
        position: int, 
        text: str, 
        preceding_entities: list = None
    ) -> dict:
        """Get capitalization decision for Spanish text based on context.
        
        Args:
            word: The word to potentially capitalize
            position: Position of the word in text
            text: Full text context
            preceding_entities: List of entities that precede this word
            
        Returns:
            Dictionary with capitalization decision and reasoning
        """
        decision = {
            "capitalize": True,
            "reason": "default",
            "entity_influenced": False
        }
        
        # Check if this word follows a technical entity
        if preceding_entities:
            for entity in preceding_entities:
                entity_type = getattr(entity, 'type', None) or getattr(entity, 'entity_type', None)
                if entity_type and hasattr(entity_type, 'name'):
                    entity_type_name = entity_type.name
                elif isinstance(entity_type, str):
                    entity_type_name = entity_type
                else:
                    continue
                
                # Check if word should not be capitalized after this entity
                should_cap = self.should_capitalize_after_entity(
                    entity_type_name, word, text
                )
                
                if not should_cap:
                    decision.update({
                        "capitalize": False,
                        "reason": f"follows_{entity_type_name.lower()}_entity",
                        "entity_influenced": True
                    })
                    logger.debug(f"Spanish capitalization: '{word}' not capitalized due to preceding {entity_type_name}")
                    break
        
        # Override for sentence start
        if self._is_sentence_start_context(text, word):
            decision.update({
                "capitalize": True,
                "reason": "sentence_start",
                "entity_influenced": False
            })
        
        return decision

    def _should_skip_spanish_entity(self, entity_text: str, entity_label: str, full_text: str) -> bool:
        """Check if a SpaCy entity should be skipped in Spanish due to continuation word context.
        
        Args:
            entity_text: The entity text detected by SpaCy
            entity_label: SpaCy entity label (PERSON, ORG, etc.)
            full_text: Full text context
            
        Returns:
            True if the entity should be skipped (not capitalized)
        """
        # Split entity text into words
        entity_words = entity_text.lower().split()
        
        # Check if any word in the entity is a Spanish continuation word
        for word in entity_words:
            if word in self.continuation_words:
                logger.debug(f"Spanish entity '{entity_text}' contains continuation word '{word}' - skipping")
                return True
            
            if word in self.spanish_lowercase_after_entities:
                logger.debug(f"Spanish entity '{entity_text}' contains lowercase-after-entity word '{word}' - skipping")
                return True
        
        # Check if the entity appears after a technical entity (like a command flag)
        entity_start_pos = full_text.lower().find(entity_text.lower())
        if entity_start_pos > 0:
            # Look at the text before the entity to see if it contains technical indicators
            preceding_text = full_text[:entity_start_pos].strip()
            
            # Common patterns that indicate the following text should not be capitalized
            spanish_technical_patterns = ['-h', '-v', '-f', '-d', '/', '--']
            
            if any(pattern in preceding_text for pattern in spanish_technical_patterns):
                logger.debug(f"Spanish entity '{entity_text}' follows technical pattern - skipping")
                return True
        
        return False