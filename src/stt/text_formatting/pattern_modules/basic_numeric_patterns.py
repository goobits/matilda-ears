#!/usr/bin/env python3
"""
Basic numeric patterns for text formatting.

This module contains basic number constants, ordinal patterns, fraction patterns,
and numeric range patterns used throughout the text formatting system.
"""
from __future__ import annotations

import re
from typing import Pattern, Union, Tuple, List

from ..common import NumberParser
from ..nlp_provider import get_nlp
from ..pattern_cache import cached_pattern
from ..spacy_doc_cache import get_global_doc_processor
from ...core.config import setup_logging

# Setup logger for this module
logger = setup_logging(__name__)


# ==============================================================================
# NUMERIC CONSTANTS
# ==============================================================================

# Number words for speech recognition
NUMBER_WORDS = [
    "zero",
    "one",
    "two",
    "three",
    "four",
    "five",
    "six",
    "seven",
    "eight",
    "nine",
    "ten",
    "eleven",
    "twelve",
    "thirteen",
    "fourteen",
    "fifteen",
    "sixteen",
    "seventeen",
    "eighteen",
    "nineteen",
    "twenty",
    "thirty",
    "forty",
    "fifty",
    "sixty",
    "seventy",
    "eighty",
    "ninety",
    "hundred",
    "thousand",
    "million",
    "billion",
    "trillion",
]


# ==============================================================================
# SPACY-BASED ORDINAL MATCHER
# ==============================================================================


