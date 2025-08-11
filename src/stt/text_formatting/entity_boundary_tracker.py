#!/usr/bin/env python3
"""
Entity Boundary Tracker

This module provides post-conversion entity boundary preservation to fix
boundary tracking issues after Spanish entity conversion.

Theory 14: Post-Conversion Entity Boundary Preservation

Core Problem: When Spanish entities like "guión guión" (2 words, 12 chars) are 
converted to "--" (1 symbol, 2 chars), all subsequent entity boundaries become 
misaligned, causing incorrect spacing decisions, failed entity conversions, and 
entity protection failures.

Solution: Track and update all entity boundaries after each conversion to maintain
accurate position information throughout the conversion pipeline.
"""

from __future__ import annotations

import logging
from typing import List, Dict, Any
from dataclasses import dataclass

from .common import Entity, EntityType

logger = logging.getLogger(__name__)


@dataclass
class BoundaryChange:
    """Represents a change in text that affects entity boundaries."""
    start: int
    old_length: int
    new_length: int
    old_text: str
    new_text: str


class EntityBoundaryTracker:
    """
    Track entity boundaries through text modifications.
    
    This class maintains entity position accuracy as text is modified during
    entity conversion, particularly for Spanish multi-word entities that change
    the length of text segments.
    """
    
    def __init__(self, entities: List[Entity], original_text: str):
        """
        Initialize the boundary tracker with original entities and text.
        
        Args:
            entities: List of original entities to track
            original_text: Original text before any conversions
        """
        self.entities = [self._copy_entity(entity) for entity in entities]
        self.original_text = original_text
        self.current_text = original_text
        self.changes_log: List[BoundaryChange] = []
        
        logger.debug(f"EntityBoundaryTracker initialized with {len(self.entities)} entities")
        
    def _copy_entity(self, entity: Entity) -> Entity:
        """Create a deep copy of an entity."""
        return Entity(
            start=entity.start,
            end=entity.end,
            text=entity.text,
            type=entity.type,
            metadata=entity.metadata.copy() if entity.metadata else {}
        )
    
    def record_conversion(self, entity: Entity, old_text: str, new_text: str) -> None:
        """
        Record a conversion and update all affected boundaries.
        
        Args:
            entity: The entity being converted
            old_text: The original text of the entity
            new_text: The new text after conversion
        """
        # Find the entity in our tracked list
        tracked_entity = self._find_tracked_entity(entity)
        if not tracked_entity:
            logger.debug(f"Entity not found in tracked list: {entity.type}('{old_text}')")
            return
            
        # Record the change
        change = BoundaryChange(
            start=tracked_entity.start,
            old_length=len(old_text),
            new_length=len(new_text),
            old_text=old_text,
            new_text=new_text
        )
        self.changes_log.append(change)
        
        # Update the current text
        self.current_text = (
            self.current_text[:tracked_entity.start] +
            new_text +
            self.current_text[tracked_entity.end:]
        )
        
        # Update the converted entity's text and end position
        tracked_entity.text = new_text
        tracked_entity.end = tracked_entity.start + len(new_text)
        
        # Adjust all other entity boundaries after this change
        self.adjust_boundaries_after_change(
            tracked_entity.start, 
            len(old_text), 
            len(new_text)
        )
        
        logger.debug(f"Recorded conversion: '{old_text}' -> '{new_text}' at position {tracked_entity.start}")
        
    def _find_tracked_entity(self, target_entity: Entity) -> Entity | None:
        """
        Find the corresponding tracked entity by matching position and type.
        
        Args:
            target_entity: The entity to find
            
        Returns:
            The tracked entity if found, None otherwise
        """
        for entity in self.entities:
            if (entity.start == target_entity.start and 
                entity.end == target_entity.end and
                entity.type == target_entity.type):
                return entity
        return None
        
    def adjust_boundaries_after_change(self, start: int, old_length: int, new_length: int) -> None:
        """
        Adjust all entity boundaries after a text change.
        
        This is the core algorithm that maintains entity position accuracy.
        
        Args:
            start: Start position of the change
            old_length: Length of the old text
            new_length: Length of the new text
        """
        offset_change = new_length - old_length
        change_end = start + old_length
        
        if offset_change == 0:
            return  # No boundary adjustment needed
            
        logger.debug(f"Adjusting boundaries after change at {start}, offset: {offset_change}")
        
        for entity in self.entities:
            # Skip the entity that was just converted (it was already updated)
            if entity.start == start and entity.end == start + new_length:
                continue
                
            if entity.start >= change_end:
                # Entity is completely after the change - shift it
                entity.start += offset_change
                entity.end += offset_change
                logger.debug(f"Shifted entity {entity.type} by {offset_change}: [{entity.start}-{entity.end}]")
                
            elif entity.end > start and entity.start < change_end:
                # Entity overlaps with the change area - this is complex
                self._handle_overlapping_entity(entity, start, old_length, new_length)
                
    def _handle_overlapping_entity(self, entity: Entity, change_start: int, old_length: int, new_length: int) -> None:
        """
        Handle entities that overlap with the conversion area.
        
        This is where Spanish multi-word entity conversions typically occur.
        
        Args:
            entity: The overlapping entity
            change_start: Start position of the change
            old_length: Original length of changed text
            new_length: New length of changed text
        """
        change_end = change_start + old_length
        
        if entity.start < change_start and entity.end > change_end:
            # Entity contains the change - adjust end position
            offset_change = new_length - old_length
            entity.end += offset_change
            logger.debug(f"Adjusted containing entity {entity.type}: end position shifted by {offset_change}")
            
        elif entity.start >= change_start and entity.end <= change_end:
            # Entity is completely within the change - this shouldn't happen in normal conversion
            logger.warning(f"Entity {entity.type} completely within change area - may indicate overlap issue")
            
        else:
            # Partial overlap - adjust the affected boundary
            if entity.start < change_start:
                # Entity starts before change, ends within - adjust end
                offset_change = new_length - old_length
                entity.end += offset_change
            else:
                # Entity starts within change, ends after - adjust start
                # This is rare but can happen with nested entities
                entity.start = change_start + new_length
                logger.debug(f"Adjusted overlapping entity {entity.type}: repositioned to start at {entity.start}")
                
    def get_updated_entities(self) -> List[Entity]:
        """
        Get entities with corrected boundaries.
        
        Returns:
            List of entities with updated positions
        """
        # Validate all entities have correct boundaries
        validated_entities = []
        
        for entity in self.entities:
            if self._validate_entity_boundaries(entity):
                validated_entities.append(entity)
            else:
                logger.debug(f"Removing entity with invalid boundaries: {entity.type}('{entity.text}')")
                
        logger.debug(f"Returning {len(validated_entities)} validated entities")
        return validated_entities
        
    def _validate_entity_boundaries(self, entity: Entity) -> bool:
        """
        Validate that an entity's boundaries are correct in the current text.
        
        Args:
            entity: Entity to validate
            
        Returns:
            True if boundaries are valid, False otherwise
        """
        if entity.start < 0 or entity.end > len(self.current_text):
            return False
            
        if entity.start >= entity.end:
            return False
            
        # Check if the entity text matches what's at that position
        actual_text = self.current_text[entity.start:entity.end]
        if actual_text != entity.text:
            logger.debug(f"Text mismatch for {entity.type}: expected '{entity.text}', found '{actual_text}'")
            return False
            
        return True
        
    def get_spanish_entity_spacing_rules(self) -> Dict[str, Dict[str, Any]]:
        """
        Get Spanish entity spacing rules for proper conversion handling.
        
        Returns:
            Dictionary of Spanish entity spacing rules
        """
        return {
            "guión guión": {
                "target": "--",
                "preserve_leading_space": True,
                "preserve_trailing_space": True,
                "is_operator": True
            },
            "guión bajo": {
                "target": "_",
                "preserve_leading_space": False,
                "preserve_trailing_space": False,
                "is_connector": True
            },
            "menos menos": {
                "target": "--",
                "preserve_leading_space": True,
                "preserve_trailing_space": False,
                "is_operator": True
            },
            "punto": {
                "target": ".",
                "preserve_leading_space": False,
                "preserve_trailing_space": False,
                "is_punctuation": True
            }
        }
        
    def apply_spanish_spacing_rules(self, entity_text: str, converted_text: str, 
                                  context_before: str = "", context_after: str = "") -> str:
        """
        Apply Spanish-specific spacing rules to converted text.
        
        This handles the spacing issues that occur when Spanish multi-word entities
        are converted to symbols. For example:
        - "guión guión" -> "--" should preserve proper spacing
        - "guión bajo" -> "_" should connect words without spaces
        - "menos menos" -> "--" should work as operator
        
        Args:
            entity_text: Original Spanish entity text
            converted_text: Converted text
            context_before: Text immediately before the entity
            context_after: Text immediately after the entity
            
        Returns:
            Converted text with proper spacing applied
        """
        rules = self.get_spanish_entity_spacing_rules()
        entity_key = entity_text.lower().strip()
        
        if entity_key not in rules:
            # For entities not in our rules, apply basic spacing preservation
            return self._apply_basic_spacing_preservation(entity_text, converted_text, context_before, context_after)
            
        rule = rules[entity_key]
        result = converted_text
        
        # Handle specific Spanish entity spacing patterns
        if entity_key == "guión guión":
            # "usa guión guión versión" -> "usa --versión" (preserve space before, add space after if needed)
            if context_before and not context_before.endswith(" "):
                result = " " + result
            if context_after and context_after[0:1].isalpha() and not result.endswith(" "):
                result = result + " "
        elif entity_key == "guión bajo":
            # "archivo guión bajo configuración" -> "archivo _configuración" (space before underscore, no space after)
            if context_before and not context_before.endswith(" "):
                result = " " + result
            # No space after underscore - it should connect words
        elif entity_key == "menos menos":
            # "valor y menos menos" -> "valor y--" (preserve existing spacing, no trailing space)
            # The operator should stick to what follows
            pass
        else:
            # Apply general rules
            if rule.get("preserve_leading_space") and context_before and not context_before.endswith(" "):
                result = " " + result
            if rule.get("preserve_trailing_space") and context_after and not context_after.startswith(" "):
                result = result + " "
            
        logger.debug(f"Applied Spanish spacing rules for '{entity_text}': '{converted_text}' -> '{result}'")
        return result
        
    def _apply_basic_spacing_preservation(self, entity_text: str, converted_text: str, 
                                        context_before: str, context_after: str) -> str:
        """
        Apply basic spacing preservation for Spanish entities not in our specific rules.
        
        Args:
            entity_text: Original entity text
            converted_text: Converted text
            context_before: Context before entity
            context_after: Context after entity
            
        Returns:
            Text with basic spacing preserved
        """
        # For most multi-word Spanish entities, preserve natural word spacing
        if " " in entity_text:
            # Multi-word entity - preserve leading space if there was one
            if context_before and not context_before.endswith(" "):
                converted_text = " " + converted_text
                
        return converted_text
        
    def get_debug_info(self) -> Dict[str, Any]:
        """
        Get debug information about the tracking state.
        
        Returns:
            Dictionary with debug information
        """
        return {
            "original_text_length": len(self.original_text),
            "current_text_length": len(self.current_text),
            "entity_count": len(self.entities),
            "changes_count": len(self.changes_log),
            "changes": [
                {
                    "start": change.start,
                    "old_text": change.old_text,
                    "new_text": change.new_text,
                    "length_change": change.new_length - change.old_length
                }
                for change in self.changes_log
            ]
        }