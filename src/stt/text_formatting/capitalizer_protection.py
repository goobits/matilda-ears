#!/usr/bin/env python3
"""Entity protection logic for the SmartCapitalizer."""
from __future__ import annotations

import re
from typing import TYPE_CHECKING

from ..core.config import setup_logging

if TYPE_CHECKING:
    from .common import Entity
    from .capitalizer_rules import CapitalizationRules

# Setup logging
logger = setup_logging(__name__, log_filename="text_formatting.txt", include_console=False)


class EntityProtection:
    """Handles entity protection logic for capitalization."""

    def __init__(self, rules: 'CapitalizationRules'):
        """Initialize entity protection with capitalization rules.
        
        Args:
            rules: CapitalizationRules instance containing protection logic
        """
        self.rules = rules

    def should_capitalize_first_letter(
        self, 
        text: str, 
        first_letter_index: int, 
        entities: list['Entity'] | None = None
    ) -> bool:
        """Determine if the first letter should be capitalized based on entity protection.
        
        Args:
            text: The full text being processed
            first_letter_index: Index of the first alphabetic character
            entities: List of entities that may affect capitalization
            
        Returns:
            True if the first letter should be capitalized
        """
        if entities is None:
            return True

        for entity in entities:
            if entity.start <= first_letter_index < entity.end:
                logger.debug(
                    f"Checking entity at start: {entity.type} '{entity.text}' [{entity.start}:{entity.end}], first_letter_index={first_letter_index}"
                )
                
                # Don't capitalize if it's a strictly protected type, except for abbreviations and special cases
                if self.rules.is_strictly_protected_type(entity.type):
                    if entity.type.name == "ABBREVIATION":
                        # Special case: abbreviations at sentence start should have first letter capitalized
                        # but preserve the abbreviation format (e.g., "i.e." -> "I.e.")
                        logger.debug(f"Abbreviation '{entity.text}' at sentence start, capitalizing first letter only")
                        # Don't set should_capitalize = False, let it capitalize normally
                        # The abbreviation entity will handle maintaining the correct format
                        return True
                    elif entity.type.name in ["URL", "SPOKEN_URL", "SPOKEN_PROTOCOL_URL", "PORT_NUMBER"]:
                        # URLs and port numbers should NEVER be capitalized, even at sentence start
                        logger.debug(f"URL/Port entity '{entity.text}' at sentence start - preventing capitalization")
                        return False
                    elif entity.type.name == "VARIABLE" and entity.text == "i":
                        # Special case: single letter 'i' variables need context-aware handling
                        # Check if this is truly a pronoun context vs variable context
                        is_pronoun_context = self._is_i_pronoun_context(text, first_letter_index)
                        if is_pronoun_context:
                            logger.debug(f"Variable 'i' detected as pronoun in context - allowing capitalization")
                            return True
                        else:
                            logger.debug(f"Variable 'i' in variable context - preventing capitalization")
                            return False
                    else:
                        logger.debug(f"Entity {entity.type} is strictly protected")
                        return False
                        
                # Special rule for CLI commands: only keep lowercase if the *entire* text is the command
                elif entity.type.name == "CLI_COMMAND":
                    if entity.text.strip() == text.strip():
                        logger.debug("CLI command is entire text, not capitalizing")
                        return False
                    logger.debug(
                        f"CLI command '{entity.text}' is not entire text '{text}', allowing capitalization"
                    )
                    # Otherwise, allow normal capitalization for CLI commands at sentence start
                    
                # Special rule for versions starting with 'v' (e.g., v1.2)
                elif entity.type.name == "VERSION" and entity.text.startswith("v"):
                    logger.debug(f"Version entity '{entity.text}' starts with 'v', not capitalizing")
                    return False
                    
                # PROGRAMMING STATEMENT LOGIC: Programming keywords that start code statements
                # should NOT be capitalized because they start code, not natural language sentences
                elif entity.type.name == "PROGRAMMING_KEYWORD" and entity.start == 0:
                    # Check if this is a programming statement keyword that should stay lowercase
                    code_statement_keywords = {"if", "when", "while", "unless", "until", "let", "const", "var", "for", "def", "function"}
                    if entity.text.lower() in code_statement_keywords:
                        logger.debug(
                            f"Programming statement keyword '{entity.text}' at sentence start - preventing capitalization to preserve code context"
                        )
                        return False
                    else:
                        logger.debug(
                            f"Non-statement programming keyword '{entity.text}' at sentence start - allowing capitalization for proper sentence structure"
                        )
                        # Allow capitalization for non-statement programming keywords
                        break

        return True

    def is_entity_protected_from_sentence_capitalization(
        self, 
        position: int, 
        entities: list['Entity'] | None = None
    ) -> bool:
        """Check if a position is inside a protected entity for sentence capitalization.
        
        Args:
            position: Character position to check
            entities: List of entities to check against
            
        Returns:
            True if the position should be protected from sentence capitalization
        """
        if entities is None:
            return False

        for entity in entities:
            if entity.start <= position < entity.end:
                return True
        return False

    def is_position_inside_protected_entity(
        self, 
        position: int, 
        entities: list['Entity'] | None = None
    ) -> bool:
        """Check if a position is inside any protected entity.
        
        Args:
            position: Character position to check
            entities: List of entities to check against
            
        Returns:
            True if the position is inside a protected entity
        """
        return self.is_entity_protected_from_sentence_capitalization(position, entities)

    def should_protect_from_spacy_capitalization(
        self, 
        start: int, 
        end: int, 
        entities: list['Entity'] | None = None
    ) -> bool:
        """Check if a text span should be protected from SpaCy proper noun capitalization.
        
        Args:
            start: Start position of the span
            end: End position of the span
            entities: List of entities to check against
            
        Returns:
            True if the span should be protected from SpaCy capitalization
        """
        if entities is None:
            return False

        for entity in entities:
            # Check if the SpaCy entity overlaps with any protected entity
            if start < entity.end and end > entity.start:
                logger.debug(
                    f"SpaCy entity at {start}-{end} overlaps with protected entity {entity.type} at {entity.start}-{entity.end}"
                )
                
                if self.rules.should_protect_entity_from_spacy_capitalization(entity.type):
                    logger.debug(f"Protecting entity from capitalization due to {entity.type}")
                    return True
                logger.debug(f"Entity type {entity.type} not in protected list, allowing capitalization")
                
        return False

    def should_protect_from_uppercase_conversion(
        self, 
        start: int, 
        end: int, 
        entities: list['Entity'] | None = None
    ) -> bool:
        """Check if a text span should be protected from uppercase abbreviation conversion.
        
        Args:
            start: Start position of the span
            end: End position of the span
            entities: List of entities to check against
            
        Returns:
            True if the span should be protected from uppercase conversion
        """
        if entities is None:
            return False

        for entity in entities:
            if (start < entity.end and end > entity.start and 
                self.rules.should_protect_entity_from_uppercase_conversion(entity.type)):
                return True
                
        return False

    def has_placeholders(self, text: str) -> bool:
        """Check if text contains placeholders that should skip SpaCy processing.
        
        Args:
            text: Text to check for placeholders
            
        Returns:
            True if text contains placeholders
        """
        return "__CAPS_" in text or "__PLACEHOLDER_" in text or "__ENTITY_" in text

    def is_placeholder_context(self, text: str, start: int, end: int) -> bool:
        """Check if a text span is in a placeholder context.
        
        Args:
            text: Full text
            start: Start position of the span
            end: End position of the span
            
        Returns:
            True if the span is in a placeholder context
        """
        # Check the actual text at this position
        actual_text = text[start:end]
        # Also check if we're inside a placeholder by looking at surrounding context
        context_start = max(0, start - 2)
        context_end = min(len(text), end + 2)
        context = text[context_start:context_end]

        return "__" in context or actual_text.strip(".,!?").endswith("__")

    def restore_placeholders(self, text: str, placeholder_pattern: str) -> str:
        """Restore original case for placeholders in text.
        
        Args:
            text: Text with potential placeholder modifications
            placeholder_pattern: Regex pattern for placeholders
            
        Returns:
            Text with restored placeholder casing
        """
        placeholders_found = re.findall(placeholder_pattern, text)
        
        # Restore original case for placeholders
        for placeholder in placeholders_found:
            text = re.sub(placeholder, placeholder, text, flags=re.IGNORECASE)
            
        return text
    
    def _is_i_pronoun_context(self, text: str, position: int) -> bool:
        """Check if 'i' at given position should be treated as a pronoun (not variable).
        
        Args:
            text: Full text
            position: Position of 'i' in text
            
        Returns:
            True if 'i' should be treated as a pronoun and capitalized
        """
        # Simple heuristic: if 'i' is at sentence start OR followed by a verb, treat as pronoun
        # This is a simplified approach since SpaCy is not available
        
        # Check if this is sentence start (accounting for leading punctuation/spaces)
        if position <= 5:  # Near beginning of sentence
            return True
            
        # Look at surrounding context
        context_before = text[max(0, position - 15):position].lower()
        context_after = text[position + 1:position + 15].lower()
        
        # If preceded by "when", "if", "because", etc., likely a pronoun
        pronoun_indicators = ["when ", "if ", "because ", "since ", "while ", "after "]
        if any(text[max(0, position - len(indicator) - 1):position].lower().endswith(indicator) 
               for indicator in pronoun_indicators):
            return True
            
        # If followed by common verbs, likely a pronoun
        verb_indicators = [" think", " write", " am", " was", " will", " have", " had", " do", " did"]
        if any(context_after.startswith(verb) for verb in verb_indicators):
            return True
            
        # If followed by assignment operators, likely a variable
        assignment_indicators = [" equals", " =", " +=", " -="]
        if any(context_after.startswith(op) for op in assignment_indicators):
            return False
            
        # Default: treat as pronoun (safer to over-capitalize than under-capitalize)
        return True