class SpacyOrdinalMatcher:
    """
    SpaCy-based ordinal matcher that replaces hardcoded regex patterns.
    
    This class provides a regex-like interface but uses spaCy NER for ORDINAL
    entity detection, significantly reducing hardcoded patterns.
    """
    
    def __init__(self, nlp, language: str = "en"):
        """
        Initialize the SpaCy-based ordinal matcher.
        
        Args:
            nlp: SpaCy NLP model instance
            language: Language code (currently only 'en' supported)
        """
        self.nlp = nlp
        self.language = language
    
    def search(self, text: str, pos: int = 0) -> Union['SpacyOrdinalMatch', None]:
        """
        Search for ordinal patterns using spaCy NER.
        
        Args:
            text: Text to search in
            pos: Starting position (for regex compatibility)
        
        Returns:
            SpacyOrdinalMatch object if ordinal found, None otherwise
        """
        try:
            # Use centralized document processor for better caching
            doc_processor = get_global_doc_processor()
            if doc_processor:
                doc = doc_processor.get_or_create_doc(text)
            else:
                # Use shared document processor for optimal caching
                from ..spacy_doc_cache import get_or_create_shared_doc
                doc = get_or_create_shared_doc(text, nlp_model=self.nlp) if self.nlp else None
            
            if not doc:
                return None
            
            # Find ORDINAL entities starting from the given position
            for ent in doc.ents:
                if ent.label_ == "ORDINAL" and ent.start_char >= pos:
                    # Skip idiomatic uses (basic check)
                    if self._should_skip_ordinal_basic(ent, text):
                        continue
                    
                    return SpacyOrdinalMatch(
                        match_text=ent.text,
                        start=ent.start_char,
                        end=ent.end_char,
                        groups=(ent.text,)  # For regex compatibility
                    )
            
            return None
            
        except Exception as e:
            # Log the error and fallback to regex search
            logger.debug(f"SpaCy ordinal detection failed: {e}. Falling back to regex pattern.")
            
            # Fallback: basic regex search on common ordinals
            import re
            fallback_pattern = re.compile(
                r"\b(first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth)\b",
                re.IGNORECASE
            )
            match = fallback_pattern.search(text, pos)
            if match:
                logger.debug(f"Regex fallback found ordinal: '{match.group(0)}' at {match.start()}-{match.end()}")
                return SpacyOrdinalMatch(
                    match_text=match.group(0),
                    start=match.start(),
                    end=match.end(),
                    groups=match.groups()
                )
            return None
    
    def findall(self, text: str) -> List[str]:
        """
        Find all ordinal matches in text.
        
        Args:
            text: Text to search in
        
        Returns:
            List of matched ordinal strings
        """
        matches = []
        try:
            # Use centralized document processor for better caching
            doc_processor = get_global_doc_processor()
            if doc_processor:
                doc = doc_processor.get_or_create_doc(text)
            else:
                # Use shared document processor for optimal caching
                from ..spacy_doc_cache import get_or_create_shared_doc
                doc = get_or_create_shared_doc(text, nlp_model=self.nlp) if self.nlp else None
                
            if not doc:
                raise Exception("No document available")
            for ent in doc.ents:
                if ent.label_ == "ORDINAL":
                    if not self._should_skip_ordinal_basic(ent, text):
                        matches.append(ent.text)
        except Exception as e:
            # Log the error and fallback to basic regex
            logger.debug(f"SpaCy ordinal findall failed: {e}. Falling back to regex pattern.")
            import re
            fallback_pattern = re.compile(
                r"\b(first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth)\b",
                re.IGNORECASE
            )
            matches = fallback_pattern.findall(text)
            logger.debug(f"Regex fallback found {len(matches)} ordinals: {matches}")
        
        return matches
    
    def finditer(self, text: str) -> List['SpacyOrdinalMatch']:
        """
        Find all ordinal matches and return iterator-like list of match objects.
        
        Args:
            text: Text to search in
        
        Returns:
            List of SpacyOrdinalMatch objects (for regex compatibility)
        """
        matches = []
        try:
            # Use centralized document processor for better caching
            doc_processor = get_global_doc_processor()
            if doc_processor:
                doc = doc_processor.get_or_create_doc(text)
            else:
                # Use shared document processor for optimal caching
                from ..spacy_doc_cache import get_or_create_shared_doc
                doc = get_or_create_shared_doc(text, nlp_model=self.nlp) if self.nlp else None
                
            if not doc:
                raise Exception("No document available")
            for ent in doc.ents:
                if ent.label_ == "ORDINAL":
                    if not self._should_skip_ordinal_basic(ent, text):
                        matches.append(SpacyOrdinalMatch(
                            match_text=ent.text,
                            start=ent.start_char,
                            end=ent.end_char,
                            groups=(ent.text,)
                        ))
        except Exception as e:
            # Log the error and fallback to basic regex
            logger.debug(f"SpaCy ordinal finditer failed: {e}. Falling back to regex pattern.")
            import re
            fallback_pattern = re.compile(
                r"\b(first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth)\b",
                re.IGNORECASE
            )
            for match in fallback_pattern.finditer(text):
                matches.append(SpacyOrdinalMatch(
                    match_text=match.group(0),
                    start=match.start(),
                    end=match.end(),
                    groups=match.groups()
                ))
            logger.debug(f"Regex fallback found {len(matches)} ordinals")
        
        return matches
    
    def _should_skip_ordinal_basic(self, ent, text: str) -> bool:
        """
        Basic check for whether to skip ordinal (simplified version of spacy_detector logic).
        
        Args:
            ent: SpaCy entity
            text: Full text
        
        Returns:
            True if ordinal should be skipped
        """
        # Basic check: skip if it starts a sentence and is followed by comma
        if ent.start_char == 0 or (ent.start_char > 0 and text[ent.start_char-1] in '.!?'):
            remaining_text = text[ent.end_char:].strip()
            if remaining_text.startswith(','):
                return True
        
        # Skip common idiomatic uses (basic check)
        ordinal_lower = ent.text.lower()
        following_text = text[ent.end_char:].strip().lower()
        
        # Common idiomatic patterns to skip
        idiomatic_starts = ['place', 'time', 'person', 'thing', 'impression', 'thought']
        for idiom in idiomatic_starts:
            if following_text.startswith(idiom):
                return True
                
        return False


