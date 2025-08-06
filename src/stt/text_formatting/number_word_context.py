"""
Context-based number word detection using research-backed approaches.

This module implements standard techniques for disambiguating when number
words should be converted to digits vs. kept as words.
"""

from typing import List, Set, Optional, Tuple
from enum import Enum
import re

from stt.text_formatting.common import Entity, EntityType


class NumberWordDecision(Enum):
    """Decision for number word conversion."""
    KEEP_WORD = "keep"
    CONVERT_DIGIT = "convert"
    CONTEXT_DEPENDENT = "context"


class NumberWordContextAnalyzer:
    """
    Analyzes context to determine if number words should be converted to digits.
    
    Based on research from:
    - Sproat et al. (2001) "Normalization of non-standard words"
    - Taylor (2009) "Text-to-speech synthesis" 
    - Zhang et al. (2019) "Neural Models of Text Normalization"
    """
    
    def __init__(self, nlp=None):
        """Initialize with optional SpaCy model."""
        self.nlp = nlp
        
        # Common patterns where numbers should remain as words
        self.keep_as_word_patterns = [
            # Determiners
            r'\b(the|a|an)\s+one\s+(of|who|that|which)',
            r'\b(the|a|an)\s+one\s+\w+ing\b',  # "the one thing", "a one standing"
            
            # Idiomatic expressions
            r'\bone\s+(of\s+the|of\s+these|of\s+those|of\s+them)\b',
            r'\b(no|any|every|each)\s+one\b',
            r'\b(one|two|three)\s+or\s+(two|three|four)\b',  # "one or two"
            
            # Pronouns and emphasis
            r'\b(only|just|another|other)\s+one\b',
            r'\byou\'re\s+the\s+one\b',
            r'\bthe\s+one\s+(and\s+only|who|that)\b',
            
            # Common phrases
            r'\bone\s+(day|time|moment|minute)\b(?!\s+ago)',  # But not "one day ago"
            r'\bat\s+one\s+with\b',
            r'\bone\s+by\s+one\b',
            r'\bone\s+on\s+one\b',
        ]
        
        # Patterns where numbers should be converted to digits
        self.convert_to_digit_patterns = [
            # Explicit numbering
            r'\b(page|chapter|section|volume|part|step|line|verse)\s+(\w+)\b',
            r'\b(number|#|no\.?)\s*(\w+)\b',
            
            # Lists and sequences  
            r'\b(\w+)[,;]\s*(\w+)[,;]?\s*(?:and\s+)?(\w+)\b',  # "one, two, three"
            r'\b(step|item|point)\s+(\w+)[:.]',
            
            # Mathematical contexts
            r'\b(\w+)\s*(plus|minus|times|divided\s+by|over)\s*(\w+)\b',
            r'\b(\w+)\s*([\+\-\*/=])\s*(\w+)\b',
            
            # Measurements and quantities
            r'\b(\w+)\s+(feet|inches|meters|miles|pounds|dollars|percent)\b',
            r'\b(\w+)\s+(hundred|thousand|million|billion)\b',
            
            # Time expressions
            r'\b(\w+)\s+o\'clock\b',
            r'\b(\w+)\s+(a\.?m\.?|p\.?m\.?)\b',
            r'\b(\w+)\s+(hours?|minutes?|seconds?)\s+(ago|later|before|after)\b',
            
            # Scores and rankings
            r'\b(\w+)\s+to\s+(\w+)\b(?=\s+(lead|win|victory|score))',
            r'\b(top|first|last)\s+(\w+)\b',
        ]
        
        # Number words to consider
        self.number_words = {
            'zero', 'one', 'two', 'three', 'four', 'five',
            'six', 'seven', 'eight', 'nine', 'ten',
            'eleven', 'twelve', 'thirteen', 'fourteen', 'fifteen',
            'sixteen', 'seventeen', 'eighteen', 'nineteen', 'twenty'
        }
    
    def should_convert_number_word(self, text: str, word_start: int, word_end: int) -> NumberWordDecision:
        """
        Determine if a number word at the given position should be converted.
        
        Args:
            text: Full text
            word_start: Start position of number word
            word_end: End position of number word
            
        Returns:
            Decision on whether to convert
        """
        word = text[word_start:word_end].lower()
        
        # Quick check if it's a number word
        if word not in self.number_words:
            return NumberWordDecision.KEEP_WORD
        
        # Get surrounding context
        context_start = max(0, word_start - 50)
        context_end = min(len(text), word_end + 50)
        context = text[context_start:context_end]
        
        # Check keep-as-word patterns
        for pattern in self.keep_as_word_patterns:
            if re.search(pattern, context, re.IGNORECASE):
                return NumberWordDecision.KEEP_WORD
        
        # Check convert-to-digit patterns
        for pattern in self.convert_to_digit_patterns:
            if re.search(pattern, context, re.IGNORECASE):
                return NumberWordDecision.CONVERT_DIGIT
        
        # Use SpaCy if available
        if self.nlp:
            decision = self._analyze_with_spacy(text, word_start, word_end)
            if decision != NumberWordDecision.CONTEXT_DEPENDENT:
                return decision
        
        # Default heuristics
        return self._apply_heuristics(text, word_start, word_end)
    
    def _analyze_with_spacy(self, text: str, word_start: int, word_end: int) -> NumberWordDecision:
        """Use SpaCy for linguistic analysis."""
        try:
            doc = self.nlp(text)
            
            # Find the token
            target_token = None
            for token in doc:
                if token.idx <= word_start and token.idx + len(token.text) >= word_end:
                    target_token = token
                    break
            
            if not target_token:
                return NumberWordDecision.CONTEXT_DEPENDENT
            
            # POS tag analysis
            if target_token.pos_ == "DET":  # Determiner
                return NumberWordDecision.KEEP_WORD
            
            if target_token.pos_ == "NUM":
                # Check dependency
                if target_token.dep_ in ["det", "nsubj", "dobj"]:
                    # Could be either - need more context
                    return NumberWordDecision.CONTEXT_DEPENDENT
                elif target_token.dep_ in ["nummod", "compound"]:
                    # Likely a number modifier
                    return NumberWordDecision.CONVERT_DIGIT
            
            # Entity type analysis
            if target_token.ent_type_ == "CARDINAL":
                # Check if it's modifying something
                if any(child.dep_ in ["compound", "amod"] for child in target_token.children):
                    return NumberWordDecision.CONVERT_DIGIT
            
        except Exception:
            pass
        
        return NumberWordDecision.CONTEXT_DEPENDENT
    
    def _apply_heuristics(self, text: str, word_start: int, word_end: int) -> NumberWordDecision:
        """Apply additional heuristics for edge cases."""
        word = text[word_start:word_end].lower()
        
        # Check previous word
        prev_word_match = re.search(r'(\w+)\s+$', text[:word_start])
        if prev_word_match:
            prev_word = prev_word_match.group(1).lower()
            
            # Strong indicators to keep as word
            if prev_word in ['the', 'a', 'an', 'only', 'just', 'another']:
                return NumberWordDecision.KEEP_WORD
            
            # Strong indicators to convert
            if prev_word in ['page', 'chapter', 'section', 'step', 'number']:
                return NumberWordDecision.CONVERT_DIGIT
        
        # Check next word
        next_word_match = re.search(r'^\s+(\w+)', text[word_end:])
        if next_word_match:
            next_word = next_word_match.group(1).lower()
            
            # Units suggest conversion
            if next_word in ['percent', 'dollars', 'feet', 'meters', 'miles']:
                return NumberWordDecision.CONVERT_DIGIT
            
            # "one thing/person/way" patterns
            if word == 'one' and next_word in ['thing', 'person', 'way', 'time', 'place']:
                return NumberWordDecision.KEEP_WORD
        
        # Check capitalization (beginning of sentence)
        if word_start == 0 or (word_start > 0 and text[word_start-1] in '.!?'):
            # More likely to be a word at sentence start
            return NumberWordDecision.KEEP_WORD
        
        # Default: keep words like "one" as words in most contexts
        if word in ['one', 'zero']:
            return NumberWordDecision.KEEP_WORD
        
        # Other numbers more likely to be digits
        return NumberWordDecision.CONVERT_DIGIT


def integrate_with_detector(analyzer: NumberWordContextAnalyzer, 
                           entities: List[Entity]) -> List[Entity]:
    """
    Filter entities based on context analysis.
    
    This would be integrated into the detection pipeline to prevent
    incorrect number word conversions.
    """
    filtered_entities = []
    
    for entity in entities:
        if entity.type == EntityType.CARDINAL:
            # Check if this cardinal should be kept as a word
            decision = analyzer.should_convert_number_word(
                entity.metadata.get('full_text', ''),
                entity.start,
                entity.end
            )
            
            if decision != NumberWordDecision.KEEP_WORD:
                filtered_entities.append(entity)
        else:
            filtered_entities.append(entity)
    
    return filtered_entities