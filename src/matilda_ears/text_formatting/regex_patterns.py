#!/usr/bin/env python3
"""Centralized regular expression patterns for text formatting.

This module contains all complex regex patterns used throughout the text formatting
system, organized logically and using verbose formatting for readability and
maintainability.

All patterns use re.VERBOSE flag where beneficial and include detailed comments
explaining each component.

This is a facade module that re-exports all patterns from the patterns subpackage.
For the actual implementations, see:
- patterns/components.py - Data constants and helper functions
- patterns/static.py - Pre-compiled static patterns
- patterns/builders.py - Dynamic i18n-aware pattern builders
"""

from .patterns import *  # noqa: F401, F403
