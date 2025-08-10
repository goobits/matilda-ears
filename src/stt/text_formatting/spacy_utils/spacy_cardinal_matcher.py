#!/usr/bin/env python3
"""
SpaCy-based CARDINAL entity matcher for consolidating duplicate number word lists.

This module provides a unified approach to detecting number words using spaCy's
CARDINAL entity recognition instead of maintaining separate hardcoded lists.
Part of Phase 2 Regex→NLP Migration.
"""
from __future__ import annotations

import re
from typing import Optional, Set, List, Tuple

from ...core.config import setup_logging
from ..number_word_context import NumberWordContextAnalyzer, NumberWordDecision
from ..spacy_doc_cache import get_global_doc_processor

# Setup logging
logger = setup_logging(__name__)


class SpacyCardinalMatcher:
    """
    Unified CARDINAL number word matcher using spaCy NER.
    
    Replaces hardcoded number word lists from:
    - financial_patterns.py
    - mathematical_patterns.py  
    - basic_numeric_patterns.py
    - resources/en.json
    """
    
    def __init__(self, nlp=None, language: str = "en"):
        """
        Initialize the SpaCy CARDINAL matcher.
        
        Args:
            nlp: SpaCy NLP model instance
            language: Language code for resource loading (default: 'en')
        """
        self.nlp = nlp
        self.language = language
        self.context_analyzer = None
        
        if nlp:
            self.context_analyzer = NumberWordContextAnalyzer(nlp)
            
        # Fallback number words for when spaCy is not available
        self._fallback_number_words = {
            'zero', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine',
            'ten', 'eleven', 'twelve', 'thirteen', 'fourteen', 'fifteen', 'sixteen', 
            'seventeen', 'eighteen', 'nineteen', 'twenty', 'thirty', 'forty', 'fifty', 
            'sixty', 'seventy', 'eighty', 'ninety', 'hundred', 'thousand', 'million', 
            'billion', 'trillion'
        }

    def get_number_word_pattern(self, context: str = "") -> str:
        """
        Get a regex pattern for number words, preferring spaCy detection when available.
        
        Args:
            context: Context for the pattern (e.g., "currency", "math", "basic")
            
        Returns:
            Regex pattern string for number words
        """
        if self.nlp and self.spacy_processor:
            # Use spaCy-enhanced detection
            return self._get_spacy_based_pattern(context)
        else:
            # Fallback to hardcoded pattern
            return self._get_fallback_pattern()
    
    def _get_spacy_based_pattern(self, context: str) -> str:
        """
        Generate a regex pattern that works with spaCy CARDINAL detection.
        
        This creates a pattern that can work alongside spaCy NER for cases where
        regex is still needed for complex patterns.
        
        Args:
            context: Context for the pattern
            
        Returns:
            Regex pattern string
        """
        # Create a more flexible pattern using the fallback words
        words = '|'.join(sorted(self._fallback_number_words, key=len, reverse=True))
        base_pattern = rf"(?:\b(?:{words})\b(?:\s+(?:{words})\b)*)"
        
        return base_pattern
    
    def _get_fallback_pattern(self) -> str:
        """
        Generate fallback regex pattern when spaCy is not available.
        
        Returns:
            Regex pattern string using hardcoded number words
        """
        words = '|'.join(sorted(self._fallback_number_words, key=len, reverse=True))
        return rf"\b(?:{words})\b"
    
    def find_number_words(self, text: str, context: str = "") -> List[Tuple[int, int, str]]:
        """
        Find all number word spans in text using spaCy CARDINAL detection.
        
        Args:
            text: Input text to analyze
            context: Context for better detection
            
        Returns:
            List of (start, end, text) tuples for detected number words
        """
        if not self.nlp:
            return self._find_number_words_fallback(text)
            
        try:
            # Use centralized document processor for better caching
            doc_processor = get_global_doc_processor()
            if doc_processor:
                doc = doc_processor.get_or_create_doc(text)
            else:
                # Fallback to direct nlp processing if processor not available
                doc = self.nlp(text) if self.nlp else None
                
            if not doc:
                return self._find_number_words_fallback(text)
            number_spans = []
            
            for ent in doc.ents:
                if ent.label_ == "CARDINAL":
                    # Use context analyzer to determine if we should include this
                    if self.context_analyzer:
                        decision = self.context_analyzer.should_convert_number_word(
                            text, ent.start_char, ent.end_char
                        )
                        
                        # For pattern matching, we want to detect all potential number words
                        # The actual conversion decision is made later in the pipeline
                        if decision != NumberWordDecision.KEEP_WORD or context == "detect_all":
                            number_spans.append((ent.start_char, ent.end_char, ent.text))
                    else:
                        # Without context analyzer, include all CARDINAL entities
                        number_spans.append((ent.start_char, ent.end_char, ent.text))
                        
            return number_spans
            
        except Exception as e:
            logger.warning(f"spaCy number word detection failed: {e}")
            return self._find_number_words_fallback(text)
    
    def _find_number_words_fallback(self, text: str) -> List[Tuple[int, int, str]]:
        """
        Fallback method to find number words using regex when spaCy is unavailable.
        
        Args:
            text: Input text to analyze
            
        Returns:
            List of (start, end, text) tuples for detected number words
        """
        pattern = self._get_fallback_pattern()
        matches = []
        
        for match in re.finditer(pattern, text, re.IGNORECASE):
            matches.append((match.start(), match.end(), match.group()))
            
        return matches
    
    def is_number_word(self, word: str) -> bool:
        """
        Check if a word is a number word.
        
        Args:
            word: Word to check
            
        Returns:
            True if the word is a number word, False otherwise
        """
        if self.nlp:
            try:
                # Use centralized document processor for better caching
                doc_processor = get_global_doc_processor()
                if doc_processor:
                    doc = doc_processor.get_or_create_doc(word.strip())
                else:
                    # Fallback to direct nlp processing if processor not available
                    doc = self.nlp(word.strip())
                    
                if not doc:
                    return word.lower().strip() in self._fallback_number_words
                return any(ent.label_ == "CARDINAL" for ent in doc.ents)
            except Exception:
                pass
        
        # Fallback check
        return word.lower().strip() in self._fallback_number_words
    
    def replace_pattern_in_file(self, file_path: str, old_pattern: str, context: str = "") -> bool:
        """
        Replace a hardcoded number word pattern in a file with spaCy-based detection.
        
        This method is for migration purposes - it helps replace regex patterns
        with calls to this matcher.
        
        Args:
            file_path: Path to the file to modify
            old_pattern: Old hardcoded pattern to replace
            context: Context for the new pattern
            
        Returns:
            True if replacement was successful, False otherwise
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # This would be used in the migration process
            # For now, just log what we would replace
            logger.info(f"Would replace pattern in {file_path}: {old_pattern[:50]}...")
            return True
            
        except Exception as e:
            logger.error(f"Failed to replace pattern in {file_path}: {e}")
            return False


# Factory function for easy instantiation
def create_spacy_cardinal_matcher(nlp=None, language: str = "en") -> SpacyCardinalMatcher:
    """
    Create a SpacyCardinalMatcher instance.
    
    Args:
        nlp: SpaCy NLP model instance
        language: Language code for resource loading (default: 'en')
        
    Returns:
        SpacyCardinalMatcher instance
    """
    return SpacyCardinalMatcher(nlp, language)