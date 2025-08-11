#!/usr/bin/env python3
"""
Theory 12: Entity Interaction Conflict Resolution System

This module implements a robust conflict resolution system for overlapping entity types
that cause test failures in the GOOBITS STT text formatting pipeline.

The system handles:
- Entity overlap detection and resolution
- Priority-based conflict resolution using contextual rules
- Boundary adjustment after entity conversions
- Type hierarchy management
- Position tracking throughout the pipeline

This conservative implementation focuses on resolving specific known conflicts
without major architectural changes to the existing system.
"""

import logging
from typing import Dict, List, Set, Tuple, Optional, Any
from dataclasses import dataclass
from enum import Enum

# Local imports
from stt.text_formatting.common import Entity, EntityType
from stt.text_formatting.universal_priority_manager import get_priority_manager

# Setup logging
logger = logging.getLogger(__name__)


class ConflictType(Enum):
    """Types of entity conflicts that can occur."""
    OVERLAP = "overlap"           # Entities with overlapping character ranges
    CONTAINMENT = "containment"   # One entity completely contains another
    ADJACENT = "adjacent"         # Entities are adjacent and may merge
    BOUNDARY = "boundary"         # Entities share boundaries
    PRIORITY = "priority"         # Same range, different types


@dataclass
class ConflictContext:
    """Context information for resolving entity conflicts."""
    sentence_position: str    # start, middle, end
    surrounding_text: str     # Text around the conflict
    has_punctuation: bool     # Whether punctuation is nearby
    language: str = "en"      # Language for context-specific resolution


@dataclass
class EntityConflict:
    """Represents a conflict between two or more entities."""
    entities: List[Entity]
    conflict_type: ConflictType
    context: ConflictContext
    priority_matrix: Dict[EntityType, int]
    
    def get_winner(self) -> Entity:
        """Determine the winning entity based on priority and context."""
        return _resolve_conflict_winner(self.entities, self.conflict_type, 
                                      self.context, self.priority_matrix)


