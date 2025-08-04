#!/usr/bin/env python3
"""Code-related entity detection and conversion for Matilda transcriptions."""
from __future__ import annotations

import re

from stt.core.config import setup_logging
from stt.text_formatting import regex_patterns
from stt.text_formatting.common import Entity, EntityType
from stt.text_formatting.constants import get_resources
from stt.text_formatting.utils import is_inside_entity, overlaps_with_entity

logger = setup_logging(__name__, log_filename="text_formatting.txt", include_console=False)


class CodeEntityDetector:
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

        # Load language-specific resources
        self.resources = get_resources(language)

        # Build patterns dynamically for the specified language
        self.slash_command_pattern = regex_patterns.get_slash_command_pattern(language)
        self.underscore_delimiter_pattern = regex_patterns.get_underscore_delimiter_pattern(language)
        self.simple_underscore_pattern = regex_patterns.get_simple_underscore_pattern(language)
        self.long_flag_pattern = regex_patterns.get_long_flag_pattern(language)
        self.short_flag_pattern = regex_patterns.get_short_flag_pattern(language)
        self.assignment_pattern = regex_patterns.get_assignment_pattern(language)

    def detect(self, text: str, entities: list[Entity]) -> list[Entity]:
        """Detects all code-related entities."""
        code_entities: list[Entity] = []

        # Start with existing entities and build cumulatively
        all_entities = entities[:]  # Start with copy of existing entities

        self._detect_filenames(text, code_entities, all_entities)
        all_entities = entities[:] + code_entities  # Update with found entities (preserve cumulative state)

        self._detect_cli_commands(text, code_entities, all_entities)
        all_entities = entities[:] + code_entities  # Update with found entities (preserve cumulative state)

        self._detect_programming_keywords(text, code_entities, all_entities)
        all_entities = entities[:] + code_entities  # Update with found entities (preserve cumulative state)

        self._detect_spoken_operators(text, code_entities, all_entities)
        all_entities = entities[:] + code_entities  # Update with found entities (preserve cumulative state)

        self._detect_assignment_operators(text, code_entities, all_entities)
        all_entities = entities[:] + code_entities  # Update with found entities (preserve cumulative state)

        self._detect_abbreviations(text, code_entities, all_entities)
        all_entities = entities[:] + code_entities  # Update with found entities (preserve cumulative state)

        self._detect_underscore_delimiters(text, code_entities, all_entities)
        all_entities = entities[:] + code_entities  # Update with found entities (preserve cumulative state)

        self._detect_simple_underscore_variables(text, code_entities, all_entities)
        all_entities = entities[:] + code_entities  # Update with found entities (preserve cumulative state)

        self._detect_command_flags(text, code_entities, all_entities)
        all_entities = entities[:] + code_entities  # Update with found entities (preserve cumulative state)

        self._detect_preformatted_flags(text, code_entities, all_entities)
        all_entities = entities[:] + code_entities  # Update with found entities (preserve cumulative state)

        self._detect_slash_commands(text, code_entities, all_entities)

        logger.debug(f"CodeEntityDetector found {len(code_entities)} entities in '{text}'")
        for entity in code_entities:
            logger.debug(f"  - {entity.type}: '{entity.text}' [{entity.start}:{entity.end}]")

        return code_entities

    def _detect_filenames(self, text: str, entities: list[Entity], all_entities: list[Entity] | None = None) -> None:
        """Detect filenames using a simple regex anchor and robust spaCy context analysis."""
        if all_entities is None:
            all_entities = entities

        # --- Part 1: Handle already-formatted files first (e.g., main.py, com.example.app) ---
        for match in regex_patterns.FILENAME_WITH_EXTENSION_PATTERN.finditer(text):
            if not overlaps_with_entity(match.start(), match.end(), all_entities):
                new_entity = Entity(start=match.start(), end=match.end(), text=match.group(0), type=EntityType.FILENAME)
                entities.append(new_entity)
                all_entities.append(new_entity)

        for match in regex_patterns.JAVA_PACKAGE_PATTERN.finditer(text):
            if not overlaps_with_entity(match.start(), match.end(), all_entities):
                package_text = match.group(1).lower()
                common_prefixes = ["com dot", "org dot", "net dot", "io dot", "gov dot", "edu dot"]
                if any(package_text.startswith(prefix) for prefix in common_prefixes):
                    new_entity = Entity(
                        start=match.start(),
                        end=match.end(),
                        text=match.group(0),
                        type=EntityType.FILENAME,
                        metadata={"is_package": True},
                    )
                    entities.append(new_entity)
                    all_entities.append(new_entity)

        # --- Part 2: Handle spoken filenames ("my file dot py") with a robust, non-greedy method ---
        if not self.nlp:
            logger.debug("SpaCy model not available. Using regex fallback for spoken filename detection.")
            self._detect_filenames_regex_fallback(text, entities, all_entities)
            return

        entities_before_spacy = len(entities)

        try:
            doc = self.nlp(text)
        except (AttributeError, ValueError, IndexError) as e:
            logger.warning(f"SpaCy filename detection failed: {e}")
            self._detect_filenames_regex_fallback(text, entities, all_entities)
            return

        end_char_to_token = {token.idx + len(token.text): token for token in doc}

        for match in regex_patterns.SPOKEN_DOT_FILENAME_PATTERN.finditer(text):
            if overlaps_with_entity(match.start(), match.end(), all_entities):
                continue

            logger.debug(
                f"SPACY FILENAME: Found 'dot extension' match: '{match.group()}' at {match.start()}-{match.end()}"
            )

            if " at " in text[max(0, match.start() - 10) : match.start()]:
                continue

            start_of_dot = match.start()
            if start_of_dot not in end_char_to_token:
                logger.debug(f"SPACY FILENAME: No token ends at position {start_of_dot}, skipping")
                continue

            current_token = end_char_to_token[start_of_dot]
            filename_tokens: list = []

            # Walk backwards from the token before "dot"
            for i in range(current_token.i, -1, -1):
                token = doc[i]

                # ** THE CRITICAL STOPPING LOGIC **
                # Get language-specific filename stop words from i18n resources
                filename_actions = self.resources.get("context_words", {}).get("filename_actions", [])
                filename_linking = self.resources.get("context_words", {}).get("filename_linking", [])
                filename_stop_words = self.resources.get("context_words", {}).get("filename_stop_words", [])

                is_action_verb = token.lemma_ in filename_actions
                is_linking_verb = token.lemma_ in filename_linking
                is_stop_word = token.text.lower() in filename_stop_words
                is_punctuation = token.is_punct
                is_separator = token.pos_ in ("ADP", "CCONJ", "SCONJ") and token.text.lower() != "v"

                # Special handling for "file" - stop if preceded by articles or stop words
                if token.text.lower() == "file" and i > 0:
                    prev_token = doc[i - 1].text.lower()
                    if prev_token in ["the", "a", "an", "this", "that"] or prev_token in filename_stop_words:
                        break

                # Don't treat "file" as a stop word if it's part of a compound filename
                # Allow "file" when it's at the start OR when it's clearly part of a filename phrase
                is_file_in_compound = token.text.lower() == "file" and (
                    len(filename_tokens) == 0  # At start (like "makefile")
                    or (
                        len(filename_tokens) > 0
                        and filename_tokens[-1].text.lower() not in ["the", "a", "an", "this", "that"]
                    )
                )
                is_stop_word_filtered = is_stop_word and not is_file_in_compound

                if is_action_verb or is_linking_verb or is_stop_word_filtered or is_punctuation or is_separator:
                    logger.debug(
                        f"SPACY FILENAME: Stopping at token '{token.text}' (action:{is_action_verb}, link:{is_linking_verb}, stop:{is_stop_word}, punc:{is_punctuation}, sep:{is_separator})"
                    )
                    break

                if len(filename_tokens) >= 8:
                    break

                filename_tokens.insert(0, token)

            if not filename_tokens:
                continue

            start_pos = filename_tokens[0].idx
            end_pos = match.end()
            entity_text = text[start_pos:end_pos]

            if not overlaps_with_entity(start_pos, end_pos, all_entities):
                new_entity = Entity(start=start_pos, end=end_pos, text=entity_text, type=EntityType.FILENAME)
                entities.append(new_entity)
                all_entities.append(new_entity)
                logger.debug(f"SPACY FILENAME: Created filename entity: '{entity_text}'")
            else:
                logger.debug("SPACY FILENAME: Entity overlaps with existing entity, skipping")

        if len(entities) == entities_before_spacy:
            logger.debug("SpaCy filename detection found no new entities, trying regex fallback")
            self._detect_filenames_regex_fallback(text, entities, all_entities)

    def _detect_spoken_operators(
        self, text: str, entities: list[Entity], all_entities: list[Entity] | None = None
    ) -> None:
        """
        Detect spoken operators using SpaCy token context analysis.

        This method detects patterns like "variable plus plus" or "count minus minus"
        using token analysis to ensure they're used in valid programming contexts.
        """
        if not self.nlp:
            logger.debug("SpaCy not available for spoken operator detection, using regex fallback")
            self._detect_spoken_operators_regex(text, entities, all_entities)
            return
        try:
            doc = self.nlp(text)
        except (AttributeError, ValueError, IndexError) as e:
            logger.warning(f"SpaCy operator detection failed: {e}")
            return
        logger.debug(f"Processing text for operators: '{text}'")

        # Get operator keywords for the current language
        operators = get_resources(self.language)["spoken_keywords"]["operators"]

        # Build a map of operator patterns to their symbols
        operator_patterns = {}
        for pattern, symbol in operators.items():
            operator_patterns[pattern.lower()] = symbol

        # Iterate through tokens to find operator patterns
        for i, token in enumerate(doc):
            # Check for multi-word operators
            if i + 1 < len(doc):
                two_word_pattern = f"{token.text.lower()} {doc[i + 1].text.lower()}"
                if two_word_pattern in operator_patterns:
                    logger.debug(f"Found '{two_word_pattern}' pattern at token {i}")

                    # Check if there's a preceding token that could be a variable
                    if i > 0:
                        prev_token = doc[i - 1]
                        # Check if the preceding token is a valid variable name
                        # Include single letter pronouns like 'i' which SpaCy tags as PRON
                        if (
                            (
                                prev_token.pos_ in ["NOUN", "PROPN", "SYM", "VERB"]
                                or (prev_token.pos_ == "PRON" and len(prev_token.text) == 1)
                            )  # Single letter like 'i'
                            and prev_token.text.isalpha()
                            and prev_token.text.lower() not in {"the", "a", "an", "this", "that"}
                        ):
                            symbol = operator_patterns[two_word_pattern]
                            
                            # For comparison operators, check if there's a following value
                            if symbol == "==":
                                # Check if there's a next token that could be a value
                                if i + 2 < len(doc):
                                    next_token = doc[i + 2]
                                    if (next_token.is_alpha and not next_token.is_stop) or next_token.like_num or next_token.text.lower() in ["true", "false", "null"]:
                                        # Create comparison entity spanning variable + operator + value
                                        start_pos = prev_token.idx
                                        end_pos = next_token.idx + len(next_token.text)
                                        entity_text = text[start_pos:end_pos]
                                        
                                        check_entities = all_entities if all_entities else entities
                                        if not is_inside_entity(start_pos, end_pos, check_entities):
                                            entities.append(
                                                Entity(
                                                    start=start_pos,
                                                    end=end_pos,
                                                    text=entity_text,
                                                    type=EntityType.COMPARISON,
                                                    metadata={
                                                        "left": prev_token.text,
                                                        "right": next_token.text,
                                                        "operator": symbol,
                                                    },
                                                )
                                            )
                                            logger.debug(f"SpaCy detected {symbol} comparison: '{entity_text}' at {start_pos}-{end_pos}")
                            else:
                                # For increment/decrement operators, create entity spanning variable and operator
                                start_pos = prev_token.idx
                                end_pos = doc[i + 1].idx + len(doc[i + 1].text)
                                entity_text = text[start_pos:end_pos]

                                check_entities = all_entities if all_entities else entities
                                if not is_inside_entity(start_pos, end_pos, check_entities):
                                    entities.append(
                                        Entity(
                                            start=start_pos,
                                            end=end_pos,
                                            text=entity_text,
                                            type=(
                                                EntityType.INCREMENT_OPERATOR
                                                if symbol == "++"
                                                else EntityType.DECREMENT_OPERATOR
                                            ),
                                            metadata={
                                                "variable": prev_token.text,
                                                "operator": symbol,
                                            },
                                    )
                                )

                # Also check for three-word operators if present
                elif i + 2 < len(doc):
                    three_word_pattern = f"{token.text.lower()} {doc[i + 1].text.lower()} {doc[i + 2].text.lower()}"
                    if three_word_pattern in operator_patterns:
                        # Handle comparison operators like "equals equals"
                        if i > 0 and i + 3 < len(doc):
                            prev_token = doc[i - 1]
                            next_token = doc[i + 3]

                            # Check for variable on left and value/variable on right
                            is_left_var = prev_token.is_alpha and not prev_token.is_stop
                            is_right_var = (
                                (next_token.is_alpha and not next_token.is_stop)
                                or next_token.like_num
                                or next_token.text.lower() in ["true", "false", "null"]
                            )

                            if is_left_var and is_right_var:
                                # Check if there's an "if" before the comparison
                                start_pos = prev_token.idx
                                if i > 1 and doc[i - 2].text.lower() == "if":
                                    start_pos = doc[i - 2].idx

                                end_pos = next_token.idx + len(next_token.text)
                                entity_text = text[start_pos:end_pos]
                                check_entities = all_entities if all_entities else entities
                                if not is_inside_entity(start_pos, end_pos, check_entities):
                                    entities.append(
                                        Entity(
                                            start=start_pos,
                                            end=end_pos,
                                            text=entity_text,
                                            type=EntityType.COMPARISON,
                                            metadata={
                                                "left": prev_token.text,
                                                "right": next_token.text,
                                                "operator": operator_patterns[three_word_pattern],
                                            },
                                        )
                                    )

    def _detect_spoken_operators_regex(
        self, text: str, entities: list[Entity], all_entities: list[Entity] | None = None
    ) -> None:
        """Regex-based fallback for operator detection when spaCy is not available."""
        # Get operator keywords for the current language
        resources = get_resources(self.language)
        operators = resources.get("spoken_keywords", {}).get("operators", {})

        # Build patterns for all operators
        for operator_phrase, symbol in operators.items():
            if symbol in ["++", "--"]:
                # Build pattern: variable + operator phrase
                # Use word boundaries and allow for spaces in the operator phrase
                escaped_phrase = re.escape(operator_phrase)
                pattern = rf"\b([a-zA-Z_]\w*)\s+{escaped_phrase}\b"

                for match in re.finditer(pattern, text, re.IGNORECASE):
                    start_pos = match.start()
                    end_pos = match.end()
                    check_entities = all_entities if all_entities else entities

                    if not is_inside_entity(start_pos, end_pos, check_entities):
                        variable_name = match.group(1)
                        entity_type = EntityType.INCREMENT_OPERATOR if symbol == "++" else EntityType.DECREMENT_OPERATOR

                        entities.append(
                            Entity(
                                start=start_pos,
                                end=end_pos,
                                text=match.group(0),
                                type=entity_type,
                                metadata={"variable": variable_name, "operator": symbol},
                            )
                        )
                        logger.debug(f"Regex detected {symbol} operator: '{match.group(0)}' at {start_pos}-{end_pos}")

            elif symbol == "==":
                # Build pattern for comparison: variable + operator phrase + value
                escaped_phrase = re.escape(operator_phrase)
                pattern = rf"\b([a-zA-Z_]\w*)\s+{escaped_phrase}\s+(\w+)\b"

                for match in re.finditer(pattern, text, re.IGNORECASE):
                    start_pos = match.start()
                    end_pos = match.end()
                    check_entities = all_entities if all_entities else entities

                    if not is_inside_entity(start_pos, end_pos, check_entities):
                        left_var = match.group(1)
                        right_val = match.group(2)

                        entities.append(
                            Entity(
                                start=start_pos,
                                end=end_pos,
                                text=match.group(0),
                                type=EntityType.COMPARISON,
                                metadata={"left": left_var, "right": right_val, "operator": symbol},
                            )
                        )
                        logger.debug(f"Regex detected {symbol} comparison: '{match.group(0)}' at {start_pos}-{end_pos}")

    def _detect_assignment_operators(
        self, text: str, entities: list[Entity], all_entities: list[Entity] | None = None
    ) -> None:
        """
        Detects assignment operators like 'x equals 5' -> 'x=5' or 'let x equals 5' -> 'let x=5'.

        This method identifies patterns where a variable name is followed by 'equals'
        and then a value, capturing the entire phrase until punctuation or end of line.
        The pattern allows for number words like 'twenty five' to be captured properly.
        Also supports variable declaration keywords like 'let', 'const', and 'var'.

        Args:
            text: The text to search for assignment patterns
            entities: List to append detected assignment entities to
            all_entities: Complete list of entities for overlap checking

        """
        # This pattern looks for optional keyword, variable name, 'equals', and then captures everything after
        assignment_pattern = self.assignment_pattern
        for match in assignment_pattern.finditer(text):
            check_entities = all_entities if all_entities else entities
            if not is_inside_entity(match.start(), match.end(), check_entities):
                entities.append(
                    Entity(
                        start=match.start(),
                        end=match.end(),
                        text=match.group(0),
                        type=EntityType.ASSIGNMENT,
                        metadata={
                            "keyword": match.group(1),  # Optional keyword (let, const, var)
                            "left": match.group(2),  # Variable name
                            "right": match.group(3),  # Value
                        },
                    )
                )

    def _detect_abbreviations(
        self, text: str, entities: list[Entity], all_entities: list[Entity] | None = None
    ) -> None:
        """Detect Latin abbreviations that should remain lowercase."""
        abbrev_pattern = regex_patterns.ABBREVIATION_PATTERN
        for match in abbrev_pattern.finditer(text):
            check_entities = all_entities if all_entities else entities
            if not is_inside_entity(match.start(), match.end(), check_entities):
                entities.append(
                    Entity(start=match.start(), end=match.end(), text=match.group(1), type=EntityType.ABBREVIATION)
                )

    def _detect_command_flags(
        self, text: str, entities: list[Entity], all_entities: list[Entity] | None = None
    ) -> None:
        """Detects spoken command-line flags like 'dash dash verbose' or 'dash f'."""
        # Pattern for long flags: --flag
        for match in self.long_flag_pattern.finditer(text):
            check_entities = all_entities if all_entities else entities
            if not is_inside_entity(match.start(), match.end(), check_entities):
                logger.debug(f"Found long flag: '{match.group(0)}' -> '--{match.group(1)}'")
                entities.append(
                    Entity(
                        start=match.start(),
                        end=match.end(),
                        text=match.group(0),
                        type=EntityType.COMMAND_FLAG,
                        metadata={"type": "long", "name": match.group(1)},
                    )
                )

        # Pattern for short flags: -f or -flag
        # But make sure we don't match long flags we already detected
        for match in self.short_flag_pattern.finditer(text):
            # Include both original entities and newly detected entities for overlap checking
            check_entities = (all_entities if all_entities else []) + entities
            # Ensure we don't overlap with a long flag we just detected
            if not is_inside_entity(match.start(), match.end(), check_entities):
                # Also make sure this isn't part of "dash dash" by checking preceding context
                # Get preceding characters to check for another "dash"
                preceding_text = text[max(0, match.start() - 10) : match.start()].strip()
                if not preceding_text.endswith("dash"):
                    logger.debug(f"Found short flag: '{match.group(0)}' -> '-{match.group(1)}'")
                    entities.append(
                        Entity(
                            start=match.start(),
                            end=match.end(),
                            text=match.group(0),
                            type=EntityType.COMMAND_FLAG,
                            metadata={"type": "short", "name": match.group(1)},
                        )
                    )

    def _detect_preformatted_flags(
        self, text: str, entities: list[Entity], all_entities: list[Entity] | None = None
    ) -> None:
        """Detects already-formatted command flags (like --MESSAGE) and normalizes them to lowercase."""
        if all_entities is None:
            all_entities = entities

        # Pattern to match already-formatted flags with uppercase letters
        preformatted_flag_pattern = re.compile(r"--[A-Z][A-Z0-9_-]*", re.IGNORECASE)

        for match in preformatted_flag_pattern.finditer(text):
            # Only detect if it has uppercase letters and isn't already detected
            flag_text = match.group(0)
            if any(c.isupper() for c in flag_text) and not is_inside_entity(match.start(), match.end(), all_entities):
                # Extract flag name (everything after --)
                flag_name = flag_text[2:]  # Remove --
                entities.append(
                    Entity(
                        start=match.start(),
                        end=match.end(),
                        text=flag_text,
                        type=EntityType.COMMAND_FLAG,
                        metadata={"type": "preformatted", "name": flag_name.lower()},
                    )
                )
                # Update all_entities to include newly found entity for subsequent overlap checks
                all_entities.append(entities[-1])

    def _detect_slash_commands(
        self, text: str, entities: list[Entity], all_entities: list[Entity] | None = None
    ) -> None:
        """Detects spoken slash commands like 'slash commit' -> '/commit'."""
        slash_command_pattern = self.slash_command_pattern
        matches = list(slash_command_pattern.finditer(text))

        for i, match in enumerate(matches):
            check_entities = all_entities if all_entities else entities
            if not is_inside_entity(match.start(), match.end(), check_entities):
                # Check if preceded by a number word (likely math division)
                if match.start() > 0:
                    preceding_text = text[: match.start()].rstrip()
                    # Get the last word before "slash"
                    if preceding_text:
                        words = preceding_text.split()
                        if words:
                            last_word = words[-1].lower()
                            # Check if it's a number word
                            from stt.text_formatting.common import NumberParser

                            parser = NumberParser(language=self.language)
                            if last_word in parser.all_number_words or last_word.isdigit():
                                # Skip this - it's likely division, not a slash command
                                continue

                command = match.group(1)

                # Determine if this command has parameters
                # Parameters are text between this command and the next slash command (or end)
                start_pos = match.end()
                if i + 1 < len(matches):
                    # Next slash command exists
                    end_pos = matches[i + 1].start()
                else:
                    # This is the last slash command, check for sentence end
                    end_pos = len(text)
                    # Look for sentence punctuation
                    for punct_pos in range(start_pos, len(text)):
                        if text[punct_pos] in ".!?":
                            end_pos = punct_pos
                            break

                # Extract parameters if any
                parameters = ""
                entity_end = match.end()
                if start_pos < end_pos:
                    potential_params = text[start_pos:end_pos].strip()
                    # Only consider it parameters if it doesn't start with "slash" (another command)
                    if potential_params and not potential_params.lower().startswith("slash"):
                        parameters = potential_params
                        # Extend the entity to include parameters
                        entity_end = end_pos
                        # Remove trailing punctuation from entity boundary
                        while entity_end > start_pos and text[entity_end - 1] in ".!?":
                            entity_end -= 1

                logger.debug(
                    f"Found slash command: '{text[match.start():entity_end]}' -> '/{command}' with params: '{parameters}'"
                )
                entities.append(
                    Entity(
                        start=match.start(),
                        end=entity_end,
                        text=text[match.start() : entity_end],
                        type=EntityType.SLASH_COMMAND,
                        metadata={"command": command, "parameters": parameters},
                    )
                )

    def _detect_underscore_delimiters(
        self, text: str, entities: list[Entity], all_entities: list[Entity] | None = None
    ) -> None:
        """Detects spoken underscore delimiters like 'underscore underscore blah underscore underscore' -> '__blah__'."""
        underscore_delimiter_pattern = self.underscore_delimiter_pattern
        for match in underscore_delimiter_pattern.finditer(text):
            check_entities = all_entities if all_entities else entities
            if not is_inside_entity(match.start(), match.end(), check_entities):
                # Count leading and trailing underscores
                full_match = match.group(0)
                content = match.group(2)  # The content between underscores

                # Count leading underscores by counting "underscore" words at the start
                leading_part = match.group(1)  # e.g., "underscore underscore "
                leading_underscores = leading_part.count("underscore")

                # Count trailing underscores by counting "underscore" words at the end
                trailing_part = match.group(3)  # e.g., " underscore underscore"
                trailing_underscores = trailing_part.count("underscore")

                logger.debug(
                    f"Found underscore delimiter: '{full_match}' -> '{'_' * leading_underscores}{content}{'_' * trailing_underscores}'"
                )
                entities.append(
                    Entity(
                        start=match.start(),
                        end=match.end(),
                        text=full_match,
                        type=EntityType.UNDERSCORE_DELIMITER,
                        metadata={
                            "content": content,
                            "leading_underscores": leading_underscores,
                            "trailing_underscores": trailing_underscores,
                        },
                    )
                )

    def _detect_simple_underscore_variables(
        self, text: str, entities: list[Entity], all_entities: list[Entity] | None = None
    ) -> None:
        """Detects simple underscore variables like 'user underscore id' -> 'user_id'."""
        simple_underscore_pattern = self.simple_underscore_pattern
        for match in simple_underscore_pattern.finditer(text):
            check_entities = all_entities if all_entities else entities
            if not is_inside_entity(match.start(), match.end(), check_entities):
                first_word = match.group(1)
                second_word = match.group(2)

                # Check context - only detect if preceded by programming keywords OR
                # if the first word itself is a programming context word
                context_words = text[: match.start()].lower().split()
                preceding_word = context_words[-1] if context_words else ""

                # Valid programming context words from resources
                programming_keywords = set(self.resources.get("context_words", {}).get("programming_keywords", []))
                technical_context = set(self.resources.get("context_words", {}).get("technical_context", []))
                # Also include some universal words that are common across languages
                universal_words = {"variable", "let", "const", "var", "set", "is", "check", "mi", "my"}
                valid_context_words = programming_keywords | technical_context | universal_words

                # Check if either there's a preceding context word OR the first word is a context word
                has_valid_context = (
                    preceding_word in valid_context_words  # Preceding word is valid
                    or first_word.lower() in valid_context_words  # First word itself is valid context
                )

                if not has_valid_context:
                    continue

                logger.debug(f"Found simple underscore variable: '{match.group(0)}' -> '{first_word}_{second_word}'")
                entities.append(
                    Entity(
                        start=match.start(),
                        end=match.end(),
                        text=match.group(0),
                        type=EntityType.SIMPLE_UNDERSCORE_VARIABLE,
                        metadata={
                            "first_word": first_word,
                            "second_word": second_word,
                        },
                    )
                )

    def _detect_cli_commands(self, text: str, entities: list[Entity], all_entities: list[Entity] | None = None) -> None:
        """Detects standalone CLI commands and keywords."""
        if all_entities is None:
            all_entities = entities

        resources = get_resources(self.language)
        multi_word_commands = resources.get("context_words", {}).get("multi_word_commands", [])

        # Only use specific CLI tools and multi-word commands, not all technical terms
        cli_tools = {
            "git",
            "npm",
            "pip",
            "docker",
            "kubectl",
            "cargo",
            "yarn",
            "brew",
            "apt",
            "make",
            "cmake",
            "node",
            "python",
            "java",
            "mvn",
            "gradle",
            "composer",
            "gem",
            "conda",
            "helm",
            "terraform",
            "ansible",
            "vagrant",
        }

        # Combine CLI tools with multi-word technical terms and sort by length
        all_commands = sorted(list(multi_word_commands) + list(cli_tools), key=len, reverse=True)

        for command in all_commands:
            # Use regex to find whole-word matches
            pattern = rf"\b{re.escape(command)}\b"
            for match in re.finditer(pattern, text, re.IGNORECASE):
                if not is_inside_entity(match.start(), match.end(), all_entities):
                    new_entity = Entity(
                        start=match.start(),
                        end=match.end(),
                        text=match.group(0),
                        type=EntityType.CLI_COMMAND,
                        metadata={"command": match.group(0)},
                    )
                    entities.append(new_entity)
                    # Update all_entities to include newly found entity for subsequent overlap checks
                    all_entities.append(new_entity)

    def _detect_filenames_regex_fallback(
        self, text: str, entities: list[Entity], all_entities: list[Entity] | None = None
    ) -> None:
        """Regex-based fallback for filename detection when spaCy is not available."""
        if all_entities is None:
            all_entities = entities

        logger.debug(f"REGEX FALLBACK: Processing text '{text}' for filename detection")

        # Use the comprehensive pattern that captures both filename and extension
        for match in regex_patterns.FULL_SPOKEN_FILENAME_PATTERN.finditer(text):
            if overlaps_with_entity(match.start(), match.end(), all_entities):
                continue

            full_filename = match.group(0)  # e.g., "my script dot py"
            filename_part = match.group(1)  # e.g., "my script"
            extension = match.group(2)  # e.g., "py"

            # Skip if this looks like it includes command verbs
            # Get the context before the match to check for command patterns
            max(0, match.start() - 20)
            # before_context = text[context_start : match.start()].strip().lower()  # Unused variable

            # Known filename action words that should not be part of the filename
            resources = get_resources(self.language)
            filename_actions = resources.get("context_words", {}).get("filename_actions", [])

            # Filter out filename stop words and action words from the filename part
            filename_words = filename_part.split()
            filename_stop_words = resources.get("context_words", {}).get("filename_stop_words", [])
            
            # Remove action words and stop words from the beginning
            filtered_words = []
            for word in filename_words:
                word_lower = word.lower()
                if word_lower not in filename_actions and word_lower not in filename_stop_words:
                    filtered_words.append(word)
                elif not filtered_words:  # Only skip words at the beginning
                    continue
                else:  # Once we have content words, include everything else
                    filtered_words.append(word)
            
            if filtered_words:
                actual_filename = " ".join(filtered_words)
                # Find where the actual filename starts in the original text
                actual_start = text.find(actual_filename, match.start())
                if actual_start != -1:
                    actual_match_text = f"{actual_filename} dot {extension}"
                    actual_end = actual_start + len(actual_match_text)

                    entities.append(
                        Entity(
                            start=actual_start,
                            end=actual_end,
                            text=actual_match_text,
                            type=EntityType.FILENAME,
                            metadata={
                                "filename": actual_filename,
                                "extension": extension,
                                "method": "regex_fallback",
                            },
                        )
                    )
                    logger.debug(
                        f"Detected filename (regex fallback): '{actual_match_text}' -> filename: '{actual_filename}', ext: '{extension}'"
                    )
                    continue
            else:
                # If no words left after filtering, skip this match
                logger.debug(
                    f"Regex Fallback: Skipping '{full_filename}' because no filename words remain after filtering"
                )
                continue

            # This code path should not be reached anymore due to the filtering above
            entities.append(
                Entity(
                    start=match.start(),
                    end=match.end(),
                    text=full_filename,
                    type=EntityType.FILENAME,
                    metadata={"filename": filename_part, "extension": extension, "method": "regex_fallback"},
                )
            )
            logger.debug(
                f"Detected filename (regex fallback): '{full_filename}' -> filename: '{filename_part}', ext: '{extension}'"
            )

    def _detect_programming_keywords(
        self, text: str, entities: list[Entity], all_entities: list[Entity] | None = None
    ) -> None:
        """Detects standalone programming keywords like 'let', 'const', 'if'."""
        if all_entities is None:
            all_entities = entities

        resources = get_resources(self.language)
        programming_keywords = resources.get("context_words", {}).get("programming_keywords", [])

        for keyword in programming_keywords:
            # Use regex to find whole-word matches, ensuring it's not part of another word
            pattern = rf"\b{re.escape(keyword)}\b"
            for match in re.finditer(pattern, text, re.IGNORECASE):
                if not is_inside_entity(match.start(), match.end(), all_entities):
                    entities.append(
                        Entity(
                            start=match.start(),
                            end=match.end(),
                            text=match.group(0),
                            type=EntityType.PROGRAMMING_KEYWORD,
                            metadata={"keyword": match.group(0)},
                        )
                    )
