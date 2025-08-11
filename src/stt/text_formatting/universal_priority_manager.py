#!/usr/bin/env python3
"""
Universal Cross-Language Entity Priority System - Theory 9 Implementation

This module provides a generalized, smart system for dynamic entity priorities per language
that solves cross-language conflicts universally. It extends the existing priority_config.py
system with language-specific priority matrices and universal conflict resolution.

Key Features:
- Language-specific priority matrices loaded from resources (en.json, es.json, etc.)
- Universal priority resolution engine that handles conflicts between any entity types
- Extensible priority configuration system for easy addition of new languages
- Smart conflict detection that automatically resolves entity overlaps
- Integration with existing entity detection pipeline

The system addresses the core problem where Spanish code entities like:
"comando barra iniciar" → Expected: "Comando /iniciar" → Actual: "Comando Barraiar"
have different linguistic priority needs than English patterns.

Architecture:
- Language-specific priority matrices in resources/*.json files
- Universal priority resolution engine in this module
- Conflict detection and resolution system
- Integration hooks for the existing entity detection pipeline
"""

from __future__ import annotations

import logging
from typing import Dict, Optional, Any
from enum import Enum

from stt.text_formatting.common import EntityType
from stt.text_formatting.constants import get_resources
from stt.core.config import setup_logging

logger = setup_logging(__name__)


