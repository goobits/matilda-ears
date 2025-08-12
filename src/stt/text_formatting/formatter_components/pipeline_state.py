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
from typing import Dict, List, Set, Tuple, Optional, Any
from dataclasses import dataclass, field
from enum import Enum

from ..constants import get_resources
from stt.text_formatting.common import Entity, EntityType

# PHASE 21: Debug Mode Enhancement - Pipeline State Tracing
from stt.text_formatting.debug_utils import (
    get_entity_debugger, DebugModule, is_debug_enabled
)


class EntityState(Enum):
    """Represents the current state of an entity in the pipeline"""
    DETECTED = "detected"           # Entity has been detected but not converted
    CONVERTED = "converted"         # Entity has been converted to final form
    PROTECTED = "protected"         # Entity is protected from further modifications
    CORRUPTED = "corrupted"         # Entity boundaries have been corrupted by another step
    RESTORED = "restored"           # Entity has been restored after corruption


@dataclass
class EntityStateInfo:
    """Tracks comprehensive state information for a single entity"""
    entity: Entity
    state: EntityState
    original_text: str              # Original text before any modifications
    converted_text: Optional[str]   # Text after conversion
    current_start: int              # Current start position (may shift during pipeline)
    current_end: int                # Current end position (may shift during pipeline)
    original_start: int             # Original start position (fixed reference)
    original_end: int               # Original end position (fixed reference)
    step_modifications: Dict[str, str] = field(default_factory=dict)  # Track which steps modified it
    protection_zones: Set[Tuple[int, int]] = field(default_factory=set)  # Areas that should not be modified
    conflicts: List[str] = field(default_factory=list)  # List of detected conflicts
    
    def add_modification(self, step: str, modification: str):
        """Record a modification made by a pipeline step"""
        self.step_modifications[step] = modification
        
    def add_conflict(self, conflict_description: str):
        """Record a detected conflict"""
        self.conflicts.append(conflict_description)
        
    def is_in_protection_zone(self, start: int, end: int) -> bool:
        """Check if a position range overlaps with any protection zone"""
        for zone_start, zone_end in self.protection_zones:
            if not (end <= zone_start or start >= zone_end):  # Overlapping ranges
                return True
        return False
        
    def add_protection_zone(self, start: int, end: int):
        """Add a protection zone around this entity"""
        self.protection_zones.add((start, end))


