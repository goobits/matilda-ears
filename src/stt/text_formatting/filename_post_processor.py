#!/usr/bin/env python3
"""
Filename Post-Processor for Theory 12: Entity Interaction Conflict Resolution

This module provides post-processing logic to fix over-detected filename entities
that include action words or other extraneous text.

The key issue being addressed:
- Input: "go to main dot py on example dot com"
- Current: Detects "go to main dot py" as a single filename -> "go_to_main.py"
- Expected: Should detect "main dot py" as filename -> "main.py"

This is a targeted fix for specific filename detection issues without disrupting
the broader entity detection system.
"""

import logging
import re
from typing import List, Optional

from stt.text_formatting.common import Entity, EntityType

# Setup logging
logger = logging.getLogger(__name__)


def post_process_filename_entities(entities: List[Entity], text: str) -> List[Entity]:
    """
    Post-process filename entities to fix over-detection issues.
    
    This function identifies filename entities that include action words or other
    extraneous text and creates corrected versions.
    
    Args:
        entities: List of detected entities
        text: Original text
        
    Returns:
        List of entities with filename over-detections corrected
    """
    if not entities:
        return entities
        
    corrected_entities = []
    
    for entity in entities:
        if entity.type == EntityType.FILENAME:
            corrected_entity = _fix_over_detected_filename(entity, text)
            if corrected_entity:
                corrected_entities.append(corrected_entity)
                logger.debug(f"Fixed filename over-detection: '{entity.text}' -> '{corrected_entity.text}'")
            else:
                corrected_entities.append(entity)  # Keep original if no fix needed
        else:
            corrected_entities.append(entity)
    
    return corrected_entities


def _fix_over_detected_filename(entity: Entity, text: str) -> Optional[Entity]:
    """
    Fix a single over-detected filename entity.
    
    Args:
        entity: Filename entity to check and potentially fix
        text: Original text
        
    Returns:
        Corrected entity if fix was needed, None if original should be kept
    """
    if entity.type != EntityType.FILENAME:
        return None
        
    entity_text = entity.text.lower()
    
    # Define action words that shouldn't be part of filenames
    action_prefixes = [
        'go to ', 'run ', 'open ', 'edit ', 'create ', 'save ', 'load ', 
        'check ', 'use ', 'execute ', 'launch ', 'start ', 'call ',
        'import ', 'include ', 'view ', 'see ', 'look at ', 'find '
    ]
    
    # Check if the filename starts with an action prefix
    for prefix in action_prefixes:
        if entity_text.startswith(prefix):
            remaining_text = entity_text[len(prefix):].strip()
            
            # Verify the remaining text looks like a reasonable filename
            if _is_reasonable_filename_text(remaining_text):
                # Calculate new positions
                prefix_len = len(prefix)
                new_start = entity.start + prefix_len
                
                # Skip whitespace
                while new_start < entity.end and text[new_start].isspace():
                    new_start += 1
                
                if new_start < entity.end:
                    new_text = text[new_start:entity.end]
                    
                    # Create corrected entity
                    return Entity(
                        start=new_start,
                        end=entity.end,
                        text=new_text,
                        type=EntityType.FILENAME,
                        metadata={
                            **(entity.metadata or {}),
                            "corrected_over_detection": True,
                            "removed_prefix": prefix.strip()
                        }
                    )
    
    # Also check for trailing context that shouldn't be included
    # Example: "main dot py on server" -> should be just "main dot py"
    trailing_contexts = [
        ' on ', ' at ', ' in ', ' from ', ' to ', ' with ', ' for ',
        ' and ', ' or ', ' but ', ' then ', ' now ', ' here ', ' there '
    ]
    
    for context in trailing_contexts:
        if context in entity_text:
            # Split and take only the first part if it looks like a filename
            parts = entity_text.split(context, 1)
            if len(parts) > 1:
                filename_part = parts[0].strip()
                if _is_reasonable_filename_text(filename_part) and ' dot ' in filename_part:
                    # Calculate new end position
                    context_pos = entity.text.lower().find(context)
                    if context_pos > 0:
                        new_end = entity.start + context_pos
                        new_text = text[entity.start:new_end].strip()
                        
                        if new_text:
                            return Entity(
                                start=entity.start,
                                end=entity.start + len(new_text),
                                text=new_text,
                                type=EntityType.FILENAME,
                                metadata={
                                    **(entity.metadata or {}),
                                    "corrected_over_detection": True,
                                    "removed_suffix": context.strip()
                                }
                            )
                    break
    
    return None


def _is_reasonable_filename_text(text: str) -> bool:
    """
    Check if text looks like a reasonable filename.
    
    Args:
        text: Text to check
        
    Returns:
        True if it looks like a filename, False otherwise
    """
    if not text or len(text.strip()) < 3:
        return False
        
    text = text.strip().lower()
    
    # Must contain "dot" followed by a reasonable extension
    if ' dot ' not in text:
        return False
        
    # Split on "dot" and check the parts
    parts = text.split(' dot ')
    if len(parts) < 2:
        return False
        
    filename_part = parts[0].strip()
    extension_part = parts[-1].strip()
    
    # Filename part should be reasonable (1-6 words, no weird patterns)
    filename_words = filename_part.split()
    if len(filename_words) == 0 or len(filename_words) > 6:
        return False
        
    # Extension should look reasonable
    if not extension_part or len(extension_part) > 10:
        return False
        
    # Common file extensions
    common_extensions = {
        'py', 'js', 'ts', 'java', 'cpp', 'c', 'h', 'go', 'rs', 'rb', 'php',
        'html', 'css', 'json', 'xml', 'yaml', 'yml', 'toml', 'csv', 'txt',
        'md', 'pdf', 'doc', 'docx', 'png', 'jpg', 'jpeg', 'gif', 'svg',
        'zip', 'tar', 'gz', 'exe', 'dll', 'so', 'dylib'
    }
    
    if extension_part in common_extensions:
        return True
        
    # Allow some flexibility for less common but reasonable extensions
    if re.match(r'^[a-z0-9]{1,8}$', extension_part):
        return True
        
    return False