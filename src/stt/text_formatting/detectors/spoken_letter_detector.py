#!/usr/bin/env python3
"""Spoken letter entity detection and conversion for transcriptions."""
from __future__ import annotations

import re
from typing import List

from stt.core.config import setup_logging
from stt.text_formatting import regex_patterns
from stt.text_formatting.common import Entity, EntityType

logger = setup_logging(__name__, log_filename="text_formatting.txt", include_console=False)


class SpokenLetterDetector:
    """Detector for spoken letters and letter sequences."""

    def __init__(self, language: str = "en"):
        """
        Initialize SpokenLetterDetector.

        Args:
            language: Language code for resource loading (default: 'en')
        """
        self.language = language
        
        # Build patterns dynamically for the specified language
        self.spoken_letter_pattern = regex_patterns.build_spoken_letter_pattern(language)
        self.letter_sequence_pattern = regex_patterns.build_letter_sequence_pattern(language)

    def detect(self, text: str, existing_entities: List[Entity]) -> List[Entity]:
        """
        Detects spoken letter entities in the text.

        Args:
            text: The text to analyze
            existing_entities: List of already detected entities to avoid overlaps

        Returns:
            List of detected Entity objects
        """
        entities: List[Entity] = []
        
        # Use instance language
        detect_language = self.language
        spoken_letter_pattern = self.spoken_letter_pattern
        letter_sequence_pattern = self.letter_sequence_pattern

        # Detect letter sequences first (they take precedence over single letters)
        self._detect_letter_sequences(text, entities, letter_sequence_pattern, detect_language, existing_entities)
        
        # Then detect single spoken letters (avoiding overlaps with sequences)
        self._detect_single_letters(text, entities, spoken_letter_pattern, detect_language, existing_entities)
        
        return entities

    def _detect_letter_sequences(
        self, text: str, entities: List[Entity], pattern: re.Pattern, language: str, existing_entities: List[Entity]
    ) -> None:
        """Detect letter sequences like 'A B C' or 'capital A B C'."""
        logger.debug(f"Detecting letter sequences in: '{text}'")
        
        for match in pattern.finditer(text):
            if (self._overlaps_with_existing(match.start(), match.end(), entities) or 
                self._overlaps_with_existing(match.start(), match.end(), existing_entities)):
                continue
                
            full_text = match.group(0)
            logger.debug(f"Found letter sequence match: '{full_text}' at {match.start()}-{match.end()}")
            
            # Extract letters from the sequence
            letters, case_info = self._extract_letters_from_sequence(match, language)
            
            if letters:
                metadata = {
                    "letters": letters,
                    "case": case_info,
                    "sequence_length": len(letters)
                }
                
                entities.append(
                    Entity(
                        start=match.start(),
                        end=match.end(),
                        text=full_text,
                        type=EntityType.LETTER_SEQUENCE,
                        metadata=metadata
                    )
                )
                
                logger.debug(f"Created letter sequence entity: {letters} with case: {case_info}")

    def _detect_single_letters(
        self, text: str, entities: List[Entity], pattern: re.Pattern, language: str, existing_entities: List[Entity]
    ) -> None:
        """Detect single spoken letters like 'capital A' or 'A mayúscula'."""
        logger.debug(f"Detecting single letters in: '{text}'")
        
        for match in pattern.finditer(text):
            if (self._overlaps_with_existing(match.start(), match.end(), entities) or 
                self._overlaps_with_existing(match.start(), match.end(), existing_entities)):
                continue
                
            full_text = match.group(0)
            logger.debug(f"Found single letter match: '{full_text}' at {match.start()}-{match.end()}")
            
            # Extract letter and case information
            letter, case_info = self._extract_single_letter(match, language)
            
            if letter:
                metadata = {
                    "letter": letter,
                    "case": case_info
                }
                
                entities.append(
                    Entity(
                        start=match.start(),
                        end=match.end(),
                        text=full_text,
                        type=EntityType.SPOKEN_LETTER,
                        metadata=metadata
                    )
                )
                
                logger.debug(f"Created single letter entity: {letter} with case: {case_info}")

    def _extract_letters_from_sequence(self, match: re.Match, language: str) -> tuple[List[str], str]:
        """Extract individual letters and case information from a sequence match."""
        # Get the full match text
        full_text = match.group(0).lower()
        
        # Get language resources to understand case keywords and letter mappings
        from stt.text_formatting.constants import get_resources
        resources = get_resources(language)
        letter_case_keywords = resources.get("letters", {})
        letter_keywords = resources.get("spoken_keywords", {}).get("letters", {})
        
        # Parse the sequence word by word to handle mixed case modifiers
        words = full_text.split()
        letters = []
        case_info = "mixed"  # Default for sequences with multiple case modifiers
        current_case = None
        has_mixed_cases = False
        
        i = 0
        while i < len(words):
            word = words[i]
            
            # Check if this word is a case modifier
            case_modifier = None
            for case_word, case_type in letter_case_keywords.items():
                if word == case_word.lower():
                    case_modifier = case_type
                    break
            
            if case_modifier:
                # This is a case modifier, apply it to the next letter
                current_case = case_modifier
                i += 1
                # Process the next word as a letter if it exists
                if i < len(words):
                    letter_word = words[i]
                    letter = self._word_to_letter(letter_word, letter_keywords)
                    if letter:
                        # Apply the case modifier to the letter
                        if current_case == "lowercase":
                            letters.append(letter.lower())
                        else:  # uppercase, capital, etc.
                            letters.append(letter.upper())
                        
                        # Track if we have mixed cases
                        if len(letters) > 1:
                            prev_case = "lowercase" if letters[-2].islower() else "uppercase"
                            curr_case = "lowercase" if letters[-1].islower() else "uppercase"
                            if prev_case != curr_case:
                                has_mixed_cases = True
            else:
                # This word should be a letter (no preceding case modifier)
                letter = self._word_to_letter(word, letter_keywords)
                if letter:
                    # Use current case or default to uppercase
                    if current_case == "lowercase":
                        letters.append(letter.lower())
                    else:
                        letters.append(letter.upper())
                        
                    # Track if we have mixed cases
                    if len(letters) > 1:
                        prev_case = "lowercase" if letters[-2].islower() else "uppercase"
                        curr_case = "lowercase" if letters[-1].islower() else "uppercase"
                        if prev_case != curr_case:
                            has_mixed_cases = True
            
            i += 1
        
        # Determine overall case information
        if has_mixed_cases:
            case_info = "mixed"
        elif letters:
            if all(l.isupper() for l in letters):
                case_info = "uppercase"
            elif all(l.islower() for l in letters):
                case_info = "lowercase"
            else:
                case_info = "mixed"
        
        return letters, case_info

    def _extract_single_letter(self, match: re.Match, language: str) -> tuple[str, str]:
        """Extract letter and case information from a single letter match."""
        # Get language resources
        from stt.text_formatting.constants import get_resources
        resources = get_resources(language)
        letter_case_keywords = resources.get("letters", {})
        letter_keywords = resources.get("spoken_keywords", {}).get("letters", {})
        
        # Handle different group structures based on language
        if language == "es":
            # Spanish: "A mayúscula" (letter + case)
            letter_word = match.group(1).lower() if match.group(1) else ""
            case_word = match.group(2).lower() if match.group(2) else ""
        else:
            # English and others: "capital A" (case + letter)
            case_word = match.group(1).lower() if match.group(1) else ""
            letter_word = match.group(2).lower() if match.group(2) else ""
        
        # Convert case word to case type
        case_info = letter_case_keywords.get(case_word, "uppercase")  # Default to uppercase
        
        # Convert word to letter
        letter = self._word_to_letter(letter_word, letter_keywords)
        
        # If no letter found via keywords, try direct letter mapping
        if not letter and len(letter_word) == 1 and letter_word.isalpha():
            letter = letter_word.upper() if case_info == "uppercase" else letter_word.lower()
        
        return letter, case_info

    def _word_to_letter(self, word: str, letter_keywords: dict) -> str:
        """Convert a spoken word to its corresponding letter."""
        word_lower = word.lower()
        
        # First try the phonetic alphabet and custom pronunciations
        for key, value in letter_keywords.items():
            if key.lower() == word_lower and len(value) == 1 and value.isalpha():
                return value.upper()  # Always return uppercase, case will be handled by metadata
        
        # If not found in keywords and it's a single letter, return it
        if len(word_lower) == 1 and word_lower.isalpha():
            return word_lower.upper()
        
        return ""

    def _overlaps_with_existing(self, start: int, end: int, entities: List[Entity]) -> bool:
        """Check if the given range overlaps with any existing entity."""
        for entity in entities:
            if not (end <= entity.start or start >= entity.end):
                return True
        return False