class EntityConflictResolver:
    """
    Main class for resolving entity interaction conflicts.
    
    This resolver uses intelligent priority matrices and contextual analysis
    to resolve conflicts between overlapping entities while maintaining
    backwards compatibility with existing behavior.
    """
    
    def __init__(self, language: str = "en"):
        """
        Initialize the conflict resolver.
        
        Args:
            language: Language code for priority resolution
        """
        self.language = language
        self.priority_manager = get_priority_manager(language)
        self.priority_matrix = self.priority_manager.get_all_priorities()
        
        # Custom priority overrides for specific conflict scenarios
        self._setup_conflict_priorities()
        
        logger.debug(f"EntityConflictResolver initialized for language '{language}'")
    
    def _setup_conflict_priorities(self):
        """Setup conflict-specific priority rules."""
        # These rules handle specific conflict scenarios that need custom resolution
        self.conflict_rules = {
            # Filename vs URL: Both should coexist when clearly separate
            (EntityType.FILENAME, EntityType.URL): self._resolve_filename_url_conflict,
            (EntityType.URL, EntityType.FILENAME): self._resolve_filename_url_conflict,
            
            # Email vs Filename: Email takes priority at domain boundaries  
            (EntityType.EMAIL, EntityType.FILENAME): self._resolve_email_filename_conflict,
            (EntityType.FILENAME, EntityType.EMAIL): self._resolve_email_filename_conflict,
            
            # Command vs Text: Command takes priority at sentence start
            (EntityType.SLASH_COMMAND, EntityType.CARDINAL): self._resolve_command_priority,
            (EntityType.COMMAND_FLAG, EntityType.CARDINAL): self._resolve_command_priority,
        }
    
    def resolve_conflicts(self, entities: List[Entity], text: str) -> List[Entity]:
        """
        Main conflict resolution method.
        
        Conservative approach: Only resolve clear, problematic conflicts.
        Most entity overlap is already handled by the existing priority system.
        
        Args:
            entities: List of detected entities that may have conflicts
            text: Original text for context analysis
            
        Returns:
            List of entities with conflicts resolved
        """
        if not entities or len(entities) < 2:
            return entities
            
        logger.debug(f"Starting conservative conflict resolution for {len(entities)} entities")
        
        # Step 1: Only detect severe conflicts that existing system misses
        conflicts = self._detect_severe_conflicts(entities, text)
        
        if not conflicts:
            logger.debug("No severe conflicts detected - using existing entities")
            return entities
            
        logger.debug(f"Found {len(conflicts)} severe conflicts to resolve")
        
        # Step 2: Resolve only the most problematic conflicts
        resolved_entities = self._resolve_severe_conflicts(conflicts, entities, text)
        
        logger.debug(f"Conservative conflict resolution: {len(entities)} -> {len(resolved_entities)} entities")
        return resolved_entities
    
    def _detect_severe_conflicts(self, entities: List[Entity], text: str) -> List[EntityConflict]:
        """
        Detect only severe conflicts that the existing system can't handle well.
        
        Focus on specific problematic patterns rather than all overlaps.
        """
        severe_conflicts = []
        
        # Sort entities by start position
        sorted_entities = sorted(entities, key=lambda e: e.start)
        
        for i, entity1 in enumerate(sorted_entities):
            for entity2 in sorted_entities[i+1:]:
                # Only check nearby entities
                if entity2.start > entity1.end + 5:
                    break
                
                # Check for specific problematic conflict patterns
                if self._is_severe_conflict(entity1, entity2, text):
                    context = self._analyze_context(entity1, entity2, text)
                    conflict = EntityConflict(
                        entities=[entity1, entity2],
                        conflict_type=self._classify_conflict(entity1, entity2),
                        context=context,
                        priority_matrix=self.priority_matrix
                    )
                    severe_conflicts.append(conflict)
        
        return severe_conflicts
    
    def _is_severe_conflict(self, entity1: Entity, entity2: Entity, text: str) -> bool:
        """
        Determine if two entities represent a severe conflict that needs resolution.
        
        Focus on specific known problematic patterns rather than all conflicts.
        """
        # Only resolve exact overlaps 
        exact_overlap = (entity1.start == entity2.start and entity1.end == entity2.end)
        
        if exact_overlap:
            return True
        
        # Check for filename over-detection issues
        if self._is_filename_over_detection(entity1, entity2, text):
            return True
            
        # Don't interfere with most other conflicts - let existing system handle them
        return False
    
    def _is_filename_over_detection(self, entity1: Entity, entity2: Entity, text: str) -> bool:
        """
        Detect cases where filename detection is too aggressive and captures extra words.
        
        This handles the specific case where "go to main dot py" becomes "go_to_main.py"
        instead of separate entities.
        """
        # Check if one entity is a filename that starts with common action words
        filename_entity = None
        other_entity = None
        
        if entity1.type == EntityType.FILENAME:
            filename_entity = entity1
            other_entity = entity2
        elif entity2.type == EntityType.FILENAME:
            filename_entity = entity2
            other_entity = entity1
        else:
            return False
        
        if not filename_entity:
            return False
            
        # Check if filename starts with common action/direction words that shouldn't be included
        action_words = ['go to', 'run', 'open', 'edit', 'create', 'save', 'load', 'check', 'use']
        filename_text = filename_entity.text.lower()
        
        # Check if the filename starts with action words followed by a more reasonable filename
        for action in action_words:
            if filename_text.startswith(action + ' '):
                remaining_text = filename_text[len(action):].strip()
                # If the remaining text looks like a reasonable filename (has dot extension)
                if ' dot ' in remaining_text and len(remaining_text.split()) <= 4:
                    logger.debug(f"Detected filename over-detection: '{filename_entity.text}' starts with action word '{action}'")
                    return True
        
        return False
    
    def _resolve_severe_conflicts(self, conflicts: List[EntityConflict], 
                                original_entities: List[Entity], text: str) -> List[Entity]:
        """
        Resolve only severe conflicts using minimal intervention.
        """
        if not conflicts:
            return original_entities
            
        resolved_entities = list(original_entities)
        entities_to_remove = set()
        entities_to_add = []
        
        for conflict in conflicts:
            # Skip if any entity in this conflict was already removed
            if any(id(e) in entities_to_remove for e in conflict.entities):
                continue
                
            # Handle filename over-detection specifically
            if self._has_filename_over_detection(conflict):
                corrected_entities = self._fix_filename_over_detection(conflict, text)
                if corrected_entities:
                    # Remove the over-detected entity and add corrected ones
                    for entity in conflict.entities:
                        if entity.type == EntityType.FILENAME:
                            entities_to_remove.add(id(entity))
                    entities_to_add.extend(corrected_entities)
                    continue
                
            # For exact overlaps, use priority to choose winner
            if conflict.conflict_type == ConflictType.PRIORITY:
                winner = max(conflict.entities, key=lambda e: self.priority_matrix.get(e.type, 0))
                losers = [e for e in conflict.entities if e != winner]
                
                for loser in losers:
                    entities_to_remove.add(id(loser))
                    logger.debug(f"Severe conflict resolution: {winner.type}('{winner.text}') beats "
                               f"{loser.type}('{loser.text}')")
        
        # Remove losing entities and add corrected entities
        resolved_entities = [e for e in resolved_entities if id(e) not in entities_to_remove]
        resolved_entities.extend(entities_to_add)
        
        return resolved_entities
    
    def _has_filename_over_detection(self, conflict: EntityConflict) -> bool:
        """Check if the conflict involves filename over-detection."""
        return any(entity.type == EntityType.FILENAME for entity in conflict.entities) and \
               self._is_filename_over_detection(conflict.entities[0], conflict.entities[1] if len(conflict.entities) > 1 else None, "")
    
    def _fix_filename_over_detection(self, conflict: EntityConflict, text: str) -> List[Entity]:
        """
        Fix filename over-detection by creating properly scoped filename entities.
        
        Args:
            conflict: The conflict involving over-detected filename
            text: Original text
            
        Returns:
            List of corrected entities to replace the over-detected one
        """
        corrected_entities = []
        
        for entity in conflict.entities:
            if entity.type == EntityType.FILENAME:
                # Extract just the filename part, removing action words
                filename_text = entity.text.lower()
                action_words = ['go to', 'run', 'open', 'edit', 'create', 'save', 'load', 'check', 'use']
                
                for action in action_words:
                    if filename_text.startswith(action + ' '):
                        remaining_text = filename_text[len(action):].strip()
                        
                        # Find the position of the actual filename in the original text
                        action_end_pos = entity.start + len(action)
                        while action_end_pos < entity.end and text[action_end_pos].isspace():
                            action_end_pos += 1
                            
                        if action_end_pos < entity.end:
                            # Create a new filename entity for just the filename part
                            corrected_filename = Entity(
                                start=action_end_pos,
                                end=entity.end,
                                text=text[action_end_pos:entity.end],
                                type=EntityType.FILENAME,
                                metadata={"corrected_over_detection": True}
                            )
                            corrected_entities.append(corrected_filename)
                            logger.debug(f"Fixed filename over-detection: '{entity.text}' -> '{corrected_filename.text}'")
                        break
                        
        return corrected_entities
    
    def _detect_conflicts(self, entities: List[Entity], text: str) -> List[EntityConflict]:
        """
        Detect all entity conflicts using geometric overlap detection.
        
        Args:
            entities: Entities to check for conflicts
            text: Original text for context
            
        Returns:
            List of detected conflicts
        """
        conflicts = []
        
        # Sort entities by start position for efficient processing
        sorted_entities = sorted(entities, key=lambda e: e.start)
        
        for i, entity1 in enumerate(sorted_entities):
            for entity2 in sorted_entities[i+1:]:
                # Check if entities are close enough to potentially conflict
                if entity2.start > entity1.end + 10:  # Stop if too far apart
                    break
                    
                conflict_type = self._classify_conflict(entity1, entity2)
                if conflict_type:
                    context = self._analyze_context(entity1, entity2, text)
                    conflict = EntityConflict(
                        entities=[entity1, entity2],
                        conflict_type=conflict_type,
                        context=context,
                        priority_matrix=self.priority_matrix
                    )
                    conflicts.append(conflict)
        
        return conflicts
    
    def _classify_conflict(self, entity1: Entity, entity2: Entity) -> Optional[ConflictType]:
        """
        Classify the type of conflict between two entities.
        
        Args:
            entity1, entity2: Entities to check
            
        Returns:
            ConflictType if conflict exists, None otherwise
        """
        # Check for exact overlap (same boundaries)
        if entity1.start == entity2.start and entity1.end == entity2.end:
            return ConflictType.PRIORITY
        
        # Check for containment
        if (entity1.start <= entity2.start and entity1.end >= entity2.end):
            return ConflictType.CONTAINMENT
        if (entity2.start <= entity1.start and entity2.end >= entity1.end):
            return ConflictType.CONTAINMENT
            
        # Check for overlap
        if not (entity1.end <= entity2.start or entity2.end <= entity1.start):
            return ConflictType.OVERLAP
            
        # Check for adjacency (entities are very close)
        if abs(entity1.end - entity2.start) <= 1 or abs(entity2.end - entity1.start) <= 1:
            return ConflictType.ADJACENT
        
        return None
    
    def _analyze_context(self, entity1: Entity, entity2: Entity, text: str) -> ConflictContext:
        """
        Analyze the context around conflicting entities.
        
        Args:
            entity1, entity2: Conflicting entities
            text: Original text
            
        Returns:
            ConflictContext with contextual information
        """
        # Determine position in sentence
        start_pos = min(entity1.start, entity2.start)
        end_pos = max(entity1.end, entity2.end)
        
        # Check sentence position
        sentence_position = "middle"
        if start_pos < 50:  # Near beginning
            sentence_position = "start"
        elif end_pos > len(text) - 50:  # Near end
            sentence_position = "end"
        
        # Get surrounding text for context
        context_start = max(0, start_pos - 20)
        context_end = min(len(text), end_pos + 20)
        surrounding_text = text[context_start:context_end]
        
        # Check for nearby punctuation
        has_punctuation = any(p in surrounding_text for p in ".?!,:;")
        
        return ConflictContext(
            sentence_position=sentence_position,
            surrounding_text=surrounding_text,
            has_punctuation=has_punctuation,
            language=self.language
        )
    
    def _resolve_all_conflicts(self, conflicts: List[EntityConflict], 
                             original_entities: List[Entity], text: str) -> List[Entity]:
        """
        Resolve all detected conflicts using priority rules.
        
        Args:
            conflicts: List of conflicts to resolve
            original_entities: Original entity list
            text: Original text
            
        Returns:
            List of entities with conflicts resolved
        """
        resolved_entities = list(original_entities)
        entities_to_remove = set()
        
        # Sort conflicts by priority (highest priority conflicts first)
        sorted_conflicts = sorted(conflicts, key=lambda c: self._conflict_priority(c))
        
        for conflict in sorted_conflicts:
            # Skip if any entity in this conflict was already removed
            if any(id(e) in entities_to_remove for e in conflict.entities):
                continue
                
            # Determine winner
            winner = conflict.get_winner()
            losers = [e for e in conflict.entities if e != winner]
            
            # Mark losers for removal
            for loser in losers:
                entities_to_remove.add(id(loser))
                logger.debug(f"Conflict resolution: {winner.type}('{winner.text}') beats "
                           f"{loser.type}('{loser.text}')")
        
        # Remove losing entities
        resolved_entities = [e for e in resolved_entities if id(e) not in entities_to_remove]
        
        return resolved_entities
    
    def _conflict_priority(self, conflict: EntityConflict) -> int:
        """Calculate priority for resolving conflicts (higher = resolve first)."""
        # Priority conflicts should be resolved first
        if conflict.conflict_type == ConflictType.PRIORITY:
            return 100
        # Containment conflicts next
        elif conflict.conflict_type == ConflictType.CONTAINMENT:
            return 90
        # Overlap conflicts
        elif conflict.conflict_type == ConflictType.OVERLAP:
            return 80
        # Adjacent conflicts last
        else:
            return 70
    
    def _post_resolution_cleanup(self, entities: List[Entity], text: str) -> List[Entity]:
        """
        Apply post-resolution cleanup and validation.
        
        Args:
            entities: Resolved entities
            text: Original text
            
        Returns:
            Final cleaned entities
        """
        # Sort by position
        sorted_entities = sorted(entities, key=lambda e: e.start)
        
        # Validate entity boundaries
        cleaned_entities = []
        for entity in sorted_entities:
            if self._validate_entity_boundaries(entity, text):
                cleaned_entities.append(entity)
            else:
                logger.debug(f"Removing invalid entity: {entity.type}('{entity.text}')")
        
        return cleaned_entities
    
    def _validate_entity_boundaries(self, entity: Entity, text: str) -> bool:
        """Validate that entity boundaries are correct."""
        if entity.start < 0 or entity.end > len(text):
            return False
        if entity.start >= entity.end:
            return False
        if entity.text != text[entity.start:entity.end]:
            return False
        return True
    
    # Conflict-specific resolution methods
    
    def _resolve_filename_url_conflict(self, entities: List[Entity], 
                                     conflict_type: ConflictType,
                                     context: ConflictContext) -> Entity:
        """
        Resolve conflicts between filenames and URLs.
        
        Strategy: Allow both to coexist when they're clearly separate entities.
        """
        filename_entity = next((e for e in entities if e.type == EntityType.FILENAME), None)
        url_entity = next((e for e in entities if e.type == EntityType.URL), None)
        
        if not filename_entity or not url_entity:
            # Default to higher priority entity
            return max(entities, key=lambda e: self.priority_matrix.get(e.type, 0))
        
        # If they don't actually overlap significantly, prefer to keep both
        # But for now, use standard priority resolution
        return max(entities, key=lambda e: self.priority_matrix.get(e.type, 0))
    
    def _resolve_email_filename_conflict(self, entities: List[Entity],
                                       conflict_type: ConflictType,
                                       context: ConflictContext) -> Entity:
        """Resolve conflicts between emails and filenames."""
        email_entity = next((e for e in entities if e.type == EntityType.EMAIL), None)
        
        # Email usually takes priority when @ symbol is present
        if email_entity and "@" in email_entity.text:
            return email_entity
            
        # Default to priority-based resolution
        return max(entities, key=lambda e: self.priority_matrix.get(e.type, 0))
    
    def _resolve_command_priority(self, entities: List[Entity],
                                conflict_type: ConflictType, 
                                context: ConflictContext) -> Entity:
        """Resolve command vs other entity conflicts."""
        command_entity = next((e for e in entities 
                             if e.type in [EntityType.SLASH_COMMAND, EntityType.COMMAND_FLAG]), None)
        
        # Commands take priority at sentence start
        if command_entity and context.sentence_position == "start":
            return command_entity
            
        # Default to priority-based resolution
        return max(entities, key=lambda e: self.priority_matrix.get(e.type, 0))


