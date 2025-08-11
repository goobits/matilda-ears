#!/usr/bin/env python3
"""
Theory 17: Spanish Conversational Flow Preservation

This module implements conversational flow analysis for Spanish technical instructions.
It identifies when Spanish text represents conversational technical commands rather than
formal sentences, and applies appropriate processing that preserves natural conversational
flow while correctly converting technical entities.

Key Problems Addressed:
1. "comprobar si valor mayor que cero" → Convert "cero" to "0" in comparative context
2. "resultado igual a más b" → Process as "resultado = a + b" not "resultado = a_más_b"
3. "archivo guión bajo config" → Natural underscore connection as "archivo_config"
"""

import logging
import re
from typing import List, Dict, Optional, Tuple, Set
from dataclasses import dataclass
from enum import Enum

from .common import Entity, EntityType
from .constants import get_resources

logger = logging.getLogger(__name__)


class ConversationalContext(Enum):
    """Types of conversational contexts for Spanish technical instructions."""
    FORMAL = "formal"                    # Formal documentation or sentences
    CONVERSATIONAL = "conversational"   # Technical conversational instructions  
    COMMAND = "command"                  # Direct command instructions
    COMPARISON = "comparison"            # Mathematical/logical comparisons
    ASSIGNMENT = "assignment"            # Variable assignments
    CONFIGURATION = "configuration"     # Configuration or setup contexts


@dataclass
class ConversationalEntity:
    """Represents an entity detected in conversational context."""
    text: str
    start: int
    end: int
    entity_type: EntityType
    context: ConversationalContext
    conversational_replacement: Optional[str] = None
    preserve_case: bool = False
    preserve_spacing: bool = False