class SpacyOrdinalMatch:
    """Match object that mimics regex Match behavior for spaCy ordinal matches."""
    
    def __init__(self, match_text: str, start: int, end: int, groups: Tuple[str, ...]):
        self.match_text = match_text
        self._start = start
        self._end = end
        self._groups = groups
    
    def group(self, n: int = 0) -> str:
        """Return the nth group from the match."""
        if n == 0:
            return self.match_text
        return self._groups[n-1] if n-1 < len(self._groups) else ""
    
    def start(self, group: int = 0) -> int:
        """Return start position of match."""
        return self._start
    
    def end(self, group: int = 0) -> int:
        """Return end position of match.""" 
        return self._end
    
    def span(self, group: int = 0) -> Tuple[int, int]:
        """Return (start, end) span of match."""
        return (self._start, self._end)


# ==============================================================================
# ORDINAL AND FRACTION PATTERN BUILDERS
# ==============================================================================


def build_ordinal_pattern(language: str = "en") -> Union[re.Pattern[str], 'SpacyOrdinalMatcher']:
    """Build the spoken ordinal pattern for the specified language.
    
    Uses spaCy NER for ORDINAL detection when available, falls back to regex patterns.
    """
    nlp = get_nlp()
    if nlp is not None:
        logger.debug("Using spaCy-based ordinal detection")
        return SpacyOrdinalMatcher(nlp, language)
    else:
        logger.info("spaCy not available, falling back to hardcoded ordinal regex patterns")
        # Fallback to original hardcoded regex pattern
        return re.compile(
            r"\b(first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth|"
            r"eleventh|twelfth|thirteenth|fourteenth|fifteenth|sixteenth|seventeenth|"
            r"eighteenth|nineteenth|twentieth|twenty[-\s]?first|twenty[-\s]?second|"
            r"twenty[-\s]?third|twenty[-\s]?fourth|twenty[-\s]?fifth|twenty[-\s]?sixth|"
            r"twenty[-\s]?seventh|twenty[-\s]?eighth|twenty[-\s]?ninth|thirtieth|"
            r"thirty[-\s]?first|thirty[-\s]?second|thirty[-\s]?third|thirty[-\s]?fourth|"
            r"thirty[-\s]?fifth|thirty[-\s]?sixth|thirty[-\s]?seventh|thirty[-\s]?eighth|"
            r"thirty[-\s]?ninth|fortieth|forty[-\s]?first|forty[-\s]?second|forty[-\s]?third|"
            r"forty[-\s]?fourth|forty[-\s]?fifth|forty[-\s]?sixth|forty[-\s]?seventh|"
            r"forty[-\s]?eighth|forty[-\s]?ninth|fiftieth|fifty[-\s]?first|fifty[-\s]?second|"
            r"fifty[-\s]?third|fifty[-\s]?fourth|fifty[-\s]?fifth|fifty[-\s]?sixth|"
            r"fifty[-\s]?seventh|fifty[-\s]?eighth|fifty[-\s]?ninth|sixtieth|sixty[-\s]?first|"
            r"sixty[-\s]?second|sixty[-\s]?third|sixty[-\s]?fourth|sixty[-\s]?fifth|"
            r"sixty[-\s]?sixth|sixty[-\s]?seventh|sixty[-\s]?eighth|sixty[-\s]?ninth|"
            r"seventieth|seventy[-\s]?first|seventy[-\s]?second|seventy[-\s]?third|"
            r"seventy[-\s]?fourth|seventy[-\s]?fifth|seventy[-\s]?sixth|seventy[-\s]?seventh|"
            r"seventy[-\s]?eighth|seventy[-\s]?ninth|eightieth|eighty[-\s]?first|"
            r"eighty[-\s]?second|eighty[-\s]?third|eighty[-\s]?fourth|eighty[-\s]?fifth|"
            r"eighty[-\s]?sixth|eighty[-\s]?seventh|eighty[-\s]?eighth|eighty[-\s]?ninth|"
            r"ninetieth|ninety[-\s]?first|ninety[-\s]?second|ninety[-\s]?third|"
            r"ninety[-\s]?fourth|ninety[-\s]?fifth|ninety[-\s]?sixth|ninety[-\s]?seventh|"
            r"ninety[-\s]?eighth|ninety[-\s]?ninth|hundredth|thousandth)\b",
            re.IGNORECASE,
        )


