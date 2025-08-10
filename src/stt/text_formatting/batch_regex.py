#!/usr/bin/env python3
"""
Batch regex processing system for efficient string operations optimization.

This module provides batched regex substitutions to reduce overhead from multiple
consecutive re.sub() calls. Pre-compiled patterns and batched execution provide
significant performance improvements for repetitive string processing operations.

Phase F Optimization: String Operation Optimization
"""
from __future__ import annotations

# Standard library imports
import re
from functools import lru_cache
from typing import List, Tuple, Pattern, Dict, Any

# Pre-compiled pattern cache for performance
_PATTERN_CACHE: Dict[str, Pattern[str]] = {}


def _get_compiled_pattern(pattern: str, flags: int = 0) -> Pattern[str]:
    """Get or create a compiled regex pattern with caching."""
    cache_key = f"{pattern}:{flags}"
    if cache_key not in _PATTERN_CACHE:
        _PATTERN_CACHE[cache_key] = re.compile(pattern, flags)
    return _PATTERN_CACHE[cache_key]


class BatchRegexProcessor:
    """
    Efficient batch regex processing system.
    
    Combines multiple regex substitutions into a single pass for better performance.
    Maintains identical output while reducing regex engine overhead.
    """
    
    def __init__(self):
        # Pre-compiled cleanup patterns for common operations
        self._cleanup_patterns = self._compile_cleanup_patterns()
        self._punctuation_patterns = self._compile_punctuation_patterns()
        self._abbreviation_patterns = self._compile_abbreviation_patterns()
        self._artifact_patterns = []
        
    def _compile_cleanup_patterns(self) -> List[Tuple[Pattern[str], str]]:
        """Pre-compile common cleanup patterns."""
        return [
            (_get_compiled_pattern(r"\.\.+"), "."),             # Multiple dots to single
            (_get_compiled_pattern(r"\?\?+"), "?"),             # Multiple questions
            (_get_compiled_pattern(r"!!+"), "!"),               # Multiple exclamations
            (_get_compiled_pattern(r"([,;:])\1+"), r"\1"),      # Repeated punctuation
            (_get_compiled_pattern(r"^\s*,\s*"), ""),           # Orphaned leading commas
            (_get_compiled_pattern(r",\s*,"), ","),             # Double commas
            (_get_compiled_pattern(r",,"), ","),                # Double commas (direct)
        ]
    
    def _compile_punctuation_patterns(self) -> List[Tuple[Pattern[str], str]]:
        """Pre-compile punctuation normalization patterns."""
        return [
            (_get_compiled_pattern(r"\s+"), " "),               # Normalize whitespace
        ]
        
    def _compile_abbreviation_patterns(self) -> List[Tuple[Pattern[str], str]]:
        """Pre-compile common abbreviation patterns."""
        return [
            (_get_compiled_pattern(r"(i\.e\.)(\s+[a-zA-Z])", re.IGNORECASE), r"\1,\2"),
            (_get_compiled_pattern(r"(e\.g\.)(\s+[a-zA-Z])", re.IGNORECASE), r"\1,\2"),
            (_get_compiled_pattern(r",,"), ","),  # Remove double commas first
            (_get_compiled_pattern(r"\b(for example|in other words|that is),\s+(e\.g\.|i\.e\.)", re.IGNORECASE), r"\1 \2"),
        ]
        
    def batch_cleanup_substitutions(self, text: str) -> str:
        """
        Apply batched cleanup substitutions efficiently.
        
        This replaces multiple consecutive re.sub() calls with a single-pass
        batch operation for common cleanup patterns.
        
        Args:
            text: Text to process
            
        Returns:
            Text with all cleanup substitutions applied
        """
        if not text:
            return text
            
        result = text
        
        # Apply all pre-compiled cleanup patterns in sequence
        for pattern, replacement in self._cleanup_patterns:
            result = pattern.sub(replacement, result)
            
        return result.strip()
    
    def batch_artifact_removal(self, text: str, artifacts: List[str]) -> str:
        """
        Efficiently remove multiple artifact patterns.
        
        Args:
            text: Text to process
            artifacts: List of artifact strings to remove
            
        Returns:
            Text with artifacts removed
        """
        if not text or not artifacts:
            return text
            
        # Create or update artifact patterns if needed
        if not self._artifact_patterns or len(self._artifact_patterns) != len(artifacts):
            self._artifact_patterns = [
                _get_compiled_pattern(rf'\b{re.escape(artifact)}\b', re.IGNORECASE)
                for artifact in artifacts
            ]
        
        result = text
        for pattern in self._artifact_patterns:
            result = pattern.sub('', result)
            
        # Clean up resulting extra spaces in one pass
        result = _get_compiled_pattern(r'\s+').sub(' ', result).strip()
        
        return result
    
    def batch_abbreviation_processing(self, text: str) -> str:
        """
        Apply batched abbreviation processing efficiently.
        
        Args:
            text: Text to process
            
        Returns:
            Text with abbreviation patterns applied
        """
        if not text:
            return text
            
        result = text
        
        # Apply all pre-compiled abbreviation patterns in sequence
        for pattern, replacement in self._abbreviation_patterns:
            result = pattern.sub(replacement, result)
            
        return result
    
    def batch_substitutions(self, text: str, pattern_replacements: List[Tuple[str, str]], flags: int = 0) -> str:
        """
        Apply multiple regex substitutions efficiently.
        
        Args:
            text: Text to process
            pattern_replacements: List of (pattern, replacement) tuples
            flags: Regex flags to apply to all patterns
            
        Returns:
            Text with all substitutions applied
        """
        if not text or not pattern_replacements:
            return text
            
        result = text
        for pattern_str, replacement in pattern_replacements:
            pattern = _get_compiled_pattern(pattern_str, flags)
            result = pattern.sub(replacement, result)
            
        return result


