#!/usr/bin/env python3
"""Code-related entity detection and conversion for Matilda transcriptions."""

import re
from typing import List
from .common import Entity, EntityType, NumberParser
from .utils import is_inside_entity
from ..core.config import get_config, setup_logging
from . import regex_patterns
from .constants import get_resources

logger = setup_logging(__name__, log_filename="text_formatting.txt")


class CodeEntityDetector:
    def __init__(self, nlp=None, language: str = "en"):
        """Initialize CodeEntityDetector with dependency injection.

        Args:
            nlp: SpaCy NLP model instance. If None, will load from nlp_provider.
            language: Language code for resource loading (default: 'en')

        """
        if nlp is None:
            from .nlp_provider import get_nlp

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

    def detect(self, text: str, entities: List[Entity]) -> List[Entity]:
        """Detects all code-related entities."""
        code_entities = []
        # Add the new detector call here
        all_entities = entities + code_entities
        self._detect_cli_commands(text, code_entities, all_entities)
        all_entities = entities + code_entities
        self._detect_programming_keywords(text, code_entities, all_entities)
        # ... (rest of the existing detector calls)
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
        """Detect filenames using a simple regex anchor and robust spaCy context analysis."""
        if all_entities is None:
            all_entities = entities

        # --- Part 1: Handle already-formatted files first (e.g., main.py, com.example.app) ---
        # This logic is sound and should run first.
        for match in regex_patterns.FILENAME_WITH_EXTENSION_PATTERN.finditer(text):
            if not is_inside_entity(match.start(), match.end(), all_entities):
                entities.append(
                    Entity(start=match.start(), end=match.end(), text=match.group(0), type=EntityType.FILENAME)
                )

        for match in regex_patterns.JAVA_PACKAGE_PATTERN.finditer(text):
            if not is_inside_entity(match.start(), match.end(), all_entities):
                package_text = match.group(1).lower()
                if any(package_text.startswith(prefix) for prefix in ["com dot", "org dot", "net dot"]):
                    entities.append(
                        Entity(start=match.start(), end=match.end(), text=match.group(0), type=EntityType.FILENAME)
                    )

        # --- Part 2: Handle spoken filenames ("my file dot py") with a robust, non-greedy method ---
        if not self.nlp:
            logger.debug("SpaCy model not available. Using regex fallback for spoken filename detection.")
            self._detect_filenames_regex_fallback(text, entities, all_entities)
            return

        # Count entities before spaCy detection
        entities_before_spacy = len(entities)

        try:
            doc = self.nlp(text)
        except (AttributeError, ValueError, IndexError) as e:
            logger.warning(f"SpaCy filename detection failed: {e}")
            logger.debug("Falling back to regex-based filename detection")
            self._detect_filenames_regex_fallback(text, entities, all_entities)
            return

        # Create a reverse map from a token's end position to the token itself.
        # This helps us find the token that ends right before our "dot extension" match.
        end_char_to_token = {token.idx + len(token.text): token for token in doc}

        for match in regex_patterns.SPOKEN_DOT_FILENAME_PATTERN.finditer(text):
            if is_inside_entity(match.start(), match.end(), all_entities):
                continue

            logger.debug(f"SPACY FILENAME: Found 'dot extension' match: '{match.group()}' at {match.start()}-{match.end()}")

            # Check for email conflict
            if " at " in text[max(0, match.start() - 10) : match.start()]:
                continue

            # Find the token immediately preceding the " dot " match
            start_of_dot = match.start()
            if start_of_dot not in end_char_to_token:
                logger.debug(f"SPACY FILENAME: No token ends at position {start_of_dot}, skipping")
                continue  # No token ends exactly where " dot " begins, weird spacing.

            current_token = end_char_to_token[start_of_dot]
            logger.debug(f"SPACY FILENAME: Token before 'dot': '{current_token.text}' at {current_token.idx}-{current_token.idx + len(current_token.text)}")

            filename_tokens = []
            # Walk backwards from the token before "dot"
            for i in range(current_token.i, -1, -1):
                token = doc[i]

                # ** THE CRITICAL STOPPING LOGIC **
                # Stop if we hit a clear sentence-starting verb, preposition, or conjunction.
                # This prevents walking back across an entire sentence.
                is_verb = token.pos_ == "VERB"
                is_preposition = token.pos_ == "ADP" and token.text.lower() != "v"
                is_conjunction = token.pos_ == "CCONJ"
                is_punctuation = token.is_punct

                # Check for words that clearly separate context from a filename
                resources = get_resources(self.language)
                filename_actions = resources.get("context_words", {}).get("filename_actions", [])
                filename_linking = resources.get("context_words", {}).get("filename_linking", [])

                is_context_separator = token.lemma_ in filename_actions or token.lemma_ in filename_linking
                
                # Additional common separators that indicate we should stop
                filename_separators = {"file", "document", "script", "program", "application", "the"}
                is_filename_separator = token.text.lower() in filename_separators

                if is_context_separator or is_preposition or is_conjunction or is_punctuation or is_filename_separator:
                    # Always stop at context separators - don't include them in the filename
                    break

                # If we've walked back more than ~5 words, it's probably not a filename.
                if len(filename_tokens) >= 5:
                    break

                # If all checks pass, this token is part of the filename
                filename_tokens.insert(0, token)

            if not filename_tokens:
                logger.debug(f"SPACY FILENAME: No filename tokens collected, skipping")
                continue

            logger.debug(f"SPACY FILENAME: Collected filename tokens: {[t.text for t in filename_tokens]}")

            # Construct the final entity
            start_pos = filename_tokens[0].idx
            # The end position is the end of the original "dot extension" match
            end_pos = match.end()
            entity_text = text[start_pos:end_pos]

            logger.debug(f"SPACY FILENAME: Entity text: '{entity_text}' at {start_pos}-{end_pos}")

            # Final check to ensure we don't create an overlapping entity
            if not is_inside_entity(start_pos, end_pos, all_entities):
                entities.append(Entity(start=start_pos, end=end_pos, text=entity_text, type=EntityType.FILENAME))
                logger.debug(f"SPACY FILENAME: Created filename entity: '{entity_text}'")
            else:
                logger.debug(f"SPACY FILENAME: Entity overlaps with existing entity, skipping")

        # Check if spaCy detection found any new entities, if not, fall back to regex
        entities_after_spacy = len(entities)
        if entities_after_spacy == entities_before_spacy:
            # spaCy didn't find any filename entities, try regex fallback
            logger.debug("SpaCy filename detection found no entities, trying regex fallback")
            self._detect_filenames_regex_fallback(text, entities, all_entities)

    def _detect_spoken_operators(self, text: str, entities: List[Entity], all_entities: List[Entity] = None) -> None:
        """Detect spoken operators using SpaCy token context analysis.

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
                                        type=EntityType.INCREMENT_OPERATOR if operator_patterns[two_word_pattern] == "++" else EntityType.DECREMENT_OPERATOR if operator_patterns[two_word_pattern] == "--" else EntityType.COMPARISON,
                                        metadata={"variable": prev_token.text, "operator": operator_patterns[two_word_pattern]},
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

    def _detect_spoken_operators_regex(self, text: str, entities: List[Entity], all_entities: List[Entity] = None) -> None:
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
                            from .common import NumberParser

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
        self, text: str, entities: List[Entity], all_entities: List[Entity] = None
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
        self, text: str, entities: List[Entity], all_entities: List[Entity] = None
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
                
                # Valid programming context words
                valid_context_words = {"variable", "let", "const", "var", "set", "is", "check", "mi", "my"}
                
                # Check if either there's a preceding context word OR the first word is a context word
                has_valid_context = (
                    preceding_word in valid_context_words or  # Preceding word is valid
                    first_word.lower() in valid_context_words  # First word itself is valid context
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

    def _detect_cli_commands(self, text: str, entities: List[Entity], all_entities: List[Entity] = None) -> None:
        """Detects standalone CLI commands and keywords."""
        if all_entities is None:
            all_entities = entities

        resources = get_resources(self.language)
        multi_word_commands = resources.get("context_words", {}).get("multi_word_commands", [])

        # Only use specific CLI tools and multi-word commands, not all technical terms
        cli_tools = {
            "git", "npm", "pip", "docker", "kubectl", "cargo", "yarn", 
            "brew", "apt", "make", "cmake", "node", "python", "java",
            "mvn", "gradle", "composer", "gem", "conda", "helm",
            "terraform", "ansible", "vagrant"
        }

        # Combine CLI tools with multi-word technical terms and sort by length
        all_commands = sorted(
            list(multi_word_commands) + list(cli_tools),
            key=len,
            reverse=True
        )

        for command in all_commands:
            # Use regex to find whole-word matches
            pattern = rf"\b{re.escape(command)}\b"
            for match in re.finditer(pattern, text, re.IGNORECASE):
                if not is_inside_entity(match.start(), match.end(), all_entities):
                    entities.append(
                        Entity(
                            start=match.start(),
                            end=match.end(),
                            text=match.group(0),
                            type=EntityType.CLI_COMMAND,
                            metadata={'command': match.group(0)}
                        )
                    )

    def _detect_filenames_regex_fallback(self, text: str, entities: List[Entity], all_entities: List[Entity] = None) -> None:
        """Regex-based fallback for filename detection when spaCy is not available."""
        if all_entities is None:
            all_entities = entities
        
        logger.debug(f"REGEX FALLBACK: Processing text '{text}' for filename detection")
        
        # Use the comprehensive pattern that captures both filename and extension
        for match in regex_patterns.FULL_SPOKEN_FILENAME_PATTERN.finditer(text):
            if is_inside_entity(match.start(), match.end(), all_entities):
                continue
                
            full_filename = match.group(0)  # e.g., "my script dot py"
            filename_part = match.group(1)  # e.g., "my script"  
            extension = match.group(2)      # e.g., "py"
            
            # Skip if this looks like it includes command verbs
            # Get the context before the match to check for command patterns
            context_start = max(0, match.start() - 20)
            before_context = text[context_start:match.start()].strip().lower()
            
            # Known filename action words that should not be part of the filename
            resources = get_resources(self.language)
            filename_actions = resources.get("context_words", {}).get("filename_actions", [])
            
            # Check if the filename part starts with a command verb
            filename_words = filename_part.split()
            if filename_words and filename_words[0].lower() in filename_actions:
                # Skip the command verb and only use the remaining words as filename
                actual_filename_words = filename_words[1:]
                if actual_filename_words:
                    # Recalculate the match boundaries to exclude the command verb
                    actual_filename = " ".join(actual_filename_words)
                    # Find where the actual filename starts
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
                                    "method": "regex_fallback"
                                }
                            )
                        )
                        logger.debug(f"Detected filename (regex fallback): '{actual_match_text}' -> filename: '{actual_filename}', ext: '{extension}'")
                        continue
            
            # If no command verb detected, use the full match
            entities.append(
                Entity(
                    start=match.start(),
                    end=match.end(),
                    text=full_filename,
                    type=EntityType.FILENAME,
                    metadata={
                        "filename": filename_part,
                        "extension": extension,
                        "method": "regex_fallback"
                    }
                )
            )
            logger.debug(f"Detected filename (regex fallback): '{full_filename}' -> filename: '{filename_part}', ext: '{extension}'")

    def _detect_programming_keywords(self, text: str, entities: List[Entity], all_entities: List[Entity] = None) -> None:
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
                            metadata={'keyword': match.group(0)}
                        )
                    )


class CodePatternConverter:
    def __init__(self, number_parser: NumberParser, language: str = "en"):
        self.number_parser = number_parser
        self.language = language
        self.config = get_config()

        self.converters = {
            EntityType.CLI_COMMAND: self.convert_cli_command,
            EntityType.PROGRAMMING_KEYWORD: self.convert_programming_keyword,
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

    def convert_cli_command(self, entity: Entity) -> str:
        """Preserve the original text of a CLI command."""
        return entity.text

    def convert_programming_keyword(self, entity: Entity) -> str:
        """Preserve the original text of a programming keyword."""
        return entity.text

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
            # Try parse_as_digits first for filenames, then fall back to regular parsing
            result = self.number_parser.parse_as_digits(match.group(0))
            if result:
                return result
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
        """Convert increment operators using language-specific keywords."""
        # Get language-specific resources
        resources = get_resources(self.language)
        operators = resources.get("spoken_keywords", {}).get("operators", {})
        
        # Find the increment operator keyword (++ symbol)
        increment_keywords = [k for k, v in operators.items() if v == "++"]
        
        if increment_keywords:
            # Try each possible increment keyword pattern
            for keyword in increment_keywords:
                # Build dynamic pattern - escape keyword for regex
                escaped_keyword = re.escape(keyword)
                pattern = rf"(\w+)\s+{escaped_keyword}"
                match = re.match(pattern, entity.text, re.IGNORECASE)
                if match:
                    variable = match.group(1).lower()  # Keep variable lowercase for code
                    return f"{variable}++"
        
        # Fallback for backward compatibility
        match = re.match(r"(\w+)\s+plus\s+plus", entity.text, re.IGNORECASE)
        if match:
            variable = match.group(1).lower()
            return f"{variable}++"
        
        return entity.text

    def convert_decrement_operator(self, entity: Entity) -> str:
        """Convert decrement operators using language-specific keywords."""
        if entity.metadata and "variable" in entity.metadata:
            return f"{entity.metadata['variable'].lower()}--"
            
        # Get language-specific resources
        resources = get_resources(self.language)
        operators = resources.get("spoken_keywords", {}).get("operators", {})
        
        # Find the decrement operator keyword (-- symbol)
        decrement_keywords = [k for k, v in operators.items() if v == "--"]
        
        if decrement_keywords:
            # Try each possible decrement keyword pattern
            for keyword in decrement_keywords:
                # Build dynamic pattern - escape keyword for regex
                escaped_keyword = re.escape(keyword)
                pattern = rf"(\w+)\s+{escaped_keyword}"
                match = re.match(pattern, entity.text, re.IGNORECASE)
                if match:
                    variable = match.group(1).lower()  # Keep variable lowercase for code
                    return f"{variable}--"
        
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
                name = name.replace(" ", "-").lower()
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
