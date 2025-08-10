#!/usr/bin/env python3
"""Variable and identifier-related entity detection for code transcriptions."""
from __future__ import annotations

import re

from stt.core.config import setup_logging
from stt.text_formatting import regex_patterns
from stt.text_formatting.common import Entity, EntityType
from stt.text_formatting.constants import get_resources
from stt.text_formatting.utils import is_inside_entity

logger = setup_logging(__name__)


class VariableDetector:
    """Detects variable and identifier-related entities like underscore variables and programming keywords."""

    def __init__(self, language: str = "en"):
        """
        Initialize VariableDetector.

        Args:
            language: Language code for resource loading (default: 'en')
        """
        self.language = language
        self.resources = get_resources(language)

        # Build patterns dynamically for the specified language
        self.underscore_delimiter_pattern = regex_patterns.get_underscore_delimiter_pattern(language)
        self.simple_underscore_pattern = regex_patterns.get_simple_underscore_pattern(language)

    def detect_programming_keywords(
        self, text: str, entities: list[Entity], all_entities: list[Entity] | None = None
    ) -> None:
        """Detects standalone programming keywords like 'let', 'const', 'if'."""
        if all_entities is None:
            all_entities = entities

        resources = get_resources(self.language)
        programming_keywords = resources.get("context_words", {}).get("programming_keywords", [])

        for keyword in programming_keywords:
            # Use regex to find whole-word matches, ensuring it's not part of another word
            pattern = rf"\b{re.escape(keyword)}\b"
            for match in re.finditer(pattern, text, re.IGNORECASE):
                if not is_inside_entity(match.start(), match.end(), all_entities):
                    entities.append(
                        Entity(
                            start=match.start(),
                            end=match.end(),
                            text=match.group(0),
                            type=EntityType.PROGRAMMING_KEYWORD,
                            metadata={"keyword": match.group(0)},
                        )
                    )

    def detect_abbreviations(
        self, text: str, entities: list[Entity], all_entities: list[Entity] | None = None
    ) -> None:
        """Detect Latin abbreviations that should remain lowercase."""
        abbrev_pattern = regex_patterns.ABBREVIATION_PATTERN
        for match in abbrev_pattern.finditer(text):
            check_entities = all_entities if all_entities else entities
            if not is_inside_entity(match.start(), match.end(), check_entities):
                entities.append(
                    Entity(start=match.start(), end=match.end(), text=match.group(1), type=EntityType.ABBREVIATION)
                )

    def detect_underscore_delimiters(
        self, text: str, entities: list[Entity], all_entities: list[Entity] | None = None
    ) -> None:
        """Detects spoken underscore delimiters like 'underscore underscore blah underscore underscore' -> '__blah__'."""
        underscore_delimiter_pattern = self.underscore_delimiter_pattern
        for match in underscore_delimiter_pattern.finditer(text):
            check_entities = all_entities if all_entities else entities
            if not is_inside_entity(match.start(), match.end(), check_entities):
                # Count leading and trailing underscores
                full_match = match.group(0)
                content = match.group(2)  # The content between underscores

                # Count leading underscores by counting "underscore" words at the start
                leading_part = match.group(1)  # e.g., "underscore underscore "
                leading_underscores = leading_part.count("underscore")

                # Count trailing underscores by counting "underscore" words at the end
                trailing_part = match.group(3)  # e.g., " underscore underscore"
                trailing_underscores = trailing_part.count("underscore")

                logger.debug(
                    f"Found underscore delimiter: '{full_match}' -> '{'_' * leading_underscores}{content}{'_' * trailing_underscores}'"
                )
                entities.append(
                    Entity(
                        start=match.start(),
                        end=match.end(),
                        text=full_match,
                        type=EntityType.UNDERSCORE_DELIMITER,
                        metadata={
                            "content": content,
                            "leading_underscores": leading_underscores,
                            "trailing_underscores": trailing_underscores,
                        },
                    )
                )

    def detect_simple_underscore_variables(
        self, text: str, entities: list[Entity], all_entities: list[Entity] | None = None
    ) -> None:
        """Detects simple underscore variables like 'user underscore id' -> 'user_id'."""
        simple_underscore_pattern = self.simple_underscore_pattern
        for match in simple_underscore_pattern.finditer(text):
            check_entities = all_entities if all_entities else entities
            if not is_inside_entity(match.start(), match.end(), check_entities):
                first_word = match.group(1)
                second_word = match.group(2)

                # Check context - only detect if preceded by programming keywords OR
                # if the first word itself is a programming context word
                context_words = text[: match.start()].lower().split()
                preceding_word = context_words[-1] if context_words else ""

                # Valid programming context words from resources
                programming_keywords = set(self.resources.get("context_words", {}).get("programming_keywords", []))
                technical_context = set(self.resources.get("context_words", {}).get("technical_context", []))
                # Also include some universal words that are common across languages
                universal_words = {"variable", "let", "const", "var", "set", "is", "check", "mi", "my"}
                valid_context_words = programming_keywords | technical_context | universal_words

                # Check if either there's a preceding context word OR the first word is a context word
                has_valid_context = (
                    preceding_word in valid_context_words  # Preceding word is valid
                    or first_word.lower() in valid_context_words  # First word itself is valid context
                )

                if not has_valid_context:
                    continue

                logger.debug(f"Found simple underscore variable: '{match.group(0)}' -> '{first_word}_{second_word}'")
                entities.append(
                    Entity(
                        start=match.start(),
                        end=match.end(),
                        text=match.group(0),
                        type=EntityType.SIMPLE_UNDERSCORE_VARIABLE,
                        metadata={
                            "first_word": first_word,
                            "second_word": second_word,
                        },
                    )
                )
                
    def detect_single_letter_variables(
        self, text: str, entities: list[Entity], all_entities: list[Entity] | None = None
    ) -> None:
        """Detects single-letter variables like 'i', 'x', 'y' in code contexts."""
        if all_entities is None:
            all_entities = entities
            
        # Pattern to find single letters that could be variables
        pattern = r'\b([ijklmnxyz])\b'
        
        for match in re.finditer(pattern, text, re.IGNORECASE):
            if not is_inside_entity(match.start(), match.end(), all_entities):
                letter = match.group(1)
                
                # Check if this single letter is in a variable context
                context_before = text[max(0, match.start() - 30):match.start()].lower()
                # Limit context_after to immediate next few words to avoid false positives from later assignments
                context_after = text[match.end():match.end() + 8].lower()  # Reduced from 15 to 8
                
                # Variable context indicators  
                variable_contexts = [
                    "variable", "counter", "iterator", "the variable is", "variable called",
                    "set " + letter.lower(), "for " + letter.lower() + " in",
                    "let " + letter.lower(), "const " + letter.lower(), "var " + letter.lower()
                ]
                
                # Special handling for "write" context - only consider it a variable context
                # if this letter comes AFTER "write", not before it
                write_context_found = False
                if "write " + letter.lower() in context_before:
                    # The letter comes after "write", likely a variable: "write i equals"
                    write_context_found = True
                
                # Check for assignment/mathematical operators after
                assignment_contexts = [" equals", " =", " +", " -", " *", " /"]
                
                is_variable_context = (
                    any(ctx in context_before for ctx in variable_contexts) or
                    any(ctx in context_after for ctx in assignment_contexts) or
                    write_context_found
                )
                
                if is_variable_context:
                    logger.debug(f"Found single-letter variable: '{letter}' at position {match.start()}-{match.end()}")
                    logger.debug(f"  Context before: '{context_before}'")
                    logger.debug(f"  Context after: '{context_after}'")
                    logger.debug(f"  Variable contexts match: {any(ctx in context_before for ctx in variable_contexts)}")
                    logger.debug(f"  Assignment contexts match: {any(ctx in context_after for ctx in assignment_contexts)}")
                    logger.debug(f"  Write context match: {write_context_found}")
                    entities.append(
                        Entity(
                            start=match.start(),
                            end=match.end(),
                            text=letter,
                            type=EntityType.VARIABLE,
                            metadata={"letter": letter.lower()},
                        )
                    )