class SpanishConversationalFlowAnalyzer:
    """
    Analyzes Spanish text to identify conversational technical instructions
    and applies context-appropriate entity processing.
    """
    
    def __init__(self, language: str = "es"):
        self.language = language
        if language != "es":
            # Only works for Spanish - fallback for other languages
            self.active = False
            return
            
        self.active = True
        self.resources = get_resources(language)
        self._init_conversational_patterns()
    
    def _init_conversational_patterns(self):
        """Initialize conversational pattern recognition."""
        # Conversational instruction starters
        self.instruction_patterns = [
            r'\b(?:comprobar si|verificar que|asegurarse de que)\b',
            r'\b(?:resultado|valor|variable|archivo|función)\s+(?:igual|es)\b',
            r'\b(?:establecer|configurar|definir)\b',
            r'\b(?:ejecutar|correr|usar)\b',
        ]
        
        # Conversational comparison patterns
        self.comparison_patterns = [
            r'\b(\w+)\s+(?:mayor que|menor que|igual a|diferente de)\s+(\w+)\b',
            r'\bsi\s+(\w+)\s+(?:mayor que|menor que|igual|diferente)\s+(\w+)\b',
        ]
        
        # Conversational assignment patterns  
        self.assignment_patterns = [
            r'\b(\w+)\s+igual\s+(?:a\s+)?(\w+(?:\s+[+\-×÷]\s+\w+)*)\b',
            r'\bresultado\s+igual\s+(?:a\s+)?(.+)\b',
        ]
        
        # Configuration patterns
        self.configuration_patterns = [
            r'\barchivo\s+guión\s+bajo\b',
            r'\bvariable\s+guión\s+bajo\b', 
            r'\bfunción\s+guión\s+bajo\b',
        ]
        
        # Conversational number context patterns
        self.conversational_number_contexts = [
            r'(?:mayor que|menor que|igual a|diferente de)\s+(cero|uno|dos|tres|cuatro|cinco|seis|siete|ocho|nueve|diez)',
            r'(?:si|cuando|mientras)\s+\w+\s+(?:es|sea)\s+(cero|uno|dos|tres|cuatro|cinco|seis|siete|ocho|nueve|diez)',
        ]
        
        # Conversational operator contexts
        self.conversational_operator_contexts = [
            r'(\w+)\s+igual\s+(?:a\s+)?(\w+)\s+(más|menos|por|dividido\s+(?:por|entre))\s+(\w+)',
            r'(\w+)\s+(más|menos|por)\s+(\w+)',
        ]
        
        # Formal sentence indicators (NOT conversational)
        # Note: We need to be careful not to exclude conversational instructions just because
        # they have punctuation added by the pipeline
        self.formal_indicators = [
            r'^\s*(?:La|El|Una|Un|Los|Las)\s+\w+.*[.!?]$',  # Formal article starts
            r'(?:documentación|instrucciones|manual|guía)',  # Documentation context
            r'^[A-Z]\w*\s+(?:es|son|fue|fueron|está|están)\s+.*[.!?]$',  # Formal descriptive sentences
        ]
    
    def is_conversational_instruction(self, text: str) -> bool:
        """
        Determine if text represents a conversational Spanish technical instruction
        rather than formal documentation.
        """
        if not self.active:
            return False
            
        text_clean = text.strip().lower()
        
        # Check for formal indicators first (exclusions)
        for pattern in self.formal_indicators:
            if re.search(pattern, text, re.IGNORECASE):
                logger.debug(f"THEORY_17: Formal indicator found: {pattern}")
                return False
        
        # Check for conversational instruction patterns
        for pattern in self.instruction_patterns:
            if re.search(pattern, text_clean):
                logger.debug(f"THEORY_17: Conversational instruction pattern: {pattern}")
                return True
        
        # Check for conversational assignment patterns
        for pattern in self.assignment_patterns:
            if re.search(pattern, text_clean):
                logger.debug(f"THEORY_17: Conversational assignment pattern: {pattern}")
                return True
        
        # Check for configuration patterns
        for pattern in self.configuration_patterns:
            if re.search(pattern, text_clean):
                logger.debug(f"THEORY_17: Configuration pattern: {pattern}")
                return True
                
        return False
    
    def identify_conversational_context(self, text: str) -> ConversationalContext:
        """Identify the specific type of conversational context."""
        if not self.active:
            return ConversationalContext.FORMAL
            
        text_clean = text.strip().lower()
        
        # Check comparison contexts
        for pattern in self.comparison_patterns:
            if re.search(pattern, text_clean):
                logger.debug(f"THEORY_17: Comparison context detected")
                return ConversationalContext.COMPARISON
        
        # Check assignment contexts
        for pattern in self.assignment_patterns:
            if re.search(pattern, text_clean):
                logger.debug(f"THEORY_17: Assignment context detected")
                return ConversationalContext.ASSIGNMENT
                
        # Check configuration contexts
        for pattern in self.configuration_patterns:
            if re.search(pattern, text_clean):
                logger.debug(f"THEORY_17: Configuration context detected")
                return ConversationalContext.CONFIGURATION
        
        # Default to conversational if we detected it as conversational
        if self.is_conversational_instruction(text):
            return ConversationalContext.CONVERSATIONAL
            
        return ConversationalContext.FORMAL
    
    def identify_conversational_entities(self, text: str) -> List[ConversationalEntity]:
        """
        Identify entities that should be processed with conversational context awareness.
        """
        if not self.active:
            return []
            
        entities = []
        context = self.identify_conversational_context(text)
        
        if context == ConversationalContext.FORMAL:
            return entities
            
        # Find conversational numbers in comparison contexts
        for pattern in self.conversational_number_contexts:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                number_word = match.group(1)
                if number_word in self.resources.get("number_words", {}).get("digit_words", {}):
                    entities.append(ConversationalEntity(
                        text=number_word,
                        start=match.start(1),
                        end=match.end(1),
                        entity_type=EntityType.CARDINAL,
                        context=ConversationalContext.COMPARISON,
                        conversational_replacement=self.resources["number_words"]["digit_words"][number_word]
                    ))
        
        # Find conversational operators in assignment contexts
        for pattern in self.conversational_operator_contexts:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                # Process operator words (más, menos, por, etc.)
                full_match = match.group(0)
                operator_words = ["más", "menos", "por", "igual", "dividido por", "dividido entre"]
                
                for op_word in operator_words:
                    op_pattern = r'\b' + re.escape(op_word) + r'\b'
                    for op_match in re.finditer(op_pattern, full_match, re.IGNORECASE):
                        op_start = match.start() + op_match.start()
                        op_end = match.start() + op_match.end()
                        
                        # Get conversational replacement for operator
                        conversational_replacement = self._get_conversational_operator_replacement(
                            op_word, context
                        )
                        
                        if conversational_replacement:
                            entities.append(ConversationalEntity(
                                text=op_word,
                                start=op_start,
                                end=op_end,
                                entity_type=EntityType.ASSIGNMENT,
                                context=context,
                                conversational_replacement=conversational_replacement,
                                preserve_spacing=True
                            ))
        
        # Find underscore patterns in configuration contexts
        underscore_pattern = r'\bguión\s+bajo\b'
        for match in re.finditer(underscore_pattern, text, re.IGNORECASE):
            entities.append(ConversationalEntity(
                text=match.group(0),
                start=match.start(),
                end=match.end(),
                entity_type=EntityType.UNDERSCORE_DELIMITER,
                context=ConversationalContext.CONFIGURATION,
                conversational_replacement="_",
                preserve_case=True
            ))
        
        logger.debug(f"THEORY_17: Found {len(entities)} conversational entities")
        return entities
    
    def _get_conversational_operator_replacement(self, operator_word: str, context: ConversationalContext) -> Optional[str]:
        """Get the appropriate replacement for an operator in conversational context."""
        conversational_operators = {
            "igual": "=" if context == ConversationalContext.ASSIGNMENT else "==",
            "más": "+",
            "menos": "-", 
            "por": "×",
            "dividido por": "÷",
            "dividido entre": "÷"
        }
        
        return conversational_operators.get(operator_word.lower())
    
    def process_conversational_flow(self, text: str, entities: List[Entity]) -> Tuple[str, List[Entity]]:
        """
        Apply conversational flow processing to preserve natural conversation patterns
        while correctly converting technical entities.
        """
        if not self.active:
            return text, entities
            
        if not self.is_conversational_instruction(text):
            logger.debug("THEORY_17: Not conversational instruction, using standard processing")
            return text, entities
        
        logger.info(f"THEORY_17: Processing conversational flow for: '{text}'")
        
        # Identify conversational entities  
        conversational_entities = self.identify_conversational_entities(text)
        context = self.identify_conversational_context(text)
        
        # Apply conversational processing based on context
        processed_text = text
        processed_entities = entities.copy()
        
        # BUGFIX: Process conversational entities in reverse order (end to start)
        # This prevents position corruption when multiple entities are replaced
        conversational_entities_sorted = sorted(conversational_entities, key=lambda e: e.start, reverse=True)
        
        # Process conversational entities with proper spacing and context
        for conv_entity in conversational_entities_sorted:
            if conv_entity.conversational_replacement:
                # Replace the conversational entity text
                before = processed_text[:conv_entity.start]
                after = processed_text[conv_entity.end:]
                replacement = conv_entity.conversational_replacement
                
                # Apply contextual spacing rules
                if conv_entity.preserve_spacing and context == ConversationalContext.ASSIGNMENT:
                    # For assignments like "resultado igual a más b" → "resultado = a + b"
                    # Ensure proper spacing around operators
                    replacement = f" {replacement} "
                
                processed_text = before + replacement + after
                
                # Update entity positions for the change
                length_change = len(replacement) - len(conv_entity.text)
                
                # Update processed entities that come after this entity
                # (Since we process in reverse order, these are entities that were processed earlier)
                for entity in processed_entities:
                    if entity.start > conv_entity.start:
                        entity.start += length_change
                        entity.end += length_change
        
        logger.debug(f"THEORY_17: Conversational processing result: '{processed_text}'")
        return processed_text, processed_entities
    
    def should_preserve_conversational_capitalization(self, text: str, entity_start: int = 0, original_text: str = None) -> bool:
        """
        Determine if capitalization should be preserved for conversational flow.
        
        In conversational contexts, we often want to preserve lowercase continuations
        rather than applying formal sentence capitalization.
        """
        if not self.active:
            return False
            
        # Use original text for analysis if provided, otherwise use current text
        analysis_text = original_text if original_text else text
        
        # Remove punctuation for analysis if it was added by the pipeline
        if not original_text and text.endswith('.'):
            analysis_text = text.rstrip('.')
            
        if not self.is_conversational_instruction(analysis_text):
            return False
            
        context = self.identify_conversational_context(analysis_text)
        
        # In conversational contexts, preserve natural flow
        if context in [ConversationalContext.CONVERSATIONAL, 
                      ConversationalContext.ASSIGNMENT,
                      ConversationalContext.CONFIGURATION,
                      ConversationalContext.COMPARISON]:
            # Only capitalize at true sentence starts, not entity starts
            return entity_start > 0
            
        return False