class UniversalPriorityManager:
    """
    Universal cross-language priority system that dynamically loads and applies
    language-specific entity priorities.
    
    This system replaces hardcoded priority dictionaries with language-aware
    priority matrices that can be customized per language to handle linguistic
    differences in entity importance and conflict resolution.
    """
    
    # Fallback priorities (from original system) in case language-specific priorities are missing
    DEFAULT_PRIORITIES = {
        EntityType.SPOKEN_LETTER: 100,
        EntityType.LETTER_SEQUENCE: 95,
        EntityType.FILENAME: 90,
        EntityType.URL: 85,
        EntityType.SPOKEN_URL: 85,
        EntityType.SPOKEN_PROTOCOL_URL: 85,
        EntityType.EMAIL: 80,
        EntityType.SPOKEN_EMAIL: 80,
        EntityType.TEMPERATURE: 80,
        EntityType.MATH_EXPRESSION: 75,
        EntityType.MATH: 75,
        EntityType.ROOT_EXPRESSION: 74,
        EntityType.SCIENTIFIC_NOTATION: 73,
        EntityType.COMPARISON: 70,
        EntityType.ASSIGNMENT: 70,
        EntityType.INCREMENT_OPERATOR: 68,
        EntityType.DECREMENT_OPERATOR: 68,
        EntityType.SLASH_COMMAND: 65,
        EntityType.CLI_COMMAND: 65,
        EntityType.DOLLAR_CENTS: 65,
        EntityType.DOLLARS: 64,
        EntityType.CENTS: 63,
        EntityType.PROGRAMMING_KEYWORD: 63,
        EntityType.COMMAND_FLAG: 62,
        EntityType.CURRENCY: 62,
        EntityType.POUNDS: 61,
        EntityType.EUROS: 61,
        EntityType.UNDERSCORE_DELIMITER: 60,
        EntityType.SIMPLE_UNDERSCORE_VARIABLE: 60,
        EntityType.UNIX_PATH: 58,
        EntityType.WINDOWS_PATH: 58,
        EntityType.DATA_SIZE: 55,
        EntityType.FREQUENCY: 54,
        EntityType.VERSION: 53,
        EntityType.PORT_NUMBER: 52,
        EntityType.MONEY: 50,
        EntityType.METRIC_LENGTH: 50,
        EntityType.METRIC_WEIGHT: 50,
        EntityType.METRIC_VOLUME: 50,
        EntityType.TIME_AMPM: 48,
        EntityType.TIME: 47,
        EntityType.TIME_DURATION: 46,
        EntityType.TIME_CONTEXT: 45,
        EntityType.TIME_RELATIVE: 44,
        EntityType.DATE: 42,
        EntityType.PHONE_LONG: 40,
        EntityType.NUMERIC_RANGE: 38,
        EntityType.FRACTION: 36,
        EntityType.PERCENT: 35,
        EntityType.PHYSICS_SQUARED: 35,
        EntityType.PHYSICS_TIMES: 35,
        EntityType.MATH_CONSTANT: 34,
        EntityType.ORDINAL: 32,
        EntityType.QUANTITY: 30,
        EntityType.MUSIC_NOTATION: 30,
        EntityType.SPOKEN_EMOJI: 28,
        EntityType.PROTOCOL: 26,
        EntityType.CARDINAL: 20,
        EntityType.ABBREVIATION: 105,
    }
    
    def __init__(self, language: str = "en"):
        """
        Initialize the universal priority manager with a specific language.
        
        Args:
            language: Language code (e.g., 'en', 'es', 'fr', 'de')
        """
        self.language = language
        self.resources = get_resources(language)
        self._language_priorities: Optional[Dict[EntityType, int]] = None
        self._load_language_priorities()
        
        logger.info(f"Universal Priority Manager initialized for language '{language}' with {len(self._language_priorities)} entity priorities")
    
    def _load_language_priorities(self) -> None:
        """
        Load language-specific entity priorities from resource files.
        
        This method loads the priority matrix from the language resource file,
        converting string entity type names to EntityType enums for use in the system.
        """
        try:
            # Load priority matrix from language resources
            priority_data = self.resources.get("entity_priorities", {})
            
            if not priority_data:
                logger.warning(f"No entity_priorities found in {self.language}.json, using default priorities")
                self._language_priorities = self.DEFAULT_PRIORITIES.copy()
                return
            
            # Convert string keys to EntityType enums
            self._language_priorities = {}
            for entity_name, priority in priority_data.items():
                try:
                    # Find EntityType by name (not value)
                    entity_type = None
                    for et in EntityType:
                        if et.name == entity_name:
                            entity_type = et
                            break
                    
                    if entity_type is not None:
                        self._language_priorities[entity_type] = priority
                    else:
                        logger.warning(f"Unknown entity type '{entity_name}' in {self.language}.json priority matrix")
                        continue
                        
                except Exception as e:
                    logger.warning(f"Error processing entity type '{entity_name}' in {self.language}.json: {e}")
                    continue
            
            # Add any missing default priorities not specified in language file
            for entity_type, default_priority in self.DEFAULT_PRIORITIES.items():
                if entity_type not in self._language_priorities:
                    self._language_priorities[entity_type] = default_priority
                    
            logger.info(f"Loaded {len(self._language_priorities)} entity priorities for language '{self.language}'")
            
            # Log key differences from default priorities for debugging
            key_differences = []
            for entity_type, priority in self._language_priorities.items():
                default_priority = self.DEFAULT_PRIORITIES.get(entity_type, 0)
                if priority != default_priority:
                    key_differences.append(f"{entity_type.value}: {default_priority} → {priority}")
            
            if key_differences:
                logger.info(f"Language-specific priority adjustments for '{self.language}': {key_differences[:5]}")
                
        except Exception as e:
            logger.error(f"Failed to load language priorities for '{self.language}': {e}")
            self._language_priorities = self.DEFAULT_PRIORITIES.copy()
    
    def get_entity_priority(self, entity_type: EntityType) -> int:
        """
        Get the priority for a specific entity type in the current language.
        
        Args:
            entity_type: The EntityType to get priority for
            
        Returns:
            Priority value (higher number = higher priority)
        """
        if self._language_priorities is None:
            self._load_language_priorities()
        
        return self._language_priorities.get(entity_type, 0)
    
    def get_all_priorities(self) -> Dict[EntityType, int]:
        """
        Get the complete priority dictionary for the current language.
        
        Returns:
            Dictionary mapping EntityType to priority values
        """
        if self._language_priorities is None:
            self._load_language_priorities()
        
        return self._language_priorities.copy()
    
    def compare_entity_priorities(self, entity_type_1: EntityType, entity_type_2: EntityType) -> int:
        """
        Compare the priorities of two entity types.
        
        Args:
            entity_type_1: First entity type
            entity_type_2: Second entity type
            
        Returns:
            Positive if entity_type_1 has higher priority,
            Negative if entity_type_2 has higher priority,
            Zero if they have equal priority
        """
        priority_1 = self.get_entity_priority(entity_type_1)
        priority_2 = self.get_entity_priority(entity_type_2)
        return priority_1 - priority_2
    
    def resolve_entity_conflict(self, entity_1: Any, entity_2: Any) -> Any:
        """
        Resolve a conflict between two overlapping entities based on language-specific priorities.
        
        Args:
            entity_1: First entity (must have .type attribute)
            entity_2: Second entity (must have .type attribute)
            
        Returns:
            The entity that should be kept based on priority rules
        """
        priority_1 = self.get_entity_priority(entity_1.type)
        priority_2 = self.get_entity_priority(entity_2.type)
        
        # Primary factor: priority
        if priority_1 > priority_2:
            logger.debug(f"Resolved conflict: {entity_1.type.value} (priority={priority_1}) wins over {entity_2.type.value} (priority={priority_2})")
            return entity_1
        elif priority_2 > priority_1:
            logger.debug(f"Resolved conflict: {entity_2.type.value} (priority={priority_2}) wins over {entity_1.type.value} (priority={priority_1})")
            return entity_2
        else:
            # Same priority - use length as tiebreaker (longer is more specific)
            length_1 = entity_1.end - entity_1.start
            length_2 = entity_2.end - entity_2.start
            
            if length_1 > length_2:
                logger.debug(f"Resolved conflict: {entity_1.type.value} wins by length ({length_1} > {length_2})")
                return entity_1
            else:
                logger.debug(f"Resolved conflict: {entity_2.type.value} wins by length ({length_2} >= {length_1})")
                return entity_2
    
    def get_language_summary(self) -> str:
        """
        Get a human-readable summary of the priority configuration for the current language.
        
        Returns:
            String summary of the language-specific priority configuration
        """
        if self._language_priorities is None:
            self._load_language_priorities()
        
        lines = [f"Entity Priority Configuration for Language: {self.language}"]
        lines.append("=" * len(lines[0]))
        
        # Sort by priority (highest first)
        sorted_priorities = sorted(
            self._language_priorities.items(), 
            key=lambda x: (-x[1], x[0].value)
        )
        
        for entity_type, priority in sorted_priorities:
            # Show differences from default
            default_priority = self.DEFAULT_PRIORITIES.get(entity_type, 0)
            diff_marker = ""
            if priority > default_priority:
                diff_marker = f" ↑+{priority - default_priority}"
            elif priority < default_priority:
                diff_marker = f" ↓-{default_priority - priority}"
            
            lines.append(f"  {entity_type.value:<25} {priority:3d}{diff_marker}")
        
        return "\n".join(lines)
    
    @classmethod
    def create_for_language(cls, language: str) -> 'UniversalPriorityManager':
        """
        Factory method to create a priority manager for a specific language.
        
        Args:
            language: Language code (e.g., 'en', 'es', 'fr')
            
        Returns:
            Configured UniversalPriorityManager instance
        """
        return cls(language=language)
    
    def detect_priority_conflicts(self, entities: list) -> list:
        """
        Detect and log potential priority conflicts between entities.
        
        This method analyzes a list of entities and identifies cases where
        entity priorities might be causing unexpected behavior.
        
        Args:
            entities: List of entities to analyze
            
        Returns:
            List of conflict descriptions for debugging
        """
        conflicts = []
        
        # Look for entities with unexpectedly low priorities that might be getting overridden
        for entity in entities:
            priority = self.get_entity_priority(entity.type)
            
            # Check if this is a code-related entity with potentially low priority
            if entity.type.value in ['SLASH_COMMAND', 'COMMAND_FLAG', 'UNDERSCORE_DELIMITER']:
                if priority < 70:  # Threshold for what we consider "high priority" for code entities
                    conflicts.append(
                        f"Code entity {entity.type.value} ('{entity.text}') has lower priority ({priority}) "
                        f"than expected in language '{self.language}'"
                    )
        
        if conflicts:
            logger.info(f"Detected {len(conflicts)} potential priority conflicts in language '{self.language}'")
            for conflict in conflicts[:3]:  # Log first 3 conflicts to avoid spam
                logger.debug(conflict)
        
        return conflicts


# Global instances for common languages
_priority_managers: Dict[str, UniversalPriorityManager] = {}


def get_priority_manager(language: str = "en") -> UniversalPriorityManager:
    """
    Get or create a priority manager for the specified language.
    
    This function maintains a cache of priority managers to avoid reloading
    language resources repeatedly.
    
    Args:
        language: Language code (default: 'en')
        
    Returns:
        UniversalPriorityManager instance for the language
    """
    global _priority_managers
    
    if language not in _priority_managers:
        _priority_managers[language] = UniversalPriorityManager(language)
        logger.debug(f"Created new priority manager for language '{language}'")
    
    return _priority_managers[language]


def get_entity_priorities_for_language(language: str = "en") -> Dict[EntityType, int]:
    """
    Convenience function to get entity priorities for a specific language.
    
    Args:
        language: Language code (default: 'en')
        
    Returns:
        Dictionary mapping EntityType to priority values
    """
    return get_priority_manager(language).get_all_priorities()


def clear_priority_manager_cache():
    """
    Clear the cached priority managers.
    
    This is useful for testing or when language resources are updated.
    """
    global _priority_managers
    _priority_managers.clear()
    logger.info("Cleared priority manager cache")