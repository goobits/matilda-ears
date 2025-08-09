"""
Pattern Factory for Text Formatting

This module provides a centralized factory for creating and caching patterns
to avoid duplication across pattern modules.
"""

import re
import inspect
from typing import Dict, Any, Callable, Union, List
from functools import lru_cache


class PatternFactory:
    """Factory for creating and caching patterns to avoid duplication."""
    
    def __init__(self):
        """Initialize the pattern factory with lazy loading of builders."""
        # Pattern builders will be loaded dynamically to avoid circular imports
        self._builders: Dict[str, Callable] = {}
        self._builders_loaded = False
        
        # Pre-computed signature metadata to eliminate runtime inspect.signature() calls
        self._builder_signatures: Dict[str, bool] = {}  # True if accepts language param
        self._signature_cache_loaded = False
        
        # Cache for created patterns
        self._pattern_cache: Dict[str, Any] = {}
        
        # Performance monitoring
        self._pattern_requests = 0
        self._cache_hits = 0
    
    def _load_builders(self):
        """Lazily load all builder functions to avoid circular imports."""
        if self._builders_loaded:
            return
        
        # Import builder functions dynamically to avoid circular imports
        from . import code_patterns, web_patterns, numeric_patterns, text_patterns
        
        self._builders = {
            # Code patterns
            "SLASH_COMMAND_PATTERN": code_patterns.build_slash_command_pattern,
            "UNDERSCORE_DELIMITER_PATTERN": code_patterns.build_underscore_delimiter_pattern,
            "SIMPLE_UNDERSCORE_PATTERN": code_patterns.build_simple_underscore_pattern,
            "LONG_FLAG_PATTERN": code_patterns.build_long_flag_pattern,
            "SHORT_FLAG_PATTERN": code_patterns.build_short_flag_pattern,
            "ASSIGNMENT_PATTERN": code_patterns.build_assignment_pattern,
            
            # Web patterns
            "SPOKEN_URL_PATTERN": web_patterns.build_spoken_url_pattern,
            "SPOKEN_EMAIL_PATTERN": web_patterns.build_spoken_email_pattern,
            "SPOKEN_PROTOCOL_PATTERN": web_patterns.build_spoken_protocol_pattern,
            "PORT_NUMBER_PATTERN": web_patterns.build_port_number_pattern,
            
            # Numeric patterns
            "SPOKEN_ORDINAL_PATTERN": numeric_patterns.build_ordinal_pattern,
            "SPOKEN_FRACTION_PATTERN": numeric_patterns.build_fraction_pattern,
            "SPOKEN_COMPOUND_FRACTION_PATTERN": numeric_patterns.build_compound_fraction_pattern,
            "SPOKEN_NUMERIC_RANGE_PATTERN": numeric_patterns.build_numeric_range_pattern,
            "COMPLEX_MATH_EXPRESSION_PATTERN": numeric_patterns.build_complex_math_expression_pattern,
            "SIMPLE_MATH_EXPRESSION_PATTERN": numeric_patterns.build_simple_math_expression_pattern,
            "NUMBER_CONSTANT_PATTERN": numeric_patterns.build_number_constant_pattern,
            "DOLLAR_PATTERN": numeric_patterns.build_dollar_pattern,
            "CENTS_PATTERN": numeric_patterns.build_cents_pattern,
            "SPOKEN_PHONE_PATTERN": numeric_patterns.build_spoken_phone_pattern,
            "SPOKEN_TIME_RELATIVE_PATTERN": numeric_patterns.build_time_relative_pattern,
            "TIME_AM_PM_COLON_PATTERN": numeric_patterns.build_time_am_pm_colon_pattern,
            "TIME_AM_PM_SPACE_PATTERN": numeric_patterns.build_time_am_pm_space_pattern,
            "TIME_EXPRESSION_PATTERNS": numeric_patterns.build_time_expression_patterns,
            
            # Text patterns
            "FILLER_PATTERN": text_patterns.build_filler_pattern,
            "ALL_CAPS_PRESERVATION_PATTERN": text_patterns.build_all_caps_preservation_pattern,
            "SENTENCE_CAPITALIZATION_PATTERN": text_patterns.build_sentence_capitalization_pattern,
            "PRONOUN_I_PATTERN": text_patterns.build_pronoun_i_pattern,
            "TECHNICAL_CONTENT_PATTERNS": text_patterns.build_technical_content_patterns,
            "SPOKEN_LETTER_PATTERN": text_patterns.build_spoken_letter_pattern,
            "LETTER_SEQUENCE_PATTERN": text_patterns.build_letter_sequence_pattern,
            "ABBREVIATION_PATTERN": text_patterns.build_abbreviation_pattern,
            "PLACEHOLDER_PATTERN": text_patterns.build_placeholder_pattern,
            "WHITESPACE_NORMALIZATION_PATTERN": text_patterns.build_whitespace_normalization_pattern,
            "REPEATED_DOTS_PATTERN": text_patterns.build_repeated_dots_pattern,
            "REPEATED_QUESTION_MARKS_PATTERN": text_patterns.build_repeated_question_marks_pattern,
            "REPEATED_EXCLAMATION_MARKS_PATTERN": text_patterns.build_repeated_exclamation_marks_pattern,
            "PRONOUN_I_STANDALONE_PATTERN": text_patterns.build_pronoun_i_standalone_pattern,
            "TEMPERATURE_PROTECTION_PATTERN": text_patterns.build_temperature_protection_pattern,
            "ENTITY_BOUNDARY_PATTERN": text_patterns.build_entity_boundary_pattern,
        }
        
        self._builders_loaded = True
        
        # Pre-compute signatures after loading builders
        self._precompute_signatures()
    
    def _precompute_signatures(self):
        """Pre-compute builder function signatures for fast lookup."""
        if self._signature_cache_loaded:
            return
            
        # Pre-compute which builders accept language parameter
        for pattern_name, builder in self._builders.items():
            try:
                sig = inspect.signature(builder)
                self._builder_signatures[pattern_name] = "language" in sig.parameters
            except (ValueError, TypeError):
                # If signature inspection fails, assume no language parameter
                self._builder_signatures[pattern_name] = False
        
        self._signature_cache_loaded = True
    
    def get_pattern(self, pattern_name: str, language: str = "en") -> Union[re.Pattern[str], List[re.Pattern[str]]]:
        """
        Get a pattern by name and language, with caching.
        
        Args:
            pattern_name: Name of the pattern to create
            language: Language code for localized patterns (default: "en")
            
        Returns:
            The compiled pattern or list of patterns
            
        Raises:
            KeyError: If pattern_name is not found
        """
        self._load_builders()
        
        # Performance monitoring
        self._pattern_requests += 1
        
        cache_key = f"{pattern_name}_{language}"
        
        if cache_key not in self._pattern_cache:
            if pattern_name not in self._builders:
                raise KeyError(f"Unknown pattern: {pattern_name}")
            
            builder = self._builders[pattern_name]
            
            # Use pre-computed signature cache instead of runtime inspection
            if self._builder_signatures.get(pattern_name, False):
                pattern = builder(language)
            else:
                pattern = builder()
            
            self._pattern_cache[cache_key] = pattern
        else:
            # Track cache hits for performance monitoring
            self._cache_hits += 1
        
        return self._pattern_cache[cache_key]
    
    def get_all_pattern_names(self) -> List[str]:
        """Get a list of all available pattern names."""
        self._load_builders()
        return list(self._builders.keys())
    
    def clear_cache(self) -> None:
        """Clear the pattern cache."""
        self._pattern_cache.clear()
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """
        Get performance statistics for the pattern factory.
        
        Returns:
            Dictionary containing performance metrics
        """
        cache_hit_rate = (self._cache_hits / self._pattern_requests * 100) if self._pattern_requests > 0 else 0.0
        
        return {
            "total_requests": self._pattern_requests,
            "cache_hits": self._cache_hits,
            "cache_hit_rate_percent": round(cache_hit_rate, 2),
            "cache_size": len(self._pattern_cache),
            "builders_loaded": self._builders_loaded,
            "signatures_cached": len(self._builder_signatures),
        }
    
    def reset_performance_stats(self) -> None:
        """Reset performance monitoring counters."""
        self._pattern_requests = 0
        self._cache_hits = 0


# Global factory instance
_factory = PatternFactory()

# Public interface functions
def get_pattern(pattern_name: str, language: str = "en") -> Union[re.Pattern[str], List[re.Pattern[str]]]:
    """Get a pattern by name and language."""
    return _factory.get_pattern(pattern_name, language)

def get_all_pattern_names() -> List[str]:
    """Get a list of all available pattern names."""
    return _factory.get_all_pattern_names()

def clear_pattern_cache() -> None:
    """Clear the pattern cache."""
    _factory.clear_cache()

def get_factory_performance_stats() -> Dict[str, Any]:
    """Get performance statistics for the pattern factory."""
    return _factory.get_performance_stats()

def reset_factory_performance_stats() -> None:
    """Reset performance monitoring counters."""
    _factory.reset_performance_stats()


# Export the factory interface
__all__ = [
    "PatternFactory",
    "get_pattern", 
    "get_all_pattern_names",
    "clear_pattern_cache",
    "get_factory_performance_stats",
    "reset_factory_performance_stats"
]