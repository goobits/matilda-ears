#!/usr/bin/env python3
"""
Spanish Technical Context Pattern Recognition System

THEORY 20: Spanish Technical Context Pattern Recognition

This module implements pattern-based recognition of Spanish technical instruction 
contexts to improve entity handling and capitalization decisions. The focus is on
identifying when Spanish text contains technical instructions that should be
formatted differently from conversational Spanish.

Core Functions:
1. Recognize Spanish technical instruction patterns
2. Identify programming/command contexts in Spanish speech
3. Apply context-appropriate formatting rules
4. Coordinate with existing Spanish processing systems

Technical Patterns Addressed:
- Programming instructions: "ejecutar el comando git", "escribir la función"
- File operations: "abrir el archivo", "guardar como"
- Code explanations: "esta función hace", "el parámetro es"
- Technical procedures: "instalar la dependencia", "configurar el puerto"
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple, Set
from dataclasses import dataclass, field
from enum import Enum

from .constants import get_resources
from .common import Entity, EntityType
from ..core.config import setup_logging

logger = setup_logging(__name__)


class TechnicalContextType(Enum):
    """Types of technical contexts in Spanish speech"""
    COMMAND_INSTRUCTION = "command_instruction"      # "ejecutar el comando"
    FILE_OPERATION = "file_operation"               # "abrir el archivo"
    CODE_EXPLANATION = "code_explanation"           # "esta función hace"
    CONFIGURATION = "configuration"                 # "configurar el puerto"
    PROGRAMMING_TASK = "programming_task"           # "escribir una función"
    TECHNICAL_PROCEDURE = "technical_procedure"     # "instalar la dependencia"
    DEBUG_CONTEXT = "debug_context"                # "el error dice que"
    SYSTEM_OPERATION = "system_operation"          # "reiniciar el servidor"


@dataclass
class TechnicalPattern:
    """Represents a Spanish technical pattern"""
    pattern_type: TechnicalContextType
    trigger_words: List[str]
    pattern_regex: re.Pattern[str]
    context_indicators: List[str]
    priority: int = 50  # Higher number = higher priority
    capitalization_rule: str = "preserve_technical"  # "preserve_technical", "force_lowercase", "standard"
    entity_handling: str = "technical_mode"  # "technical_mode", "conversational_mode", "mixed"


@dataclass 
class SpanishTechnicalContext:
    """Context information for Spanish technical instruction"""
    context_type: TechnicalContextType
    confidence: float  # 0.0 to 1.0
    start_pos: int
    end_pos: int
    triggered_by: str  # The specific pattern that triggered this context
    technical_entities: List[Entity] = field(default_factory=list)
    formatting_hints: Dict[str, str] = field(default_factory=dict)
    should_preserve_case: bool = True
    should_use_technical_spacing: bool = True


class SpanishTechnicalPatternRecognizer:
    """
    THEORY 20: Spanish Technical Context Pattern Recognition
    
    Recognizes Spanish technical instruction patterns and provides context-aware
    formatting guidance for better handling of Spanish technical speech.
    
    Core Strategy:
    1. Pattern-based recognition of Spanish technical contexts
    2. Context-sensitive entity processing decisions
    3. Capitalization rules based on technical vs conversational context
    4. Integration with existing Spanish processing pipeline
    """
    
    def __init__(self, language: str = "es"):
        self.language = language
        self.resources = get_resources(language)
        
        # Initialize technical patterns
        self.patterns: List[TechnicalPattern] = []
        self._initialize_technical_patterns()
        
        # Context tracking
        self.active_contexts: List[SpanishTechnicalContext] = []
        self.pattern_cache: Dict[str, List[SpanishTechnicalContext]] = {}
        
    def _initialize_technical_patterns(self):
        """Initialize Spanish technical instruction patterns"""
        
        # Pattern 1: Command Execution Contexts
        # "ejecutar el comando", "correr el script", "lanzar la aplicación"
        command_words = ["ejecutar", "correr", "lanzar", "arrancar", "iniciar", "parar", "detener"]
        command_targets = ["comando", "script", "aplicación", "programa", "servicio", "proceso"]
        
        command_pattern = self._build_pattern(
            command_words, command_targets,
            optional_articles=["el", "la", "los", "las", "un", "una"],
            pattern_type=TechnicalContextType.COMMAND_INSTRUCTION
        )
        
        # Pattern 2: File Operations
        # "abrir el archivo", "guardar como", "crear un directorio"
        file_verbs = ["abrir", "cerrar", "guardar", "crear", "eliminar", "borrar", "copiar", "mover"]
        file_objects = ["archivo", "fichero", "documento", "directorio", "carpeta", "folder"]
        
        file_pattern = self._build_pattern(
            file_verbs, file_objects,
            optional_articles=["el", "la", "un", "una"],
            pattern_type=TechnicalContextType.FILE_OPERATION
        )
        
        # Pattern 3: Code Explanation Contexts  
        # "esta función hace", "el parámetro es", "la variable contiene"
        explanation_starters = ["esta", "este", "esa", "ese", "la", "el"]
        code_objects = ["función", "método", "clase", "variable", "parámetro", "objeto", "array", "lista"]
        explanation_verbs = ["hace", "es", "contiene", "representa", "devuelve", "recibe", "ejecuta"]
        
        explanation_pattern = r'\b(?:' + '|'.join(explanation_starters) + r')\s+(?:' + '|'.join(code_objects) + r')\s+(?:' + '|'.join(explanation_verbs) + r')\b'
        
        # Pattern 4: Configuration Contexts
        # "configurar el puerto", "establecer la variable", "definir el valor"
        config_verbs = ["configurar", "establecer", "definir", "asignar", "cambiar", "modificar"]
        config_objects = ["puerto", "variable", "valor", "parámetro", "configuración", "opción", "ajuste"]
        
        config_pattern = self._build_pattern(
            config_verbs, config_objects,
            optional_articles=["el", "la", "un", "una"],
            pattern_type=TechnicalContextType.CONFIGURATION
        )
        
        # Pattern 5: Programming Task Contexts
        # "escribir una función", "implementar el método", "desarrollar la clase"
        programming_verbs = ["escribir", "implementar", "desarrollar", "codificar", "programar", "crear"]
        programming_objects = ["función", "método", "clase", "módulo", "componente", "interfaz", "api"]
        
        programming_pattern = self._build_pattern(
            programming_verbs, programming_objects,
            optional_articles=["una", "un", "el", "la"],
            pattern_type=TechnicalContextType.PROGRAMMING_TASK
        )
        
        # Pattern 6: Technical Procedure Contexts
        # "instalar la dependencia", "actualizar el paquete", "compilar el proyecto"
        procedure_verbs = ["instalar", "actualizar", "compilar", "construir", "desplegar", "publicar"]
        procedure_objects = ["dependencia", "paquete", "proyecto", "aplicación", "biblioteca", "librería"]
        
        procedure_pattern = self._build_pattern(
            procedure_verbs, procedure_objects,
            optional_articles=["la", "el", "las", "los"],
            pattern_type=TechnicalContextType.TECHNICAL_PROCEDURE
        )
        
        # Pattern 7: Debug and Error Contexts
        # "el error dice que", "la excepción indica", "falló porque"
        debug_subjects = ["error", "excepción", "fallo", "problema", "bug", "issue"]
        debug_verbs = ["dice", "indica", "muestra", "reporta", "señala", "sugiere"]
        
        debug_pattern = r'\b(?:el|la)\s+(?:' + '|'.join(debug_subjects) + r')\s+(?:' + '|'.join(debug_verbs) + r')\s+(?:que|el|la)?\b'
        
        # Pattern 8: System Operation Contexts
        # "reiniciar el servidor", "conectar a la base de datos"
        system_verbs = ["reiniciar", "conectar", "desconectar", "monitorear", "supervisar"]
        system_objects = ["servidor", "base", "datos", "red", "sistema", "servicio"]
        
        system_pattern = self._build_pattern(
            system_verbs, system_objects,
            optional_articles=["el", "la", "los", "las"],
            pattern_type=TechnicalContextType.SYSTEM_OPERATION,
            additional_words=["de", "a"]  # for "base de datos", "conectar a la"
        )
        
        # Compile and store patterns
        patterns_data = [
            (TechnicalContextType.COMMAND_INSTRUCTION, command_pattern, command_words + command_targets, 90),
            (TechnicalContextType.FILE_OPERATION, file_pattern, file_verbs + file_objects, 85),
            (TechnicalContextType.CODE_EXPLANATION, explanation_pattern, explanation_starters + code_objects, 80),
            (TechnicalContextType.CONFIGURATION, config_pattern, config_verbs + config_objects, 75),
            (TechnicalContextType.PROGRAMMING_TASK, programming_pattern, programming_verbs + programming_objects, 85),
            (TechnicalContextType.TECHNICAL_PROCEDURE, procedure_pattern, procedure_verbs + procedure_objects, 80),
            (TechnicalContextType.DEBUG_CONTEXT, debug_pattern, debug_subjects + debug_verbs, 70),
            (TechnicalContextType.SYSTEM_OPERATION, system_pattern, system_verbs + system_objects, 75)
        ]
        
        for pattern_type, regex_pattern, trigger_words, priority in patterns_data:
            try:
                compiled_pattern = re.compile(regex_pattern, re.IGNORECASE | re.UNICODE)
                technical_pattern = TechnicalPattern(
                    pattern_type=pattern_type,
                    trigger_words=trigger_words,
                    pattern_regex=compiled_pattern,
                    context_indicators=[],
                    priority=priority,
                    capitalization_rule=self._get_capitalization_rule_for_type(pattern_type),
                    entity_handling=self._get_entity_handling_for_type(pattern_type)
                )
                self.patterns.append(technical_pattern)
                logger.debug(f"Initialized pattern {pattern_type.value} with priority {priority}")
            except re.error as e:
                logger.warning(f"Failed to compile pattern for {pattern_type.value}: {e}")
    
    def _build_pattern(self, verbs: List[str], objects: List[str], 
                      optional_articles: List[str] = None,
                      pattern_type: TechnicalContextType = None,
                      additional_words: List[str] = None) -> str:
        """Build regex pattern from verbs and objects with optional articles"""
        
        if optional_articles:
            article_part = r'(?:' + '|'.join(optional_articles) + r')\s+'
        else:
            article_part = r''
            
        additional_part = ''
        if additional_words:
            additional_part = r'(?:\s+(?:' + '|'.join(additional_words) + r'))?'
            
        # Create pattern: verb + [article] + object + [additional words]
        pattern = (
            r'\b(?:' + '|'.join(verbs) + r')\s+' +
            article_part +
            r'(?:' + '|'.join(objects) + r')' +
            additional_part + r'\b'
        )
        
        return pattern
    
    def _get_capitalization_rule_for_type(self, context_type: TechnicalContextType) -> str:
        """Get capitalization rule for context type"""
        rules = {
            TechnicalContextType.COMMAND_INSTRUCTION: "preserve_technical",
            TechnicalContextType.FILE_OPERATION: "preserve_technical", 
            TechnicalContextType.CODE_EXPLANATION: "standard",
            TechnicalContextType.CONFIGURATION: "preserve_technical",
            TechnicalContextType.PROGRAMMING_TASK: "standard",
            TechnicalContextType.TECHNICAL_PROCEDURE: "preserve_technical",
            TechnicalContextType.DEBUG_CONTEXT: "standard",
            TechnicalContextType.SYSTEM_OPERATION: "preserve_technical"
        }
        return rules.get(context_type, "standard")
    
    def _get_entity_handling_for_type(self, context_type: TechnicalContextType) -> str:
        """Get entity handling mode for context type"""
        modes = {
            TechnicalContextType.COMMAND_INSTRUCTION: "technical_mode",
            TechnicalContextType.FILE_OPERATION: "technical_mode",
            TechnicalContextType.CODE_EXPLANATION: "mixed",
            TechnicalContextType.CONFIGURATION: "technical_mode", 
            TechnicalContextType.PROGRAMMING_TASK: "mixed",
            TechnicalContextType.TECHNICAL_PROCEDURE: "technical_mode",
            TechnicalContextType.DEBUG_CONTEXT: "mixed",
            TechnicalContextType.SYSTEM_OPERATION: "technical_mode"
        }
        return modes.get(context_type, "conversational_mode")
    
    def analyze_spanish_technical_context(self, text: str, entities: List[Entity] = None) -> List[SpanishTechnicalContext]:
        """
        Analyze text for Spanish technical instruction patterns.
        
        Args:
            text: Spanish text to analyze
            entities: Optional list of detected entities
            
        Returns:
            List of detected technical contexts with formatting guidance
        """
        if not text.strip():
            return []
            
        logger.debug(f"THEORY_20: Analyzing Spanish technical context for: '{text[:50]}...'")
        
        # Check cache first
        cache_key = hash(text)
        if cache_key in self.pattern_cache:
            logger.debug("THEORY_20: Using cached technical context analysis")
            return self.pattern_cache[cache_key]
        
        contexts = []
        
        # Apply each pattern
        for pattern in sorted(self.patterns, key=lambda p: p.priority, reverse=True):
            matches = list(pattern.pattern_regex.finditer(text))
            
            for match in matches:
                start, end = match.span()
                matched_text = match.group()
                
                # Calculate confidence based on pattern specificity and context
                confidence = self._calculate_pattern_confidence(
                    pattern, matched_text, text, start, end, entities
                )
                
                if confidence >= 0.6:  # Minimum confidence threshold
                    context = SpanishTechnicalContext(
                        context_type=pattern.pattern_type,
                        confidence=confidence,
                        start_pos=start,
                        end_pos=end,
                        triggered_by=matched_text,
                        should_preserve_case=(pattern.capitalization_rule == "preserve_technical"),
                        should_use_technical_spacing=True
                    )
                    
                    # Add formatting hints based on pattern type
                    context.formatting_hints = self._get_formatting_hints(pattern, matched_text, text)
                    
                    # Identify related technical entities
                    if entities:
                        context.technical_entities = self._find_related_technical_entities(
                            start, end, entities, pattern.pattern_type
                        )
                    
                    contexts.append(context)
                    logger.debug(f"THEORY_20: Found {pattern.pattern_type.value} context at {start}-{end} (confidence: {confidence:.2f})")
        
        # Remove overlapping contexts (keep highest confidence)
        contexts = self._resolve_overlapping_contexts(contexts)
        
        # Cache results
        self.pattern_cache[cache_key] = contexts
        
        logger.debug(f"THEORY_20: Found {len(contexts)} technical contexts")
        return contexts
    
    def _calculate_pattern_confidence(self, pattern: TechnicalPattern, matched_text: str,
                                    full_text: str, start: int, end: int,
                                    entities: List[Entity] = None) -> float:
        """Calculate confidence score for a pattern match"""
        
        confidence = 0.7  # Base confidence
        
        # Factor 1: Pattern priority (normalized)
        priority_factor = pattern.priority / 100.0
        confidence += priority_factor * 0.2
        
        # Factor 2: Context reinforcement
        # Look for additional technical terms around the match
        context_window = 50
        context_start = max(0, start - context_window)
        context_end = min(len(full_text), end + context_window)
        context_text = full_text[context_start:context_end].lower()
        
        # Technical context words that increase confidence
        technical_indicators = [
            "código", "función", "método", "clase", "variable", "parámetro",
            "api", "servidor", "base", "datos", "aplicación", "sistema",
            "git", "npm", "python", "javascript", "java", "docker",
            "puerto", "url", "http", "https", "json", "xml", "html",
            "error", "excepción", "debug", "log", "consola", "terminal"
        ]
        
        technical_count = sum(1 for indicator in technical_indicators if indicator in context_text)
        if technical_count > 0:
            confidence += min(0.15, technical_count * 0.05)
            
        # Factor 3: Entity presence reinforcement
        if entities:
            technical_entity_types = {
                EntityType.CLI_COMMAND, EntityType.FILENAME, EntityType.URL,
                EntityType.COMMAND_FLAG, EntityType.VARIABLE, EntityType.PORT_NUMBER
            }
            
            nearby_technical_entities = [
                e for e in entities 
                if e.type in technical_entity_types and 
                abs(e.start - start) <= context_window
            ]
            
            if nearby_technical_entities:
                confidence += min(0.1, len(nearby_technical_entities) * 0.03)
                
        # Factor 4: Position in sentence (technical instructions often start sentences)
        if start <= 10 or (start > 0 and full_text[start-1:start+1] in ['. ', '! ', '? ']):
            confidence += 0.05
            
        # Factor 5: Sentence structure (imperative vs descriptive)
        # Imperative technical instructions get higher confidence
        imperative_indicators = pattern.trigger_words[:3]  # First few words are usually verbs
        first_words = matched_text.lower().split()[:2]
        if any(word in imperative_indicators for word in first_words):
            confidence += 0.1
            
        # Clamp confidence between 0 and 1
        return max(0.0, min(1.0, confidence))
    
    def _get_formatting_hints(self, pattern: TechnicalPattern, matched_text: str, full_text: str) -> Dict[str, str]:
        """Get formatting hints for the detected pattern"""
        
        hints = {
            "capitalization_rule": pattern.capitalization_rule,
            "entity_handling": pattern.entity_handling,
            "preserve_technical_case": "true" if pattern.capitalization_rule == "preserve_technical" else "false"
        }
        
        # Context-specific hints
        if pattern.pattern_type == TechnicalContextType.COMMAND_INSTRUCTION:
            hints["prefer_lowercase_commands"] = "true"
            hints["preserve_flag_case"] = "true"
            
        elif pattern.pattern_type == TechnicalContextType.FILE_OPERATION:
            hints["preserve_filename_case"] = "true"
            hints["use_dot_extensions"] = "true"
            
        elif pattern.pattern_type == TechnicalContextType.CODE_EXPLANATION:
            hints["allow_mixed_case_terms"] = "true"
            hints["preserve_code_entities"] = "true"
            
        elif pattern.pattern_type == TechnicalContextType.CONFIGURATION:
            hints["preserve_parameter_case"] = "true"
            hints["prefer_lowercase_values"] = "true"
            
        return hints
    
    def _find_related_technical_entities(self, start: int, end: int, entities: List[Entity],
                                       context_type: TechnicalContextType) -> List[Entity]:
        """Find technical entities related to the detected context"""
        
        # Define entity types that are relevant to each context type
        relevant_entity_types = {
            TechnicalContextType.COMMAND_INSTRUCTION: {
                EntityType.CLI_COMMAND, EntityType.COMMAND_FLAG, EntityType.VARIABLE
            },
            TechnicalContextType.FILE_OPERATION: {
                EntityType.FILENAME, EntityType.UNIX_PATH, EntityType.WINDOWS_PATH
            },
            TechnicalContextType.CODE_EXPLANATION: {
                EntityType.VARIABLE, EntityType.PROGRAMMING_KEYWORD, EntityType.ASSIGNMENT
            },
            TechnicalContextType.CONFIGURATION: {
                EntityType.PORT_NUMBER, EntityType.VARIABLE, EntityType.ASSIGNMENT
            },
            TechnicalContextType.PROGRAMMING_TASK: {
                EntityType.PROGRAMMING_KEYWORD, EntityType.VARIABLE, EntityType.ASSIGNMENT
            },
            TechnicalContextType.TECHNICAL_PROCEDURE: {
                EntityType.CLI_COMMAND, EntityType.FILENAME, EntityType.URL
            },
            TechnicalContextType.DEBUG_CONTEXT: {
                EntityType.VARIABLE, EntityType.ASSIGNMENT, EntityType.PROGRAMMING_KEYWORD
            },
            TechnicalContextType.SYSTEM_OPERATION: {
                EntityType.PORT_NUMBER, EntityType.URL, EntityType.CLI_COMMAND
            }
        }
        
        relevant_types = relevant_entity_types.get(context_type, set())
        if not relevant_types:
            return []
        
        # Find entities within a reasonable distance from the context
        context_window = 100
        related_entities = []
        
        for entity in entities:
            if (entity.type in relevant_types and 
                abs(entity.start - start) <= context_window):
                related_entities.append(entity)
                
        return related_entities
    
    def _resolve_overlapping_contexts(self, contexts: List[SpanishTechnicalContext]) -> List[SpanishTechnicalContext]:
        """Resolve overlapping contexts by keeping the highest confidence ones"""
        
        if len(contexts) <= 1:
            return contexts
        
        # Sort by confidence descending
        sorted_contexts = sorted(contexts, key=lambda c: c.confidence, reverse=True)
        
        # Keep non-overlapping contexts
        resolved_contexts = []
        
        for context in sorted_contexts:
            # Check if this context overlaps with any already selected
            overlaps = False
            for selected in resolved_contexts:
                if (context.start_pos < selected.end_pos and 
                    context.end_pos > selected.start_pos):
                    overlaps = True
                    break
                    
            if not overlaps:
                resolved_contexts.append(context)
                
        return resolved_contexts
    
    def should_apply_technical_formatting(self, text: str, position: int) -> Tuple[bool, Optional[SpanishTechnicalContext]]:
        """
        Check if technical formatting should be applied at a specific position.
        
        Args:
            text: Full text context
            position: Position to check
            
        Returns:
            Tuple of (should_apply_technical_formatting, context_info)
        """
        
        # Get or analyze contexts for this text
        contexts = self.analyze_spanish_technical_context(text)
        
        # Find context that contains this position
        for context in contexts:
            if context.start_pos <= position <= context.end_pos:
                return True, context
                
        # Check if position is within reasonable distance of a high-confidence context
        for context in contexts:
            if (context.confidence >= 0.8 and 
                abs(position - context.start_pos) <= 50):
                return True, context
                
        return False, None
    
    def get_capitalization_guidance(self, text: str, position: int, word: str) -> Dict[str, str]:
        """
        Get capitalization guidance for a word at a specific position.
        
        Args:
            text: Full text context
            position: Position of the word
            word: The word to get guidance for
            
        Returns:
            Dictionary with capitalization guidance
        """
        
        should_apply, context = self.should_apply_technical_formatting(text, position)
        
        if should_apply and context:
            guidance = {
                "rule": context.formatting_hints.get("capitalization_rule", "standard"),
                "preserve_case": str(context.should_preserve_case).lower(),
                "context_type": context.context_type.value,
                "confidence": str(context.confidence)
            }
            
            # Add specific guidance based on context type
            if context.context_type in [
                TechnicalContextType.COMMAND_INSTRUCTION, 
                TechnicalContextType.CONFIGURATION
            ]:
                guidance["prefer_lowercase_technical"] = "true"
                
            elif context.context_type == TechnicalContextType.CODE_EXPLANATION:
                guidance["allow_mixed_case"] = "true"
                
            return guidance
            
        # Default guidance for non-technical contexts
        return {
            "rule": "standard",
            "preserve_case": "false",
            "context_type": "conversational",
            "confidence": "0.0"
        }


# Global instance for easy access
_spanish_technical_recognizer: Optional[SpanishTechnicalPatternRecognizer] = None


def get_spanish_technical_recognizer(language: str = "es") -> SpanishTechnicalPatternRecognizer:
    """Get or create the global Spanish technical pattern recognizer"""
    global _spanish_technical_recognizer
    
    if _spanish_technical_recognizer is None:
        _spanish_technical_recognizer = SpanishTechnicalPatternRecognizer(language)
        logger.debug("THEORY_20: Initialized Spanish Technical Pattern Recognizer")
        
    return _spanish_technical_recognizer