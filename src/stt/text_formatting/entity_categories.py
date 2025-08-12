"""
Simplified entity type hierarchy with logical categories.

This module provides a cleaner organization of entity types into logical
categories, making it easier for AI agents and developers to understand
entity relationships.
"""

from enum import Enum, auto
from typing import Dict, Set, List, Optional
from stt.text_formatting.common import EntityType


class EntityCategory(Enum):
    """High-level categories for entity types."""
    NUMERIC = auto()      # All number-related entities
    WEB = auto()          # URLs, emails, protocols
    CODE = auto()         # Programming-related entities  
    TEXT = auto()         # Natural language entities
    TEMPORAL = auto()     # Time and date entities
    FINANCIAL = auto()    # Currency and money entities
    MEASUREMENT = auto()  # Units and quantities
    OPERATOR = auto()     # Mathematical and programming operators


class EntityHierarchy:
    """
    Provides a simplified view of entity type relationships.
    
    This class maps the 70+ EntityType values to logical categories,
    making it easier to understand and work with entity types.
    """
    
    def __init__(self):
        """Initialize the entity hierarchy mappings."""
        self._category_map = self._build_category_map()
        self._subcategory_map = self._build_subcategory_map()
        
    def _build_category_map(self) -> Dict[EntityType, EntityCategory]:
        """Build mapping from entity types to categories."""
        return {
            # NUMERIC category
            EntityType.CARDINAL: EntityCategory.NUMERIC,
            EntityType.ORDINAL: EntityCategory.NUMERIC,
            EntityType.FRACTION: EntityCategory.NUMERIC,
            EntityType.NUMERIC_RANGE: EntityCategory.NUMERIC,
            EntityType.PERCENT: EntityCategory.NUMERIC,
            EntityType.SCIENTIFIC_NOTATION: EntityCategory.NUMERIC,
            EntityType.CONSECUTIVE_DIGITS: EntityCategory.NUMERIC,
            
            # WEB category
            EntityType.URL: EntityCategory.WEB,
            EntityType.SPOKEN_URL: EntityCategory.WEB,
            EntityType.SPOKEN_PROTOCOL_URL: EntityCategory.WEB,
            EntityType.EMAIL: EntityCategory.WEB,
            EntityType.SPOKEN_EMAIL: EntityCategory.WEB,
            EntityType.PROTOCOL: EntityCategory.WEB,
            EntityType.PORT_NUMBER: EntityCategory.WEB,
            
            # CODE category
            EntityType.FILENAME: EntityCategory.CODE,
            EntityType.UNIX_PATH: EntityCategory.CODE,
            EntityType.WINDOWS_PATH: EntityCategory.CODE,
            EntityType.COMMAND_FLAG: EntityCategory.CODE,
            EntityType.SLASH_COMMAND: EntityCategory.CODE,
            EntityType.CLI_COMMAND: EntityCategory.CODE,
            EntityType.PROGRAMMING_KEYWORD: EntityCategory.CODE,
            EntityType.UNDERSCORE_DELIMITER: EntityCategory.CODE,
            EntityType.SIMPLE_UNDERSCORE_VARIABLE: EntityCategory.CODE,
            EntityType.VERSION: EntityCategory.CODE,
            
            # TEXT category
            EntityType.ABBREVIATION: EntityCategory.TEXT,
            EntityType.SPOKEN_EMOJI: EntityCategory.TEXT,
            EntityType.SPOKEN_LETTER: EntityCategory.TEXT,
            EntityType.LETTER_SEQUENCE: EntityCategory.TEXT,
            EntityType.MUSIC_NOTATION: EntityCategory.TEXT,
            
            # TEMPORAL category
            EntityType.DATE: EntityCategory.TEMPORAL,
            EntityType.TIME: EntityCategory.TEMPORAL,
            EntityType.TIME_CONTEXT: EntityCategory.TEMPORAL,
            EntityType.TIME_AMPM: EntityCategory.TEMPORAL,
            EntityType.TIME_RELATIVE: EntityCategory.TEMPORAL,
            EntityType.TIME_DURATION: EntityCategory.TEMPORAL,
            
            # FINANCIAL category
            EntityType.CURRENCY: EntityCategory.FINANCIAL,
            EntityType.MONEY: EntityCategory.FINANCIAL,
            EntityType.CENTS: EntityCategory.FINANCIAL,
            EntityType.DOLLAR_CENTS: EntityCategory.FINANCIAL,
            EntityType.EURO_CENTS: EntityCategory.FINANCIAL,
            EntityType.POUND_PENCE: EntityCategory.FINANCIAL,
            EntityType.DOLLARS: EntityCategory.FINANCIAL,
            EntityType.POUNDS: EntityCategory.FINANCIAL,
            EntityType.EUROS: EntityCategory.FINANCIAL,
            
            # MEASUREMENT category
            EntityType.QUANTITY: EntityCategory.MEASUREMENT,
            EntityType.TEMPERATURE: EntityCategory.MEASUREMENT,
            EntityType.METRIC_LENGTH: EntityCategory.MEASUREMENT,
            EntityType.METRIC_WEIGHT: EntityCategory.MEASUREMENT,
            EntityType.METRIC_VOLUME: EntityCategory.MEASUREMENT,
            EntityType.DATA_SIZE: EntityCategory.MEASUREMENT,
            EntityType.FREQUENCY: EntityCategory.MEASUREMENT,
            EntityType.PHONE_LONG: EntityCategory.MEASUREMENT,
            
            # OPERATOR category
            EntityType.ASSIGNMENT: EntityCategory.OPERATOR,
            EntityType.COMPARISON: EntityCategory.OPERATOR,
            EntityType.INCREMENT_OPERATOR: EntityCategory.OPERATOR,
            EntityType.DECREMENT_OPERATOR: EntityCategory.OPERATOR,
            EntityType.MATH: EntityCategory.OPERATOR,
            EntityType.MATH_EXPRESSION: EntityCategory.OPERATOR,
            EntityType.PHYSICS_SQUARED: EntityCategory.OPERATOR,
            EntityType.PHYSICS_TIMES: EntityCategory.OPERATOR,
            EntityType.ROOT_EXPRESSION: EntityCategory.OPERATOR,
            EntityType.MATH_CONSTANT: EntityCategory.OPERATOR,
        }
        
    def _build_subcategory_map(self) -> Dict[str, Set[EntityType]]:
        """Build subcategory groupings for finer granularity."""
        return {
            # Numeric subcategories
            "basic_numbers": {
                EntityType.CARDINAL, 
                EntityType.ORDINAL,
                EntityType.FRACTION,
                EntityType.NUMERIC_RANGE,
            },
            "percentage_numbers": {
                EntityType.PERCENT,
            },
            "scientific_numbers": {
                EntityType.SCIENTIFIC_NOTATION,
                EntityType.ROOT_EXPRESSION,
            },
            
            # Web subcategories
            "web_addresses": {
                EntityType.URL,
                EntityType.SPOKEN_URL,
                EntityType.SPOKEN_PROTOCOL_URL,
                EntityType.PROTOCOL,
                EntityType.PORT_NUMBER,
            },
            "email_addresses": {
                EntityType.EMAIL,
                EntityType.SPOKEN_EMAIL,
            },
            
            # Code subcategories
            "file_paths": {
                EntityType.FILENAME,
                EntityType.UNIX_PATH, 
                EntityType.WINDOWS_PATH,
            },
            "command_elements": {
                EntityType.COMMAND_FLAG,
                EntityType.SLASH_COMMAND,
                EntityType.CLI_COMMAND,
            },
            "code_elements": {
                EntityType.PROGRAMMING_KEYWORD,
                EntityType.UNDERSCORE_DELIMITER,
                EntityType.SIMPLE_UNDERSCORE_VARIABLE,
                EntityType.VERSION,
            },
            
            # Financial subcategories
            "currency_symbols": {
                EntityType.CURRENCY,
                EntityType.DOLLARS,
                EntityType.POUNDS,
                EntityType.EUROS,
            },
            "money_amounts": {
                EntityType.MONEY,
                EntityType.CENTS,
                EntityType.DOLLAR_CENTS,
                EntityType.EURO_CENTS,
                EntityType.POUND_PENCE,
            },
            
            # Measurement subcategories
            "metric_units": {
                EntityType.METRIC_LENGTH,
                EntityType.METRIC_WEIGHT,
                EntityType.METRIC_VOLUME,
            },
            "data_units": {
                EntityType.DATA_SIZE,
                EntityType.FREQUENCY,
            },
            "other_quantities": {
                EntityType.QUANTITY,
                EntityType.TEMPERATURE,
                EntityType.PHONE_LONG,
            },
            
            # Operator subcategories
            "assignment_operators": {
                EntityType.ASSIGNMENT,
                EntityType.INCREMENT_OPERATOR,
                EntityType.DECREMENT_OPERATOR,
            },
            "comparison_operators": {
                EntityType.COMPARISON,
            },
            "math_operators": {
                EntityType.MATH,
                EntityType.MATH_EXPRESSION,
                EntityType.PHYSICS_SQUARED,
                EntityType.PHYSICS_TIMES,
                EntityType.ROOT_EXPRESSION,
                EntityType.MATH_CONSTANT,
            },
        }
    
    def get_category(self, entity_type: EntityType) -> EntityCategory:
        """Get the category for an entity type."""
        return self._category_map.get(entity_type, EntityCategory.TEXT)
        
    def get_entities_in_category(self, category: EntityCategory) -> Set[EntityType]:
        """Get all entity types in a category."""
        return {et for et, cat in self._category_map.items() if cat == category}
        
    def get_subcategory(self, entity_type: EntityType) -> Optional[str]:
        """Get the subcategory name for an entity type."""
        for subcategory, entities in self._subcategory_map.items():
            if entity_type in entities:
                return subcategory
        return None
        
    def get_related_entities(self, entity_type: EntityType) -> Set[EntityType]:
        """Get entity types that are related (same subcategory)."""
        subcategory = self.get_subcategory(entity_type)
        if subcategory:
            return self._subcategory_map[subcategory] - {entity_type}
        
        # Fall back to category-level relations
        category = self.get_category(entity_type)
        return self.get_entities_in_category(category) - {entity_type}
        
    def is_numeric_entity(self, entity_type: EntityType) -> bool:
        """Check if entity type is numeric."""
        return self.get_category(entity_type) == EntityCategory.NUMERIC
        
    def is_web_entity(self, entity_type: EntityType) -> bool:
        """Check if entity type is web-related."""
        return self.get_category(entity_type) == EntityCategory.WEB
        
    def is_code_entity(self, entity_type: EntityType) -> bool:
        """Check if entity type is code-related."""
        return self.get_category(entity_type) == EntityCategory.CODE
        
    def get_category_stats(self) -> Dict[EntityCategory, int]:
        """Get count of entity types per category."""
        stats = {}
        for category in EntityCategory:
            stats[category] = len(self.get_entities_in_category(category))
        return stats
        
    def get_hierarchy_summary(self) -> str:
        """Get a human-readable summary of the entity hierarchy."""
        lines = ["Entity Type Hierarchy Summary", "=" * 40]
        
        for category in EntityCategory:
            entities = self.get_entities_in_category(category)
            lines.append(f"\n{category.name} ({len(entities)} types):")
            
            # Group by subcategory
            subcategory_entities = {}
            uncategorized = set()
            
            for entity in entities:
                subcategory = self.get_subcategory(entity)
                if subcategory:
                    if subcategory not in subcategory_entities:
                        subcategory_entities[subcategory] = []
                    subcategory_entities[subcategory].append(entity)
                else:
                    uncategorized.add(entity)
                    
            # Print subcategories
            for subcategory, entity_list in sorted(subcategory_entities.items()):
                lines.append(f"  {subcategory}:")
                for entity in sorted(entity_list, key=lambda e: e.name):
                    lines.append(f"    - {entity.name}")
                    
            # Print uncategorized
            if uncategorized:
                lines.append("  other:")
                for entity in sorted(uncategorized, key=lambda e: e.name):
                    lines.append(f"    - {entity.name}")
                    
        return "\n".join(lines)


# Singleton instance
_hierarchy = None

def get_entity_hierarchy() -> EntityHierarchy:
    """Get the singleton entity hierarchy instance."""
    global _hierarchy
    if _hierarchy is None:
        _hierarchy = EntityHierarchy()
    return _hierarchy


# Convenience functions
def get_entity_category(entity_type: EntityType) -> EntityCategory:
    """Get the category for an entity type."""
    return get_entity_hierarchy().get_category(entity_type)
    
    
def is_same_category(entity1: EntityType, entity2: EntityType) -> bool:
    """Check if two entity types are in the same category."""
    hierarchy = get_entity_hierarchy()
    return hierarchy.get_category(entity1) == hierarchy.get_category(entity2)
    

def get_entities_by_category(category: EntityCategory) -> Set[EntityType]:
    """Get all entity types in a specific category."""
    return get_entity_hierarchy().get_entities_in_category(category)