@dataclass
class UniversalEntityTracker:
    """Universal entity state tracker for cross-step coordination"""
    entities: Dict[str, EntityStateInfo] = field(default_factory=dict)  # entity_id -> EntityStateInfo
    text_modifications: List[Tuple[str, int, int, str]] = field(default_factory=list)  # (step, start, end, new_text)
    global_protection_zones: Set[Tuple[int, int]] = field(default_factory=set)
    step_history: List[str] = field(default_factory=list)
    
    def generate_entity_id(self, entity: Entity) -> str:
        """Generate a unique ID for an entity"""
        return f"{entity.type.value}_{entity.start}_{entity.end}_{hash(entity.text) % 10000}"
    
    def register_entity(self, entity: Entity, original_text: str) -> str:
        """Register a new entity for tracking"""
        entity_id = self.generate_entity_id(entity)
        
        state_info = EntityStateInfo(
            entity=entity,
            state=EntityState.DETECTED,
            original_text=original_text[entity.start:entity.end],
            converted_text=None,
            current_start=entity.start,
            current_end=entity.end,
            original_start=entity.start,
            original_end=entity.end
        )
        
        self.entities[entity_id] = state_info
        
        # PHASE 21: Debug tracing - Entity registration
        if is_debug_enabled(DebugModule.PIPELINE):
            debugger = get_entity_debugger()
            debugger.trace_entity_operation(
                entity,
                "pipeline",
                "entity_registered",
                DebugModule.PIPELINE,
                entity_id=entity_id,
                state=EntityState.DETECTED.value,
                original_text_preview=original_text[entity.start:entity.end]
            )
        
        return entity_id
    
    def update_entity_position(self, entity_id: str, new_start: int, new_end: int):
        """Update entity position after text modifications"""
        if entity_id in self.entities:
            self.entities[entity_id].current_start = new_start
            self.entities[entity_id].current_end = new_end
    
    def update_all_positions_after_text_change(self, modification_start: int, modification_end: int, new_text: str):
        """
        Update all entity positions after a text modification.
        
        Args:
            modification_start: Start position of the modification
            modification_end: End position of the modification
            new_text: The new text that replaced the modified section
        """
        old_length = modification_end - modification_start
        new_length = len(new_text)
        length_delta = new_length - old_length
        
        # Record this modification for tracking
        self.text_modifications.append(("text_change", modification_start, modification_end, new_text))
        
        # Update positions of all entities
        for entity_id, state_info in self.entities.items():
            # Update current positions based on the modification
            updated_start, updated_end = self._calculate_updated_position(
                state_info.current_start, state_info.current_end,
                modification_start, modification_end, length_delta
            )
            
            # Only update if positions actually changed
            if updated_start != state_info.current_start or updated_end != state_info.current_end:
                state_info.current_start = updated_start
                state_info.current_end = updated_end
                state_info.add_modification("position_update", f"Updated from ({state_info.original_start}, {state_info.original_end}) to ({updated_start}, {updated_end})")
    
    def _calculate_updated_position(self, entity_start: int, entity_end: int, 
                                   mod_start: int, mod_end: int, length_delta: int) -> tuple[int, int]:
        """
        Calculate new entity position after a text modification.
        
        Args:
            entity_start: Current start position of entity
            entity_end: Current end position of entity
            mod_start: Start position of text modification
            mod_end: End position of text modification
            length_delta: Change in text length (new_length - old_length)
            
        Returns:
            Tuple of (new_start, new_end)
        """
        # Case 1: Entity is completely before the modification
        if entity_end <= mod_start:
            return entity_start, entity_end  # No change needed
        
        # Case 2: Entity is completely after the modification
        if entity_start >= mod_end:
            return entity_start + length_delta, entity_end + length_delta
        
        # Case 3: Entity overlaps with modification (complex case)
        if entity_start < mod_start and entity_end > mod_end:
            # Entity surrounds the modification
            return entity_start, entity_end + length_delta
        
        # Case 4: Entity starts before and overlaps modification
        if entity_start < mod_start and entity_end > mod_start:
            # Entity partially overlaps from the left
            return entity_start, entity_end + length_delta
        
        # Case 5: Entity starts within modification and extends beyond
        if entity_start < mod_end and entity_end > mod_end:
            # Entity partially overlaps from the right
            return mod_start, entity_end + length_delta
        
        # Case 6: Entity is completely within the modification (may be corrupted)
        if entity_start >= mod_start and entity_end <= mod_end:
            # This entity's boundaries may be invalid after modification
            # For now, keep it at the modification point - may need validation later
            return mod_start, mod_start + max(1, entity_end - entity_start)
        
        # Fallback: return original positions
        return entity_start, entity_end
    
    def mark_entity_converted(self, entity_id: str, converted_text: str, step: str):
        """Mark entity as converted and track the conversion"""
        if entity_id in self.entities:
            state_info = self.entities[entity_id]
            old_text = state_info.entity.text
            state_info.state = EntityState.CONVERTED
            state_info.converted_text = converted_text
            state_info.add_modification(step, f"converted to: {converted_text}")
            
            # PHASE 21: Debug tracing - Entity conversion
            if is_debug_enabled(DebugModule.PIPELINE):
                debugger = get_entity_debugger()
                debugger.trace_entity_operation(
                    state_info.entity,
                    "pipeline",
                    "entity_converted",
                    DebugModule.PIPELINE,
                    before_text=old_text,
                    after_text=converted_text,
                    entity_id=entity_id,
                    conversion_step=step,
                    state=EntityState.CONVERTED.value
                )
    
    def protect_entity(self, entity_id: str, protection_buffer: int = 5):
        """Mark entity as protected from further modifications"""
        if entity_id in self.entities:
            state_info = self.entities[entity_id]
            state_info.state = EntityState.PROTECTED
            
            # Add protection zone around the entity
            start = max(0, state_info.current_start - protection_buffer)
            end = state_info.current_end + protection_buffer
            state_info.add_protection_zone(start, end)
            self.global_protection_zones.add((start, end))
    
    def detect_conflicts(self, step: str, modification_start: int, modification_end: int) -> List[str]:
        """Detect conflicts with existing entities"""
        conflicts = []
        
        for entity_id, state_info in self.entities.items():
            # Check if modification overlaps with protected entity
            if state_info.state == EntityState.PROTECTED:
                if state_info.is_in_protection_zone(modification_start, modification_end):
                    conflict_msg = f"Step {step} attempting to modify protected entity {entity_id}"
                    conflicts.append(conflict_msg)
                    state_info.add_conflict(conflict_msg)
            
            # Check for entity boundary corruption
            entity_start, entity_end = state_info.current_start, state_info.current_end
            if (modification_start < entity_end and modification_end > entity_start and
                not (modification_start >= entity_start and modification_end <= entity_end)):
                conflict_msg = f"Step {step} partially overlapping with entity {entity_id}"
                conflicts.append(conflict_msg)
                state_info.add_conflict(conflict_msg)
                state_info.state = EntityState.CORRUPTED
        
        # PHASE 21: Debug tracing - Conflict detection
        if conflicts and is_debug_enabled(DebugModule.PIPELINE):
            debugger = get_entity_debugger()
            debugger.trace_entity_conflicts(
                [(conflict, step, modification_start, modification_end) for conflict in conflicts],
                f"conflict_detection_step_{step}",
                len([e for e in self.entities.values() if e.state != EntityState.CORRUPTED]),
                len([e for e in self.entities.values() if e.state != EntityState.CORRUPTED]) - len(conflicts)
            )
        
        return conflicts
    
    def is_modification_allowed(self, step: str, start: int, end: int) -> bool:
        """Check if a text modification is allowed at the given position"""
        conflicts = self.detect_conflicts(step, start, end)
        return len(conflicts) == 0
    
    def record_step(self, step: str):
        """Record that a pipeline step is being executed"""
        self.step_history.append(step)
    
    def get_entities_in_range(self, start: int, end: int) -> List[EntityStateInfo]:
        """Get all entities that overlap with the given range"""
        overlapping = []
        for state_info in self.entities.values():
            entity_start, entity_end = state_info.current_start, state_info.current_end
            if not (end <= entity_start or start >= entity_end):  # Overlapping
                overlapping.append(state_info)
        return overlapping


