#!/usr/bin/env python3
"""Code pattern converters for programming constructs."""

import re

from ...common import Entity
from ...constants import get_resources
from ....core.config import setup_logging

logger = setup_logging(__name__, log_filename="text_formatting.txt")


class CodeConverterMixin:
    """Mixin class providing code entity conversion methods.

    This mixin expects the host class to provide:
    - self.number_parser: NumberParser instance
    - self.config: Config instance
    - self.language: str
    - self.resources: dict
    - self.operators: dict
    """

    def convert_cli_command(self, entity: Entity) -> str:
        """Preserve the original text of a CLI command."""
        return entity.text

    def convert_programming_keyword(self, entity: Entity) -> str:
        """Preserve the original text of a programming keyword."""
        return entity.text

    def convert_filename(self, entity: Entity, full_text: str | None = None) -> str:
        """Convert spoken filenames to proper format based on extension"""
        text = entity.text.strip()
        logger.debug(f"Converting filename: '{text}'")

        # Strip common leading phrases to isolate the filename
        leading_phrases_to_strip = [
            "edit the config file",
            "open the config file",
            "check the config file",
            "edit the file",
            "open the file",
            "check the file",
            "save the file",
            "the config file",
            "config file",
            "the file",
            "my favorite file is",
        ]
        for phrase in leading_phrases_to_strip:
            if text.lower().startswith(phrase):
                text = text[len(phrase) :].lstrip()
                break

        # First, handle all spoken separators to create a clean string
        text = re.sub(r"\s*underscore\s*", "_", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*dash\s*", "-", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*dot\s+", ".", text, flags=re.IGNORECASE)

        # Special handling for CLAUDE.md
        if text.lower() == "clod.md" or text.lower().startswith("clod."):
            return "CLAUDE.md"

        # Check for Java package metadata
        if entity.metadata and entity.metadata.get("is_package"):
            # For Java packages, simply replace " dot " with "." and remove spaces
            return text.replace(" ", "").lower()

        # Check for and handle explicit underscore usage first
        # Check both the entity text and the full text context if available
        has_spoken_underscores = "_" in text  # Since we already replaced " underscore " with "_"
        if not has_spoken_underscores and full_text:
            # Check if underscore was spoken near this entity
            entity_pos = full_text.find(entity.text)
            if entity_pos > 0:
                context_start = max(0, entity_pos - 20)
                context = full_text[context_start : entity.end]
                has_spoken_underscores = " underscore " in context.lower()

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
            fallback = self.number_parser.parse(match.group(0)) or match.group(0)
            return fallback

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

        # Special handling for version patterns - treat "v<number>" as single units
        # Handle both "v1" and "v 1" patterns by collapsing them before splitting

        # Collapse "v <number>" patterns into "v<number>" to treat as single units
        version_collapse_pattern = r"\bv\s+(\d+(?:\.\d+)*)\b"
        filename_part = re.sub(version_collapse_pattern, r"v\1", filename_part, flags=re.IGNORECASE)

        # Now split on spaces, underscores, and hyphens
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
            operator = entity.metadata.get("operator", "==")

            # Try to parse the right side if it's a number word
            parsed_right = self.number_parser.parse(right)
            if parsed_right:
                right = parsed_right

            # Check for an "if" at the beginning by inspecting the original text
            if entity.text.lower().strip().startswith("if "):
                return f"if {left} {operator} {right}"
            return f"{left} {operator} {right}"
        return entity.text

    def convert_abbreviation(self, entity: Entity) -> str:
        """Convert abbreviations to proper lowercase format"""
        text = entity.text.lower()

        # Handle "v s" specifically
        if text == "v s":
            return "vs."

        # Use abbreviations from resources
        abbreviations = self.resources.get("abbreviations", {})
        return str(abbreviations.get(text, text))

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

            # Check if right side contains math expressions
            # Build regex from operators list for i18n support
            math_ops = list(self.operators.keys()) + ["squared", "cubed"]
            if self.language == "es":
                math_ops.extend(["al cuadrado", "al cubo", "más", "menos", "por", "entre", "dividido por"])

            ops_pattern = r"\b(?:" + "|".join(re.escape(op) for op in math_ops) + r")\b"
            has_math_operators = bool(re.search(ops_pattern, right, re.IGNORECASE))

            if has_math_operators:
                # Process math operators in the right side
                # For simple processing, we replace known multi-word operators first
                right_processed = right.lower()

                # Sort operators by length (descending) to handle multi-word operators first
                sorted_ops = sorted(self.operators.keys(), key=len, reverse=True)

                for op in sorted_ops:
                    if op in right_processed:
                        # Replace operator words with symbols
                        # Use word boundaries to avoid partial matches
                        pattern = r"\b" + re.escape(op) + r"\b"
                        right_processed = re.sub(pattern, self.operators[op], right_processed)

                # Handle squared/cubed
                right_processed = re.sub(r"\bsquared\b", "²", right_processed)
                right_processed = re.sub(r"\bcubed\b", "³", right_processed)
                if self.language == "es":
                    right_processed = re.sub(r"\bal cuadrado\b", "²", right_processed)
                    right_processed = re.sub(r"\bal cubo\b", "³", right_processed)

                # Process number words
                words = right_processed.split()
                converted_words = []
                for word in words:
                    # Skip operators/symbols
                    if word in ["+", "-", "×", "÷", "/", "=", "²", "³"]:
                        converted_words.append(word)
                    # Check for number words
                    elif word in self.number_parser.all_number_words:
                        parsed = self.number_parser.parse(word)
                        converted_words.append(parsed if parsed else word)
                    else:
                        converted_words.append(word)

                right = " ".join(converted_words)

                # Ensure proper spacing around operators
                for op in ["+", "-", "×", "÷", "/", "="]:
                    right = right.replace(op, f" {op} ")

                # Clean up double spaces
                right = re.sub(r"\s+", " ", right).strip()

            elif " " in right:
                # If the right side seems like a function call (multiple words), snake_case it.
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
                    argument_words = {"test", "file", "message", "mode", "path", "name", "value", "option", "flag"}
                    if second_word.lower() in argument_words:
                        # Return the flag followed by the argument (preserving the argument)
                        return f"--{first_word.lower()} {second_word.lower()}"

                # Default: replace spaces with hyphens for multi-word flags
                name = name.replace(" ", "-").lower()
                return f"--{name}"
            if flag_type == "short":
                return f"-{name.lower()}"
            if flag_type == "preformatted":
                # Already-formatted flag, just ensure lowercase
                return f"--{name.lower()}"

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
        result_words: list[str] = []

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
