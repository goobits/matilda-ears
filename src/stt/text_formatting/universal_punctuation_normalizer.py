#!/usr/bin/env python3
"""
Universal Punctuation Normalization Framework (Phase 22)

This module provides a language-agnostic punctuation cleanup framework that
consolidates punctuation normalization patterns into a unified system. The
framework ensures consistent punctuation handling across all languages while
maintaining compatibility with existing functionality.

Key Features:
- Language-agnostic repeated punctuation normalization
- Centralized punctuation cleanup patterns
- Framework for future language-specific extensions
- No functional changes to existing punctuation behavior
- Minimal code addition focused on consistency improvement
"""
from __future__ import annotations

import re
from abc import ABC, abstractmethod
from typing import Dict, List, Tuple, Pattern, Optional, Any
from dataclasses import dataclass
from enum import Enum

from .pattern_cache import cached_pattern


class PunctuationType(Enum):
    """Types of punctuation that can be normalized."""
    REPEATED_DOTS = "repeated_dots"
    REPEATED_QUESTION = "repeated_question"
    REPEATED_EXCLAMATION = "repeated_exclamation"
    REPEATED_COMMA_LIKE = "repeated_comma_like"  # commas, semicolons, colons
    MIXED_PUNCTUATION = "mixed_punctuation"
    SPACING_PUNCTUATION = "spacing_punctuation"


@dataclass
class PunctuationRule:
    """Represents a punctuation normalization rule."""
    pattern: Pattern[str]
    replacement: str
    punctuation_type: PunctuationType
    description: str
    language_specific: bool = False


class LanguagePunctuationInterface(ABC):
    """Interface for language-specific punctuation handling."""
    
    @abstractmethod
    def get_language_code(self) -> str:
        """Get the language code (e.g., 'en', 'es', 'fr')."""
        pass
    
    @abstractmethod
    def get_custom_punctuation_rules(self) -> List[PunctuationRule]:
        """Get language-specific punctuation rules."""
        pass
    
    @abstractmethod
    def should_apply_rule(self, rule: PunctuationRule, text: str, position: int) -> bool:
        """Determine if a rule should be applied at a specific position."""
        pass


