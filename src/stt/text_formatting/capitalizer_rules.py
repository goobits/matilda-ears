#!/usr/bin/env python3
"""Capitalization rules and patterns for the SmartCapitalizer."""
from __future__ import annotations

from .common import EntityType


class CapitalizationRules:
    """Manages capitalization rules, patterns, and constants."""

    def __init__(self, resources: dict, language: str = "en"):
        """Initialize capitalization rules with language-specific resources.
        
        Args:
            resources: Language-specific resource dictionary from constants
            language: Language code (e.g., "en", "es")
        """
        self.resources = resources
        self.language = language
        
        # Entity types that must have their casing preserved under all circumstances
        self.STRICTLY_PROTECTED_TYPES = {
            EntityType.URL,
            EntityType.SPOKEN_URL,
            EntityType.SPOKEN_PROTOCOL_URL,
            EntityType.EMAIL,
            EntityType.SPOKEN_EMAIL,
            EntityType.FILENAME,
            EntityType.INCREMENT_OPERATOR,
            EntityType.DECREMENT_OPERATOR,
            EntityType.SLASH_COMMAND,
            EntityType.COMMAND_FLAG,
            EntityType.SIMPLE_UNDERSCORE_VARIABLE,
            EntityType.UNDERSCORE_DELIMITER,
            EntityType.VARIABLE,  # Single-letter variables must preserve their case (e.g., 'i' in code contexts)
            EntityType.PORT_NUMBER,  # URLs with ports should stay lowercase (e.g., localhost:8080)
            # Note: VERSION removed - version numbers at sentence start should be capitalized
            EntityType.ASSIGNMENT,
            EntityType.COMPARISON,
            EntityType.MATH_EXPRESSION,  # Math expressions should preserve their formatting
            EntityType.MATH_CONSTANT,  # Mathematical constants like π, ∞ should preserve their exact form
            EntityType.ABBREVIATION,  # Latin abbreviations like i.e., e.g. should stay lowercase
            # Note: CLI_COMMAND removed - they should be capitalized at sentence start
        }

        # Version patterns that indicate technical content
        self.version_patterns = {"version", "v.", "v", "build", "release"}

        # Abbreviation patterns and their corrections (only applies mid-sentence)
        self.abbreviation_fixes = {
            # Only fix capitalized abbreviations in mid-sentence contexts
            # At sentence start, they should remain capitalized
            "Vs.": "vs.",  # vs. should not be capitalized mid-sentence
            "Cf.": "cf.",  # cf. should not be capitalized mid-sentence
            "Ie.": "i.e.",  # Fix wrong abbreviation form
            "Eg.": "e.g.",  # Fix wrong abbreviation form  
            "Ex.": "e.g.",  # Convert Ex. to e.g.
        }

        # Load uppercase abbreviations from resources
        self.uppercase_abbreviations = self.resources.get("technical", {}).get("uppercase_abbreviations", {})

        # Load common abbreviations from resources
        self.common_abbreviations = tuple(self.resources.get("technical", {}).get("common_abbreviations", []))

    def is_strictly_protected_type(self, entity_type: EntityType) -> bool:
        """Check if an entity type is strictly protected from capitalization.
        
        Args:
            entity_type: The entity type to check
            
        Returns:
            True if the entity type should never be modified for capitalization
        """
        return entity_type in self.STRICTLY_PROTECTED_TYPES

    def should_protect_entity_from_spacy_capitalization(self, entity_type: EntityType) -> bool:
        """Check if an entity should be protected from SpaCy proper noun capitalization.
        
        Args:
            entity_type: The entity type to check
            
        Returns:
            True if the entity should be protected from SpaCy capitalization
        """
        protected_types = {
            EntityType.URL,
            EntityType.SPOKEN_URL,
            EntityType.SPOKEN_PROTOCOL_URL,
            EntityType.EMAIL,
            EntityType.SPOKEN_EMAIL,
            EntityType.FILENAME,
            EntityType.ASSIGNMENT,
            EntityType.INCREMENT_OPERATOR,
            EntityType.DECREMENT_OPERATOR,
            EntityType.COMMAND_FLAG,
            EntityType.PORT_NUMBER,
            EntityType.ABBREVIATION,  # Protect abbreviations from SpaCy proper noun capitalization
            EntityType.VARIABLE,  # Protect single-letter variables from SpaCy capitalization
        }
        return entity_type in protected_types

    def should_protect_entity_from_uppercase_conversion(self, entity_type: EntityType) -> bool:
        """Check if an entity should be protected from uppercase abbreviation conversion.
        
        Args:
            entity_type: The entity type to check
            
        Returns:
            True if the entity should be protected from uppercase conversion
        """
        protected_types = {
            EntityType.URL,
            EntityType.SPOKEN_URL,
            EntityType.SPOKEN_PROTOCOL_URL,
            EntityType.EMAIL,
            EntityType.SPOKEN_EMAIL,
            EntityType.FILENAME,
            EntityType.ASSIGNMENT,
            EntityType.INCREMENT_OPERATOR,
            EntityType.DECREMENT_OPERATOR,
            EntityType.COMMAND_FLAG,
            EntityType.PORT_NUMBER,
            EntityType.ABBREVIATION,  # Protect abbreviations from uppercase conversion
            EntityType.VARIABLE,  # Protect single-letter variables from uppercase conversion
        }
        return entity_type in protected_types

    def get_technical_verbs(self) -> list[str]:
        """Get list of technical verbs that should not be capitalized as proper nouns.
        
        Returns:
            List of technical verb strings
        """
        return self.resources.get("technical", {}).get("verbs", [])

    def get_common_abbreviations_pattern(self) -> str:
        """Get regex pattern for common abbreviations.
        
        Returns:
            Regex pattern string for matching common abbreviations
        """
        common_abbreviations = self.resources.get("technical", {}).get("common_abbreviations", [])
        return "|".join(abbrev.replace(".", "\\.") for abbrev in common_abbreviations)