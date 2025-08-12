#!/usr/bin/env python3
"""Smart capitalization module for Matilda transcriptions."""
from __future__ import annotations

# Standard library imports
import re

# Local imports - core/config
from stt.core.config import setup_logging

# Local imports - common data structures
from stt.text_formatting.common import Entity, EntityType

# Local imports - utilities and resources
from . import regex_patterns
from .constants import get_resources
from .nlp_provider import get_nlp
from .utils import is_inside_entity

# Local imports - modular components
from .capitalizer_rules import CapitalizationRules
from .capitalizer_protection import EntityProtection
from .capitalizer_context import ContextAnalyzer

# Setup logging
logger = setup_logging(__name__)


class SmartCapitalizer:
    """Intelligent capitalization using SpaCy POS tagging"""

    def __init__(self, language: str = "en"):
        self.nlp = get_nlp()
        self.language = language

        # Load language-specific resources
        self.resources = get_resources(language)

        # Initialize modular components
        self.rules = CapitalizationRules(self.resources, language)
        self.protection = EntityProtection(self.rules)
        self.context = ContextAnalyzer(self.rules, self.nlp)

        # Keep backward compatibility properties
        self.STRICTLY_PROTECTED_TYPES = self.rules.STRICTLY_PROTECTED_TYPES
        self.version_patterns = self.rules.version_patterns
        self.abbreviation_fixes = self.rules.abbreviation_fixes
        self.uppercase_abbreviations = self.rules.uppercase_abbreviations
        self.common_abbreviations = self.rules.common_abbreviations

    def capitalize(self, text: str, entities: list[Entity] | None = None, doc=None) -> str:
        """Apply intelligent capitalization with entity protection"""
        if not text:
            return text

        # Apply entity type-specific spacing rules first
        if entities:
            text = self.rules.apply_entity_type_spacing_rules(text, entities, self.language)

        # Preserve all-caps words (acronyms like CPU, API, JSON) and number+unit combinations (500MB, 2.5GHz)
        # But exclude version numbers (v16.4.2)
        all_caps_words = {}
        matches = list(regex_patterns.ALL_CAPS_PRESERVATION_PATTERN.finditer(text))

        # Also preserve mixed-case technical terms (JavaScript, GitHub, etc.)
        mixed_case_matches = list(regex_patterns.MIXED_CASE_TECH_PATTERN.finditer(text))
        matches.extend(mixed_case_matches)

        # Sort matches by position and process in reverse order to maintain positions
        matches.sort(key=lambda m: m.start())

        # Remove duplicates and overlapping matches
        unique_matches: list[re.Match[str]] = []
        for match in matches:
            # Check if this match overlaps with any already added
            overlaps = False
            for existing in unique_matches:
                if match.start() < existing.end() and match.end() > existing.start():
                    # If there's overlap, keep the longer match
                    if len(match.group()) > len(existing.group()):
                        unique_matches.remove(existing)
                    else:
                        overlaps = True
                        break
            if not overlaps:
                unique_matches.append(match)

        # Process in reverse order to maintain positions
        for i, match in enumerate(reversed(unique_matches)):
            placeholder = f"__CAPS_{len(unique_matches) - i - 1}__"
            all_caps_words[placeholder] = match.group()
            # old_len = len(text)  # Unused variable
            text = text[: match.start()] + placeholder + text[match.end() :]

        # Preserve placeholders and entities
        placeholder_pattern = r"__PLACEHOLDER_\d+__|__ENTITY_\d+__|__CAPS_\d+__"
        placeholders_found = re.findall(placeholder_pattern, text)

        # Apply proper noun capitalization using spaCy NER
        text = self._capitalize_proper_nouns(text, entities or [], doc=doc)

        # Only capitalize after clear sentence endings with space, but not for abbreviations like i.e., e.g.
        def capitalize_after_sentence(match):
            punctuation_and_space = match.group(1)
            letter = match.group(2)
            letter_pos = match.start() + len(punctuation_and_space)

            # Check if the letter is inside ANY entity - entities should control their own formatting
            if self.protection.is_entity_protected_from_sentence_capitalization(letter_pos, entities):
                return match.group(0)  # Don't capitalize - let entity handle formatting

            # Check the text before the match to see if it's an abbreviation
            context = self.context.get_sentence_capitalization_context(text, match.start())
            if context["follows_abbreviation"]:
                return match.group(0)  # Don't capitalize

            # For Spanish language, check if we should preserve case based on entity context
            if self.language == "es":
                should_capitalize = self._should_capitalize_word_spanish(text, letter_pos, letter, entities)
                if not should_capitalize:
                    return match.group(0)  # Don't capitalize

            return punctuation_and_space + letter.upper()

        text = re.sub(r"([.!?]\s+)([a-z])", capitalize_after_sentence, text)

        # Fix capitalization after abbreviations: don't capitalize letters immediately after abbreviations like "i.e. "
        # This needs to handle both uppercase and lowercase letters since punctuation might have already capitalized them
        def protect_after_abbreviation(match):
            abbrev_and_space = match.group(1)  # "i.e. "
            letter = match.group(2)  # "t" or "T"
            return abbrev_and_space + letter.lower()  # Force lowercase

        # Build pattern from constants - match both upper and lowercase letters  
        abbrev_pattern = self.rules.get_common_abbreviations_pattern()
        text = re.sub(rf"(\b(?:{abbrev_pattern})\s+)([a-zA-Z])", protect_after_abbreviation, text)

        # Fix first letter capitalization with entity protection and entity type rules
        if text and text[0].islower():
            # Find the first alphabetic character to potentially capitalize
            first_letter_index = -1
            for i, char in enumerate(text):
                if char.isalpha():
                    first_letter_index = i
                    break

            if first_letter_index != -1:
                # Check for entities that prevent sentence capitalization
                should_prevent = False
                if entities:
                    for entity in entities:
                        # Check if entity contains or starts at the first letter
                        if (entity.start <= first_letter_index < entity.end and 
                            self.rules.should_prevent_sentence_capitalization(entity.type, entity.text)):
                            logger.debug(f"Entity {entity.type} prevents sentence capitalization: '{entity.text}'")
                            should_prevent = True
                            break

                if not should_prevent:
                    should_capitalize = self.protection.should_capitalize_first_letter(
                        text, first_letter_index, entities
                    )

                    if should_capitalize:
                        logger.debug(f"Capitalizing first letter at index {first_letter_index}")
                        text = text[:first_letter_index] + text[first_letter_index].upper() + text[first_letter_index + 1 :]
                    else:
                        logger.debug("Not capitalizing first letter")
                else:
                    logger.debug("Not capitalizing first letter due to entity type rule")

        # Fix "i" pronoun using grammatical context
        if self.nlp:
            # IMPORTANT: Always create a fresh doc object on the current text
            # The passed-in doc was created on the original text and its token indices
            # are no longer valid after text modifications
            from .spacy_doc_cache import get_or_create_shared_doc
            try:
                # Force creation since text may have been modified
                doc_to_use = get_or_create_shared_doc(text, nlp_model=self.nlp, force_create=True)
                if doc_to_use is None:
                    raise ValueError("SpaCy document creation failed")
            except Exception as e:
                logger.warning(f"SpaCy-based 'i' capitalization failed: {e}")
                doc_to_use = None

            if doc_to_use:
                try:
                    text_chars = list(text)  # Work on a list of characters to avoid slicing errors
                    for token in doc_to_use:
                        # Find standalone 'i' tokens that are pronouns
                        if token.text == "i" and token.pos_ == "PRON":
                            # Enhanced context analysis for variable 'i'
                            is_variable_context = self._is_i_in_variable_assignment_context(token, doc_to_use)

                            # Check if this 'i' is inside a protected entity (like a filename)
                            is_protected = self.protection.is_position_inside_protected_entity(token.idx, entities)

                            if not is_protected and not is_variable_context:
                                # Safely replace the character at the correct index
                                text_chars[token.idx] = "I"
                    text = "".join(text_chars)  # Re-assemble the string once at the end
                except Exception as e:
                    logger.warning(f"SpaCy-based 'i' capitalization failed: {e}")
                    # If spaCy fails, do nothing. It's better to have a lowercase 'i'
                    # than to risk corrupting the text with the old regex method.
        else:
            # No SpaCy available, use regex approach with context check
            new_text = ""
            last_end = 0
            from .pattern_modules.common_patterns import PRONOUN_I_BASIC_PATTERN
            for match in re.finditer(PRONOUN_I_BASIC_PATTERN, text):
                start, end = match.span()
                new_text += text[last_end:start]

                is_protected = self.protection.is_position_inside_protected_entity(start, entities)
                is_part_of_identifier = self.context.is_part_of_identifier(text, start, end)
                is_variable_context = self.context.is_variable_context_for_i(text, start)
                
                # Special handling for 'i' VARIABLE entities - check if it's really a pronoun
                if is_protected and entities:
                    for entity in entities:
                        if (entity.start <= start < entity.end and 
                            entity.type.name == "VARIABLE" and entity.text == "i"):
                            # Check if this should be treated as pronoun despite being a VARIABLE entity
                            is_pronoun_context = self.protection._is_i_pronoun_context(text, start)
                            if is_pronoun_context:
                                is_protected = False  # Allow capitalization
                                logger.debug(f"Overriding VARIABLE protection for pronoun 'i' at position {start}")
                            break

                if not is_protected and not is_part_of_identifier and not is_variable_context:
                    new_text += "I"  # Capitalize
                else:
                    new_text += "i"  # Keep lowercase
                last_end = end

            new_text += text[last_end:]
            text = new_text

        # Post-processing: Fix any remaining abbreviation capitalization issues
        # Use simple string replacement to avoid regex complications
        for old, new in self.abbreviation_fixes.items():
            # Replace mid-text instances but preserve true sentence starts
            text = text.replace(f" {old}", f" {new}")
            text = text.replace(f": {old}", f": {new}")
            text = text.replace(f", {old}", f", {new}")

            # Fix at start only if not truly the beginning of input
            if text.startswith(old) and len(text) > len(old) + 5:
                text = new + text[len(old) :]

        # Apply uppercase abbreviations (case-insensitive matching)
        # But skip if the abbreviation is inside a protected entity
        for lower_abbrev, upper_abbrev in self.uppercase_abbreviations.items():
            # Use word boundaries to avoid partial matches
            # Match the abbreviation with word boundaries, case-insensitive
            pattern = r"\b" + re.escape(lower_abbrev) + r"\b"

            # If we have entities to protect, check each match before replacing
            if entities:
                # Find all matches first
                matches = list(re.finditer(pattern, text, flags=re.IGNORECASE))
                # Process in reverse order to maintain positions
                for match in reversed(matches):
                    match_start, match_end = match.span()

                    # Check if this match overlaps with any protected entity
                    is_protected = self.protection.should_protect_from_uppercase_conversion(
                        match_start, match_end, entities
                    )

                    if not is_protected:
                        # Safe to replace this match
                        text = text[:match_start] + upper_abbrev + text[match_end:]

            else:
                # No entities to protect, do normal replacement
                text = re.sub(pattern, upper_abbrev, text, flags=re.IGNORECASE)

        # Restore original case for placeholders
        text = self.protection.restore_placeholders(text, placeholder_pattern)

        # Restore all-caps words (acronyms) - use regex replacement to avoid mangling
        for placeholder, caps_word in all_caps_words.items():
            text = re.sub(rf"\b{re.escape(placeholder)}\b", caps_word, text)

        return text

    def _capitalize_proper_nouns(self, text: str, entities: list[Entity] | None = None, doc=None) -> str:
        """Capitalize proper nouns using spaCy NER and known patterns"""
        # First try rule-based proper noun detection (works without spaCy)
        text = self._apply_rule_based_proper_nouns(text, entities)
        
        if not self.nlp:
            # No spaCy available, but we've applied rule-based detection
            logger.debug("SpaCy not available, using rule-based proper noun detection only")
            return text

        # Skip SpaCy processing if text contains placeholders
        # The entity positions become invalid after placeholder substitution
        if self.protection.has_placeholders(text):
            logger.debug("Skipping SpaCy proper noun capitalization due to placeholders in text")
            return text

        doc_to_use = doc
        if doc_to_use is None:
            # Use shared document processor for proper noun capitalization
            from .spacy_doc_cache import get_or_create_shared_doc
            try:
                doc_to_use = get_or_create_shared_doc(text, nlp_model=self.nlp)
                if doc_to_use is None:
                    raise ValueError("SpaCy document creation failed")
            except (AttributeError, ValueError, IndexError) as e:
                logger.debug(f"Error in spaCy proper noun capitalization: {e}")
                return text

        try:
            # Build list of entities to capitalize using context analyzer
            entities_to_capitalize = self.context.analyze_proper_noun_entities(doc_to_use, text, entities)
            
            # Handle technical verb replacements separately
            for ent in doc_to_use.ents:
                if ent.label_ in ["PERSON", "ORG"]:
                    should_replace, replacement = self.context.should_handle_technical_verb_capitalization(
                        ent.text, ent.label_
                    )
                    if should_replace and replacement:
                        text = text[: ent.start_char] + replacement + text[ent.end_char :]

            # Sort by position (reverse order to maintain indices)
            entities_to_capitalize.sort(key=lambda x: x[0], reverse=True)

            # Apply capitalizations
            for start, end, entity_text in entities_to_capitalize:
                if start < len(text) and end <= len(text):
                    # Skip placeholders - they should not be capitalized
                    if self.protection.is_placeholder_context(text, start, end):
                        continue

                    # Check if this position overlaps with any protected entity
                    is_protected = self.protection.should_protect_from_spacy_capitalization(start, end, entities)
                    if is_protected:
                        continue

                    # Capitalize the proper noun while preserving the original entity text
                    capitalized = entity_text.title()
                    text = text[:start] + capitalized + text[end:]

            return text

        except (AttributeError, ValueError, IndexError) as e:
            logger.debug(f"Error in spaCy proper noun capitalization: {e}")
            # Return text unchanged on error
            return text

    def _apply_rule_based_proper_nouns(self, text: str, entities: list[Entity] | None = None) -> str:
        """Apply rule-based proper noun capitalization using the proper_nouns resource list."""
        proper_nouns = self.resources.get("technical", {}).get("proper_nouns", [])
        
        if not proper_nouns:
            logger.debug("No proper nouns list found in resources")
            return text
        
        # Use regex to find and replace proper nouns while preserving punctuation
        replacements = []
        
        for proper_noun in proper_nouns:
            # Create a regex pattern for case-insensitive word boundary matching
            # This will match the word with optional leading/trailing punctuation
            pattern = r'\b' + re.escape(proper_noun.lower()) + r'\b'
            
            for match in re.finditer(pattern, text, re.IGNORECASE):
                start, end = match.span()
                matched_text = match.group()
                
                # Check if this position is protected by entities
                is_protected = False
                if entities:
                    for entity in entities:
                        if start < entity.end and end > entity.start:
                            # Special case: PORT_NUMBER entities should allow proper noun capitalization
                            # of the server/service name part (e.g., "redis" in "redis:6379")
                            if entity.type.name == "PORT_NUMBER":
                                # Allow capitalization if the matched text is at the start of the entity
                                # and ends before the colon (i.e., it's the server name part)
                                entity_text = text[entity.start:entity.end]
                                if ":" in entity_text:
                                    server_part_end = entity.start + entity_text.find(":")
                                    if start >= entity.start and end <= server_part_end:
                                        # This is the server name part, allow capitalization
                                        logger.debug(f"Allowing proper noun capitalization in PORT_NUMBER server name: '{matched_text}'")
                                        continue  # Don't set is_protected = True
                                        
                            is_protected = True
                            logger.debug(f"Proper noun '{matched_text}' at {start}-{end} is protected by entity {entity.type}")
                            break
                
                if not is_protected:
                    # Special case: Don't capitalize temporal words when used as adverbs
                    # "Today", "Tomorrow", "Yesterday" should only be capitalized as proper nouns (newspaper names)
                    temporal_words = {"today", "tomorrow", "yesterday"}
                    if proper_noun.lower() in temporal_words:
                        # Check if this is being used as a temporal adverb rather than proper noun
                        # Look for preceding context that suggests temporal usage
                        preceding_context = text[max(0, start-20):start].lower().strip()
                        temporal_indicators = ["watch", "see", "check", "buy", "sell", "trade", "monitor", 
                                             "look at", "analyze", "track", "follow", "review", "until", 
                                             "by", "on", "for", "since", "from"]
                        
                        # If preceded by temporal indicators, treat as adverb (don't capitalize)
                        is_temporal_adverb = any(indicator in preceding_context for indicator in temporal_indicators)
                        
                        if is_temporal_adverb:
                            logger.debug(f"Skipping capitalization of '{matched_text}' - temporal adverb context")
                            continue
                    
                    # Replace with proper capitalization, preserving case pattern of original
                    if matched_text.islower():
                        replacement = proper_noun
                    elif matched_text.isupper():
                        replacement = proper_noun.upper()
                    else:
                        replacement = proper_noun  # Use standard capitalization
                    
                    replacements.append((start, end, replacement))
                    logger.debug(f"Rule-based proper noun: '{matched_text}' -> '{replacement}'")
        
        # Apply replacements in reverse order to maintain positions
        replacements.sort(key=lambda x: x[0], reverse=True)
        for start, end, replacement in replacements:
            text = text[:start] + replacement + text[end:]
            
        return text

    def _is_i_in_variable_assignment_context(self, token, doc) -> bool:
        """Check if 'i' token is in a variable/assignment context using spaCy analysis.
        
        Args:
            token: SpaCy token representing 'i'
            doc: SpaCy document
            
        Returns:
            True if 'i' appears to be a variable in assignment context
        """
        try:
            # Look for assignment patterns (i = , i equals, etc.)
            next_tokens = []
            for j in range(token.i + 1, min(token.i + 4, len(doc))):
                next_tokens.append(doc[j])
            
            # Check for immediate assignment patterns
            if next_tokens:
                # Check for "i equals" or "i ="
                if (next_tokens[0].lemma_ in ["equal", "="] or 
                    (len(next_tokens) > 1 and 
                     next_tokens[0].lemma_ == "equal" and next_tokens[1].lemma_ == "equal")):
                    logger.debug(f"Found assignment pattern after 'i' at position {token.idx}")
                    return True
                    
                # Check for increment/decrement: "i++" or "i--"
                if (next_tokens[0].text in ["++", "--"] or
                    (len(next_tokens) > 1 and 
                     next_tokens[0].text == "+" and next_tokens[1].text == "+")):
                    logger.debug(f"Found increment/decrement pattern after 'i' at position {token.idx}")
                    return True
            
            # Look for explicit variable context words before 'i'
            prev_tokens = []
            for j in range(max(0, token.i - 5), token.i):
                prev_tokens.append(doc[j])
                
            if prev_tokens:
                prev_lemmas = [t.lemma_.lower() for t in prev_tokens]
                variable_words = ["variable", "counter", "iterator", "letter", "write", "set"]
                if any(word in prev_lemmas for word in variable_words):
                    logger.debug(f"Found variable context words before 'i' at position {token.idx}")
                    return True
            
            # Special case: "when i write i" - only the second i should be treated as variable
            # Check if this is part of "write i equals" pattern
            if (token.i >= 2 and 
                doc[token.i - 1].lemma_ == "write" and
                doc[token.i - 2].lemma_ == "i"):
                logger.debug(f"Found 'write i' pattern - treating as variable context at position {token.idx}")
                return True
                
        except (IndexError, AttributeError) as e:
            logger.debug(f"Error in variable assignment context analysis: {e}")
            
        return False

    def _is_technical_term(self, entity_text: str, full_text: str) -> bool:
        """Check if a PERSON entity is actually a technical term that shouldn't be capitalized.
        
        Deprecated: Use context.is_technical_term() instead.
        """
        return self.context.is_technical_term(entity_text, full_text)

    def _should_capitalize_word_spanish(self, text: str, word_pos: int, word: str, entities: list[Entity] = None) -> bool:
        """Determine if a word should be capitalized in Spanish context.
        
        Args:
            text: Full text context
            word_pos: Position of the word in text
            word: The word to potentially capitalize
            entities: List of entities that may influence capitalization
            
        Returns:
            True if the word should be capitalized, False otherwise
        """
        if not entities:
            return True  # Default capitalization when no entities present
        
        # Find entities that precede this word position
        preceding_entities = []
        for entity in entities:
            if entity.end_char <= word_pos and (word_pos - entity.end_char) <= 10:  # Within 10 chars
                preceding_entities.append(entity)
        
        # If no recent preceding entities, use default capitalization
        if not preceding_entities:
            return True
        
        # Get the most recent entity
        recent_entity = max(preceding_entities, key=lambda e: e.end_char)
        
        # Extract the word that would follow the entity
        start_search = recent_entity.end_char
        end_search = min(word_pos + len(word), len(text))
        following_text = text[start_search:end_search].strip()
        
        # Extract just the first word after the entity
        following_word = following_text.split()[0] if following_text.split() else word
        
        # Use the context analyzer to make the decision
        should_capitalize = self.context.should_capitalize_after_entity(
            recent_entity.type.name if hasattr(recent_entity.type, 'name') else str(recent_entity.type),
            following_word,
            text
        )
        
        logger.debug(f"Spanish capitalization decision for '{word}' after {recent_entity.type}: {should_capitalize}")
        return should_capitalize
