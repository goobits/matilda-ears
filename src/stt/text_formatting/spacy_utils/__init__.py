"""
SpaCy-based text formatting utilities.

This package contains utility classes and functions for text formatting,
including spaCy-based entity detection and pattern matching.
Renamed from 'utils' to 'spacy_utils' to avoid namespace conflicts.
"""
from .spacy_cardinal_matcher import SpacyCardinalMatcher, create_spacy_cardinal_matcher

__all__ = ['SpacyCardinalMatcher', 'create_spacy_cardinal_matcher']