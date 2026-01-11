#!/usr/bin/env python3
"""Unified Pattern Converter for Matilda transcriptions.

This module provides backward compatibility by re-exporting the PatternConverter
class from the converters submodule.

The implementation has been split into:
- converters/base.py: Main PatternConverter class with initialization
- converters/web.py: WebConverterMixin for URL/email conversions
- converters/code.py: CodeConverterMixin for programming constructs
- converters/numeric.py: NumericConverterMixin for math/currency/measurements
"""

# Re-export PatternConverter for backward compatibility
from .internal.converters import PatternConverter

# Also export mixins for extensibility
from .internal.converters import WebConverterMixin, CodeConverterMixin, NumericConverterMixin

__all__ = [
    "CodeConverterMixin",
    "NumericConverterMixin",
    "PatternConverter",
    "WebConverterMixin",
]