@dataclass
class FilenameContext:
    """Tracks filename context information for intelligent processing"""
    start: int
    end: int
    text: str
    action_word: str
    confidence_score: float
    context_type: str  # "action", "descriptive", "standalone", "compound"
    should_use_dots: bool


@dataclass  
class EntityCapitalizationGuidance:
    """Guidance information for coordinating entity conversion and capitalization"""
    entity_id: str
    entity_type: EntityType
    conversion_step: str
    conversion_result: str
    position_shift: int = 0  # How much the text position shifted after conversion
    should_preserve_case: bool = False
    should_force_lowercase: bool = False  
    should_force_title_case: bool = False
    capitalization_context: str = ""  # Additional context for capitalization decisions


class EntityCapitalizationCoordinator:
    """
    THEORY 19: Unified Entity-Capitalization Coordination System
    
    Provides cross-step coordination between conversion and capitalization steps
    to resolve boundary misalignment and inconsistent formatting decisions.
    
    Core Functions:
    1. Track entity conversions and their impact on text positions
    2. Communicate conversion results to capitalization step
    3. Coordinate position updates across pipeline steps
    4. Provide guidance for consistent entity-aware capitalization
    """
    
    def __init__(self):
        self.entity_conversion_guidance: Dict[str, EntityCapitalizationGuidance] = {}
        self.position_adjustments: List[Tuple[int, int, int]] = []  # (original_pos, new_pos, shift_amount)
        self.cross_step_metadata: Dict[str, Any] = {}
        
    def record_entity_conversion(self, entity_id: str, entity_type: EntityType, 
                               step: str, original_text: str, converted_text: str,
                               start_pos: int) -> EntityCapitalizationGuidance:
        """Record entity conversion and provide guidance for capitalization"""
        
        # Calculate position shift from conversion
        original_length = len(original_text)
        converted_length = len(converted_text)
        position_shift = converted_length - original_length
        
        # Determine capitalization guidance based on entity type and conversion
        should_preserve_case = self._should_preserve_case_for_entity(entity_type, converted_text)
        should_force_lowercase = self._should_force_lowercase_for_entity(entity_type, converted_text)  
        should_force_title_case = self._should_force_title_case_for_entity(entity_type, converted_text)
        
        # Create guidance record
        guidance = EntityCapitalizationGuidance(
            entity_id=entity_id,
            entity_type=entity_type,
            conversion_step=step,
            conversion_result=converted_text,
            position_shift=position_shift,
            should_preserve_case=should_preserve_case,
            should_force_lowercase=should_force_lowercase,
            should_force_title_case=should_force_title_case,
            capitalization_context=self._get_capitalization_context(entity_type, converted_text)
        )
        
        self.entity_conversion_guidance[entity_id] = guidance
        
        # Track position adjustment for downstream steps
        if position_shift != 0:
            self.position_adjustments.append((start_pos, start_pos + converted_length, position_shift))
            
        return guidance
        
    def get_capitalization_guidance_for_position(self, position: int) -> Optional[EntityCapitalizationGuidance]:
        """Get capitalization guidance for a specific text position"""
        
        # Find guidance that affects this position
        for guidance in self.entity_conversion_guidance.values():
            # This is a simple proximity check - could be enhanced with precise position tracking
            if abs(position - guidance.position_shift) <= 5:  # Within 5 characters
                return guidance
                
        return None
        
    def should_coordinate_capitalization(self, entity_type: EntityType, position: int) -> Tuple[bool, str]:
        """Check if capitalization should be coordinated for this entity type and position"""
        
        # Get guidance for this position
        guidance = self.get_capitalization_guidance_for_position(position)
        
        if guidance:
            # Use guidance to make capitalization decision
            if guidance.should_preserve_case:
                return True, "preserve_case"
            elif guidance.should_force_lowercase:
                return True, "force_lowercase"  
            elif guidance.should_force_title_case:
                return True, "force_title_case"
                
        # Default entity-type based coordination
        coordinate_types = {
            EntityType.COMMAND_FLAG, EntityType.VARIABLE, EntityType.FILENAME,
            EntityType.CLI_COMMAND, EntityType.URL, EntityType.EMAIL
        }
        
        if entity_type in coordinate_types:
            return True, "default_entity_coordination"
            
        return False, "no_coordination"
        
    def update_positions_after_modification(self, modification_start: int, modification_end: int,
                                          new_length: int):
        """Update tracked positions after a text modification"""
        
        length_change = new_length - (modification_end - modification_start)
        
        # Update position adjustments that come after this modification
        updated_adjustments = []
        for orig_pos, new_pos, shift in self.position_adjustments:
            if orig_pos >= modification_end:
                # Position comes after modification, shift it
                updated_adjustments.append((orig_pos + length_change, new_pos + length_change, shift))
            else:
                # Position comes before modification, keep as is
                updated_adjustments.append((orig_pos, new_pos, shift))
                
        self.position_adjustments = updated_adjustments
        
    def _should_preserve_case_for_entity(self, entity_type: EntityType, converted_text: str) -> bool:
        """Determine if case should be preserved for this entity type"""
        
        # Preserve case for technical entities that have specific casing requirements
        preserve_case_types = {
            EntityType.VARIABLE, EntityType.COMMAND_FLAG, EntityType.CLI_COMMAND,
            EntityType.FILENAME, EntityType.URL, EntityType.EMAIL
        }
        
        if entity_type in preserve_case_types:
            return True
            
        # Preserve case if converted text has mixed case (likely intentional)
        if converted_text and not converted_text.islower() and not converted_text.isupper():
            return True
            
        return False
        
    def _should_force_lowercase_for_entity(self, entity_type: EntityType, converted_text: str) -> bool:
        """Determine if entity should be forced to lowercase"""
        
        # Force lowercase for certain technical patterns
        if entity_type == EntityType.COMMAND_FLAG and converted_text.startswith('--'):
            return True
            
        if entity_type == EntityType.FILENAME and '.' in converted_text:
            return True
            
        return False
        
    def _should_force_title_case_for_entity(self, entity_type: EntityType, converted_text: str) -> bool:
        """Determine if entity should be forced to title case"""
        
        # Generally don't force title case for technical entities
        # This is more for proper nouns which would be handled differently
        return False
        
    def _get_capitalization_context(self, entity_type: EntityType, converted_text: str) -> str:
        """Get contextual information for capitalization decisions"""
        
        if entity_type == EntityType.COMMAND_FLAG and converted_text.startswith('--'):
            return "long_flag_command"
        elif entity_type == EntityType.VARIABLE and '_' in converted_text:
            return "underscore_variable"
        elif entity_type == EntityType.FILENAME and '.' in converted_text:
            return "dot_filename"
            
        return "standard"
    
    
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
    
    # Intelligent filename context tracking
    filename_contexts: List[FilenameContext]
    
    # Language resources for abbreviation detection
    language: str = "en"
    
    # UNIVERSAL ENTITY STATE COORDINATION (Theory 8)
    entity_tracker: UniversalEntityTracker = field(default_factory=UniversalEntityTracker)
    
    # THEORY 17: Spanish Conversational Flow Preservation
    conversational_context: bool = field(default=False)  # Whether text is in conversational context
    conversational_analyzer: Optional[Any] = field(default=None)  # Reference to conversational analyzer
    original_text: str = field(default="")  # Original text before pipeline processing
    
    # THEORY 19: Unified Entity-Capitalization Coordination System
    entity_capitalization_coordinator: EntityCapitalizationCoordinator = field(default_factory=EntityCapitalizationCoordinator)
    
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
    
    def get_filename_context_at(self, position: int, window: int = 10) -> Optional[FilenameContext]:
        """Get filename context information at a given position"""
        for context in self.filename_contexts:
            if context.start - window <= position <= context.end + window:
                return context
        return None
    
    def should_use_dots_for_filename(self, start: int, end: int) -> bool:
        """Determine if filename should use dots based on intelligent context analysis"""
        context = self.get_filename_context_at((start + end) // 2)
        if context:
            return context.should_use_dots
        return False  # Default to underscore if no context found
    
    # UNIVERSAL ENTITY STATE COORDINATION METHODS (Theory 8)
    
    def register_entity(self, entity: Entity) -> str:
        """Register an entity for universal tracking"""
        return self.entity_tracker.register_entity(entity, self.text)
    
    def is_modification_safe(self, step: str, start: int, end: int) -> bool:
        """Check if a text modification is safe to perform"""
        return self.entity_tracker.is_modification_allowed(step, start, end)
    
    def protect_entity_region(self, entity_id: str, buffer: int = 5):
        """Protect an entity region from further modifications"""
        self.entity_tracker.protect_entity(entity_id, buffer)
    
    def record_pipeline_step(self, step: str):
        """Record that a pipeline step is executing"""
        self.entity_tracker.record_step(step)
    
    def get_conflicting_entities(self, start: int, end: int) -> List[EntityStateInfo]:
        """Get entities that would conflict with a modification at the given range"""
        return self.entity_tracker.get_entities_in_range(start, end)
    
    def mark_entity_converted(self, entity_id: str, converted_text: str, step: str):
        """Mark an entity as converted by a pipeline step"""
        self.entity_tracker.mark_entity_converted(entity_id, converted_text, step)
    
    def has_abbreviation_entity_at(self, position: int, window: int = 10) -> bool:
        """Check if there's an abbreviation entity at the given position using universal tracking"""
        entities = self.entity_tracker.get_entities_in_range(position - window, position + window)
        
        # Check for abbreviation entities
        for entity_info in entities:
            if (entity_info.entity.type == EntityType.ABBREVIATION or
                entity_info.converted_text and any(abbrev in entity_info.converted_text.lower() 
                                                 for abbrev in ["i.e.", "e.g.", "vs.", "etc.", "cf."])):
                return True
        
        return False
    
    # THEORY 19: Entity-Capitalization Coordination Methods
    
    def record_entity_conversion(self, entity_id: str, entity_type: EntityType, 
                               step: str, original_text: str, converted_text: str,
                               start_pos: int) -> EntityCapitalizationGuidance:
        """Record entity conversion for cross-step coordination"""
        return self.entity_capitalization_coordinator.record_entity_conversion(
            entity_id, entity_type, step, original_text, converted_text, start_pos
        )
        
    def should_coordinate_entity_capitalization(self, entity_type: EntityType, position: int) -> Tuple[bool, str]:
        """Check if capitalization should be coordinated for this entity type and position"""
        return self.entity_capitalization_coordinator.should_coordinate_capitalization(entity_type, position)
        
    def get_entity_capitalization_guidance(self, position: int) -> Optional[EntityCapitalizationGuidance]:
        """Get capitalization guidance for a specific position"""
        return self.entity_capitalization_coordinator.get_capitalization_guidance_for_position(position)
        
    def update_entity_positions_after_modification(self, start: int, end: int, new_text: str):
        """Update entity positions after text modification"""
        # Update both the entity tracker and capitalization coordinator
        # This ensures position consistency across all coordination systems
        self.entity_tracker.update_all_positions_after_text_change(start, end, new_text)
        self.entity_capitalization_coordinator.update_positions_after_modification(start, end, len(new_text))
        
        # Update the current text being processed
        self.text = self.text[:start] + new_text + self.text[end:]
    
    def validate_entity_positions(self, current_text: str, step: str) -> list[str]:
        """
        Validate that all tracked entities have valid positions in the current text.
        
        Args:
            current_text: The current state of the text being processed
            step: The current pipeline step for logging
            
        Returns:
            List of validation warnings/errors
        """
        warnings = []
        
        for entity_id, state_info in self.entity_tracker.entities.items():
            start = state_info.current_start
            end = state_info.current_end
            
            # Check if position is within text bounds
            if start < 0 or end > len(current_text) or start >= end:
                warning = f"Entity {entity_id} has invalid position ({start}-{end}) for text length {len(current_text)}"
                warnings.append(warning)
                continue
            
            # Check if entity text matches current position
            expected_text = state_info.converted_text or state_info.entity.text
            actual_text = current_text[start:end]
            
            if actual_text != expected_text:
                warning = f"Entity position mismatch! Expected '{expected_text}' but found '{actual_text}' at position {start}-{end} in step {step}"
                warnings.append(warning)
                
                # Try to find the entity nearby (within 10 characters)
                search_start = max(0, start - 10)
                search_end = min(len(current_text), end + 10)
                search_text = current_text[search_start:search_end]
                
                if expected_text in search_text:
                    # Found it nearby - calculate new position
                    found_pos = current_text.find(expected_text, search_start)
                    if found_pos != -1:
                        warnings.append(f"  Found '{expected_text}' at nearby position {found_pos}")
                        # Could auto-correct here if needed
        
        return warnings
    
    def get_entity_at_position(self, position: int) -> Optional[EntityStateInfo]:
        """Get the entity that contains the given position."""
        for state_info in self.entity_tracker.entities.values():
            if state_info.current_start <= position < state_info.current_end:
                return state_info
        return None
    
    def should_skip_punctuation_modification(self, step: str, start: int, end: int, modification_type: str = "comma") -> bool:
        """
        Enhanced punctuation conflict detection using universal entity tracking.
        
        This is the core of Theory 8 - preventing punctuation modifications that would
        corrupt entity boundaries or create double punctuation after abbreviations.
        """
        # Record the step for tracking
        self.record_pipeline_step(step)
        
        # Check if modification conflicts with any tracked entities
        if not self.is_modification_safe(step, start, end):
            return True  # Skip modification due to conflict
        
        # Enhanced abbreviation detection using entity tracking
        if modification_type == "comma":
            # Look for abbreviation entities in the vicinity
            lookahead_window = end + 15  # Look ahead for abbreviations
            entities_ahead = self.entity_tracker.get_entities_in_range(end, lookahead_window)
            
            for entity_info in entities_ahead:
                # Check if this is an abbreviation entity that would create double punctuation
                if (entity_info.entity.type == EntityType.ABBREVIATION or
                    (entity_info.converted_text and 
                     any(abbrev in entity_info.converted_text.lower() for abbrev in ["i.e.", "e.g.", "vs.", "etc.", "cf."]))):
                    
                    # Skip comma insertion if abbreviation is close enough to create double punctuation
                    abbrev_distance = entity_info.current_start - end
                    if 0 <= abbrev_distance <= 12:  # Abbreviation within 12 characters
                        return True
            
            # Also check using the original abbreviation detection logic
            if self.has_pending_abbreviation_at(end):
                return True
        
        return False


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
    
    def create_state(self, text: str, entities: List[Entity] = None) -> PipelineState:
        """Create initial pipeline state for given text with universal entity tracking"""
        
        # Initialize universal entity tracker
        entity_tracker = UniversalEntityTracker()
        
        # Register all detected entities for universal tracking
        if entities:
            for entity in entities:
                entity_id = entity_tracker.register_entity(entity, text)
                
                # Protect abbreviation entities immediately
                if entity.type == EntityType.ABBREVIATION:
                    entity_tracker.protect_entity(entity_id, protection_buffer=8)
        
        # Pre-scan for abbreviation patterns (legacy support)
        pending_abbreviations = self._detect_pending_abbreviations(text)
        
        # Create comma exclusion zones around abbreviation patterns
        comma_exclusion_zones = set()
        for start, end, pattern in pending_abbreviations:
            # Create exclusion zone from potential introductory phrase to abbreviation
            exclusion_start = max(0, start - 20)  # Look back for intro phrases
            exclusion_end = end + 5  # Small buffer after abbreviation
            comma_exclusion_zones.add((exclusion_start, exclusion_end))
        
        # Pre-scan for intelligent filename contexts
        filename_contexts = self._detect_filename_contexts(text)
        
        return PipelineState(
            text=text,
            entity_tracker=entity_tracker,
            pending_abbreviations=pending_abbreviations,
            comma_exclusion_zones=comma_exclusion_zones,
            entity_boundaries={},
            filename_contexts=filename_contexts,
            language=self.language,
            original_text=text  # Store original text for conversational analysis
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
    
    def _detect_filename_contexts(self, text: str) -> List[FilenameContext]:
        """
        Intelligent filename context detection using action words and patterns.
        
        This is the core of Theory 7: Intelligent Filename Context Detection.
        It analyzes the text to determine when "dot" should become "." vs when 
        spaces should be converted to underscores.
        """
        contexts = []
        
        # Get action words from resources
        filename_actions = self.resources.get("context_words", {}).get("filename_actions", [])
        
        # Pattern 1: Action + "the" + filename + "dot" + extension
        # Example: "edit the config file settings dot json"
        action_pattern = r'\b(' + '|'.join(re.escape(action) for action in filename_actions) + r')\s+(?:the\s+)?(.+?)\s+dot\s+(\w+)\b'
        
        for match in re.finditer(action_pattern, text, re.IGNORECASE):
            action_word = match.group(1).lower()
            filename_part = match.group(2).strip()
            extension = match.group(3).lower()
            
            # THEORY 7 FIX: Exclude action word from filename context to fix capitalization and spacing
            # Find where the filename part starts (after action word + optional "the")
            action_end = match.start() + len(match.group(1))  # End of action word
            
            # Skip past whitespace and optional "the"
            filename_start = action_end
            remaining_text = text[filename_start:match.end()]
            
            # Skip whitespace
            while filename_start < match.end() and text[filename_start].isspace():
                filename_start += 1
            
            # Skip "the" if present
            if text[filename_start:].lower().startswith('the '):
                filename_start += 4  # len("the ")
                while filename_start < match.end() and text[filename_start].isspace():
                    filename_start += 1
            
            # Calculate confidence score based on multiple factors
            confidence_score = self._calculate_filename_confidence_score(
                text, filename_start, match.end(), action_word, filename_part, extension
            )
            
            # Determine context type and whether to use dots
            context_type, should_use_dots = self._analyze_filename_context_type(
                filename_part, action_word, confidence_score
            )
            
            # Create context that EXCLUDES the action word - this fixes both capitalization and spacing
            context = FilenameContext(
                start=filename_start,  # Start after action word
                end=match.end(),
                text=text[filename_start:match.end()],  # Just the filename part
                action_word=action_word,
                confidence_score=confidence_score,
                context_type=context_type,
                should_use_dots=should_use_dots
            )
            contexts.append(context)
        
        # Pattern 2: Standalone filename patterns (no action word)
        # Example: "the config dot json file" or "my script dot py"
        # Also: "main dot js", "utils dot py", "readme dot md"
        standalone_pattern = r'\b(?:the\s+|my\s+|a\s+|is\s+in\s+)?(.+?)\s+dot\s+(\w+)(?:\s+file)?\b'
        
        for match in re.finditer(standalone_pattern, text, re.IGNORECASE):
            # Skip if already covered by action pattern
            if any(c.start <= match.start() <= c.end for c in contexts):
                continue
                
            filename_part = match.group(1).strip()
            extension = match.group(2).lower()
            
            # Calculate confidence score for standalone pattern
            confidence_score = self._calculate_filename_confidence_score(
                text, match.start(), match.end(), "", filename_part, extension
            )
            
            # Analyze context type
            context_type, should_use_dots = self._analyze_filename_context_type(
                filename_part, "", confidence_score
            )
            
            context = FilenameContext(
                start=match.start(),
                end=match.end(),
                text=match.group(0),
                action_word="",
                confidence_score=confidence_score,
                context_type=context_type,
                should_use_dots=should_use_dots
            )
            contexts.append(context)
        
        return contexts
    
    def _calculate_filename_confidence_score(self, text: str, start: int, end: int, 
                                           action_word: str, filename_part: str, extension: str) -> float:
        """
        Calculate confidence score for filename context based on multiple factors.
        
        Higher score = more confident this should use dots (like "settings.json")
        Lower score = more confident this should use underscores (like "config_file_settings.json")
        """
        confidence = 0.5  # Base confidence
        
        # Factor 1: Extension type (higher confidence for common file extensions)
        common_extensions = ["json", "py", "js", "html", "css", "md", "txt", "csv", "xml"]
        if extension.lower() in common_extensions:
            confidence += 0.2
        
        # Factor 2: Action word presence (higher confidence with clear action words)
        strong_action_words = ["edit", "open", "create", "save", "run", "check"]
        if action_word.lower() in strong_action_words:
            confidence += 0.3
        
        # Factor 3: Filename part analysis
        words_in_filename = filename_part.split()
        
        # Higher confidence for simple filenames (1-2 words) - MORE GENEROUS
        if len(words_in_filename) <= 2:
            confidence += 0.3  # Increased from 0.2
        
        # Neutral for moderate compound filenames (3 words)
        elif len(words_in_filename) == 3:
            confidence += 0.0  # No penalty for 3 words
        
        # Lower confidence for very complex compound filenames (4+ words)
        elif len(words_in_filename) >= 4:
            confidence -= 0.1  # Reduced penalty
        
        # Factor 4: Presence of "file" in filename part (lower confidence, likely descriptive)
        if "file" in filename_part.lower():
            confidence -= 0.3
        
        # Factor 5: Context position (sentence beginning suggests action context)
        context_before = text[max(0, start - 50):start].strip()
        if len(context_before.split()) <= 2:  # Near sentence beginning
            confidence += 0.2
        
        # Factor 6: Presence of articles/determiners ("the config file" vs "config")
        if any(word in filename_part.lower() for word in ["the ", "a ", "an ", "this ", "that "]):
            confidence -= 0.2
        
        # Factor 7: Well-known filename patterns (boost confidence)
        well_known_patterns = ["main", "index", "config", "settings", "utils", "readme", "app", "script"]
        if any(pattern in filename_part.lower() for pattern in well_known_patterns):
            confidence += 0.2
        
        # Factor 8: Context indicators for filenames ("in", "is in")
        context_before = text[max(0, start - 20):start].lower()
        if any(phrase in context_before for phrase in [" in ", " is in ", " at ", " from "]):
            confidence += 0.1
        
        # Clamp confidence between 0 and 1
        return max(0.0, min(1.0, confidence))
    
    def _analyze_filename_context_type(self, filename_part: str, action_word: str, 
                                     confidence_score: float) -> Tuple[str, bool]:
        """
        Analyze the filename context type and determine formatting approach.
        
        Returns:
            Tuple of (context_type, should_use_dots)
        """
        
        # High confidence (>= 0.7): Use dots - this is clearly a filename
        if confidence_score >= 0.7:
            return "action", True
        
        # Medium-high confidence (>= 0.5): Use dots for simple cases
        elif confidence_score >= 0.5:
            words_count = len(filename_part.split())
            if words_count <= 2 and action_word:
                return "descriptive", True
            else:
                return "compound", False
        
        # Lower confidence (< 0.5): Use underscores - likely compound/descriptive
        else:
            return "compound", False

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