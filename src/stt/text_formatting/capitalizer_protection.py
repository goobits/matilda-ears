#!/usr/bin/env python3
"""Entity protection logic for the SmartCapitalizer."""
from __future__ import annotations

import re
from typing import TYPE_CHECKING

from ..core.config import setup_logging

if TYPE_CHECKING:
    from .common import Entity
    from .capitalizer_rules import CapitalizationRules

# Setup logging
logger = setup_logging(__name__)


class EntityProtection:
    """Handles entity protection logic for capitalization."""

    def __init__(self, rules: 'CapitalizationRules'):
        """Initialize entity protection with capitalization rules.
        
        Args:
            rules: CapitalizationRules instance containing protection logic
        """
        self.rules = rules

    def should_capitalize_first_letter(
        self, 
        text: str, 
        first_letter_index: int, 
        entities: list['Entity'] | None = None
    ) -> bool:
        """Determine if the first letter should be capitalized based on entity protection.
        
        Args:
            text: The full text being processed
            first_letter_index: Index of the first alphabetic character
            entities: List of entities that may affect capitalization
            
        Returns:
            True if the first letter should be capitalized
        """
        if entities is None:
            return True

        for entity in entities:
            if entity.start <= first_letter_index < entity.end:
                logger.debug(
                    f"Checking entity at start: {entity.type} '{entity.text}' [{entity.start}:{entity.end}], first_letter_index={first_letter_index}"
                )
                
                # Don't capitalize if it's a strictly protected type, except for abbreviations and special cases
                if self.rules.is_strictly_protected_type(entity.type):
                    if entity.type.name == "ABBREVIATION":
                        # Special case: abbreviations at sentence start should have first letter capitalized
                        # but preserve the abbreviation format (e.g., "i.e." -> "I.e.")
                        logger.debug(f"Abbreviation '{entity.text}' at sentence start, capitalizing first letter only")
                        # Don't set should_capitalize = False, let it capitalize normally
                        # The abbreviation entity will handle maintaining the correct format
                        return True
                    elif entity.type.name in ["URL", "SPOKEN_URL", "SPOKEN_PROTOCOL_URL", "PORT_NUMBER"]:
                        # URLs and port numbers should NEVER be capitalized, even at sentence start
                        logger.debug(f"URL/Port entity '{entity.text}' at sentence start - preventing capitalization")
                        return False
                    elif entity.type.name == "VARIABLE" and entity.text == "i":
                        # Special case: single letter 'i' variables need context-aware handling
                        # Check if this is truly a pronoun context vs variable context
                        is_pronoun_context = self._is_i_pronoun_context(text, first_letter_index)
                        if is_pronoun_context:
                            logger.debug(f"Variable 'i' detected as pronoun in context - allowing capitalization")
                            return True
                        else:
                            logger.debug(f"Variable 'i' in variable context - preventing capitalization")
                            return False
                    elif entity.type.name in ["SPOKEN_EMAIL", "EMAIL"]:
                        # Special case: emails at sentence start should have first letter capitalized
                        # when they begin with a normal word (e.g., "email support@..." -> "Email support@...")
                        # This handles cases like "email support at company dot com" -> "Email support@company.com"
                        if entity.start == 0 and first_letter_index == 0:
                            # Check if the first word looks like a normal word (not technical/address-like)
                            first_word = entity.text.split()[0] if entity.text else ""
                            if self._should_capitalize_first_word_in_email(first_word):
                                logger.debug(f"Email entity '{entity.text}' at sentence start - allowing first word capitalization")
                                return True
                        logger.debug(f"Email entity '{entity.text}' - preventing capitalization to preserve email format")
                        return False
                    elif entity.type.name in ["VARIABLE", "SIMPLE_UNDERSCORE_VARIABLE", "UNDERSCORE_DELIMITER", 
                                             "INCREMENT_OPERATOR", "DECREMENT_OPERATOR"]:
                        # Special case: code entities at sentence start in natural language contexts
                        # should allow sentence-start capitalization for normal words
                        # This handles Spanish cases like "índice menos menos" -> "Índice --" 
                        # and "variable guión bajo nombre" -> "Variable _nombre"
                        if entity.start == 0 and first_letter_index == 0:
                            # Extract the first word from the entity text 
                            # Handle cases like "índice--" where there are no spaces
                            entity_words = entity.text.split()
                            if entity_words:
                                first_word = entity_words[0] 
                            else:
                                first_word = ""
                            
                            # If there's only one "word" but it contains non-alphabetic characters,
                            # extract just the alphabetic prefix (e.g., "índice--" -> "índice")
                            if len(entity_words) == 1 and entity.text:
                                # Find the first sequence of alphabetic characters
                                alpha_match = re.match(r'[a-zA-ZáéíóúñÁÉÍÓÚÑ]+', entity.text)
                                if alpha_match:
                                    first_word = alpha_match.group()
                            
                            if first_word and self._should_capitalize_first_word_in_code_entity(first_word):
                                logger.debug(f"Code entity '{entity.text}' at sentence start - allowing first word capitalization for '{first_word}'")
                                return True
                        logger.debug(f"Code entity '{entity.text}' - preventing capitalization to preserve technical format")
                        return False
                    else:
                        logger.debug(f"Entity {entity.type} is strictly protected")
                        return False
                        
                # Special rule for CLI commands: only keep lowercase if the *entire* text is the command
                elif entity.type.name == "CLI_COMMAND":
                    if entity.text.strip() == text.strip():
                        logger.debug("CLI command is entire text, not capitalizing")
                        return False
                    logger.debug(
                        f"CLI command '{entity.text}' is not entire text '{text}', allowing capitalization"
                    )
                    # Otherwise, allow normal capitalization for CLI commands at sentence start
                    
                # Special rule for versions starting with 'v' (e.g., v1.2)
                elif entity.type.name == "VERSION" and entity.text.startswith("v"):
                    logger.debug(f"Version entity '{entity.text}' starts with 'v', not capitalizing")
                    return False
                    
                # PROGRAMMING STATEMENT LOGIC: Programming keywords that start code statements
                # should NOT be capitalized because they start code, not natural language sentences
                elif entity.type.name == "PROGRAMMING_KEYWORD" and entity.start == 0:
                    # Check if this is a programming statement keyword that should stay lowercase
                    code_statement_keywords = {"if", "when", "while", "unless", "until", "let", "const", "var", "for", "def", "function"}
                    if entity.text.lower() in code_statement_keywords:
                        # Special handling for conditional keywords - check if it's in natural language context
                        conditional_keywords = {"for", "if", "when", "while"}
                        if entity.text.lower() in conditional_keywords:
                            is_natural_language = self._is_conditional_in_natural_language_context(text, entity.start, entity.text.lower())
                            if is_natural_language:
                                logger.debug(
                                    f"'{entity.text}' detected in natural language context - allowing capitalization"
                                )
                                # Allow capitalization for natural language conditionals
                                break
                        
                        logger.debug(
                            f"Programming statement keyword '{entity.text}' at sentence start - preventing capitalization to preserve code context"
                        )
                        return False
                    else:
                        logger.debug(
                            f"Non-statement programming keyword '{entity.text}' at sentence start - allowing capitalization for proper sentence structure"
                        )
                        # Allow capitalization for non-statement programming keywords
                        break

        return True

    def is_entity_protected_from_sentence_capitalization(
        self, 
        position: int, 
        entities: list['Entity'] | None = None
    ) -> bool:
        """Check if a position is inside a protected entity for sentence capitalization.
        
        Args:
            position: Character position to check
            entities: List of entities to check against
            
        Returns:
            True if the position should be protected from sentence capitalization
        """
        if entities is None:
            return False

        for entity in entities:
            if entity.start <= position < entity.end:
                return True
        return False

    def is_position_inside_protected_entity(
        self, 
        position: int, 
        entities: list['Entity'] | None = None
    ) -> bool:
        """Check if a position is inside any protected entity.
        
        Args:
            position: Character position to check
            entities: List of entities to check against
            
        Returns:
            True if the position is inside a protected entity
        """
        return self.is_entity_protected_from_sentence_capitalization(position, entities)

    def should_protect_from_spacy_capitalization(
        self, 
        start: int, 
        end: int, 
        entities: list['Entity'] | None = None
    ) -> bool:
        """Check if a text span should be protected from SpaCy proper noun capitalization.
        
        Args:
            start: Start position of the span
            end: End position of the span
            entities: List of entities to check against
            
        Returns:
            True if the span should be protected from SpaCy capitalization
        """
        if entities is None:
            return False

        for entity in entities:
            # Check if the SpaCy entity overlaps with any protected entity
            if start < entity.end and end > entity.start:
                logger.debug(
                    f"SpaCy entity at {start}-{end} overlaps with protected entity {entity.type} at {entity.start}-{entity.end}"
                )
                
                if self.rules.should_protect_entity_from_spacy_capitalization(entity.type):
                    logger.debug(f"Protecting entity from capitalization due to {entity.type}")
                    return True
                logger.debug(f"Entity type {entity.type} not in protected list, allowing capitalization")
                
        return False

    def should_protect_from_uppercase_conversion(
        self, 
        start: int, 
        end: int, 
        entities: list['Entity'] | None = None
    ) -> bool:
        """Check if a text span should be protected from uppercase abbreviation conversion.
        
        Args:
            start: Start position of the span
            end: End position of the span
            entities: List of entities to check against
            
        Returns:
            True if the span should be protected from uppercase conversion
        """
        if entities is None:
            return False

        for entity in entities:
            if (start < entity.end and end > entity.start and 
                self.rules.should_protect_entity_from_uppercase_conversion(entity.type)):
                return True
                
        return False

    def has_placeholders(self, text: str) -> bool:
        """Check if text contains placeholders that should skip SpaCy processing.
        
        Args:
            text: Text to check for placeholders
            
        Returns:
            True if text contains placeholders
        """
        return "__CAPS_" in text or "__PLACEHOLDER_" in text or "__ENTITY_" in text

    def is_placeholder_context(self, text: str, start: int, end: int) -> bool:
        """Check if a text span is in a placeholder context.
        
        Args:
            text: Full text
            start: Start position of the span
            end: End position of the span
            
        Returns:
            True if the span is in a placeholder context
        """
        # Check the actual text at this position
        actual_text = text[start:end]
        # Also check if we're inside a placeholder by looking at surrounding context
        context_start = max(0, start - 2)
        context_end = min(len(text), end + 2)
        context = text[context_start:context_end]

        return "__" in context or actual_text.strip(".,!?").endswith("__")

    def restore_placeholders(self, text: str, placeholder_pattern: str) -> str:
        """Restore original case for placeholders in text.
        
        Args:
            text: Text with potential placeholder modifications
            placeholder_pattern: Regex pattern for placeholders
            
        Returns:
            Text with restored placeholder casing
        """
        placeholders_found = re.findall(placeholder_pattern, text)
        
        # Restore original case for placeholders
        for placeholder in placeholders_found:
            text = re.sub(placeholder, placeholder, text, flags=re.IGNORECASE)
            
        return text
    
    def _is_i_pronoun_context(self, text: str, position: int) -> bool:
        """Check if 'i' at given position should be treated as a pronoun (not variable).
        
        Args:
            text: Full text
            position: Position of 'i' in text
            
        Returns:
            True if 'i' should be treated as a pronoun and capitalized
        """
        # Simple heuristic: if 'i' is at sentence start OR followed by a verb, treat as pronoun
        # This is a simplified approach since SpaCy is not available
        
        # Check if this is sentence start (accounting for leading punctuation/spaces)
        if position <= 5:  # Near beginning of sentence
            return True
            
        # Look at surrounding context
        context_before = text[max(0, position - 15):position].lower()
        context_after = text[position + 1:position + 15].lower()
        
        # If preceded by "when", "if", "because", etc., likely a pronoun
        pronoun_indicators = ["when ", "if ", "because ", "since ", "while ", "after "]
        if any(text[max(0, position - len(indicator) - 1):position].lower().endswith(indicator) 
               for indicator in pronoun_indicators):
            return True
            
        # If followed by common verbs, likely a pronoun
        verb_indicators = [" think", " write", " am", " was", " will", " have", " had", " do", " did"]
        if any(context_after.startswith(verb) for verb in verb_indicators):
            return True
            
        # If followed by assignment operators, likely a variable
        assignment_indicators = [" equals", " =", " +=", " -="]
        if any(context_after.startswith(op) for op in assignment_indicators):
            return False
            
        # Default: treat as pronoun (safer to over-capitalize than under-capitalize)
        return True
    
    def _is_for_in_natural_language_context(self, text: str, position: int) -> bool:
        """Check if 'for' at given position is used in natural language context vs programming.
        
        Args:
            text: Full text
            position: Position of 'for' in text
            
        Returns:
            True if 'for' is used in natural language context (should be capitalized)
        """
        # Look at the words following 'for'
        words_after_for = text[position + 3:].strip().split()[:3]  # Get next 3 words
        
        # Natural language patterns with 'for'
        natural_language_patterns = [
            "example", "instance", "more", "information", "info", "help", "support",
            "details", "questions", "assistance", "clarification", "reference",
            "the", "a", "an", "some", "any", "each", "every", "all"
        ]
        
        # Programming context patterns (what would follow programming 'for')
        programming_patterns = [
            "loop", "i", "j", "k", "x", "y", "z", "item", "element", "each"
        ]
        
        if words_after_for:
            first_word = words_after_for[0].lower()
            
            # Check for explicit natural language indicators
            if first_word in natural_language_patterns:
                return True
                
            # Check for programming loop patterns
            if first_word in programming_patterns:
                # Additional check: look for programming syntax
                remaining_text = " ".join(words_after_for)
                if any(keyword in remaining_text.lower() for keyword in ["in", "range", "len", "iterate", "loop"]):
                    return False  # Programming context
                    
            # Check for natural language phrases
            if len(words_after_for) >= 2:
                two_word_phrase = f"{words_after_for[0].lower()} {words_after_for[1].lower()}"
                natural_phrases = [
                    "more info", "more information", "more details", "more help",
                    "the record", "the purpose", "the sake", "the time",
                    "your information", "your reference", "your help"
                ]
                if two_word_phrase in natural_phrases:
                    return True
        
        # Look at the broader context - if the sentence contains natural language words,
        # it's likely natural language context
        text_lower = text.lower()
        natural_context_indicators = [
            "visit", "website", "info", "information", "help", "support", "docs",
            "documentation", "example", "instance", "more", "please", "check",
            "see", "find", "get", "contact", "email"
        ]
        
        if any(indicator in text_lower for indicator in natural_context_indicators):
            return True
            
        # Default: assume natural language context (safer to capitalize)
        return True
    
    def _is_conditional_in_natural_language_context(self, text: str, position: int, keyword: str) -> bool:
        """Check if a conditional keyword (if, when, while, for) is used in natural language vs programming.
        
        Args:
            text: Full text
            position: Position of the keyword in text
            keyword: The conditional keyword ("if", "when", "while", "for")
            
        Returns:
            True if the keyword is used in natural language context (should be capitalized)
        """
        # Look at the words following the keyword
        keyword_len = len(keyword)
        words_after = text[position + keyword_len:].strip().split()[:5]  # Get next 5 words for context
        
        # Programming context indicators for different keywords
        programming_patterns = {
            "if": ["x", "i", "j", "k", "value", "result", "condition", "true", "false", "null", "none", 
                   "equals", "==", "!=", "<=", ">=", "<", ">", "and", "or", "not"],
            "when": ["x", "i", "condition", "true", "false", "equals", "==", "event", "trigger"],  
            "while": ["x", "i", "j", "k", "condition", "true", "false", "loop", "iterate", "equals", "<=", ">="],
            "for": ["i", "j", "k", "x", "y", "z", "item", "element", "each", "loop", "range", "in", "iterate"]
        }
        
        # Natural language patterns for different keywords
        natural_patterns = {
            "if": ["you", "we", "they", "he", "she", "it", "this", "that", "someone", "anyone", "everyone", 
                   "people", "users", "clients", "the", "a", "an", "some", "any", "there",
                   # Spanish equivalents
                   "tú", "nosotros", "ellos", "él", "ella", "esto", "eso", "alguien", "todos", "gente", "usuarios"],
            "when": ["you", "we", "they", "he", "she", "it", "this", "that", "someone", "the", "a", "time", 
                     "possible", "ready", "done", "finished", "complete",
                     # Spanish equivalents  
                     "tú", "nosotros", "ellos", "él", "ella", "esto", "eso", "alguien", "el", "la", "tiempo", "posible"],
            "while": ["you", "we", "they", "he", "she", "it", "this", "that", "working", "running", "waiting",
                      "the", "a", "some", "others",
                      # Spanish equivalents
                      "tú", "nosotros", "ellos", "él", "ella", "esto", "eso", "trabajando", "corriendo", "esperando"],  
            "for": ["example", "instance", "more", "information", "info", "help", "support", "details", 
                    "questions", "the", "a", "an", "some", "any", "each", "every", "all",
                    # Spanish equivalents
                    "ejemplo", "más", "información", "ayuda", "soporte", "detalles", "preguntas", "el", "la", "un", "una"],
            # Spanish keywords
            "variable": ["nombre", "función", "método", "archivo", "documento", "el", "la", "un", "una", "mi", "tu", "su"],
            "función": ["nombre", "método", "archivo", "documento", "el", "la", "un", "una", "mi", "tu", "su"],
            "método": ["nombre", "función", "archivo", "documento", "el", "la", "un", "una", "mi", "tu", "su"]
        }
        
        if words_after:
            first_word = words_after[0].lower()
            
            # Check for explicit natural language indicators
            if keyword in natural_patterns and first_word in natural_patterns[keyword]:
                return True
                
            # Check for programming patterns
            if keyword in programming_patterns and first_word in programming_patterns[keyword]:
                # Additional context check for programming syntax
                remaining_text = " ".join(words_after).lower()
                programming_keywords = ["equals", "==", "!=", "<=", ">=", "and", "or", "not", "true", "false", 
                                      "null", "none", "range", "len", "in", "iterate", "loop"]
                if any(prog_word in remaining_text for prog_word in programming_keywords):
                    return False  # Programming context
        
        # Look at the broader context - if sentence contains natural language indicators
        text_lower = text.lower()
        natural_context_indicators = [
            # English indicators
            "you", "think", "believe", "feel", "want", "need", "like", "love", "hate", "see", "look",
            "visit", "go", "come", "tell", "say", "speak", "talk", "ask", "answer", "help", "support", 
            "please", "thanks", "sorry", "excuse", "people", "person", "user", "users", "problem",
            "issue", "question", "solution", "differently", "carefully", "quickly", "slowly",
            # Spanish indicators
            "tú", "usted", "nosotros", "ustedes", "piensas", "pienso", "pensamos", "crees", "creo", "creemos",
            "sientes", "siento", "sentimos", "quieres", "quiero", "queremos", "necesitas", "necesito", "necesitamos",
            "te gusta", "me gusta", "nos gusta", "ves", "veo", "vemos", "miras", "miro", "miramos",
            "visitas", "visito", "visitamos", "vas", "voy", "vamos", "vienes", "vengo", "venimos",
            "dices", "digo", "decimos", "hablas", "hablo", "hablamos", "preguntas", "pregunto", "preguntamos",
            "respondes", "respondo", "respondemos", "ayudas", "ayudo", "ayudamos", "por favor", "gracias",
            "perdón", "disculpa", "gente", "persona", "personas", "usuario", "usuarios", "problema",
            "problemas", "pregunta", "preguntas", "solución", "diferente", "cuidadoso", "rápido", "lento",
            "nombre", "función", "método", "archivo", "documento", "servidor", "sistema", "guión", "bajo"
        ]
        
        if any(indicator in text_lower for indicator in natural_context_indicators):
            return True
            
        # For "if" specifically, check for common natural language patterns
        if keyword == "if" and words_after:
            # Common natural language "if" patterns
            if len(words_after) >= 2:
                two_word_phrase = f"{words_after[0].lower()} {words_after[1].lower()}"
                natural_if_phrases = [
                    "you think", "you want", "you need", "you like", "you see", "you go", "you come",
                    "you believe", "you feel", "you look", "we think", "we want", "we need", 
                    "they think", "it works", "this works", "that works"
                ]
                if two_word_phrase in natural_if_phrases:
                    return True
        
        # Default: assume natural language context (safer to capitalize)
        return True
    
    def _should_capitalize_first_word_in_email(self, first_word: str) -> bool:
        """Check if the first word in an email entity should be capitalized at sentence start.
        
        Args:
            first_word: The first word of the email entity
            
        Returns:
            True if the first word looks like a normal word that should be capitalized
        """
        if not first_word:
            return False
            
        first_word_lower = first_word.lower()
        
        # Common action words that typically start email sentences
        email_action_words = {
            "email", "contact", "send", "forward", "reach", "notify", "message", "mail",
            "write", "communicate", "support", "help", "info", "admin", "sales"
        }
        
        # Spanish equivalents
        spanish_action_words = {
            "email", "contacto", "enviar", "reenviar", "alcanzar", "notificar", 
            "mensaje", "correo", "escribir", "comunicar", "soporte", "ayuda", 
            "información", "admin", "ventas", "índice", "variable", "función",
            "método", "archivo", "documento", "servidor", "sistema"
        }
        
        # Technical terms that might appear in email contexts but should still be capitalized at sentence start
        technical_words = {
            "server", "admin", "support", "help", "info", "system", "service", "api",
            "database", "config", "setup", "install", "update", "backup", "log",
            "user", "guest", "client", "host", "domain", "account", "profile"
        }
        
        # Check if it's a recognizable word that should be capitalized
        if (first_word_lower in email_action_words or 
            first_word_lower in spanish_action_words or 
            first_word_lower in technical_words):
            return True
            
        # Don't capitalize if it looks like part of an email address or technical identifier
        # (contains digits, special chars, or is very short technical abbreviation)
        if (re.match(r'^[a-z0-9._-]+$', first_word_lower) and 
            (any(c.isdigit() for c in first_word) or '_' in first_word or '-' in first_word)):
            return False
            
        # If it's a normal-looking word (all letters), probably safe to capitalize
        if first_word.isalpha() and len(first_word) > 1:
            return True
            
        return False
    
    def _should_capitalize_first_word_in_code_entity(self, first_word: str) -> bool:
        """Check if the first word in a code entity should be capitalized at sentence start.
        
        Args:
            first_word: The first word of the code entity
            
        Returns:
            True if the first word looks like a normal word that should be capitalized
        """
        if not first_word:
            return False
            
        first_word_lower = first_word.lower()
        
        # Common natural language words that appear in code contexts but should be capitalized at sentence start
        natural_language_words = {
            # English
            "index", "variable", "function", "method", "class", "object", "value", "result", 
            "counter", "number", "item", "element", "data", "list", "array", "string", "text",
            "file", "document", "server", "client", "user", "admin", "system", "config",
            # Spanish
            "índice", "variable", "función", "método", "clase", "objeto", "valor", "resultado",
            "contador", "número", "elemento", "datos", "lista", "array", "cadena", "texto",
            "archivo", "documento", "servidor", "cliente", "usuario", "administrador", "sistema"
        }
        
        # Check if it's a recognizable natural language word
        if first_word_lower in natural_language_words:
            return True
            
        # Don't capitalize if it looks like a technical identifier 
        # (starts with underscore, contains digits mixed with letters, etc.)
        if first_word.startswith('_') or re.match(r'^[a-z0-9_-]+$', first_word_lower):
            return False
            
        # If it's a normal-looking word (all letters), probably safe to capitalize at sentence start
        if first_word.isalpha() and len(first_word) > 1:
            return True
            
        return False