class UniversalPunctuationNormalizer:
    """
    Universal punctuation normalization framework.
    
    This class provides a unified interface for punctuation cleanup that works
    across all languages. It consolidates the existing punctuation patterns
    while providing extensibility for language-specific behavior.
    """
    
    def __init__(self, language: str = "en"):
        """
        Initialize the punctuation normalizer.
        
        Args:
            language: Language code for language-specific behavior
        """
        self.language = language
        self._language_handler: Optional[LanguagePunctuationInterface] = None
        self._universal_rules: List[PunctuationRule] = []
        self._compiled_rules: List[Tuple[Pattern[str], str]] = []
        self._initialize_universal_rules()
    
    def _initialize_universal_rules(self) -> None:
        """Initialize the universal punctuation normalization rules."""
        # Import pattern functions from existing punctuation patterns module
        from .pattern_modules.punctuation_patterns import (
            build_repeated_commas_pattern,
            build_repeated_dots_pattern,
            build_repeated_question_marks_pattern,
            build_repeated_exclamation_marks_pattern
        )
        
        # Define universal rules that apply to all languages
        self._universal_rules = [
            PunctuationRule(
                pattern=build_repeated_dots_pattern(),
                replacement=".",
                punctuation_type=PunctuationType.REPEATED_DOTS,
                description="Normalize multiple dots to single dot"
            ),
            PunctuationRule(
                pattern=build_repeated_question_marks_pattern(),
                replacement="?",
                punctuation_type=PunctuationType.REPEATED_QUESTION,
                description="Normalize multiple question marks to single question mark"
            ),
            PunctuationRule(
                pattern=build_repeated_exclamation_marks_pattern(),
                replacement="!",
                punctuation_type=PunctuationType.REPEATED_EXCLAMATION,
                description="Normalize multiple exclamation marks to single exclamation mark"
            ),
            PunctuationRule(
                pattern=build_repeated_commas_pattern(),
                replacement=r"\1",
                punctuation_type=PunctuationType.REPEATED_COMMA_LIKE,
                description="Normalize repeated commas, semicolons, and colons"
            ),
        ]
        
        # Compile rules for performance
        self._compile_rules()
    
    def _compile_rules(self) -> None:
        """Compile all rules into a list of (pattern, replacement) tuples."""
        self._compiled_rules = []
        
        # Add universal rules
        for rule in self._universal_rules:
            self._compiled_rules.append((rule.pattern, rule.replacement))
        
        # Add language-specific rules if handler is available
        if self._language_handler:
            custom_rules = self._language_handler.get_custom_punctuation_rules()
            for rule in custom_rules:
                self._compiled_rules.append((rule.pattern, rule.replacement))
    
    def set_language_handler(self, handler: LanguagePunctuationInterface) -> None:
        """
        Set a language-specific punctuation handler.
        
        Args:
            handler: Language-specific punctuation handler
        """
        if handler.get_language_code() == self.language:
            self._language_handler = handler
            self._compile_rules()  # Recompile with language-specific rules
    
    def normalize_punctuation(self, text: str) -> str:
        """
        Apply universal punctuation normalization to text.
        
        This method applies all compiled punctuation rules to the input text,
        maintaining compatibility with existing functionality while providing
        a unified normalization framework.
        
        Args:
            text: Input text to normalize
            
        Returns:
            Text with normalized punctuation
        """
        if not text:
            return text
        
        result = text
        
        # Apply all compiled rules in order
        for pattern, replacement in self._compiled_rules:
            try:
                result = pattern.sub(replacement, result)
            except (re.error, TypeError):
                # Skip malformed patterns gracefully
                continue
        
        return result
    
    def get_available_rules(self) -> List[PunctuationRule]:
        """
        Get all available punctuation rules.
        
        Returns:
            List of all punctuation rules (universal + language-specific)
        """
        rules = self._universal_rules.copy()
        if self._language_handler:
            rules.extend(self._language_handler.get_custom_punctuation_rules())
        return rules
    
    def get_compiled_patterns(self) -> List[Tuple[Pattern[str], str]]:
        """
        Get compiled patterns for backward compatibility.
        
        This method provides the same interface as the existing
        REPEATED_PUNCTUATION_PATTERNS for seamless integration.
        
        Returns:
            List of compiled (pattern, replacement) tuples
        """
        return self._compiled_rules
    
    def validate_rules(self) -> bool:
        """
        Validate all punctuation rules.
        
        Returns:
            True if all rules are valid, False otherwise
        """
        try:
            # Test each rule with a sample string
            test_text = "Hello... world??? How are you!!! Yes, yes, yes;;; OK:::"
            
            for rule in self._universal_rules:
                # Test that pattern is valid and doesn't throw exceptions
                rule.pattern.sub(rule.replacement, test_text)
            
            # Validate language-specific rules if handler exists
            if self._language_handler:
                for rule in self._language_handler.get_custom_punctuation_rules():
                    rule.pattern.sub(rule.replacement, test_text)
            
            return True
        except Exception:
            return False


# Global instance for backward compatibility
_global_normalizer: Optional[UniversalPunctuationNormalizer] = None


def get_universal_punctuation_normalizer(language: str = "en") -> UniversalPunctuationNormalizer:
    """
    Get or create the global punctuation normalizer instance.
    
    Args:
        language: Language code
        
    Returns:
        Universal punctuation normalizer instance
    """
    global _global_normalizer
    
    if _global_normalizer is None or _global_normalizer.language != language:
        _global_normalizer = UniversalPunctuationNormalizer(language)
    
    return _global_normalizer


def get_universal_punctuation_patterns(language: str = "en") -> List[Tuple[Pattern[str], str]]:
    """
    Get universal punctuation patterns for backward compatibility.
    
    This function provides the same interface as the existing pattern functions
    while using the new universal framework under the hood.
    
    Args:
        language: Language code
        
    Returns:
        List of compiled (pattern, replacement) tuples
    """
    normalizer = get_universal_punctuation_normalizer(language)
    return normalizer.get_compiled_patterns()


def normalize_punctuation_universal(text: str, language: str = "en") -> str:
    """
    Normalize punctuation using the universal framework.
    
    Args:
        text: Input text to normalize
        language: Language code
        
    Returns:
        Text with normalized punctuation
    """
    normalizer = get_universal_punctuation_normalizer(language)
    return normalizer.normalize_punctuation(text)


# Framework validation function
def validate_punctuation_framework() -> bool:
    """
    Validate the universal punctuation framework.
    
    Returns:
        True if framework is valid and functional
    """
    try:
        # Test multiple languages
        for lang in ["en", "es", "fr"]:
            normalizer = UniversalPunctuationNormalizer(lang)
            if not normalizer.validate_rules():
                return False
        
        # Test pattern retrieval
        patterns = get_universal_punctuation_patterns("en")
        if not patterns:
            return False
        
        # Test normalization
        test_text = "Hello... world??? Great!!!"
        result = normalize_punctuation_universal(test_text)
        expected = "Hello. world? Great!"
        if result != expected:
            return False
        
        return True
    except Exception:
        return False