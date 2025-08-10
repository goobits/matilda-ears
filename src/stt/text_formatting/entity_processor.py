"""
Generic base class for entity detection and conversion.

This module provides a unified abstraction for the detector/converter pattern,
eliminating code duplication across specialized entity processors.
"""

import re
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Callable, Any, Pattern
from dataclasses import dataclass, field

from stt.core.config import setup_logging
from stt.text_formatting.common import Entity, EntityType
from stt.text_formatting.common import NumberParser
from stt.text_formatting.constants import get_resources
from stt.text_formatting.utils import is_inside_entity
from stt.text_formatting.mapping_registry import get_mapping_registry

logger = setup_logging(__name__)


@dataclass
class ProcessingRule:
    """Defines a rule for processing entities."""
    pattern: Pattern[str]
    entity_type: EntityType
    metadata_extractor: Optional[Callable[[re.Match], Dict[str, Any]]] = None
    priority: int = 0
    context_filters: List[Callable[[str, int, int], bool]] = field(default_factory=list)
    
    def __post_init__(self):
        """Ensure pattern is compiled."""
        if isinstance(self.pattern, str):
            self.pattern = re.compile(self.pattern, re.IGNORECASE)


class EntityProcessor(ABC):
    """
    Generic base class for entity detection and conversion.
    
    This class eliminates code duplication by providing common functionality
    for all detector/converter pairs in the text formatting system.
    """
    
    def __init__(self, nlp=None, language: str = "en"):
        """Initialize the entity processor."""
        self.language = language
        self.nlp = self._init_spacy(nlp)
        self.number_parser = NumberParser(language=language)
        self.mapping_registry = get_mapping_registry(language)
        self.resources = get_resources(language)
        
        # Initialize processing rules and conversion methods
        self.detection_rules = self._init_detection_rules()
        self.conversion_methods = self._init_conversion_methods()
        
        # Cache for performance
        self._context_cache = {}
        
    @abstractmethod
    def _init_detection_rules(self) -> List[ProcessingRule]:
        """Initialize detection rules specific to this processor."""
        pass
        
    @abstractmethod  
    def _init_conversion_methods(self) -> Dict[EntityType, str]:
        """Initialize conversion method mapping."""
        pass
    
    def detect_entities(self, text: str, entities: List[Entity], 
                       all_entities: Optional[List[Entity]] = None) -> None:
        """
        Generic entity detection using processing rules.
        
        Args:
            text: Text to process
            entities: List to append detected entities to
            all_entities: Optional list of all entities for overlap checking
        """
        # Sort rules by priority (highest first)
        sorted_rules = sorted(self.detection_rules, key=lambda r: r.priority, reverse=True)
        
        for rule in sorted_rules:
            try:
                self._apply_detection_rule(rule, text, entities, all_entities)
            except Exception as e:
                logger.error(f"Error applying rule {rule.entity_type}: {e}")
    
    def _apply_detection_rule(self, rule: ProcessingRule, text: str, 
                            entities: List[Entity], all_entities: Optional[List[Entity]]) -> None:
        """Apply a single detection rule."""
        check_entities = all_entities if all_entities is not None else entities
        
        for match in rule.pattern.finditer(text):
            # Standard overlap checking
            if not self._is_valid_entity_position(match.start(), match.end(), check_entities):
                continue
                
            # Apply context filters
            if rule.context_filters:
                if any(not filter_func(text, match.start(), match.end()) 
                      for filter_func in rule.context_filters):
                    continue
            
            # Extract metadata
            metadata = {}
            if rule.metadata_extractor:
                try:
                    metadata = rule.metadata_extractor(match)
                except Exception as e:
                    logger.warning(f"Metadata extraction failed: {e}")
            
            # Create entity
            entities.append(Entity(
                start=match.start(),
                end=match.end(),
                text=match.group(),
                type=rule.entity_type,
                metadata=metadata
            ))
    
    def convert_entity(self, entity: Entity, full_text: str = "") -> str:
        """
        Generic entity conversion using method dispatch.
        
        Args:
            entity: Entity to convert
            full_text: Full text for context analysis
            
        Returns:
            Converted text
        """
        converter_method = self.conversion_methods.get(entity.type)
        if converter_method and hasattr(self, converter_method):
            method = getattr(self, converter_method)
            
            # Handle different method signatures
            try:
                # Try with full_text first
                return method(entity, full_text)
            except TypeError:
                # Fall back to entity-only signature
                try:
                    return method(entity)
                except Exception as e:
                    logger.error(f"Conversion failed for {entity.type}: {e}")
                    
        return entity.text
    
    # Common utility methods
    
    def _is_valid_entity_position(self, start: int, end: int, 
                                existing_entities: List[Entity]) -> bool:
        """Check if entity position doesn't overlap with existing entities."""
        return not is_inside_entity(start, end, existing_entities)
    
    def _init_spacy(self, nlp):
        """Initialize SpaCy with fallback handling."""
        if nlp is None:
            try:
                from stt.text_formatting.nlp_provider import get_nlp
                return get_nlp()
            except ImportError:
                logger.warning("SpaCy not available, some features may be limited")
                return None
        return nlp
    
    # Common parsing utilities
    
    def parse_number(self, text: str) -> Optional[str]:
        """Parse number text using NumberParser."""
        return self.number_parser.parse(text)
    
    def parse_as_digits(self, text: str) -> Optional[str]:
        """Parse number text as individual digits."""
        return self.number_parser.parse_as_digits(text)
    
    def extract_trailing_punctuation(self, text: str) -> tuple[str, str]:
        """Extract trailing punctuation from text."""
        trailing_punct = ""
        if text and text[-1] in ".!?":
            trailing_punct = text[-1]
            text = text[:-1]
        return text, trailing_punct
    
    # Context analysis utilities
    
    def is_conversational_context(self, entity: Entity, full_text: str) -> bool:
        """
        Check if entity is in conversational context.
        
        Looks for casual/informal phrases that suggest spoken context.
        """
        # Cache key
        cache_key = f"conv_{entity.start}_{entity.end}"
        if cache_key in self._context_cache:
            return self._context_cache[cache_key]
            
        # Window for context analysis
        window_size = 50
        start = max(0, entity.start - window_size)
        end = min(len(full_text), entity.end + window_size)
        context_window = full_text[start:end].lower()
        
        # Conversational indicators
        conversational_phrases = [
            "like", "about", "around", "roughly", "approximately",
            "maybe", "probably", "i think", "i guess", "or so",
            "something like", "kind of", "sort of", "give or take"
        ]
        
        result = any(phrase in context_window for phrase in conversational_phrases)
        self._context_cache[cache_key] = result
        return result
        
    def is_positional_context(self, entity: Entity, full_text: str) -> bool:
        """
        Check if entity is in positional/ranking context.
        
        Looks for words indicating position, rank, or sequence.
        """
        # Cache key
        cache_key = f"pos_{entity.start}_{entity.end}"
        if cache_key in self._context_cache:
            return self._context_cache[cache_key]
            
        # Window for context analysis
        window_size = 30
        start = max(0, entity.start - window_size)
        end = min(len(full_text), entity.end + window_size)
        context_window = full_text[start:end].lower()
        
        # Positional indicators
        positional_words = [
            "place", "position", "rank", "ranking", "spot",
            "number", "finish", "came", "scored", "placed",
            "winner", "runner", "medal", "prize", "award"
        ]
        
        result = any(word in context_window for word in positional_words)
        self._context_cache[cache_key] = result
        return result
        
    def is_idiomatic_context(self, entity: Entity, full_text: str, phrase: str) -> bool:
        """
        Check if entity is part of an idiomatic expression.
        
        Args:
            entity: The entity to check
            full_text: Full text for context
            phrase: The phrase to check (e.g., "first")
            
        Returns:
            True if phrase is used idiomatically
        """
        # Get idiomatic phrases from resources
        idiomatic_phrases = self.resources.get("idiomatic_phrases", {})
        
        if phrase in idiomatic_phrases:
            following_words = idiomatic_phrases[phrase]
            
            # Check if any following word appears after the entity
            text_after = full_text[entity.end:entity.end + 20].lower()
            
            for word in following_words:
                if text_after.startswith(f" {word}") or text_after.startswith(f" {word} "):
                    return True
                    
        return False
    
    def format_with_currency_position(self, amount: str, symbol: str, 
                                    unit: str, trailing_punct: str = "") -> str:
        """
        Format currency with correct symbol position.
        
        Args:
            amount: The numeric amount
            symbol: Currency symbol
            unit: Currency unit name
            trailing_punct: Any trailing punctuation
            
        Returns:
            Formatted currency string
        """
        post_position_currencies = self.mapping_registry.get_post_position_currencies()
        
        if unit in post_position_currencies:
            # Post-position (e.g., "100 won")
            return f"{amount} {unit}{trailing_punct}"
        else:
            # Pre-position (e.g., "$100")
            return f"{symbol}{amount}{trailing_punct}"
    
    # SpaCy-based utilities
    
    def get_spacy_doc(self, text: str):
        """Get SpaCy document for text."""
        if self.nlp:
            return self.nlp(text)
        return None
        
    def find_number_tokens(self, doc, start_idx: int, end_idx: int) -> List[Any]:
        """Find tokens that could be part of a number."""
        if not doc:
            return []
            
        tokens = []
        for token in doc:
            if start_idx <= token.idx < end_idx:
                if token.pos_ in ["NUM", "NOUN"] or token.text.lower() in self.mapping_registry.get_number_word_mappings():
                    tokens.append(token)
        return tokens


