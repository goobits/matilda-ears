"""Base class and shared utilities for numeric converters."""

import re
from typing import Dict, Any, Optional
from abc import ABC, abstractmethod

from stt.core.config import setup_logging
from stt.text_formatting.common import Entity, EntityType
from stt.text_formatting.mapping_registry import get_mapping_registry

logger = setup_logging(__name__)


class BaseNumericConverter(ABC):
    """Base class for numeric converters with shared utilities and mappings."""
    
    def __init__(self, number_parser, language: str = "en"):
        """Initialize base numeric converter."""
        self.number_parser = number_parser
        self.language = language
        self.resources = {}  # Will be populated by subclasses
        
        # Get the mapping registry instance
        self.mapping_registry = get_mapping_registry(language)
        
        # Initialize mappings from registry for backward compatibility
        self._init_mappings_from_registry()
    
    def _init_mappings_from_registry(self):
        """Initialize mappings from the central registry for backward compatibility."""
        # Get all mappings from the registry
        self.post_position_currencies = self.mapping_registry.get_post_position_currencies()
        self.data_size_unit_map = self.mapping_registry.get_data_size_unit_map()
        self.frequency_unit_map = self.mapping_registry.get_frequency_unit_map()
        self.time_duration_unit_map = self.mapping_registry.get_time_duration_unit_map()
        self.time_word_mappings = self.mapping_registry.get_time_word_mappings()
        self.digit_word_mappings = self.mapping_registry.get_digit_word_mappings()
        self.number_word_mappings = self.mapping_registry.get_number_word_mappings()
        self.denominator_mappings = self.mapping_registry.get_denominator_mappings()
        self.ordinal_word_to_numeric = self.mapping_registry.get_ordinal_word_to_numeric()
        self.ordinal_numeric_to_word = self.mapping_registry.get_ordinal_numeric_to_word()
        self.unicode_fraction_mappings = self.mapping_registry.get_unicode_fraction_mappings()
        self.math_constant_mappings = self.mapping_registry.get_math_constant_mappings()
        self.superscript_mappings = self.mapping_registry.get_superscript_mappings()
        self.operator_mappings = self.mapping_registry.get_operator_mappings()
        self.hour_mappings = self.mapping_registry.get_hour_mappings()
    
    @abstractmethod
    def convert(self, entity: Entity, full_text: str = "") -> str:
        """Convert a numeric entity to its final form."""
        pass
    
    def get_converter_method(self, entity_type: EntityType) -> Optional[str]:
        """Get the converter method name for a given entity type."""
        # This will be implemented by subclasses that define supported_types
        return getattr(self, 'supported_types', {}).get(entity_type)
    
    def parse_trailing_punctuation(self, text: str) -> tuple[str, str]:
        """Extract trailing punctuation from text."""
        trailing_punct = ""
        if text and text[-1] in ".!?":
            trailing_punct = text[-1]
            text = text[:-1]
        return text, trailing_punct
    
    def format_with_currency_position(self, amount: str, symbol: str, unit: str, trailing_punct: str = "") -> str:
        """Format currency with proper symbol position."""
        if unit in self.post_position_currencies:
            return f"{amount}{symbol}{trailing_punct}"
        return f"{symbol}{amount}{trailing_punct}"
    
    def convert_number_words_in_text(self, text: str) -> str:
        """Convert number words to digits in a text string."""
        words = text.split()
        converted_words = []
        
        for word in words:
            # Try to parse as number
            num = self.number_parser.parse(word)
            if num:
                converted_words.append(num)
            # Convert operators
            elif word.lower() in self.operator_mappings:
                converted_words.append(self.operator_mappings[word.lower()])
            else:
                converted_words.append(word)
        
        return " ".join(converted_words)
    
    def get_ordinal_suffix(self, num: int) -> str:
        """Get the ordinal suffix for a number (st, nd, rd, th)."""
        if 11 <= num % 100 <= 13:
            return "th"
        return {1: "st", 2: "nd", 3: "rd"}.get(num % 10, "th")
    
    def convert_to_superscript(self, text: str) -> str:
        """Convert digits and minus sign to superscript characters."""
        result = ""
        for char in str(text):
            result += self.superscript_mappings.get(char, char)
        return result
    
    def is_conversational_context(self, entity: Entity, full_text: str) -> bool:
        """Check if the entity is in a conversational context."""
        if not full_text:
            return False
            
        context = full_text.lower()
        
        # Conversational patterns
        conversational_patterns = [
            r"\blet\'s\s+do\s+(?:this|that)\s+" + re.escape(entity.text.lower()),
            r"\bwe\s+(?:need|should)\s+(?:to\s+)?(?:handle|do)\s+(?:this|that)\s+" + re.escape(entity.text.lower()),
            r"\b(?:first|1st)\s+(?:thing|step|priority|order|task)",
            r"\bdo\s+(?:this|that)\s+" + re.escape(entity.text.lower()),
        ]
        
        for pattern in conversational_patterns:
            if re.search(pattern, context):
                return True
                
        return False
    
    def is_idiomatic_context(self, entity: Entity, full_text: str, ordinal_word: str) -> bool:
        """Check if the ordinal is in an idiomatic phrase context."""
        if not full_text:
            return False
            
        # Get idiomatic phrases from resources
        from ...constants import get_resources
        resources = get_resources(self.language)
        idiomatic_phrases = resources.get("technical", {}).get("idiomatic_phrases", {})
        
        if ordinal_word not in idiomatic_phrases:
            return False
            
        # Check if the word following the ordinal is in the idiomatic phrases list
        context = full_text.lower()
        entity_end = entity.end
        remaining_text = full_text[entity_end:].strip().lower()
        
        if remaining_text:
            words_after = remaining_text.split()
            if words_after and words_after[0] in idiomatic_phrases[ordinal_word]:
                # Check for technical/formal context that should override idiomatic detection
                technical_indicators = [
                    'software', 'technology', 'generation', 'quarter', 'earnings', 
                    'report', 'century', 'winner', 'performance', 'meeting',
                    'deadline', 'conference', 'agenda', 'process', 'option',
                    'item', 'step', 'iphone', 'competition', 'race', 'contest',
                    'ranking', 'leaderboard', 'score', 'match', 'tournament',
                    'came in', 'finished', 'placed', 'ranked', 'position',
                    'this is the', 'that was the', 'it was the', 'attempt', 'try', 'iteration'
                ]
                
                # If we find technical indicators, don't treat as idiomatic
                if any(indicator in context for indicator in technical_indicators):
                    return False
                    
                return True
        
        # Also check for sentence-start patterns with comma
        if entity.start == 0 and remaining_text.startswith(','):
            return True
            
        return False
    
    def is_positional_context(self, entity: Entity, full_text: str) -> bool:
        """Check if the entity is in a positional/ranking context."""
        if not full_text:
            return False
            
        context = full_text.lower()
        
        # Positional/ranking patterns
        positional_patterns = [
            r"\bfinished\s+" + re.escape(entity.text.lower()) + r"\s+place",
            r"\bcame\s+in\s+" + re.escape(entity.text.lower()),
            r"\branked\s+" + re.escape(entity.text.lower()),
            r"\b" + re.escape(entity.text.lower()) + r"\s+place",
            r"\bin\s+the\s+" + re.escape(entity.text.lower()),
        ]
        
        for pattern in positional_patterns:
            if re.search(pattern, context):
                return True
                
        return False
    
    def is_natural_speech_context(self, entity: Entity, full_text: str) -> bool:
        """Check if a simple number should stay as words in natural speech."""
        if not full_text or entity.text.lower() not in ["one", "two", "three", "four", "five", "six", "seven", "eight", "nine"]:
            return False
            
        # Get surrounding context
        start_context = max(0, entity.start - 50)
        end_context = min(len(full_text), entity.end + 50)
        context = full_text[start_context:end_context].lower()
        
        # Natural speech patterns where numbers should stay as words
        natural_patterns = [
            r'\b(?:which|what)\s+(?:\w+\s+)*' + re.escape(entity.text.lower()) + r'\b',
            r'\b(?:the|a)\s+' + re.escape(entity.text.lower()) + r'\s+of\b',  # "the one of", "a one of" but not "page one of"
            r'\b(?:how|which|what).*' + re.escape(entity.text.lower()) + r'.*(?:should|would|could|can)\b',
            r'\b(?:once|then|when).*' + re.escape(entity.text.lower()) + r'\b',
        ]
        
        for pattern in natural_patterns:
            if re.search(pattern, context):
                return True
                
        return False
    
    def is_hyphenated_compound(self, entity: Entity, full_text: str) -> bool:
        """Check if the entity is part of a hyphenated compound."""
        if not full_text:
            return False
            
        # Check character after entity end
        if entity.end < len(full_text) and full_text[entity.end] == "-":
            return True
            
        # Check character before entity start  
        if entity.start > 0 and full_text[entity.start - 1] == "-":
            return True
            
        return False