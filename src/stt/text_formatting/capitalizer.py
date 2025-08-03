#!/usr/bin/env python3
"""Smart capitalization module for Matilda transcriptions."""
from __future__ import annotations

import re

from stt.core.config import setup_logging

# Import centralized regex patterns
from . import regex_patterns

# Import common data structures
from .common import Entity, EntityType

# Import resource loader for i18n constants
from .constants import get_resources
from .nlp_provider import get_nlp
from .utils import is_inside_entity

# Setup logging
logger = setup_logging(__name__, log_filename="text_formatting.txt", include_console=False)


class SmartCapitalizer:
    """Intelligent capitalization using SpaCy POS tagging"""

    def __init__(self, language: str = "en"):
        self.nlp = get_nlp()
        self.language = language

        # Load language-specific resources
        self.resources = get_resources(language)

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
            # Note: PORT_NUMBER removed - host names before port should be capitalized normally
            # Note: VERSION removed - version numbers at sentence start should be capitalized
            EntityType.ASSIGNMENT,
            EntityType.COMPARISON,
            # Note: CLI_COMMAND removed - they should be capitalized at sentence start
            # Note: ABBREVIATION removed - abbreviations should be capitalized at sentence start
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

    def capitalize(self, text: str, entities: list[Entity] | None = None, doc=None) -> str:
        """Apply intelligent capitalization with entity protection"""
        if not text:
            return text

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
            if entities:
                for entity in entities:
                    if entity.start <= letter_pos < entity.end:
                        return match.group(0)  # Don't capitalize - let entity handle formatting

            # Check the text before the match to see if it's an abbreviation
            preceding_text = text[: match.start()].lower()
            common_abbreviations = self.resources.get("technical", {}).get("common_abbreviations", [])
            if any(preceding_text.endswith(abbrev) for abbrev in common_abbreviations):
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
        common_abbreviations = self.resources.get("technical", {}).get("common_abbreviations", [])
        abbrev_pattern = "|".join(abbrev.replace(".", "\\.") for abbrev in common_abbreviations)
        text = re.sub(rf"(\b(?:{abbrev_pattern})\s+)([a-zA-Z])", protect_after_abbreviation, text)

        # Fix first letter capitalization with entity protection
        if text and text[0].islower():
            # Find the first alphabetic character to potentially capitalize
            first_letter_index = -1
            for i, char in enumerate(text):
                if char.isalpha():
                    first_letter_index = i
                    break

            if first_letter_index != -1:
                should_capitalize = True

                # Check for protected entities at the start
                for entity in entities or []:
                    if entity.start <= first_letter_index < entity.end:
                        logger.debug(
                            f"Checking entity at start: {entity.type} '{entity.text}' [{entity.start}:{entity.end}], first_letter_index={first_letter_index}"
                        )
                        # Don't capitalize if it's a strictly protected type
                        if entity.type in self.STRICTLY_PROTECTED_TYPES:
                            logger.debug(f"Entity {entity.type} is strictly protected")
                            should_capitalize = False
                            break
                        # Special rule for CLI commands: only keep lowercase if the *entire* text is the command
                        if entity.type == EntityType.CLI_COMMAND:
                            if entity.text.strip() == text.strip():
                                logger.debug("CLI command is entire text, not capitalizing")
                                should_capitalize = False
                                break
                            logger.debug(
                                f"CLI command '{entity.text}' is not entire text '{text}', allowing capitalization"
                            )
                            # Otherwise, allow normal capitalization for CLI commands at sentence start
                        # Special rule for versions starting with 'v' (e.g., v1.2)
                        elif entity.type == EntityType.VERSION and entity.text.startswith("v"):
                            logger.debug(f"Version entity '{entity.text}' starts with 'v', not capitalizing")
                            should_capitalize = False
                            break
                        # Special case: Allow capitalization of sentence-starting programming keywords
                        elif entity.type == EntityType.PROGRAMMING_KEYWORD and entity.start == 0:
                            logger.debug(
                                f"Allowing capitalization of sentence-starting programming keyword: '{entity.text}'"
                            )
                            # Don't protect - allow capitalization
                            break

                if should_capitalize:
                    logger.debug(f"Capitalizing first letter at index {first_letter_index}")
                    text = text[:first_letter_index] + text[first_letter_index].upper() + text[first_letter_index + 1 :]
                else:
                    logger.debug("Not capitalizing first letter")

        # Fix "i" pronoun using grammatical context
        if self.nlp:
            # IMPORTANT: Always create a fresh doc object on the current text
            # The passed-in doc was created on the original text and its token indices
            # are no longer valid after text modifications
            try:
                doc_to_use = self.nlp(text)
            except Exception as e:
                logger.warning(f"SpaCy-based 'i' capitalization failed: {e}")
                doc_to_use = None

            if doc_to_use:
                try:
                    text_chars = list(text)  # Work on a list of characters to avoid slicing errors
                    for token in doc_to_use:
                        # Find standalone 'i' tokens that are pronouns
                        if token.text == "i" and token.pos_ == "PRON":
                            # NEW: Add context check for variable 'i'
                            is_variable_context = False
                            if token.i > 0:
                                prev_token = doc_to_use[token.i - 1]
                                if prev_token.lemma_ in ["variable", "letter", "iterator", "counter", "character"]:
                                    is_variable_context = True

                            # Check if this 'i' is inside a protected entity (like a filename)
                            is_protected = False
                            if entities:
                                is_protected = any(entity.start <= token.idx < entity.end for entity in entities)

                            if not is_protected and not is_variable_context:  # <-- ADDED CHECK
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
            for match in re.finditer(r"\bi\b", text):
                start, end = match.span()
                new_text += text[last_end:start]

                is_protected = False
                if entities:
                    is_protected = any(entity.start <= start < entity.end for entity in entities)

                is_part_of_identifier = (start > 0 and text[start - 1] in "_-") or (
                    end < len(text) and text[end] in "_-"
                )

                # Add context check for variable 'i'
                preceding_text = text[max(0, start - 25) : start].lower()
                is_variable_context = any(
                    keyword in preceding_text
                    for keyword in ["variable is", "counter is", "iterator is", "for i in", "variable i", "letter i"]
                )

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
                    # matched_text = text[match_start:match_end]  # Unused variable

                    # Check if this match overlaps with any protected entity
                    is_protected = any(
                        match_start < entity.end
                        and match_end > entity.start
                        and entity.type
                        in {
                            EntityType.URL,
                            EntityType.SPOKEN_URL,
                            EntityType.EMAIL,
                            EntityType.SPOKEN_EMAIL,
                            EntityType.FILENAME,
                            EntityType.ASSIGNMENT,
                            EntityType.INCREMENT_OPERATOR,
                            EntityType.DECREMENT_OPERATOR,
                            EntityType.COMMAND_FLAG,
                            EntityType.PORT_NUMBER,
                            EntityType.ABBREVIATION,  # Protect abbreviations from uppercase conversion
                        }
                        for entity in entities
                    )

                    if not is_protected:
                        # Safe to replace this match
                        # old_text = text  # Unused variable
                        text = text[:match_start] + upper_abbrev + text[match_end:]

            else:
                # No entities to protect, do normal replacement
                text = re.sub(pattern, upper_abbrev, text, flags=re.IGNORECASE)

        # Restore original case for placeholders
        for placeholder in placeholders_found:
            text = re.sub(placeholder, placeholder, text, flags=re.IGNORECASE)

        # Restore all-caps words (acronyms) - use regex replacement to avoid mangling
        for placeholder, caps_word in all_caps_words.items():
            text = re.sub(rf"\b{re.escape(placeholder)}\b", caps_word, text)

        return text

    def _capitalize_proper_nouns(self, text: str, entities: list[Entity] | None = None, doc=None) -> str:
        """Capitalize proper nouns using spaCy NER and known patterns"""
        if not self.nlp:
            # No spaCy available, return text unchanged
            return text

        # Skip SpaCy processing if text contains placeholders
        # The entity positions become invalid after placeholder substitution
        if "__CAPS_" in text or "__PLACEHOLDER_" in text or "__ENTITY_" in text:
            logger.debug("Skipping SpaCy proper noun capitalization due to placeholders in text")
            return text

        doc_to_use = doc
        if doc_to_use is None:
            try:
                doc_to_use = self.nlp(text)
            except (AttributeError, ValueError, IndexError) as e:
                logger.debug(f"Error in spaCy proper noun capitalization: {e}")
                return text

        try:

            # Build list of entities to capitalize
            entities_to_capitalize = []

            # Add spaCy detected named entities
            for ent in doc_to_use.ents:
                logger.debug(f"SpaCy found entity: '{ent.text}' ({ent.label_}) at {ent.start_char}-{ent.end_char}")
                if ent.label_ in [
                    "PERSON",
                    "ORG",
                    "GPE",
                    "NORP",
                    "LANGUAGE",
                    "EVENT",
                ]:  # Types that should be capitalized

                    # Skip pi constant to prevent capitalization
                    if ent.text.lower() == "pi":
                        logger.debug(f"Skipping pi constant '{ent.text}' to allow MATH_CONSTANT converter to handle it")
                        continue

                    # Skip if this SpaCy entity is inside a final filtered entity
                    if entities and is_inside_entity(ent.start_char, ent.end_char, entities):
                        logger.debug(
                            f"Skipping SpaCy-detected entity '{ent.text}' because it is inside a final filtered entity."
                        )
                        continue

                    # Skip PERSON entities that are likely technical terms in coding contexts
                    if ent.label_ == "PERSON" and self._is_technical_term(ent.text.lower(), text):
                        logger.debug(f"Skipping PERSON entity '{ent.text}' - detected as technical term")
                        continue

                    # Skip PERSON or ORG entities that are technical verbs (let, const, var, etc.)
                    technical_verbs = self.resources.get("technical", {}).get("verbs", [])
                    if ent.label_ in ["PERSON", "ORG"] and ent.text.isupper() and ent.text.lower() in technical_verbs:
                        # It's an all-caps technical term, replace with lowercase version
                        text = text[: ent.start_char] + ent.text.lower() + text[ent.end_char :]
                        continue  # Move to the next SpaCy entity

                    if ent.label_ in ["PERSON", "ORG"] and ent.text.lower() in technical_verbs:
                        logger.debug(f"Skipping capitalization for technical verb: '{ent.text}'")
                        continue

                    logger.debug(f"Adding '{ent.text}' to capitalize list (type: {ent.label_})")
                    entities_to_capitalize.append((ent.start_char, ent.end_char, ent.text))

            # Sort by position (reverse order to maintain indices)
            entities_to_capitalize.sort(key=lambda x: x[0], reverse=True)

            # Apply capitalizations
            for start, end, entity_text in entities_to_capitalize:
                if start < len(text) and end <= len(text):
                    # Skip placeholders - they should not be capitalized
                    # Check the actual text at this position, not just the entity text
                    actual_text = text[start:end]
                    # Also check if we're inside a placeholder by looking at surrounding context
                    context_start = max(0, start - 2)
                    context_end = min(len(text), end + 2)
                    context = text[context_start:context_end]

                    if "__" in context or actual_text.strip(".,!?").endswith("__"):
                        continue

                    # Check if this position overlaps with any protected entity
                    is_protected = False
                    if entities:
                        for entity in entities:
                            # Check if the SpaCy entity overlaps with any protected entity
                            if start < entity.end and end > entity.start:
                                logger.debug(
                                    f"SpaCy entity '{entity_text}' at {start}-{end} overlaps with protected entity {entity.type} at {entity.start}-{entity.end}"
                                )
                                # Skip capitalization for URL and email entities specifically
                                if entity.type in {
                                    EntityType.URL,
                                    EntityType.SPOKEN_URL,
                                    EntityType.EMAIL,
                                    EntityType.SPOKEN_EMAIL,
                                    EntityType.FILENAME,
                                    EntityType.ASSIGNMENT,
                                    EntityType.INCREMENT_OPERATOR,
                                    EntityType.DECREMENT_OPERATOR,
                                    EntityType.COMMAND_FLAG,
                                    EntityType.PORT_NUMBER,
                                }:
                                    logger.debug(
                                        f"Protecting entity '{entity_text}' from capitalization due to {entity.type}"
                                    )
                                    is_protected = True
                                    break
                                logger.debug(
                                    f"Entity type {entity.type} not in protected list, allowing capitalization"
                                )

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

    def _is_technical_term(self, entity_text: str, full_text: str) -> bool:
        """Check if a PERSON entity is actually a technical term that shouldn't be capitalized."""
        # Use technical terms from constants

        # Check exact match for multi-word terms
        multi_word_technical = set(self.resources.get("context_words", {}).get("multi_word_commands", []))
        if entity_text.lower() in multi_word_technical:
            return True

        # Check single words in the entity
        entity_words = entity_text.lower().split()
        technical_terms = set(self.resources.get("technical", {}).get("terms", []))
        if any(word in technical_terms for word in entity_words):
            return True

        # Check context - if surrounded by technical keywords, likely technical

        # Check words around the entity
        full_text_lower = full_text.lower()
        words = full_text_lower.split()

        try:
            entity_index = words.index(entity_text)
            # Check 2 words before and after
            context_start = max(0, entity_index - 2)
            context_end = min(len(words), entity_index + 3)
            context_words = words[context_start:context_end]

            technical_context_words = set(self.resources.get("context_words", {}).get("technical_context", []))
            if any(word in technical_context_words for word in context_words):
                return True
        except ValueError:
            # Entity not found as single word, might be multi-word
            pass

        return False