@cached_pattern
def build_fraction_pattern(language: str = "en") -> re.Pattern[str]:
    """Build the spoken fraction pattern for the specified language."""
    return re.compile(
        r"\b(one|two|three|four|five|six|seven|eight|nine|ten)\s+"
        r"(half|halves|third|thirds|quarter|quarters|fourth|fourths|fifth|fifths|"
        r"sixth|sixths|seventh|sevenths|eighth|eighths|ninth|ninths|tenth|tenths)\b",
        re.IGNORECASE,
    )


@cached_pattern
def build_compound_fraction_pattern(language: str = "en") -> re.Pattern[str]:
    """Build the compound fraction pattern for mixed numbers like 'one and one half'."""
    return re.compile(
        r"\b(one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)\s+"
        r"and\s+"
        r"(one|a|two|three|four|five|six|seven|eight|nine|ten)\s+"
        r"(half|halves|third|thirds|quarter|quarters|fourth|fourths|fifth|fifths|"
        r"sixth|sixths|seventh|sevenths|eighth|eighths|ninth|ninths|tenth|tenths)\b",
        re.IGNORECASE,
    )


@cached_pattern
def build_numeric_range_pattern(language: str = "en") -> re.Pattern[str]:
    """Build the numeric range pattern for ranges like 'one to ten'."""
    # Get the number words from a single source of truth
    _number_parser_instance = NumberParser(language)
    _number_words_pattern = "(?:" + "|".join(_number_parser_instance.all_number_words) + ")"

    # Define a reusable pattern for a sequence of one or more number words
    number_word_sequence = f"{_number_words_pattern}(?:\\s+{_number_words_pattern})*"

    # Build the range pattern from components - much more readable and maintainable
    return re.compile(
        rf"""
        \b                      # Word boundary
        (                       # Capture group 1: Start of range
            {number_word_sequence}
        )
        \s+to\s+                # The word "to"
        (                       # Capture group 2: End of range
            {number_word_sequence}
        )
        \b                      # Word boundary
        """,
        re.IGNORECASE | re.VERBOSE,
    )


@cached_pattern
def build_consecutive_digits_pattern(language: str = "en") -> re.Pattern[str]:
    """Build the consecutive digits pattern for sequences like 'six four four' -> '644'."""
    # Build pattern for single digits (zero through nine)
    single_digits = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine"]
    digit_pattern = "|".join(single_digits)
    
    # Pattern for consecutive single digits (3 or more for specificity)
    return re.compile(
        rf"\b({digit_pattern})\s+({digit_pattern})\s+({digit_pattern})(?:\s+({digit_pattern}))?\b", 
        re.IGNORECASE
    )


# ==============================================================================
# GETTER FUNCTIONS
# ==============================================================================


def get_ordinal_pattern(language: str = "en") -> re.Pattern[str]:
    """Get the ordinal pattern for the specified language."""
    return build_ordinal_pattern(language)


def get_fraction_pattern(language: str = "en") -> re.Pattern[str]:
    """Get the fraction pattern for the specified language."""
    return build_fraction_pattern(language)


def get_compound_fraction_pattern(language: str = "en") -> re.Pattern[str]:
    """Get the compound fraction pattern for the specified language."""
    return build_compound_fraction_pattern(language)


def get_numeric_range_pattern(language: str = "en") -> re.Pattern[str]:
    """Get the numeric range pattern for the specified language."""
    return build_numeric_range_pattern(language)


def get_consecutive_digits_pattern(language: str = "en") -> re.Pattern[str]:
    """Get the consecutive digits pattern for the specified language."""
    return build_consecutive_digits_pattern(language)


def get_number_words() -> list[str]:
    """Get the list of number words."""
    return NUMBER_WORDS.copy()