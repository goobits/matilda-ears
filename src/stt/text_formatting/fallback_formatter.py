#!/usr/bin/env python3
"""
Fallback Text Formatter - Robust text formatting with graceful degradation.

This module provides a text formatter that gracefully handles failures by
implementing multiple fallback strategies when the primary SpaCy-based
formatting fails.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# Import batch regex processing for string optimization
from .batch_regex import batch_artifact_removal

logger = logging.getLogger(__name__)


@dataclass
class FormattingResult:
    """Result of text formatting with metadata about the process."""
    
    original_text: str
    formatted_text: str
    success: bool = True
    fallback_used: Optional[str] = None
    errors: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def add_error(self, error: str) -> None:
        """Add an error to the error list."""
        self.errors.append(error)
        if self.success:
            self.success = False


class FallbackTextFormatter:
    """
    Text formatter with comprehensive fallback chain.
    
    Primary Strategy: SpaCy-based advanced formatting
    Fallback Strategies (in order):
    1. Regex-based entity detection
    2. Simple punctuation and capitalization
    3. Basic cleaning only
    4. Passthrough (return original)
    """
    
    def __init__(self, primary_formatter=None, language: str = "en"):
        """
        Initialize the fallback formatter.
        
        Args:
            primary_formatter: Primary TextFormatter instance (optional)
            language: Language for formatting
        """
        self.primary_formatter = primary_formatter
        self.language = language
        self.spacy_available = True
        
        # Compile regex patterns for fallback strategies
        self._compile_fallback_patterns()
    
    def _compile_fallback_patterns(self) -> None:
        """Compile regex patterns for fallback strategies."""
        # Basic entity patterns for regex fallback
        self.patterns = {
            'email': re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'),
            'url': re.compile(r'https?://[^\s]+|www\.[^\s]+'),
            'phone': re.compile(r'\b\d{3}-\d{3}-\d{4}\b|\b\(\d{3}\)\s*\d{3}-\d{4}\b'),
            'currency': re.compile(r'\$\d+(?:\.\d{2})?|\d+\s*(?:dollars?|cents?|USD)\b', re.IGNORECASE),
            'percentage': re.compile(r'\d+(?:\.\d+)?\s*%|\d+\s*percent', re.IGNORECASE),
            'number': re.compile(r'\b\d+(?:\.\d+)?\b'),
            'time': re.compile(r'\b\d{1,2}:\d{2}(?::\d{2})?\s*(?:AM|PM|am|pm)?\b'),
            'date': re.compile(r'\b\d{1,2}/\d{1,2}/\d{2,4}\b|\b\d{4}-\d{2}-\d{2}\b'),
        }
        
        # Common abbreviations that should keep periods
        self.abbreviations = {
            'dr', 'mr', 'mrs', 'ms', 'prof', 'inc', 'corp', 'ltd',
            'etc', 'vs', 'eg', 'ie', 'ph', 'md', 'phd', 'jr', 'sr'
        }
    
    def format_text(
        self, 
        text: str, 
        key_name: str = "", 
        enter_pressed: bool = False,
        language: Optional[str] = None
    ) -> FormattingResult:
        """
        Format text with comprehensive fallback chain.
        
        Args:
            text: Text to format
            key_name: Key name for context
            enter_pressed: Whether enter was pressed
            language: Optional language override
            
        Returns:
            FormattingResult with formatted text and metadata
        """
        if not text or not text.strip():
            return FormattingResult(
                original_text=text,
                formatted_text="",
                metadata={"strategy": "empty_input"}
            )
        
        result = FormattingResult(original_text=text, formatted_text=text)
        current_language = language or self.language
        
        # Strategy 1: Primary SpaCy-based formatting
        if self.spacy_available and self.primary_formatter:
            try:
                formatted = self.primary_formatter.format_transcription(
                    text, key_name, enter_pressed, current_language
                )
                result.formatted_text = formatted
                result.metadata["strategy"] = "primary_spacy"
                result.metadata["language"] = current_language
                logger.debug(f"Primary formatting successful: '{text}' -> '{formatted}'")
                return result
                
            except Exception as e:
                error_msg = f"Primary SpaCy formatting failed: {e}"
                result.add_error(error_msg)
                logger.warning(error_msg)
                
                # Disable SpaCy for this session if it's consistently failing
                self.spacy_available = False
        
        # Strategy 2: Regex-based entity detection
        try:
            formatted = self._regex_based_formatting(text)
            result.formatted_text = formatted
            result.fallback_used = "regex_entities"
            result.metadata["strategy"] = "regex_entities"
            logger.info(f"Regex fallback used: '{text}' -> '{formatted}'")
            return result
            
        except Exception as e:
            error_msg = f"Regex-based formatting failed: {e}"
            result.add_error(error_msg)
            logger.warning(error_msg)
        
        # Strategy 3: Simple punctuation and capitalization
        try:
            formatted = self._simple_formatting(text)
            result.formatted_text = formatted
            result.fallback_used = "simple_punctuation"
            result.metadata["strategy"] = "simple_punctuation"
            logger.info(f"Simple formatting fallback used: '{text}' -> '{formatted}'")
            return result
            
        except Exception as e:
            error_msg = f"Simple formatting failed: {e}"
            result.add_error(error_msg)
            logger.warning(error_msg)
        
        # Strategy 4: Basic cleaning only
        try:
            formatted = self._basic_cleaning(text)
            result.formatted_text = formatted
            result.fallback_used = "basic_cleaning"
            result.metadata["strategy"] = "basic_cleaning"
            logger.warning(f"Basic cleaning fallback used: '{text}' -> '{formatted}'")
            return result
            
        except Exception as e:
            error_msg = f"Basic cleaning failed: {e}"
            result.add_error(error_msg)
            logger.error(error_msg)
        
        # Strategy 5: Passthrough (last resort)
        result.formatted_text = text
        result.fallback_used = "passthrough"
        result.metadata["strategy"] = "passthrough"
        logger.error(f"All formatting strategies failed, using passthrough: '{text}'")
        
        return result
    
    def _regex_based_formatting(self, text: str) -> str:
        """Regex-based entity detection and basic formatting."""
        formatted = text.strip()
        
        # Protect entities by replacing with placeholders
        protected_entities = []
        placeholder_text = formatted
        
        # Protect entities in order of specificity
        for entity_type, pattern in self.patterns.items():
            matches = list(pattern.finditer(placeholder_text))
            for i, match in enumerate(reversed(matches)):  # Reverse to preserve indices
                placeholder = f"__ENTITY_{entity_type.upper()}_{len(protected_entities)}__"
                protected_entities.append((placeholder, match.group()))
                start, end = match.span()
                placeholder_text = placeholder_text[:start] + placeholder + placeholder_text[end:]
        
        # Apply basic formatting to non-entity text
        formatted_text = self._apply_basic_rules(placeholder_text)
        
        # Restore protected entities
        for placeholder, original in protected_entities:
            formatted_text = formatted_text.replace(placeholder, original)
        
        return formatted_text
    
    def _simple_formatting(self, text: str) -> str:
        """Simple punctuation and capitalization rules."""
        formatted = text.strip()
        
        if not formatted:
            return formatted
        
        # Basic sentence capitalization
        sentences = re.split(r'([.!?]+)', formatted)
        capitalized_sentences = []
        
        for i, part in enumerate(sentences):
            if i % 2 == 0 and part.strip():  # Text parts (not punctuation)
                # Capitalize first letter of sentence
                part = part.strip()
                if part:
                    part = part[0].upper() + part[1:]
                capitalized_sentences.append(part)
            else:
                capitalized_sentences.append(part)
        
        formatted = ''.join(capitalized_sentences)
        
        # Add period if no ending punctuation
        if formatted and not formatted.rstrip()[-1] in '.!?':
            formatted = formatted.rstrip() + '.'
        
        return formatted
    
    def _basic_cleaning(self, text: str) -> str:
        """Basic text cleaning only."""
        # Remove common transcription artifacts using batch processing for efficiency
        artifacts = ['um', 'uh', 'er', 'ah']
        cleaned = batch_artifact_removal(text, artifacts)
        
        return cleaned
    
    def _apply_basic_rules(self, text: str) -> str:
        """Apply basic formatting rules to text."""
        # Capitalize first letter
        if text:
            text = text[0].upper() + text[1:]
        
        # Capitalize "I"
        from .pattern_modules.common_patterns import PRONOUN_I_BASIC_PATTERN
        text = re.sub(PRONOUN_I_BASIC_PATTERN, 'I', text)
        
        # Basic punctuation
        if text and not text.rstrip()[-1] in '.!?':
            text = text.rstrip() + '.'
        
        return text
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get formatter statistics and status."""
        return {
            "spacy_available": self.spacy_available,
            "primary_formatter_loaded": self.primary_formatter is not None,
            "language": self.language,
            "fallback_patterns_loaded": len(self.patterns),
            "abbreviations_loaded": len(self.abbreviations)
        }
    
    def reset_spacy_availability(self) -> None:
        """Reset SpaCy availability (useful for testing)."""
        self.spacy_available = True