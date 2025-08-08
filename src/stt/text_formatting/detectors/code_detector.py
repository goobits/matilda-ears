#!/usr/bin/env python3
"""Code-related entity detection and conversion for Matilda transcriptions.

This module acts as a facade that coordinates specialized detection modules:
- CommandDetector: CLI commands, slash commands, and flags
- FileDetector: Filename and package detection
- VariableDetector: Programming keywords, underscore variables, abbreviations
- AssignmentDetector: Assignment operators and spoken operators
"""
from __future__ import annotations

from stt.core.config import setup_logging
from stt.text_formatting.common import Entity
from .assignment_detector import AssignmentDetector
from .command_detector import CommandDetector
from .file_detector import FileDetector
from .variable_detector import VariableDetector

logger = setup_logging(__name__, log_filename="text_formatting.txt", include_console=False)


class CodeEntityDetector:
    """Main facade for code-related entity detection.
    
    Coordinates specialized detectors to maintain backward compatibility
    while providing modular architecture.
    """
    
    def __init__(self, nlp=None, language: str = "en"):
        """
        Initialize CodeEntityDetector with dependency injection.

        Args:
            nlp: SpaCy NLP model instance. If None, will load from nlp_provider.
            language: Language code for resource loading (default: 'en')
        """
        if nlp is None:
            from stt.text_formatting.nlp_provider import get_nlp
            nlp = get_nlp()

        self.nlp = nlp
        self.language = language

        # Initialize specialized detectors
        self.file_detector = FileDetector(nlp=nlp, language=language)
        self.command_detector = CommandDetector(language=language)
        self.variable_detector = VariableDetector(language=language)
        self.assignment_detector = AssignmentDetector(nlp=nlp, language=language)

    def _update_entities_state(self, entities, code_entities, all_entities):
        """Update all_entities with newly found entities."""
        all_entities.clear()
        all_entities.extend(entities)
        all_entities.extend(code_entities)

    def _run_detector(self, detector_method, text, entities, code_entities, all_entities):
        """Run a detector method and update entities state.
        
        Args:
            detector_method: The detector method to call
            text: The text to analyze
            entities: List of existing entities
            code_entities: List of detected code entities
            all_entities: Combined list of all entities
        """
        detector_method(text, code_entities, all_entities)
        self._update_entities_state(entities, code_entities, all_entities)

    def detect(self, text: str, entities: list[Entity]) -> list[Entity]:
        """Detects all code-related entities using specialized detectors."""
        code_entities: list[Entity] = []

        # Start with existing entities and build cumulatively
        all_entities = entities[:]  # Start with copy of existing entities

        # Run detectors in order, maintaining detection sequence
        # Command flags detection first (before filename) to prevent conflicts
        self._run_detector(self.command_detector.detect_command_flags, text, entities, code_entities, all_entities)
        self._run_detector(self.command_detector.detect_preformatted_flags, text, entities, code_entities, all_entities)
        
        # Command detection
        self._run_detector(self.command_detector.detect_cli_commands, text, entities, code_entities, all_entities)
        
        # File detection (after command flags to avoid conflicts)
        self._run_detector(self.file_detector.detect_filenames, text, entities, code_entities, all_entities)
        
        # Variable detection
        self._run_detector(self.variable_detector.detect_programming_keywords, text, entities, code_entities, all_entities)
        
        # Assignment detection
        self._run_detector(self.assignment_detector.detect_spoken_operators, text, entities, code_entities, all_entities)
        self._run_detector(self.assignment_detector.detect_assignment_operators, text, entities, code_entities, all_entities)
        
        # More variable detection
        self._run_detector(self.variable_detector.detect_abbreviations, text, entities, code_entities, all_entities)
        self._run_detector(self.variable_detector.detect_underscore_delimiters, text, entities, code_entities, all_entities)
        self._run_detector(self.variable_detector.detect_simple_underscore_variables, text, entities, code_entities, all_entities)
        self._run_detector(self.variable_detector.detect_single_letter_variables, text, entities, code_entities, all_entities)

        # Last detector doesn't use _run_detector to preserve exact functionality
        self.command_detector.detect_slash_commands(text, code_entities, all_entities)

        logger.debug(f"CodeEntityDetector found {len(code_entities)} entities in '{text}'")
        for entity in code_entities:
            logger.debug(f"  - {entity.type}: '{entity.text}' [{entity.start}:{entity.end}]")

        return code_entities

    # Delegate methods for backward compatibility
    def _detect_filenames(self, text: str, entities: list[Entity], all_entities: list[Entity] | None = None) -> None:
        """Detect filenames (delegated to FileDetector)."""
        self.file_detector.detect_filenames(text, entities, all_entities)

    def _detect_spoken_operators(self, text: str, entities: list[Entity], all_entities: list[Entity] | None = None) -> None:
        """Detect spoken operators (delegated to AssignmentDetector)."""
        self.assignment_detector.detect_spoken_operators(text, entities, all_entities)

    def _detect_assignment_operators(self, text: str, entities: list[Entity], all_entities: list[Entity] | None = None) -> None:
        """Detect assignment operators (delegated to AssignmentDetector)."""
        self.assignment_detector.detect_assignment_operators(text, entities, all_entities)

    def _detect_abbreviations(self, text: str, entities: list[Entity], all_entities: list[Entity] | None = None) -> None:
        """Detect abbreviations (delegated to VariableDetector)."""
        self.variable_detector.detect_abbreviations(text, entities, all_entities)

    def _detect_command_flags(self, text: str, entities: list[Entity], all_entities: list[Entity] | None = None) -> None:
        """Detect command flags (delegated to CommandDetector)."""
        self.command_detector.detect_command_flags(text, entities, all_entities)

    def _detect_preformatted_flags(self, text: str, entities: list[Entity], all_entities: list[Entity] | None = None) -> None:
        """Detect preformatted flags (delegated to CommandDetector)."""
        self.command_detector.detect_preformatted_flags(text, entities, all_entities)

    def _detect_slash_commands(self, text: str, entities: list[Entity], all_entities: list[Entity] | None = None) -> None:
        """Detect slash commands (delegated to CommandDetector)."""
        self.command_detector.detect_slash_commands(text, entities, all_entities)

    def _detect_underscore_delimiters(self, text: str, entities: list[Entity], all_entities: list[Entity] | None = None) -> None:
        """Detect underscore delimiters (delegated to VariableDetector)."""
        self.variable_detector.detect_underscore_delimiters(text, entities, all_entities)

    def _detect_simple_underscore_variables(self, text: str, entities: list[Entity], all_entities: list[Entity] | None = None) -> None:
        """Detect simple underscore variables (delegated to VariableDetector)."""
        self.variable_detector.detect_simple_underscore_variables(text, entities, all_entities)

    def _detect_cli_commands(self, text: str, entities: list[Entity], all_entities: list[Entity] | None = None) -> None:
        """Detect CLI commands (delegated to CommandDetector)."""
        self.command_detector.detect_cli_commands(text, entities, all_entities)

    def _detect_programming_keywords(self, text: str, entities: list[Entity], all_entities: list[Entity] | None = None) -> None:
        """Detect programming keywords (delegated to VariableDetector)."""
        self.variable_detector.detect_programming_keywords(text, entities, all_entities)

    # Regex fallback method for backward compatibility
    def _detect_filenames_regex_fallback(self, text: str, entities: list[Entity], all_entities: list[Entity] | None = None) -> None:
        """Regex fallback for filename detection (delegated to FileDetector)."""
        self.file_detector._detect_filenames_regex_fallback(text, entities, all_entities)