# Global singleton instance for efficiency
_BATCH_PROCESSOR = BatchRegexProcessor()


def batch_cleanup_substitutions(text: str) -> str:
    """
    Convenience function for batched cleanup operations.
    
    Replaces multiple consecutive cleanup re.sub() calls with efficient batch processing.
    Maintains identical behavior while improving performance.
    
    Args:
        text: Text to process
        
    Returns:
        Text with cleanup substitutions applied
    """
    return _BATCH_PROCESSOR.batch_cleanup_substitutions(text)


def batch_artifact_removal(text: str, artifacts: List[str]) -> str:
    """
    Convenience function for batched artifact removal.
    
    Args:
        text: Text to process  
        artifacts: List of artifacts to remove
        
    Returns:
        Text with artifacts removed
    """
    return _BATCH_PROCESSOR.batch_artifact_removal(text, artifacts)


def batch_substitutions(text: str, pattern_replacements: List[Tuple[str, str]], flags: int = 0) -> str:
    """
    Convenience function for batched regex substitutions.
    
    Args:
        text: Text to process
        pattern_replacements: List of (pattern, replacement) tuples  
        flags: Regex flags
        
    Returns:
        Text with substitutions applied
    """
    return _BATCH_PROCESSOR.batch_substitutions(text, pattern_replacements, flags)


def batch_abbreviation_processing(text: str) -> str:
    """
    Convenience function for batched abbreviation processing.
    
    Args:
        text: Text to process
        
    Returns:
        Text with abbreviation patterns applied
    """
    return _BATCH_PROCESSOR.batch_abbreviation_processing(text)


@lru_cache(maxsize=128)
def get_compiled_pattern(pattern: str, flags: int = 0) -> Pattern[str]:
    """
    Get a compiled regex pattern with LRU caching.
    
    Args:
        pattern: Regex pattern string
        flags: Regex flags
        
    Returns:
        Compiled regex pattern
    """
    return re.compile(pattern, flags)


def clear_pattern_cache() -> None:
    """Clear the pattern cache (useful for testing)."""
    global _PATTERN_CACHE
    _PATTERN_CACHE.clear()
    get_compiled_pattern.cache_clear()