class BaseNumericProcessor(EntityProcessor):
    """Base class for numeric processors with shared numeric utilities."""
    
    def __init__(self, nlp=None, language: str = "en"):
        """Initialize base numeric processor."""
        super().__init__(nlp, language)
        
        # Get common numeric mappings
        self.time_word_mappings = self.mapping_registry.get_time_word_mappings()
        self.digit_word_mappings = self.mapping_registry.get_digit_word_mappings()
        self.number_word_mappings = self.mapping_registry.get_number_word_mappings()
        self.denominator_mappings = self.mapping_registry.get_denominator_mappings()
        self.ordinal_word_to_numeric = self.mapping_registry.get_ordinal_word_to_numeric()
        self.ordinal_numeric_to_word = self.mapping_registry.get_ordinal_numeric_to_word()
        self.math_constant_mappings = self.mapping_registry.get_math_constant_mappings()
        self.superscript_mappings = self.mapping_registry.get_superscript_mappings()
        self.operator_mappings = self.mapping_registry.get_operator_mappings()
        
    def convert_to_superscript(self, text: str) -> str:
        """Convert digits and minus sign to superscript characters."""
        result = ""
        for char in str(text):
            result += self.superscript_mappings.get(char, char)
        return result
    
    def convert_ordinal_to_position(self, ordinal: str) -> str:
        """
        Convert ordinal to positional format based on context.
        
        Args:
            ordinal: Ordinal string (e.g., "1st", "2nd")
            
        Returns:
            Positional format (e.g., "#1", "#2") or original
        """
        # Extract number from ordinal
        import re
        match = re.match(r'(\d+)', ordinal)
        if match:
            number = match.group(1)
            return f"#{number}"
        return ordinal