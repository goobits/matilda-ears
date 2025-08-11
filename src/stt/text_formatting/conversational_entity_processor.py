#!/usr/bin/env python3
"""
Theory 17: Conversational Entity Processor

This module provides specialized processing for Spanish conversational entities,
handling context-sensitive conversions that preserve natural conversational flow.

Key Features:
1. Context-aware number word conversion ("cero" → "0" in comparison contexts)
2. Operator flow processing ("resultado igual a más b" → "resultado = a + b")
3. Connector preservation with natural spacing ("guión bajo" → "_" appropriately)
4. Conversational capitalization that avoids formal sentence structure
"""

import logging
import re
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass

from .common import Entity, EntityType
from .constants import get_resources
from .spanish_conversational_flow import (
    SpanishConversationalFlowAnalyzer,
    ConversationalContext,
    ConversationalEntity
)

logger = logging.getLogger(__name__)


@dataclass
class ConversationalProcessingResult:
    """Result of conversational entity processing."""
    processed_text: str
    updated_entities: List[Entity]
    conversational_context: ConversationalContext
    changes_applied: int


class ConversationalEntityProcessor:
    """
    Processes entities with conversational context awareness for Spanish.
    
    This processor specializes in handling Spanish technical conversations where
    entities should be converted differently than in formal contexts.
    """
    
    def __init__(self, language: str = "es"):
        self.language = language
        if language != "es":
            self.active = False
            return
            
        self.active = True
        self.resources = get_resources(language)
        self.flow_analyzer = SpanishConversationalFlowAnalyzer(language)
        
        # Load conversational patterns from resources
        self.conversational_patterns = self.resources.get("conversational_patterns", {})
        self.conversational_entities = self.conversational_patterns.get("conversational_entities", {})
        
    def process_conversational_entities(self, text: str, entities: List[Entity]) -> ConversationalProcessingResult:
        """
        Process entities with conversational context awareness.
        
        This is the main entry point that applies Theory 17 conversational processing.
        """
        if not self.active:
            return ConversationalProcessingResult(
                processed_text=text,
                updated_entities=entities,
                conversational_context=ConversationalContext.FORMAL,
                changes_applied=0
            )
            
        logger.info(f"THEORY_17: Processing conversational entities in: '{text}'")
        
        # Check if this is conversational context
        if not self.flow_analyzer.is_conversational_instruction(text):
            logger.debug("THEORY_17: Not conversational context, skipping")
            return ConversationalProcessingResult(
                processed_text=text,
                updated_entities=entities,
                conversational_context=ConversationalContext.FORMAL,
                changes_applied=0
            )
        
        context = self.flow_analyzer.identify_conversational_context(text)
        logger.info(f"THEORY_17: Detected conversational context: {context.value}")
        
        processed_text = text
        updated_entities = entities.copy()
        changes_applied = 0
        
        # Apply context-specific processing
        if context == ConversationalContext.COMPARISON:
            processed_text, updated_entities, changes = self._process_comparison_entities(
                processed_text, updated_entities
            )
            changes_applied += changes
            
        elif context == ConversationalContext.ASSIGNMENT:
            processed_text, updated_entities, changes = self._process_assignment_entities(
                processed_text, updated_entities
            )
            changes_applied += changes
            
        elif context == ConversationalContext.CONFIGURATION:
            processed_text, updated_entities, changes = self._process_configuration_entities(
                processed_text, updated_entities
            )
            changes_applied += changes
        
        # Apply general conversational processing
        processed_text, updated_entities, general_changes = self._apply_general_conversational_rules(
            processed_text, updated_entities, context
        )
        changes_applied += general_changes
        
        logger.info(f"THEORY_17: Applied {changes_applied} conversational changes")
        logger.debug(f"THEORY_17: Result: '{processed_text}'")
        
        return ConversationalProcessingResult(
            processed_text=processed_text,
            updated_entities=updated_entities,
            conversational_context=context,
            changes_applied=changes_applied
        )
    
    def _process_comparison_entities(self, text: str, entities: List[Entity]) -> Tuple[str, List[Entity], int]:
        """
        Process entities in comparison contexts.
        
        Key case: "comprobar si valor mayor que cero" → "comprobar si valor mayor que 0"
        """
        processed_text = text
        changes = 0
        
        # Find number words in comparison contexts
        comparison_number_patterns = [
            r'(mayor que|menor que|igual a|diferente de)\s+(cero|uno|dos|tres|cuatro|cinco|seis|siete|ocho|nueve|diez)',
            r'(si|cuando|mientras)\s+\w+\s+(mayor que|menor que|igual a|es)\s+(cero|uno|dos|tres|cuatro|cinco|seis|siete|ocho|nueve|diez)'
        ]
        
        numbers_in_context = self.conversational_entities.get("numbers_in_context", {})
        
        for pattern in comparison_number_patterns:
            for match in re.finditer(pattern, processed_text, re.IGNORECASE):
                number_word = match.group(-1)  # Last group is always the number word
                if number_word.lower() in numbers_in_context:
                    number_replacement = numbers_in_context[number_word.lower()]
                    
                    # Replace the number word with its numeric form
                    start_pos = match.start(match.lastindex)  # Start of last group
                    end_pos = match.end(match.lastindex)      # End of last group
                    
                    processed_text = (processed_text[:start_pos] + 
                                    number_replacement + 
                                    processed_text[end_pos:])
                    
                    changes += 1
                    logger.debug(f"THEORY_17: Converted comparison number '{number_word}' → '{number_replacement}'")
                    
                    # Update entity positions
                    length_diff = len(number_replacement) - len(number_word)
                    for entity in entities:
                        if entity.start > end_pos:
                            entity.start += length_diff
                            entity.end += length_diff
        
        return processed_text, entities, changes
    
    def _process_assignment_entities(self, text: str, entities: List[Entity]) -> Tuple[str, List[Entity], int]:
        """
        Process entities in assignment contexts.
        
        Key case: "resultado igual a más b" → "resultado = a + b"
        """
        processed_text = text
        changes = 0
        
        operators_in_context = self.conversational_entities.get("operators_in_context", {})
        
        # Pattern for assignment operators with proper spacing
        assignment_patterns = [
            r'(\w+)\s+(igual(?:\s+a)?)\s+(\w+(?:\s+(?:más|menos|por|dividido\s+(?:por|entre))\s+\w+)*)',
            r'(resultado|valor|total)\s+(igual(?:\s+a)?)\s+(.+)'
        ]
        
        for pattern in assignment_patterns:
            for match in re.finditer(pattern, processed_text, re.IGNORECASE):
                full_expression = match.group(0)
                
                # Process the assignment operator
                igual_part = match.group(2)
                if "igual" in igual_part.lower():
                    # Replace "igual" or "igual a" with "="
                    processed_expression = full_expression.replace(igual_part, " = ")
                    
                    # Now process any math operators in the expression
                    for op_spanish, op_symbol in operators_in_context.items():
                        if op_spanish in ["más", "menos", "por", "dividido por", "dividido entre"]:
                            # Add proper spacing around operators
                            op_pattern = r'\b' + re.escape(op_spanish) + r'\b'
                            processed_expression = re.sub(
                                op_pattern, 
                                f' {op_symbol} ', 
                                processed_expression, 
                                flags=re.IGNORECASE
                            )
                    
                    # Replace in the original text
                    processed_text = processed_text.replace(full_expression, processed_expression)
                    changes += 1
                    logger.debug(f"THEORY_17: Converted assignment '{full_expression}' → '{processed_expression}'")
                    
                    # Update entity positions
                    length_diff = len(processed_expression) - len(full_expression)
                    for entity in entities:
                        if entity.start > match.end():
                            entity.start += length_diff
                            entity.end += length_diff
                    
                    break  # Process one match at a time to avoid conflicts
        
        return processed_text, entities, changes
    
    def _process_configuration_entities(self, text: str, entities: List[Entity]) -> Tuple[str, List[Entity], int]:
        """
        Process entities in configuration contexts.
        
        Key case: "archivo guión bajo configuración guión bajo principal" → "archivo_configuración_principal"
        """
        processed_text = text
        changes = 0
        
        # Handle underscore connectors in configuration contexts
        underscore_pattern = r'\bguión\s+bajo\b'
        
        for match in re.finditer(underscore_pattern, processed_text, re.IGNORECASE):
            # In conversational context, replace with underscore
            processed_text = (processed_text[:match.start()] + 
                            "_" + 
                            processed_text[match.end():])
            
            changes += 1
            logger.debug(f"THEORY_17: Converted underscore connector '{match.group()}' → '_'")
            
            # Update entity positions
            length_diff = 1 - len(match.group())  # "_" vs "guión bajo"
            for entity in entities:
                if entity.start > match.end():
                    entity.start += length_diff
                    entity.end += length_diff
        
        return processed_text, entities, changes
    
    def _apply_general_conversational_rules(self, text: str, entities: List[Entity], 
                                           context: ConversationalContext) -> Tuple[str, List[Entity], int]:
        """Apply general conversational processing rules."""
        processed_text = text
        changes = 0
        
        # Apply flow preservation rules
        flow_rules = self.conversational_patterns.get("flow_preservation_rules", {})
        
        if flow_rules.get("preserve_natural_spacing", False):
            # Clean up any double spaces that might have been created
            original_text = processed_text
            processed_text = re.sub(r'\s+', ' ', processed_text).strip()
            if processed_text != original_text:
                changes += 1
                logger.debug("THEORY_17: Applied natural spacing cleanup")
        
        return processed_text, entities, changes
    
    def should_preserve_conversational_case(self, text: str, position: int = 0) -> bool:
        """
        Determine if conversational case should be preserved at a specific position.
        
        This is used by the capitalization step to avoid formal sentence capitalization
        in conversational contexts.
        """
        if not self.active:
            return False
            
        return self.flow_analyzer.should_preserve_conversational_capitalization(text, position)