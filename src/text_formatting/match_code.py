#!/usr/bin/env python3
"""Code-related entity detection and conversion for STT transcriptions."""

import re
from typing import List
from .common import Entity, EntityType, NumberParser
from .utils import is_inside_entity
from ..core.config import get_logger, get_config
from . import regex_patterns
from .constants import FILENAME_ACTION_VERBS, FILENAME_LINKING_VERBS, ABBREVIATIONS

logger = get_logger(__name__)


class CodeEntityDetector:
    def __init__(self, nlp=None):
        """Initialize CodeEntityDetector with dependency injection.

        Args:
            nlp: SpaCy NLP model instance. If None, will load from nlp_provider.

        """
        if nlp is None:
            from .nlp_provider import get_nlp

            nlp = get_nlp()

        self.nlp = nlp

    def detect(self, text: str, entities: List[Entity]) -> List[Entity]:
        """Detects all code-related entities."""
        code_entities = []
        # Pass all existing entities for overlap checking
        all_entities = entities + code_entities
        self._detect_filenames(text, code_entities, all_entities)
        all_entities = entities + code_entities
        self._detect_assignment_operators(text, code_entities, all_entities)
        all_entities = entities + code_entities
        self._detect_spoken_operators(text, code_entities, all_entities)
        all_entities = entities + code_entities
        self._detect_abbreviations(text, code_entities, all_entities)
        all_entities = entities + code_entities
        self._detect_command_flags(text, code_entities, all_entities)
        all_entities = entities + code_entities
        self._detect_slash_commands(text, code_entities, all_entities)
        all_entities = entities + code_entities
        self._detect_underscore_delimiters(text, code_entities, all_entities)
        all_entities = entities + code_entities
        self._detect_simple_underscore_variables(text, code_entities, all_entities)

        logger.debug(f"CodeEntityDetector found {len(code_entities)} entities in '{text}'")
        for entity in code_entities:
            logger.debug(f"  - {entity.type}: '{entity.text}' [{entity.start}:{entity.end}]")

        return code_entities

    def _detect_filenames(self, text: str, entities: List[Entity], all_entities: List[Entity] = None) -> None:
        """Detect filenames in text and add them to entities list using NLP-driven approach.

        Args:
            text: The text to search for filenames
            entities: The list to append filename entities to

        """
        # New Detection Strategy: Find the anchor ("dot extension") and work backward

        # This pattern finds "dot py", "dot js", etc. - the most reliable anchor
        spoken_dot_pattern = regex_patterns.SPOKEN_DOT_FILENAME_PATTERN

        # Also handle already-formatted filenames (e.g., "main.py")
        extension_pattern = regex_patterns.FILENAME_WITH_EXTENSION_PATTERN

        # Find all candidate filename anchors
        candidates = []

        # Find spoken dot patterns
        for match in spoken_dot_pattern.finditer(text):
            check_entities = all_entities if all_entities else entities
            if not is_inside_entity(match.start(), match.end(), check_entities):
                # Check for "at" before the match to avoid email conflicts
                if " at " in text[max(0, match.start() - 10) : match.start()]:
                    continue
                candidates.append(("spoken", match))

        # Also detect Java package names (multiple dots without extensions)
        # Pattern: word dot word dot word (at least 2 dots)
        java_package_pattern = regex_patterns.JAVA_PACKAGE_PATTERN
        for match in java_package_pattern.finditer(text):
            check_entities = all_entities if all_entities else entities
            if not is_inside_entity(match.start(), match.end(), check_entities):
                # Check if this looks like a Java package (common prefixes)
                package_text = match.group(1).lower()
                if any(
                    package_text.startswith(prefix) for prefix in ["com dot", "org dot", "net dot", "edu dot", "io dot"]
                ):
                    candidates.append(("java_package", match))

        # Find already-formatted filenames
        for match in extension_pattern.finditer(text):
            check_entities = all_entities if all_entities else entities
            if not is_inside_entity(match.start(), match.end(), check_entities):
                # This logic is for already formatted filenames like `com.example.app`
                # which should be treated as a single FILENAME entity.
                # It has high priority.
                entities.append(
                    Entity(start=match.start(), end=match.end(), text=match.group(0), type=EntityType.FILENAME)
                )
                # We add it directly and continue to avoid reprocessing
                continue

        if not self.nlp:
            # No SpaCy available, use simple pattern matching
            for pattern_type, match in candidates:
                entities.append(
                    Entity(start=match.start(), end=match.end(), text=match.group(0), type=EntityType.FILENAME)
                )
            return

        try:
            doc = self.nlp(text)
        except (AttributeError, ValueError, IndexError) as e:
            logger.warning(f"SpaCy filename detection failed: {e}")
            # Fall back to simple pattern matching
            for pattern_type, match in candidates:
                entities.append(
                    Entity(start=match.start(), end=match.end(), text=match.group(0), type=EntityType.FILENAME)
                )
            return

        # Create token index mapping for character position to token
        char_to_token = {}
        for token in doc:
            for i in range(token.idx, token.idx + len(token.text)):
                char_to_token[i] = token

        # Process each candidate
        for pattern_type, match in candidates:

            if pattern_type == "formatted":
                # Already formatted filenames (like "main.py") can be used directly
                entities.append(
                    Entity(start=match.start(), end=match.end(), text=match.group(0), type=EntityType.FILENAME)
                )
                continue

            if pattern_type == "java_package":
                # Java package names can be used directly
                entities.append(
                    Entity(start=match.start(), end=match.end(), text=match.group(0), type=EntityType.FILENAME)
                )
                continue

            # For spoken patterns, we need to work backward from the "dot extension" anchor

            # Find the token containing the "dot" part
            dot_token = None
            for i in range(match.start(), match.end()):
                if i in char_to_token:
                    token = char_to_token[i]
                    if "dot" in token.text.lower():
                        dot_token = token
                        break

            if not dot_token:
                # Fallback if we can't find the dot token
                entities.append(
                    Entity(start=match.start(), end=match.end(), text=match.group(0), type=EntityType.FILENAME)
                )
                continue

            # Define our "Stop" conditions - simpler and more robust approach
            def should_stop_at_token(token):
                # Stop at clear action verbs that are unlikely to be in a filename
                # Using lemma_ handles variations like "running", "ran", "run"
                if token.lemma_ in FILENAME_ACTION_VERBS:
                    return True

                # Stop at linking verbs which separate the subject from the filename
                if token.lemma_ in FILENAME_LINKING_VERBS:
                    return True

                # Stop at prepositions (e.g., "in", "on"), but allow single-letter ones like 'v'
                if token.pos_ == "ADP" and len(token.text) > 1:
                    return True

                # Stop at determiners like "the", "a", "an" which often precede context words
                # But not "my" when it's part of a filename like "my file underscore name"
                if token.pos_ == "DET" and token.text.lower() != "my":
                    return True

                # Stop at conjunctions that separate clauses
                if token.pos_ == "CCONJ":
                    return True

                # Handle the "config file settings" vs "log file 100" ambiguity
                # This check is when we're looking at words BEFORE the current position
                # So if we see "file" followed by a non-number, we should stop including tokens
                # But this is checked while walking backward, so logic is inverted

                return False

            # Start by finding which token is the actual filename part (before "dot")
            # Walk backwards from dot_token to find filename tokens
            filename_tokens = []
            current_token_idx = dot_token.i

            # Walk backward through preceding tokens
            while current_token_idx > 0:
                current_token_idx -= 1
                prev_token = doc[current_token_idx]

                # Check if we should stop
                if should_stop_at_token(prev_token):
                    break

                # Special check for the word "file" - if preceded by a determiner, stop here
                if prev_token.text.lower() == "file" and current_token_idx > 0:
                    prev_prev_token = doc[current_token_idx - 1]
                    if (
                        prev_prev_token.pos_ == "DET" and prev_prev_token.text.lower() != "my"
                    ):  # "the file", "a file" but not "my file"
                        break

                    # Also check if "file" is preceded by descriptor words like "config", "log"
                    if prev_prev_token.text.lower() in ["config", "log", "data", "temp", "cache", "text"]:
                        # Check what's already in our filename_tokens
                        # If we haven't included anything yet, or only have one token, this is "X file Y" pattern
                        if len(filename_tokens) <= 1:
                            # Look ahead to see if next token after "file" is a number
                            if current_token_idx + 1 < dot_token.i:
                                next_after_file = doc[current_token_idx + 1]
                                if not next_after_file.like_num:
                                    # "X file Y" where Y is not a number - skip both X and file
                                    break

                # Special handling for "config" when followed by "file"
                if prev_token.text.lower() in [
                    "config",
                    "log",
                    "data",
                    "temp",
                    "cache",
                ] and current_token_idx + 1 < len(doc):
                    next_token = doc[current_token_idx + 1]
                    if next_token.text.lower() == "file" and current_token_idx + 2 < dot_token.i:
                        # Check what comes after "file"
                        after_file_token = doc[current_token_idx + 2]
                        if not after_file_token.like_num:
                            # "config file" followed by non-number is context, not filename
                            # Skip this token, don't include it
                            continue

                # Include this token as part of the filename
                filename_tokens.insert(0, prev_token)

                # Limit to reasonable filename length to avoid grabbing entire sentences
                if len(filename_tokens) >= 6:
                    break

            # Now build the complete tokens list: filename + dot + extension
            tokens_to_include = filename_tokens.copy()

            # Add the "dot" token
            tokens_to_include.append(dot_token)

            # Add the extension token (the one after "dot")
            if dot_token.i + 1 < len(doc):
                extension_token = doc[dot_token.i + 1]
                tokens_to_include.append(extension_token)

            # Construct the Entity with correct start and end character positions
            if tokens_to_include:
                start_pos = tokens_to_include[0].idx
                end_pos = tokens_to_include[-1].idx + len(tokens_to_include[-1].text)
                filename_text = text[start_pos:end_pos].strip(".,!?;: ")
                end_pos = start_pos + len(filename_text)

                # Add the entity
                entities.append(Entity(start=start_pos, end=end_pos, text=filename_text, type=EntityType.FILENAME))

    def _detect_spoken_operators(self, text: str, entities: List[Entity], all_entities: List[Entity] = None) -> None:
        """Detect spoken operators using SpaCy token context analysis.

        This method detects patterns like "variable plus plus" or "count minus minus"
        using token analysis to ensure they're used in valid programming contexts.
        """
        if not self.nlp:
            logger.debug("SpaCy not available for spoken operator detection")
            return
        try:
            doc = self.nlp(text)
        except (AttributeError, ValueError, IndexError) as e:
            logger.warning(f"SpaCy operator detection failed: {e}")
            return
        logger.debug(f"Processing text for operators: '{text}'")

        # Iterate through tokens to find operator patterns
        for i, token in enumerate(doc):
            # Check for "plus plus" pattern (increment operator)
            if token.text.lower() == "plus" and i + 1 < len(doc) and doc[i + 1].text.lower() == "plus":
                logger.debug(f"Found 'plus plus' pattern at token {i}")

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

                        # Create entity spanning variable and operator
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
                                    type=EntityType.INCREMENT_OPERATOR,
                                    metadata={"variable": prev_token.text},
                                )
                            )

            # Check for "minus minus" pattern (decrement operator)
            elif token.text.lower() == "minus" and i + 1 < len(doc) and doc[i + 1].text.lower() == "minus":
                if i > 0:
                    prev_token = doc[i - 1]
                    if (
                        (
                            prev_token.pos_ in ["NOUN", "PROPN", "SYM", "VERB"]
                            or (prev_token.pos_ == "PRON" and len(prev_token.text) == 1)
                        )
                        and prev_token.text.isalpha()
                        and prev_token.text.lower() not in {"the", "a", "an", "this", "that"}
                    ):
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
                                    type=EntityType.DECREMENT_OPERATOR,
                                    metadata={"variable": prev_token.text},
                                )
                            )

            # Check for "equals equals" pattern (comparison operator)
            elif token.text.lower() == "equals" and i + 1 < len(doc) and doc[i + 1].text.lower() == "equals":
                if i > 0 and i + 2 < len(doc):
                    prev_token = doc[i - 1]
                    next_next_token = doc[i + 2]
                    # Check for variable on left and value/variable on right
                    # The original POS check was too strict. Let's broaden it to accept any token
                    # that isn't a clear stopword or punctuation, which is more typical for variable names.
                    is_left_var = prev_token.is_alpha and not prev_token.is_stop
                    is_right_var = (
                        (next_next_token.is_alpha and not next_next_token.is_stop)
                        or next_next_token.like_num
                        or next_next_token.text.lower() in ["true", "false", "null"]
                    )

                    if is_left_var and is_right_var:
                        # Check if there's an "if" before the comparison
                        start_pos = prev_token.idx
                        if i > 1 and doc[i - 2].text.lower() == "if":
                            start_pos = doc[i - 2].idx

                        end_pos = next_next_token.idx + len(next_next_token.text)
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
                                        "right": next_next_token.text,
                                    },
                                )
                            )

    def _detect_assignment_operators(
        self, text: str, entities: List[Entity], all_entities: List[Entity] = None
    ) -> None:
        """Detects assignment operators like 'x equals 5' -> 'x=5' or 'let x equals 5' -> 'let x=5'.

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
        assignment_pattern = regex_patterns.ASSIGNMENT_PATTERN
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

    def _detect_abbreviations(self, text: str, entities: List[Entity], all_entities: List[Entity] = None) -> None:
        """Detect Latin abbreviations that should remain lowercase."""
        abbrev_pattern = regex_patterns.ABBREVIATION_PATTERN
        for match in abbrev_pattern.finditer(text):
            check_entities = all_entities if all_entities else entities
            if not is_inside_entity(match.start(), match.end(), check_entities):
                entities.append(
                    Entity(start=match.start(), end=match.end(), text=match.group(1), type=EntityType.ABBREVIATION)
                )

    def _detect_command_flags(self, text: str, entities: List[Entity], all_entities: List[Entity] = None) -> None:
        """Detects spoken command-line flags like 'dash dash verbose' or 'dash f'."""
        # Pattern for long flags: --flag
        for match in regex_patterns.LONG_FLAG_PATTERN.finditer(text):
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
        for match in regex_patterns.SHORT_FLAG_PATTERN.finditer(text):
            check_entities = all_entities if all_entities else entities
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

    def _detect_slash_commands(self, text: str, entities: List[Entity], all_entities: List[Entity] = None) -> None:
        """Detects spoken slash commands like 'slash commit' -> '/commit'."""
        slash_command_pattern = regex_patterns.SLASH_COMMAND_PATTERN
        matches = list(slash_command_pattern.finditer(text))

        for i, match in enumerate(matches):
            check_entities = all_entities if all_entities else entities
            if not is_inside_entity(match.start(), match.end(), check_entities):
                # Check if preceded by a number word (likely math division)
                if match.start() > 0:
                    preceding_text = text[:match.start()].rstrip()
                    # Get the last word before "slash"
                    if preceding_text:
                        words = preceding_text.split()
                        if words:
                            last_word = words[-1].lower()
                            # Check if it's a number word
                            from .common import NumberParser
                            parser = NumberParser()
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
        self, text: str, entities: List[Entity], all_entities: List[Entity] = None
    ) -> None:
        """Detects spoken underscore delimiters like 'underscore underscore blah underscore underscore' -> '__blah__'."""
        underscore_delimiter_pattern = regex_patterns.UNDERSCORE_DELIMITER_PATTERN
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
        self, text: str, entities: List[Entity], all_entities: List[Entity] = None
    ) -> None:
        """Detects simple underscore variables like 'user underscore id' -> 'user_id'."""
        simple_underscore_pattern = regex_patterns.SIMPLE_UNDERSCORE_PATTERN
        for match in simple_underscore_pattern.finditer(text):
            check_entities = all_entities if all_entities else entities
            if not is_inside_entity(match.start(), match.end(), check_entities):
                first_word = match.group(1)
                second_word = match.group(2)

                # Check context - only detect if preceded by programming keywords
                context_words = text[: match.start()].lower().split()
                if not context_words:
                    continue  # Skip if it's at the very beginning

                preceding_word = context_words[-1] if context_words else ""
                # Make this list much stricter
                if preceding_word not in {"variable", "let", "const", "var", "set", "is"}:
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


class CodePatternConverter:
    def __init__(self, number_parser: NumberParser):
        self.number_parser = number_parser
        self.config = get_config()

        self.converters = {
            EntityType.FILENAME: self.convert_filename,
            EntityType.INCREMENT_OPERATOR: self.convert_increment_operator,
            EntityType.DECREMENT_OPERATOR: self.convert_decrement_operator,
            EntityType.COMPARISON: self.convert_comparison,
            EntityType.ABBREVIATION: self.convert_abbreviation,
            EntityType.ASSIGNMENT: self.convert_assignment,
            EntityType.COMMAND_FLAG: self.convert_command_flag,
            EntityType.SLASH_COMMAND: self.convert_slash_command,
            EntityType.UNDERSCORE_DELIMITER: self.convert_underscore_delimiter,
            EntityType.SIMPLE_UNDERSCORE_VARIABLE: self.convert_simple_underscore_variable,
        }

    def convert_filename(self, entity: Entity, full_text: str = None) -> str:
        """Convert spoken filenames to proper format based on extension"""
        text = entity.text.strip()

        # Check for and handle explicit underscore usage first
        # Check both the entity text and the full text context if available
        has_spoken_underscores = " underscore " in entity.text.lower()
        if not has_spoken_underscores and full_text:
            # Check if underscore was spoken near this entity
            entity_pos = full_text.find(entity.text)
            if entity_pos > 0:
                context_start = max(0, entity_pos - 20)
                context = full_text[context_start : entity.end]
                has_spoken_underscores = " underscore " in context.lower()

        # First, handle all spoken separators to create a clean string
        text = re.sub(r"\s*underscore\s+", "_", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*dash\s*", "-", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*dot\s+", ".", text, flags=re.IGNORECASE)

        # Handle package names (e.g., com.example.app) which have multiple dots
        if text.count(".") > 1 and all(re.match(r"^[a-z0-9_.-]+$", part) for part in text.split(".")):
            return text.replace(" ", "").lower()

        parts = text.rsplit(".", 1)
        if len(parts) != 2:
            return text.replace(" ", "_").lower()  # Fallback for names without extensions

        filename_part, extension = parts
        extension = extension.lower()

        # Replace all spoken number sequences with digits *before* splitting into words
        def number_word_replacer(match):
            return self.number_parser.parse(match.group(0)) or match.group(0)

        number_word_pattern = (
            r"\b(?:"
            + "|".join(self.number_parser.all_number_words)
            + r")(?:\s+(?:"
            + "|".join(self.number_parser.all_number_words)
            + r"))*\b"
        )
        filename_part = re.sub(number_word_pattern, number_word_replacer, filename_part, flags=re.IGNORECASE)

        # If underscores were spoken, they dictate the format
        if has_spoken_underscores:
            return f"{filename_part.replace(' ', '_').lower()}.{extension}"

        # Otherwise, apply casing rules based on the config
        format_rule = self.config.get_filename_format(extension)
        casing_words = re.split(r"[ _-]", filename_part)
        casing_words = [w.lower() for w in casing_words if w]

        if not casing_words:
            return f".{extension}"  # Handle cases like ".bashrc"

        if format_rule == "PascalCase":
            formatted_filename = "".join(w.capitalize() for w in casing_words)
        elif format_rule == "camelCase":
            formatted_filename = casing_words[0] + "".join(w.capitalize() for w in casing_words[1:])
        elif format_rule == "kebab-case":
            formatted_filename = "-".join(casing_words)
        elif format_rule == "UPPER_SNAKE":
            formatted_filename = "_".join(w.upper() for w in casing_words)
        else:  # Default is lower_snake
            formatted_filename = "_".join(casing_words)

        return f"{formatted_filename}.{extension}"

    def convert_increment_operator(self, entity: Entity) -> str:
        """Convert increment operators like 'i plus plus' -> 'i++'"""
        # Extract variable name and convert to increment
        match = re.match(r"(\w+)\s+plus\s+plus", entity.text, re.IGNORECASE)
        if match:
            variable = match.group(1).lower()  # Keep variable lowercase for code
            return f"{variable}++"
        return entity.text

    def convert_decrement_operator(self, entity: Entity) -> str:
        """Convert decrement operators like 'counter minus minus' -> 'counter--'"""
        if entity.metadata and "variable" in entity.metadata:
            return f"{entity.metadata['variable'].lower()}--"
        # Fallback for older detection logic
        match = re.match(r"(\w+)\s+minus\s+minus", entity.text, re.IGNORECASE)
        if match:
            variable = match.group(1).lower()
            return f"{variable}--"
        return entity.text

    def convert_comparison(self, entity: Entity) -> str:
        """Convert comparison patterns"""
        if entity.metadata and "left" in entity.metadata and "right" in entity.metadata:
            left = entity.metadata["left"]
            right = entity.metadata["right"]

            # Try to parse the right side if it's a number word
            parsed_right = self.number_parser.parse(right)
            if parsed_right:
                right = parsed_right

            # Check for an "if" at the beginning by inspecting the original text
            if entity.text.lower().strip().startswith("if "):
                return f"if {left} == {right}"
            return f"{left} == {right}"
        return entity.text

    def convert_abbreviation(self, entity: Entity) -> str:
        """Convert abbreviations to proper lowercase format"""
        text = entity.text.lower()

        # Use abbreviations from constants
        return ABBREVIATIONS.get(text, text)

    def convert_assignment(self, entity: Entity) -> str:
        """Convert assignment patterns like 'a equals b' -> 'a=b' or 'let a equals b' -> 'let a=b'"""
        if entity.metadata:
            keyword = entity.metadata.get("keyword", "")  # Optional keyword (let, const, var)
            left = entity.metadata.get("left", "")
            right = entity.metadata.get("right", "")

            # Try to parse number words
            parsed_right = self.number_parser.parse_with_validation(right)
            if parsed_right:
                right = parsed_right

            # If the right side seems like a function call (multiple words), snake_case it.
            if " " in right:
                right = "_".join(right.lower().split())
            # For simple single word values, convert to lowercase unless they look like constants
            elif " " not in right and not any(c.isupper() for c in right[1:]) and not right.isupper():
                right = right.lower()

            # Build the assignment string with optional keyword
            if keyword:
                return f"{keyword} {left} = {right}"
            return f"{left} = {right}"
        return entity.text

    def convert_command_flag(self, entity: Entity) -> str:
        """Convert spoken flags to proper format."""
        if entity.metadata and "name" in entity.metadata:
            name = entity.metadata["name"]
            flag_type = entity.metadata.get("type")

            if flag_type == "long":
                # Handle known compound flags vs flag + argument patterns
                known_compound_flags = {
                    "save dev": "save-dev",
                    "dry run": "dry-run",
                    "no cache": "no-cache",
                    "cache dir": "cache-dir",
                    "output dir": "output-dir",
                    "config file": "config-file",
                }

                # If it's a known compound flag, use hyphenated form
                if name.lower() in known_compound_flags:
                    return f"--{known_compound_flags[name.lower()]}"

                # For single words or unknown patterns, check if second word looks like an argument
                words = name.split()
                if len(words) == 2:
                    first_word, second_word = words
                    # Common argument patterns that should NOT be part of flag name
                    argument_words = {"test", "file", "message", "mode", "path", "name", "value", "option"}
                    if second_word.lower() in argument_words:
                        # Return just the flag and let the second word remain as argument
                        return f"--{first_word.lower()}"
                
                # Default: replace spaces with hyphens for multi-word flags
                name = name.replace(' ', '-').lower()
                return f"--{name}"
            if flag_type == "short":
                return f"-{name.lower()}"

        return entity.text  # Fallback

    def convert_slash_command(self, entity: Entity) -> str:
        """Convert spoken slash commands like 'slash commit' -> '/commit' with parameter processing."""
        if entity.metadata and "command" in entity.metadata:
            command = entity.metadata["command"]
            parameters = entity.metadata.get("parameters", "")

            if parameters:
                # Process parameters to convert number words and handle concatenation
                processed_params = self._process_command_parameters(parameters)
                return f"/{command} {processed_params}"
            return f"/{command}"

        # Fallback: try to extract from text
        match = re.match(r"slash\s+([a-zA-Z][a-zA-Z0-9_-]*)", entity.text, re.IGNORECASE)
        if match:
            return f"/{match.group(1)}"

        return entity.text

    def _process_command_parameters(self, parameters: str) -> str:
        """Process command parameters to convert number words and handle concatenation."""
        # Split parameters into words
        words = parameters.split()
        result_words = []

        for i, word in enumerate(words):
            # Check if this word is a number word
            parsed_number = self.number_parser.parse(word)
            if parsed_number and parsed_number.isdigit():
                # This is a number word, convert it
                if result_words:
                    # Concatenate with the previous word (like "server" + "1" -> "server1")
                    result_words[-1] = result_words[-1] + parsed_number
                else:
                    # No previous word, just add the number
                    result_words.append(parsed_number)
            else:
                # Regular word, add as-is
                result_words.append(word)

        return " ".join(result_words)

    def convert_underscore_delimiter(self, entity: Entity) -> str:
        """Convert spoken underscore delimiters like 'underscore underscore blah underscore underscore' -> '__blah__'."""
        if entity.metadata and all(
            key in entity.metadata for key in ["content", "leading_underscores", "trailing_underscores"]
        ):
            content = entity.metadata["content"]
            leading = entity.metadata["leading_underscores"]
            trailing = entity.metadata["trailing_underscores"]
            return f"{'_' * leading}{content}{'_' * trailing}"

        # Fallback: try to extract from text using regex
        pattern = r"((?:underscore\s+)+)([a-zA-Z][a-zA-Z0-9_-]*)((?:\s+underscore)+)(?=\s|$)"
        match = re.match(pattern, entity.text, re.IGNORECASE)
        if match:
            leading_count = match.group(1).count("underscore")
            content = match.group(2)
            trailing_count = match.group(3).count("underscore")
            return f"{'_' * leading_count}{content}{'_' * trailing_count}"

        return entity.text

    def convert_simple_underscore_variable(self, entity: Entity) -> str:
        """Convert simple underscore variables like 'user underscore id' -> 'user_id'."""
        if entity.metadata and "first_word" in entity.metadata and "second_word" in entity.metadata:
            first_word = entity.metadata["first_word"]
            second_word = entity.metadata["second_word"]
            return f"{first_word}_{second_word}"

        # Fallback: try to extract from text using regex
        pattern = r"([a-zA-Z][a-zA-Z0-9_-]*)\s+underscore\s+([a-zA-Z][a-zA-Z0-9_-]*)"
        match = re.match(pattern, entity.text, re.IGNORECASE)
        if match:
            return f"{match.group(1)}_{match.group(2)}"

        return entity.text
