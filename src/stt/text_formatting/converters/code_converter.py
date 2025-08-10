"""Code pattern converter for programming-related entities."""

import re
from typing import Dict

from stt.core.config import get_config
from stt.text_formatting.common import Entity, EntityType
from stt.text_formatting.constants import get_resources
from .base import BasePatternConverter


class CodePatternConverter(BasePatternConverter):
    """Converter for code-related patterns like CLI commands, operators, and variables."""
    
    def __init__(self, number_parser, language: str = "en"):
        """Initialize code pattern converter."""
        super().__init__(number_parser, language)
        
        # Get configuration for filename formatting
        self.config = get_config()
        
        # Define supported entity types and their converter methods
        self.supported_types: Dict[EntityType, str] = {
            EntityType.CLI_COMMAND: "convert_cli_command",
            EntityType.PROGRAMMING_KEYWORD: "convert_programming_keyword",
            EntityType.FILENAME: "convert_filename",
            EntityType.INCREMENT_OPERATOR: "convert_increment_operator",
            EntityType.DECREMENT_OPERATOR: "convert_decrement_operator",
            EntityType.COMPARISON: "convert_comparison",
            EntityType.ABBREVIATION: "convert_abbreviation",
            EntityType.ASSIGNMENT: "convert_assignment",
            EntityType.COMMAND_FLAG: "convert_command_flag",
            EntityType.SLASH_COMMAND: "convert_slash_command",
            EntityType.UNDERSCORE_DELIMITER: "convert_underscore_delimiter",
            EntityType.SIMPLE_UNDERSCORE_VARIABLE: "convert_simple_underscore_variable",
        }
        
    def convert(self, entity: Entity, full_text: str = "") -> str:
        """Convert a code entity to its final form."""
        converter_method = self.get_converter_method(entity.type)
        if converter_method and hasattr(self, converter_method):
            # Some methods need full_text for context
            if entity.type in [EntityType.FILENAME, EntityType.ABBREVIATION]:
                return getattr(self, converter_method)(entity, full_text)
            else:
                return getattr(self, converter_method)(entity)
        return entity.text

    def convert_cli_command(self, entity: Entity) -> str:
        """Preserve the original text of a CLI command."""
        return entity.text

    def convert_programming_keyword(self, entity: Entity) -> str:
        """Preserve the original text of a programming keyword."""
        return entity.text

    def convert_filename(self, entity: Entity, full_text: str | None = None) -> str:
        """Convert spoken filenames to proper format based on extension"""
        text = entity.text.strip()

        # Strip common leading phrases to isolate the filename
        # But only if the remaining text after stripping looks like a complete filename
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
                remaining = text[len(phrase) :].lstrip()
                # Only strip if the remaining text looks like a simple filename (not compound)
                # E.g., "config file settings.json" should NOT strip "config file" 
                # because "settings.json" alone doesn't represent the full intended filename
                if remaining and not any(word in remaining.lower() for word in ["config", "file", "settings", "main", "index", "app", "client", "server", "data"]):
                    text = remaining
                    break

        # Check for Java package metadata
        if entity.metadata and entity.metadata.get("is_package"):
            # For Java packages, simply replace " dot " with "." and remove spaces
            return re.sub(r"\s*dot\s+", ".", text, flags=re.IGNORECASE).replace(" ", "").lower()

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
        # Handle consecutive underscores first (for dunder patterns like __init__)
        text = re.sub(r"\bunderscore\s+underscore\b", "__", text, flags=re.IGNORECASE)
        
        # Then handle single underscores
        text = re.sub(r"\s+underscore\s+", "_", text, flags=re.IGNORECASE)
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

        # Replace all spoken number sequences with digits FIRST
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
        
        # Handle compound filename patterns AFTER number conversion
        # Insert underscores for common filename patterns like "file version", "test case", etc.
        underscore_patterns = [
            (r"\b(\w+)\s+(version)\s+(\d+)\b", r"\1_\2_\3"),  # "report version 2" -> "report_version_2"
            (r"\b(\w+)\s+(file)\s+(\d+)\b", r"\1_\2_\3"),    # "log file 100" -> "log_file_100" 
            (r"\b(test)\s+(case)\s+(\d+)\b", r"\1_\2_\3"),    # "test case 3" -> "test_case_3"
            (r"\b(config)\s+(v)(\d+)\b", r"\1_\2\3"),         # "config v1" -> "config_v1"
        ]
        
        for pattern, replacement in underscore_patterns:
            filename_part = re.sub(pattern, replacement, filename_part, flags=re.IGNORECASE)

        # If underscores were spoken, they dictate the format
        if has_spoken_underscores:
            # Special handling for dunder patterns (e.g., "__init__")
            # Check if this is already a properly formatted dunder pattern
            if re.match(r'^__\w+__$', filename_part.replace(' ', '')):
                # This is a dunder pattern, just remove spaces without adding underscores
                formatted_filename = filename_part.replace(' ', '').lower()
            else:
                # Regular underscore handling
                formatted_filename = filename_part.replace(' ', '_').lower()
            return f"{formatted_filename}.{extension}"

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

        # Apply fuzzy matching for common misspellings in markdown files
        if extension.lower() == "md":
            fuzzy_corrections = {
                "clod": "claude",
                "claud": "claude",
                "cloud": "claude",
                "readme": "readme",  # Keep as-is
                "read": "readme",  # Expand "read" to "readme" for .md
            }
            casing_words = [fuzzy_corrections.get(word, word) for word in casing_words]

        if format_rule == "PascalCase":
            formatted_filename = "".join(w.capitalize() for w in casing_words)
        elif format_rule == "camelCase":
            formatted_filename = casing_words[0] + "".join(w.capitalize() for w in casing_words[1:])
        elif format_rule == "kebab-case":
            formatted_filename = "-".join(casing_words)
        elif format_rule == "UPPER_SNAKE":
            formatted_filename = "_".join(w.upper() for w in casing_words)
        else:  # Default is lower_snake, but with exceptions for natural language contexts
            # Special case: preserve spaces for compound concepts in configuration files
            # Only for JSON files that represent compound concepts like "config file settings"
            if (extension.lower() == "json" and len(casing_words) > 2 and 
                any(word in casing_words for word in ["config", "file", "settings"])):
                formatted_filename = " ".join(casing_words)  # Preserve spaces for compound concepts
            else:
                formatted_filename = "_".join(casing_words)  # Standard lower_snake format

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

    def convert_abbreviation(self, entity: Entity, full_text: str = "") -> str:
        """Convert abbreviations to proper format with comma when appropriate"""
        # Special case: protected idioms should preserve their original text
        if entity.metadata and entity.metadata.get("idiom"):
            if entity.metadata.get("preserve_case"):
                return entity.text  # Keep original case
            return entity.text.capitalize()  # Just capitalize first letter
            
        text = entity.text.lower().strip()

        # Use abbreviations from resources to get the proper format
        abbreviations = self.resources.get("abbreviations", {})
        converted = abbreviations.get(text, None)
        
        # If we didn't find it in the map, handle common patterns manually
        if converted is None:
            if text == "v s":
                converted = "vs."
            elif text == "i e":
                converted = "i.e."
            elif text == "e g":
                converted = "e.g."
            elif text == "etc":
                converted = "etc."
            elif text in ["i.e.", "e.g.", "vs.", "cf.", "etc."]:
                # Already has periods, keep as is
                converted = text
            else:
                # Fallback: assume it's already in proper format
                converted = text
        
        # Add comma after certain abbreviations when they introduce examples or clarifications
        # This follows standard grammar rules for Latin abbreviations, but only in appropriate contexts
        comma_requiring_abbreviations = {"i.e.", "e.g.", "viz.", "sc.", "cf."}
        
        # Check if this abbreviation typically requires a comma
        if any(converted.startswith(abbrev.rstrip('.')) for abbrev in comma_requiring_abbreviations):
            # Check context from full text to see if there's already an introductory phrase
            context_before = ""
            if full_text and hasattr(entity, 'start') and entity.start > 0:
                # Look at text before this entity for context
                start_context = max(0, entity.start - 20)
                context_before = full_text[start_context:entity.start]
            
            original_text = entity.text.lower().strip()
            
            # Add comma only for standalone abbreviations that clearly introduce examples
            # If there's already an introductory phrase like "for example" before this abbreviation,
            # don't add comma since the phrase already serves that function
            has_intro_phrase_before = (
                "for example" in context_before.lower() or
                "that is" in context_before.lower()
            )
            
            should_add_comma = (
                original_text in ["e g", "e.g.", "i e", "i.e."] and
                not original_text.startswith(("for example", "that is")) and  # Full phrase conversions
                not has_intro_phrase_before  # No intro phrase in context
            ) or (
                converted in ["e.g.", "i.e."] and 
                original_text.startswith(("for example", "that is"))  # Full phrase conversions
            )
            
            if should_add_comma and not converted.endswith(','):
                converted = converted + ","
        
        return converted

    def convert_assignment(self, entity: Entity) -> str:
        """Convert assignment patterns like 'a equals b' -> 'a=b' or 'let a equals b' -> 'let a=b'"""
        if entity.metadata:
            keyword = entity.metadata.get("keyword", "")  # Optional keyword (let, const, var)
            left = entity.metadata.get("left", "")
            right = entity.metadata.get("right", "")

            # Check if right side contains math expressions - if so, convert operators first
            has_math_operators = bool(
                re.search(r"\b(?:plus|minus|times|divided\s+by|over|squared?|cubed?)\b", right, re.IGNORECASE)
            )

            if has_math_operators:
                # Convert math operators in assignment expressions
                right = re.sub(r"\bplus\b", "+", right, flags=re.IGNORECASE)
                right = re.sub(r"\bminus\b", "-", right, flags=re.IGNORECASE)
                right = re.sub(r"\btimes\b", "×", right, flags=re.IGNORECASE)
                right = re.sub(r"\bdivided\s+by\b", "÷", right, flags=re.IGNORECASE)
                right = re.sub(r"\bover\b", "/", right, flags=re.IGNORECASE)
                # Clean up extra spaces after operator substitution
                right = re.sub(r"\s+", " ", right).strip()

                # Now try to parse individual number words that remain
                def convert_number_words(text):
                    words = text.split()
                    converted_words = []
                    for word in words:
                        # Try to convert individual number words
                        parsed_num = self.number_parser.parse_with_validation(word)
                        if parsed_num:
                            converted_words.append(parsed_num)
                        else:
                            converted_words.append(word)
                    return " ".join(converted_words)

                right = convert_number_words(right)
            else:
                # Check if right side contains chained assignments (e.g., "y equals z")
                has_chained_assignment = re.search(r'\b(?:equals|equal)\s+', right, re.IGNORECASE)
                if has_chained_assignment:
                    # Convert chained assignments: "y equals z" -> "y = z"
                    right = re.sub(r'\b(?:equals|equal)\s+', ' = ', right, flags=re.IGNORECASE)
                    # Clean up extra spaces
                    right = re.sub(r'\s+', ' ', right).strip()
                else:
                    # Try to parse number words for simple cases (no operators)
                    parsed_right = self.number_parser.parse_with_validation(right)
                    if parsed_right:
                        right = parsed_right
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

        for _i, word in enumerate(words):
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