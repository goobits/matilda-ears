#!/usr/bin/env python3
"""
Centralized pattern cache system for text formatting.

This module provides thread-safe LRU caching for compiled regex patterns,
dramatically improving performance by avoiding repeated pattern compilation.

Key Features:
- Thread-safe implementation using threading.Lock
- LRU cache with configurable size (default: 256)
- Automatic cache key generation from pattern strings and parameters
- Cache statistics for monitoring performance
- Warm-up functionality for common patterns

Usage:
    from pattern_cache import cached_pattern, get_cache_stats
    
    @cached_pattern
    def build_my_pattern(text: str, language: str = "en") -> re.Pattern[str]:
        return re.compile(f"\\b{text}\\b", re.IGNORECASE)
"""
from __future__ import annotations

import functools
import hashlib
import re
import threading
from typing import Any, Callable, Pattern, TypeVar

# Type variable for decorated functions
F = TypeVar('F', bound=Callable[..., Pattern[str]])

# Global cache configuration
_CACHE_SIZE = 256
_pattern_cache: dict[str, Pattern[str]] = {}
_cache_access_order: list[str] = []
_cache_lock = threading.Lock()
_cache_stats = {
    'hits': 0,
    'misses': 0,
    'evictions': 0,
    'size': 0
}


def _generate_cache_key(func_name: str, args: tuple, kwargs: dict) -> str:
    """
    Generate a unique cache key for pattern functions.
    
    Uses function name, arguments, and a hash of pattern components
    to create a deterministic cache key.
    
    Args:
        func_name: Name of the pattern building function
        args: Positional arguments passed to the function
        kwargs: Keyword arguments passed to the function
    
    Returns:
        Unique cache key string
    """
    # Create base key from function name and arguments
    key_parts = [func_name]
    
    # Add positional args
    for arg in args:
        if isinstance(arg, str):
            key_parts.append(arg)
        else:
            key_parts.append(str(arg))
    
    # Add keyword args (sorted for consistency)
    for k, v in sorted(kwargs.items()):
        key_parts.append(f"{k}={v}")
    
    # Create hash for long keys to keep cache keys manageable
    key_string = "|".join(key_parts)
    if len(key_string) > 100:
        key_hash = hashlib.md5(key_string.encode()).hexdigest()[:16]
        return f"{func_name}_{key_hash}"
    
    return key_string


def _evict_lru_if_needed() -> None:
    """
    Evict least recently used pattern if cache is at capacity.
    
    This function assumes the cache lock is already held.
    """
    global _pattern_cache, _cache_access_order, _cache_stats
    
    if len(_pattern_cache) >= _CACHE_SIZE:
        # Remove least recently used item
        lru_key = _cache_access_order.pop(0)
        del _pattern_cache[lru_key]
        _cache_stats['evictions'] += 1


def _update_access_order(cache_key: str) -> None:
    """
    Update the access order for LRU tracking.
    
    This function assumes the cache lock is already held.
    
    Args:
        cache_key: The cache key that was accessed
    """
    global _cache_access_order
    
    # Move to end (most recently used)
    if cache_key in _cache_access_order:
        _cache_access_order.remove(cache_key)
    _cache_access_order.append(cache_key)


def cached_pattern(func: F) -> F:
    r"""
    Decorator to cache compiled regex patterns with thread-safe LRU eviction.
    
    This decorator wraps pattern building functions to cache their results,
    avoiding expensive regex compilation for patterns that are used repeatedly.
    
    The cache key is automatically generated from:
    - Function name
    - All arguments (positional and keyword)
    - Hash of argument values for long keys
    
    Example:
        @cached_pattern
        def build_email_pattern(language: str = "en") -> re.Pattern[str]:
            return re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b")
    
    Args:
        func: Pattern building function that returns re.Pattern[str]
    
    Returns:
        Cached version of the pattern building function
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs) -> Pattern[str]:
        global _pattern_cache, _cache_stats, _cache_lock
        
        # Generate cache key
        cache_key = _generate_cache_key(func.__name__, args, kwargs)
        
        with _cache_lock:
            # Check cache first
            if cache_key in _pattern_cache:
                _cache_stats['hits'] += 1
                _update_access_order(cache_key)
                return _pattern_cache[cache_key]
            
            # Cache miss - evict if needed before adding new pattern
            _evict_lru_if_needed()
        
        # Compile pattern outside of lock to minimize lock time
        pattern = func(*args, **kwargs)
        
        with _cache_lock:
            # Double-check that another thread didn't add this pattern
            if cache_key not in _pattern_cache:
                _pattern_cache[cache_key] = pattern
                _update_access_order(cache_key)
                _cache_stats['misses'] += 1
                _cache_stats['size'] = len(_pattern_cache)
            else:
                # Another thread added it, use theirs and update stats
                _cache_stats['hits'] += 1
                _update_access_order(cache_key)
                pattern = _pattern_cache[cache_key]
        
        return pattern
    
    return wrapper  # type: ignore


def get_cache_stats() -> dict[str, int]:
    """
    Get current cache statistics.
    
    Returns:
        Dictionary containing cache hit/miss ratios, evictions, and current size
    """
    with _cache_lock:
        stats = _cache_stats.copy()
        total_requests = stats['hits'] + stats['misses']
        if total_requests > 0:
            stats['hit_ratio'] = stats['hits'] / total_requests
            stats['miss_ratio'] = stats['misses'] / total_requests
        else:
            stats['hit_ratio'] = 0.0
            stats['miss_ratio'] = 0.0
        return stats


def clear_cache() -> None:
    """
    Clear all cached patterns.
    
    Useful for testing or memory management.
    """
    global _pattern_cache, _cache_access_order, _cache_stats
    
    with _cache_lock:
        _pattern_cache.clear()
        _cache_access_order.clear()
        _cache_stats.update({
            'hits': 0,
            'misses': 0,
            'evictions': 0,
            'size': 0
        })


def warm_cache_common_patterns() -> None:
    """
    Pre-warm the cache with commonly used patterns.
    
    This function should be called during application startup
    to ensure frequently used patterns are already compiled.
    """
    # This will be populated as we identify common patterns
    # For now, we'll add patterns as they're converted to use caching
    pass


def configure_cache(cache_size: int = 256) -> None:
    """
    Configure cache settings.
    
    Args:
        cache_size: Maximum number of patterns to cache
    """
    global _CACHE_SIZE
    
    with _cache_lock:
        _CACHE_SIZE = cache_size
        # If new size is smaller, evict excess patterns
        while len(_pattern_cache) > _CACHE_SIZE:
            _evict_lru_if_needed()


def get_cached_pattern_direct(cache_key: str) -> Pattern[str] | None:
    """
    Get a pattern directly from cache by key (for debugging).
    
    Args:
        cache_key: The cache key to look up
        
    Returns:
        The cached pattern or None if not found
    """
    with _cache_lock:
        return _pattern_cache.get(cache_key)


# Utility function to manually cache a pattern (for migration purposes)
def cache_pattern(pattern: Pattern[str], cache_key: str) -> None:
    """
    Manually add a pattern to the cache.
    
    This is useful for gradual migration of existing pre-compiled patterns.
    
    Args:
        pattern: Compiled regex pattern
        cache_key: Key to store the pattern under
    """
    with _cache_lock:
        _evict_lru_if_needed()
        _pattern_cache[cache_key] = pattern
        _update_access_order(cache_key)
        _cache_stats['size'] = len(_pattern_cache)