def _resolve_conflict_winner(entities: List[Entity], conflict_type: ConflictType,
                           context: ConflictContext, priority_matrix: Dict[EntityType, int]) -> Entity:
    """
    Determine the winning entity in a conflict.
    
    This function implements the core conflict resolution logic using priority
    and contextual information.
    
    Args:
        entities: Conflicting entities
        conflict_type: Type of conflict
        context: Contextual information
        priority_matrix: Entity priority mapping
        
    Returns:
        Winning entity
    """
    if not entities:
        return None
        
    if len(entities) == 1:
        return entities[0]
    
    # For priority conflicts (same boundaries), use priority directly
    if conflict_type == ConflictType.PRIORITY:
        return max(entities, key=lambda e: priority_matrix.get(e.type, 0))
    
    # For containment, prefer the longer (containing) entity unless priority difference is large
    if conflict_type == ConflictType.CONTAINMENT:
        longer_entity = max(entities, key=lambda e: e.end - e.start)
        shorter_entity = min(entities, key=lambda e: e.end - e.start)
        
        longer_priority = priority_matrix.get(longer_entity.type, 0)
        shorter_priority = priority_matrix.get(shorter_entity.type, 0)
        
        # If shorter entity has significantly higher priority, choose it
        if shorter_priority - longer_priority > 20:
            return shorter_entity
        else:
            return longer_entity
    
    # For overlap, use priority with length as tiebreaker
    winner = max(entities, key=lambda e: (
        priority_matrix.get(e.type, 0),  # Primary: priority
        e.end - e.start,                 # Secondary: length
        -e.start                         # Tertiary: earlier position
    ))
    
    return winner


# Convenience functions for integration

def resolve_entity_conflicts(entities: List[Entity], text: str, language: str = "en") -> List[Entity]:
    """
    Convenience function to resolve entity conflicts.
    
    Args:
        entities: List of entities with potential conflicts
        text: Original text for context
        language: Language code
        
    Returns:
        List of entities with conflicts resolved
    """
    if not entities:
        return entities
        
    resolver = EntityConflictResolver(language)
    return resolver.resolve_conflicts(entities, text)


def update_entity_positions_after_conversion(entities: List[Entity], 
                                            original_text: str,
                                            converted_text: str) -> List[Entity]:
    """
    Update entity positions after text conversion.
    
    This function tracks how entity positions change when the underlying text
    is modified by entity conversions.
    
    Args:
        entities: Entities with original positions
        original_text: Original text before conversion
        converted_text: Text after conversion
        
    Returns:
        Entities with updated positions
    """
    # This is a complex problem that requires tracking text transformations
    # For now, return entities as-is since step3_conversion.py handles this
    return entities