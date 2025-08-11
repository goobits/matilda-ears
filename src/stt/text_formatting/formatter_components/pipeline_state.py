#!/usr/bin/env python3
"""
Pipeline State Manager for Text Formatting Pipeline

This module manages state and coordination between pipeline steps to prevent
entity corruption during multi-step processing. The primary focus is preventing
abbreviation-punctuation conflicts where step 4 (punctuation) adds commas
that interfere with step 6 (abbreviation restoration).

Core Problem:
- Step 4: "for example e g" → "for example, e g"
- Step 6: "e g" → "e.g."
- Result: "for example, e.g.," (incorrect)
- Expected: "for example e.g.," (correct)

Solution Strategy:
1. Pre-scan text for potential abbreviation patterns before punctuation
2. Track entity boundaries that should preserve punctuation state  
3. Coordinate between steps to prevent conflicting modifications
"""

from __future__ import annotations

import re
from typing import Dict, List, Set, Tuple, Optional
from dataclasses import dataclass

from ..constants import get_resources
from ..common import Entity, EntityType


@dataclass
class PipelineState:
    """Tracks state information across pipeline steps"""
    
    # Text being processed
    text: str
    
    # Pre-detected abbreviation patterns that will be restored in step 6
    pending_abbreviations: List[Tuple[int, int, str]]  # (start, end, pattern)
    
    # Comma exclusion zones (positions where commas should not be inserted)
    comma_exclusion_zones: Set[Tuple[int, int]]  # (start, end) ranges
    
    # Entity boundary information for cross-step coordination
    entity_boundaries: Dict[str, List[Tuple[int, int]]]
    
    # Language resources for abbreviation detection
    language: str = "en"
    
    def has_pending_abbreviation_at(self, position: int, window: int = 5) -> bool:
        """Check if there's a pending abbreviation within window of position"""
        for start, end, pattern in self.pending_abbreviations:
            if abs(position - start) <= window or abs(position - end) <= window:
                return True
        return False
    
    def is_in_comma_exclusion_zone(self, position: int) -> bool:
        """Check if position is in a comma exclusion zone"""
        for start, end in self.comma_exclusion_zones:
            if start <= position <= end:
                return True
        return False
    
    def add_comma_exclusion_zone(self, start: int, end: int):
        """Add a comma exclusion zone"""
        self.comma_exclusion_zones.add((start, end))


class PipelineStateManager:
    """Manages state coordination between pipeline steps"""
    
    def __init__(self, language: str = "en"):
        self.language = language
        self.resources = get_resources(language)
        
        # Get abbreviation patterns from resources
        self.abbreviations = self.resources.get("abbreviations", {})
        
        # Pre-compile abbreviation detection patterns
        self._compile_abbreviation_patterns()
    
    def _compile_abbreviation_patterns(self):
        """Pre-compile regex patterns for efficient abbreviation detection"""
        self.abbreviation_patterns = []
        
        # Create patterns for spoken forms that will become abbreviations
        for spoken, formatted in self.abbreviations.items():
            # Pattern: spoken form with spaces/boundaries
            # e.g., "e g" → "e.g.", "i e" → "i.e."
            spoken_pattern = re.escape(spoken.replace(".", " ").lower())
            self.abbreviation_patterns.append((
                re.compile(rf"\b{spoken_pattern}\b", re.IGNORECASE),
                formatted.lower(),
                spoken
            ))
    
    def create_state(self, text: str) -> PipelineState:
        """Create initial pipeline state for given text"""
        
        # Pre-scan for abbreviation patterns
        pending_abbreviations = self._detect_pending_abbreviations(text)
        
        # Create comma exclusion zones around abbreviation patterns
        comma_exclusion_zones = set()
        for start, end, pattern in pending_abbreviations:
            # Create exclusion zone from potential introductory phrase to abbreviation
            exclusion_start = max(0, start - 20)  # Look back for intro phrases
            exclusion_end = end + 5  # Small buffer after abbreviation
            comma_exclusion_zones.add((exclusion_start, exclusion_end))
        
        return PipelineState(
            text=text,
            pending_abbreviations=pending_abbreviations,
            comma_exclusion_zones=comma_exclusion_zones,
            entity_boundaries={},
            language=self.language
        )
    
    def _detect_pending_abbreviations(self, text: str) -> List[Tuple[int, int, str]]:
        """Detect abbreviation patterns that will be converted in step 3"""
        pending = []
        
        # Look for known abbreviation patterns in the original text
        for pattern, formatted, spoken in self.abbreviation_patterns:
            for match in pattern.finditer(text):
                start, end = match.span()
                # Check if this is in an introductory phrase context
                if self._is_in_abbreviation_context(text, start, end):
                    pending.append((start, end, formatted))
        
        return pending
    
    def _is_in_abbreviation_context(self, text: str, start: int, end: int) -> bool:
        """Check if abbreviation is in a context that creates punctuation conflicts"""
        
        # Look for common introductory phrases before the abbreviation
        prefix_text = text[:start].lower().strip()
        
        # Common phrases that precede abbreviations and get commas
        introductory_phrases = [
            "for example",
            "in other words", 
            "that is",
            "for instance",
            "namely",
            "specifically"
        ]
        
        # Check if any introductory phrase precedes this abbreviation
        for phrase in introductory_phrases:
            if prefix_text.endswith(phrase) or f" {phrase} " in prefix_text[-30:]:
                return True        
        return False
    
    def should_skip_comma_after_phrase(self, text: str, phrase_end: int, state: PipelineState) -> bool:
        """
        Determine if comma should be skipped after an introductory phrase
        due to a following abbreviation that would create double punctuation.
        """
        # Look ahead from the phrase end to see if there's a pending abbreviation
        lookahead_text = text[phrase_end:phrase_end + 10].strip()
        
        # Check if any pending abbreviation starts in the lookahead window
        for start, end, pattern in state.pending_abbreviations:
            # Convert absolute positions to relative to phrase_end
            relative_start = start - phrase_end
            if 0 <= relative_start <= 8:  # Abbreviation within 8 chars of phrase end
                return True
        
        return False


def create_pipeline_state_manager(language: str = "en") -> PipelineStateManager:
    """Factory function to create pipeline state manager"""
    return PipelineStateManager(language=language)