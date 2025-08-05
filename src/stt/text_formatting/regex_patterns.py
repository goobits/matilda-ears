#!/usr/bin/env python3
"""
Centralized regular expression patterns for text formatting.

This module serves as the main entry point for all regex patterns used throughout
the text formatting system. Patterns are now organized into specialized modules
under the pattern_modules directory for better maintainability.

All patterns maintain backward compatibility through this central import point.
"""
from __future__ import annotations

import re
from typing import Pattern
# Import all patterns and functions from specialized modules for backward compatibility
from .pattern_modules import *

# ==============================================================================
# PATTERN COMPILATION HELPERS
# ==============================================================================


def get_compiled_pattern(pattern_name: str) -> Pattern | None:
    """Get a pre-compiled pattern by name."""
    # Check code patterns first
    code_pattern = get_compiled_code_pattern(pattern_name)
    if code_pattern is not None:
        return code_pattern
    
    # Check numeric patterns
    numeric_pattern = get_compiled_numeric_pattern(pattern_name)
    if numeric_pattern is not None:
        return numeric_pattern
    
    # Check text patterns
    text_pattern = get_compiled_text_pattern(pattern_name)
    if text_pattern is not None:
        return text_pattern
    
    # Check remaining web patterns
    pattern_map = {
        "url_protection": URL_PROTECTION_PATTERN,
        "email_protection": EMAIL_PROTECTION_PATTERN,
        "www_domain_rescue": WWW_DOMAIN_RESCUE,
    }
    return pattern_map.get(pattern_name)


# ==============================================================================
# BACKWARD COMPATIBILITY
# ==============================================================================

# All utility functions are now available through pattern_modules imports
# This maintains full backward compatibility for existing code
