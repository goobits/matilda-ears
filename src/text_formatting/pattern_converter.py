#!/usr/bin/env python3
"""
Unified Pattern Converter for Matilda transcriptions.

This class consolidates all entity conversion logic from WebPatternConverter,
CodePatternConverter, and NumericalPatternConverter into a single unified
converter for better maintainability and performance.
"""

import re
from typing import List, Optional, Dict, Any
from .common import Entity, EntityType, NumberParser
from .constants import get_resources
from .utils import is_inside_entity
from ..core.config import get_config, setup_logging
from . import regex_patterns

logger = setup_logging(__name__, log_filename="text_formatting.txt")


class PatternConverter:
    """Unified pattern converter handling all entity type conversions."""
    
    def __init__(self, number_parser: NumberParser, language: str = "en"):
        self.number_parser = number_parser
        self.language = language
        self.config = get_config()
        
        # Load language-specific resources
        self.resources = get_resources(language)
        
        # Get URL keywords for web conversions
        self.url_keywords = self.resources["spoken_keywords"]["url"]
        
        # Operator mappings for numeric conversions
        self.operators = {
            "plus": "+",
            "minus": "-", 
            "times": "×",
            "divided by": "÷",
            "over": "/",  # Re-enabled with contextual checking
            "equals": "=",
            "plus plus": "++",
            "minus minus": "--",
            "equals equals": "==",
        }
        
        # Comprehensive converter mapping
        self.converters = {
            # Web converters
            EntityType.SPOKEN_PROTOCOL_URL: self.convert_spoken_protocol_url,
            EntityType.SPOKEN_URL: self.convert_spoken_url,
            EntityType.SPOKEN_EMAIL: self.convert_spoken_email,
            EntityType.PORT_NUMBER: self.convert_port_number,
            EntityType.URL: self.convert_url,
            EntityType.EMAIL: self.convert_email,
            
            # Code converters
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
            
            # Numeric converters
            EntityType.MATH_EXPRESSION: self.convert_math_expression,
            EntityType.CURRENCY: self.convert_currency,
            EntityType.MONEY: self.convert_currency,  # SpaCy detected money entity
            EntityType.DOLLAR_CENTS: self.convert_dollar_cents,
            EntityType.PERCENT: self.convert_percent,
            EntityType.DATA_SIZE: self.convert_data_size,
            EntityType.FREQUENCY: self.convert_frequency,
            EntityType.TIME_DURATION: self.convert_time_duration,
            EntityType.TIME: self.convert_time_or_duration,  # SpaCy detected TIME entity
            EntityType.TIME_CONTEXT: self.convert_time,
            EntityType.TIME_AMPM: self.convert_time,
            EntityType.PHONE_LONG: self.convert_phone_long,
            EntityType.CARDINAL: self.convert_cardinal,
            EntityType.ORDINAL: self.convert_ordinal,
            EntityType.TIME_RELATIVE: self.convert_time_relative,
            EntityType.FRACTION: self.convert_fraction,
            EntityType.NUMERIC_RANGE: self.convert_numeric_range,
            EntityType.VERSION_TWO: self.convert_version,
            EntityType.VERSION_THREE: self.convert_version,
            EntityType.QUANTITY: self.convert_measurement,
            EntityType.TEMPERATURE: self.convert_temperature,
            EntityType.METRIC_LENGTH: self.convert_metric_unit,
            EntityType.METRIC_WEIGHT: self.convert_metric_unit,
            EntityType.METRIC_VOLUME: self.convert_metric_unit,
            EntityType.ROOT_EXPRESSION: self.convert_root_expression,
            EntityType.MATH_CONSTANT: self.convert_math_constant,
            EntityType.SCIENTIFIC_NOTATION: self.convert_scientific_notation,
            EntityType.MUSIC_NOTATION: self.convert_music_notation,
            EntityType.SPOKEN_EMOJI: self.convert_spoken_emoji,
        }

    # ====================
    # WEB CONVERTERS
    # ====================
    
    def _process_url_params(self, param_text: str) -> str:
        """Process URL parameters: 'a equals b and c equals 3' -> 'a=b&c=3'"""
        # Split on "and" or "ampersand"
        parts = re.split(r"\s+(?:and|ampersand)\s+", param_text, flags=re.IGNORECASE)
        processed_parts = []

        for part in parts:
            equals_match = re.match(r"(\w+)\s+equals\s+(.+)", part.strip(), re.IGNORECASE)
            if equals_match:
                key = equals_match.group(1)
                value = equals_match.group(2).strip()

                # Convert number words if they appear to be numeric values
                if value.lower() in self.number_parser.all_number_words or re.match(
                    r"^(twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety)[\s-]?\w+$", value.lower()
                ):
                    parsed_value = self.number_parser.parse(value)
                    if parsed_value:
                        value = parsed_value
                    else:
                        # If not a number, remove spaces for URL-friendliness
                        value = value.replace(" ", "")

                # Format as key=value with no spaces
                processed_parts.append(f"{key}={value}")

        return "&".join(processed_parts)

    def convert_spoken_protocol_url(self, entity: Entity) -> str:
        """Convert spoken protocol URLs like 'http colon slash slash www.google.com/path?query=value'"""
        text = entity.text.lower()
        
        # Get language-specific keywords
        colon_keywords = [k for k, v in self.url_keywords.items() if v == ":"]
        slash_keywords = [k for k, v in self.url_keywords.items() if v == "/"]
        
        # Try to find and replace "colon slash slash" pattern
        for colon_kw in colon_keywords:
            for slash_kw in slash_keywords:
                pattern = f" {colon_kw} {slash_kw} {slash_kw}"
                if pattern in text:
                    text = text.replace(pattern, "://")
                    break
            else:
                continue
            break
        
        # The rest can be handled by the robust spoken URL converter
        return self.convert_spoken_url(Entity(start=0, end=len(text), text=text, type=EntityType.SPOKEN_URL), text)

    def convert_spoken_url(self, entity: Entity, full_text: str = "") -> str:
        """Convert spoken URL patterns by replacing keywords and removing spaces."""
        url_text = entity.text
        trailing_punct = ""
        if url_text and url_text[-1] in ".!?":
            trailing_punct = url_text[-1]
            url_text = url_text[:-1]

        # Handle query parameters separately first (before converting keywords)
        if "question mark" in url_text.lower():
            # Split at question mark before any conversions
            parts = re.split(r"\s+question\s+mark\s+", url_text, maxsplit=1, flags=re.IGNORECASE)
            if len(parts) == 2:
                base_part = parts[0]
                query_part = parts[1]

                # Use comprehensive keyword conversion for the base URL (handles number words properly)
                base_part = self._convert_url_keywords(base_part)
                # Use specialized parameter processing for query parameters
                processed_params = self._process_url_params(query_part)
                url_text = base_part + "?" + processed_params
            else:
                # Fallback to comprehensive conversion
                url_text = self._convert_url_keywords(url_text)
        else:
            # No query parameters, use comprehensive keyword conversion
            # This method handles both number words and keyword conversion in the right order
            url_text = self._convert_url_keywords(url_text)

        return url_text + trailing_punct

    def _convert_url_keywords(self, url_text: str) -> str:
        """Convert URL keywords in base URL text, properly handling numbers."""
        # IMPORTANT: Parse numbers FIRST, before replacing keywords
        # This ensures "servidor uno punto ejemplo" -> "servidor 1 punto ejemplo" -> "servidor1.ejemplo"
        # instead of "servidor uno punto ejemplo" -> "servidor uno . ejemplo" -> "servidor 1 . ejemplo"

        # First, parse multi-word numbers
        words = url_text.split()
        result_parts = []
        i = 0
        while i < len(words):
            # Attempt to parse a number (could be multi-word)
            # Find the longest sequence of words that is a valid number
            best_parse = None
            end_j = i
            for j in range(len(words), i, -1):
                sub_phrase = " ".join(words[i:j])
                # Try parse_as_digits first for URL contexts
                parsed = self.number_parser.parse_as_digits(sub_phrase)
                if parsed:
                    best_parse = parsed
                    end_j = j
                    break
                # Fall back to regular parsing for compound numbers
                parsed = self.number_parser.parse(sub_phrase)
                if parsed:
                    best_parse = parsed
                    end_j = j
                    break

            if best_parse:
                result_parts.append(best_parse)
                i = end_j
            else:
                result_parts.append(words[i])
                i += 1

        # Rejoin with spaces temporarily to apply keyword replacements
        temp_text = " ".join(result_parts)

        # Then apply keyword replacements
        for keyword, replacement in self.url_keywords.items():
            temp_text = re.sub(rf"\b{re.escape(keyword)}\b", replacement, temp_text, flags=re.IGNORECASE)

        # Finally, remove all spaces to form the URL
        return temp_text.replace(" ", "")

    def convert_url(self, entity: Entity) -> str:
        """Convert URL with proper formatting"""
        url_text = entity.text

        # Fix for http// or https// patterns
        url_text = re.sub(r"\b(https?)//", r"\1://", url_text)

        # Check for trailing punctuation
        trailing_punct = ""
        if url_text and url_text[-1] in ".!?":
            trailing_punct = url_text[-1]
            url_text = url_text[:-1]

        # For SpaCy-detected URLs, the text is already clean and formatted
        # We only need to normalize protocol to lowercase and preserve punctuation
        url_text = re.sub(r"^(HTTPS?|FTP)://", lambda m: m.group(0).lower(), url_text)

        return url_text + trailing_punct

    def convert_email(self, entity: Entity) -> str:
        """Convert email patterns"""
        # Check for trailing punctuation
        text = entity.text
        trailing_punct = ""
        if text and text[-1] in ".!?":
            trailing_punct = text[-1]
            text = text[:-1]

        # For SpaCy-detected emails, the text is already clean and formatted
        # We can use metadata if available for validation, but the text is reliable
        if entity.metadata and "username" in entity.metadata and "domain" in entity.metadata:
            username = entity.metadata["username"]
            domain = entity.metadata["domain"]
            return f"{username}@{domain}{trailing_punct}"

        # For clean SpaCy-detected emails, just return the text as-is
        return text + trailing_punct

    def convert_spoken_email(self, entity: Entity) -> str:
        """Convert 'user at example dot com' or 'email user at example dot com' to 'user@example.com'."""
        text = entity.text.strip()  # Strip leading/trailing spaces
        trailing_punct = ""
        if text and text[-1] in ".!?":
            trailing_punct = text[-1]
            text = text[:-1]

        prefix = ""
        # Handle various action prefixes from language resources
        resources = get_resources(self.language)
        email_actions = resources.get("context_words", {}).get("email_actions", [])
        text_lower = text.lower()
        for action in email_actions:
            action_with_space = f"{action} "
            if text_lower.startswith(action_with_space):
                # Capitalize first letter of action for prefix
                prefix = action.capitalize() + " "
                text = text[len(action_with_space) :]
                break

        # Split at the language-specific "at" keyword to isolate the username part
        at_keywords = [k for k, v in self.url_keywords.items() if v == "@"]
        at_pattern = "|".join(re.escape(k) for k in at_keywords)
        parts = re.split(rf"\s+(?:{at_pattern})\s+", text, flags=re.IGNORECASE)
        if len(parts) == 2:
            username, domain = parts
            # Process username: convert number words first, then handle spoken separators
            username = username.strip()

            # Convert number words in username BEFORE converting separators
            username_parts = username.split()
            converted_parts = []

            # First try to parse the entire username as a digit sequence
            full_parsed = self.number_parser.parse_as_digits(username)
            if full_parsed:
                # The entire username is a digit sequence
                username = full_parsed
            else:
                # Process parts individually, but look for consecutive number sequences
                i = 0
                while i < len(username_parts):
                    part = username_parts[i]

                    # Check if this part starts a number sequence
                    if part.lower() in self.number_parser.all_number_words:
                        # Look for consecutive number words
                        number_sequence = [part]
                        j = i + 1
                        while (
                            j < len(username_parts) and username_parts[j].lower() in self.number_parser.all_number_words
                        ):
                            number_sequence.append(username_parts[j])
                            j += 1

                        # Try to parse the sequence as digits first, then as a number
                        sequence_text = " ".join(number_sequence)
                        parsed = self.number_parser.parse_as_digits(sequence_text)
                        if parsed:
                            converted_parts.append(parsed)
                        else:
                            parsed = self.number_parser.parse(sequence_text)
                            if parsed and parsed.isdigit():
                                converted_parts.append(parsed)
                            else:
                                # Fall back to individual parsing
                                for seq_part in number_sequence:
                                    individual_parsed = self.number_parser.parse(seq_part)
                                    if individual_parsed and individual_parsed.isdigit():
                                        converted_parts.append(individual_parsed)
                                    else:
                                        converted_parts.append(seq_part)
                        i = j
                    else:
                        # Not a number word, keep as is
                        converted_parts.append(part)
                        i += 1

                # Join without spaces for email usernames
                username = "".join(converted_parts)

            # Now convert spoken separators in the processed username
            username = re.sub(r"underscore", "_", username, flags=re.IGNORECASE)
            username = re.sub(r"dash", "-", username, flags=re.IGNORECASE)

            # Format domain: handle number words and dots
            domain = domain.strip()

            # First, convert number words in the domain
            domain_parts = domain.split()
            converted_domain_parts = []

            i = 0
            while i < len(domain_parts):
                part = domain_parts[i]

                # Check if this part starts a number sequence
                if part.lower() in self.number_parser.all_number_words:
                    # Look for consecutive number words
                    number_sequence = [part]
                    j = i + 1
                    while j < len(domain_parts) and domain_parts[j].lower() in self.number_parser.all_number_words:
                        number_sequence.append(domain_parts[j])
                        j += 1

                    # Try to parse the sequence as digits first, then as a number
                    sequence_text = " ".join(number_sequence)
                    parsed = self.number_parser.parse_as_digits(sequence_text)
                    if parsed:
                        converted_domain_parts.append(parsed)
                    else:
                        parsed = self.number_parser.parse(sequence_text)
                        if parsed and parsed.isdigit():
                            converted_domain_parts.append(parsed)
                        else:
                            # Fall back to individual parsing
                            for seq_part in number_sequence:
                                individual_parsed = self.number_parser.parse(seq_part)
                                if individual_parsed and individual_parsed.isdigit():
                                    converted_domain_parts.append(individual_parsed)
                                else:
                                    converted_domain_parts.append(seq_part)
                    i = j
                else:
                    # Not a number word, keep as is
                    converted_domain_parts.append(part)
                    i += 1

            # Rejoin domain parts with spaces, then convert dots
            domain = " ".join(converted_domain_parts)
            dot_keywords = [k for k, v in self.url_keywords.items() if v == "."]
            for dot_keyword in dot_keywords:
                domain = re.sub(rf"\s+{re.escape(dot_keyword)}\s+", ".", domain, flags=re.IGNORECASE)

            # Remove spaces around domain components (but preserve dots)
            domain = re.sub(r"\s+", "", domain)

            return f"{prefix}{username}@{domain}{trailing_punct}"

        # Fallback: use case-insensitive regex replacement for language-specific keywords
        dot_keywords = [k for k, v in self.url_keywords.items() if v == "."]
        at_keywords = [k for k, v in self.url_keywords.items() if v == "@"]
        for dot_keyword in dot_keywords:
            text = re.sub(rf"\s+{re.escape(dot_keyword)}\s+", ".", text, flags=re.IGNORECASE)
        for at_keyword in at_keywords:
            text = re.sub(rf"\s+{re.escape(at_keyword)}\s+", "@", text, flags=re.IGNORECASE)
        text = text.replace(" ", "")
        return prefix + text + trailing_punct

    def convert_port_number(self, entity: Entity) -> str:
        """Convert port numbers like 'localhost colon eight zero eight zero' to 'localhost:8080'"""
        text = entity.text.lower()

        # Extract host and port parts using language-specific colon keyword
        colon_keywords = [k for k, v in self.url_keywords.items() if v == ":"]
        colon_pattern = None
        for colon_keyword in colon_keywords:
            colon_sep = f" {colon_keyword} "
            if colon_sep in text:
                host_part, port_part = text.split(colon_sep, 1)
                colon_pattern = colon_keyword
                break

        if colon_pattern:

            # Use digit words from constants

            port_words = port_part.split()

            # Check if all words are single digits (for sequences like "eight zero eight zero" or "ocho cero ocho cero")
            # Use language-specific number words from the NumberParser
            digit_words = {word: str(num) for word, num in self.number_parser.ones.items() if 0 <= num <= 9}
            all_single_digits = all(word in digit_words for word in port_words)

            if all_single_digits and port_words:
                # Use digit sequence logic with language-specific digit words
                port_digits = [digit_words[word] for word in port_words]
                port_number = "".join(port_digits)
                return f"{host_part}:{port_number}"

            # Use the number parser for compound numbers like "three thousand"
            parsed_port = self.number_parser.parse(port_part)
            if parsed_port and parsed_port.isdigit():
                return f"{host_part}:{parsed_port}"

        # Fallback: replace colon word even if parsing fails
        result = entity.text
        for colon_keyword in colon_keywords:
            result = result.replace(f" {colon_keyword} ", ":")
        return result

    # ====================
    # CODE CONVERTERS
    # ====================

    def convert_cli_command(self, entity: Entity) -> str:
        """Preserve the original text of a CLI command."""
        return entity.text

    def convert_programming_keyword(self, entity: Entity) -> str:
        """Preserve the original text of a programming keyword."""
        return entity.text

    def convert_filename(self, entity: Entity, full_text: str = None) -> str:
        """Convert spoken filenames to proper format based on extension"""
        text = entity.text.strip()

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
        text = re.sub(r"\s*underscore\s*", "_", text, flags=re.IGNORECASE)
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

        # Use abbreviations from resources
        abbreviations = self.resources.get("abbreviations", {})
        return abbreviations.get(text, text)

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

    # ====================
    # NUMERIC CONVERTERS
    # ====================

    def convert_math_expression(self, entity: Entity) -> str:
        """Convert parsed math expressions to properly formatted text"""
        if not entity.metadata or "parsed" not in entity.metadata:
            return entity.text

        try:
            parsed = entity.metadata["parsed"]
            result_parts = []

            # Check for trailing punctuation
            text = entity.text
            trailing_punct = ""
            if text and text[-1] in ".!?":
                trailing_punct = text[-1]

            # Flatten the parsed tokens first for easier processing
            flat_tokens = []

            def flatten_tokens(tokens):
                for token in tokens:
                    if hasattr(token, "__iter__") and not isinstance(token, str):
                        flatten_tokens(token)
                    else:
                        flat_tokens.append(str(token))

            flatten_tokens(parsed)

            # Process tokens with lookahead for better conversion
            i = 0
            while i < len(flat_tokens):
                token = flat_tokens[i]
                # Check if next token is a power word
                if i + 1 < len(flat_tokens) and flat_tokens[i + 1].lower() in ["squared", "cubed"]:
                    # Convert the variable/number and its power together
                    converted = self._convert_math_token(token)
                    power = self._convert_math_token(flat_tokens[i + 1])
                    result_parts.append(converted + power)
                    i += 2  # Skip the power token
                else:
                    # Normal token conversion
                    converted = self._convert_math_token(token)
                    if converted:
                        result_parts.append(converted)
                    i += 1

            # Join and clean up spacing
            result = " ".join(result_parts)
            result = re.sub(r"\s+", " ", result).strip()

            # Ensure there is a single space around binary operators for readability
            # but not for division operator when it's a simple expression
            if "/" in result and len(result_parts) == 3:  # Simple division like "10 / 5"
                result = re.sub(r"\s*/\s*", "/", result).strip()
            else:
                result = re.sub(r"\s*([+\-*/=×÷])\s*", r" \1 ", result).strip()
            # Clean up potential double spaces that might result
            result = re.sub(r"\s+", " ", result)

            # Remove any question marks that may have crept in from pyparsing
            result = result.replace("?", "")

            # Fix spacing around powers (remove space before superscripts)
            result = re.sub(r"\s+([²³⁴⁵⁶⁷⁸⁹⁰¹])", r"\1", result)

            # Fix spacing between numbers and math constants (e.g., "2 π" → "2π")
            result = re.sub(r"(\d)\s+([π∞e])", r"\1\2", result)

            # Fix spacing for single-letter variables next to constants (e.g., "π × r²" not "π×r²")
            result = re.sub(r"([π∞e])×([a-zA-Z])", r"\1 × \2", result)

            # Special case: strip periods from physics equations like "E = MC²"
            # Physics equations ending with superscripts should not have trailing periods
            if trailing_punct == "." and re.search(r"[²³⁴⁵⁶⁷⁸⁹⁰¹]$", result):
                trailing_punct = ""

            # Add back trailing punctuation for math expressions
            return result + trailing_punct

        except (AttributeError, ValueError, TypeError, IndexError) as e:
            logger.debug(f"Error converting math expression: {e}")
            return entity.text

    def _convert_math_token(self, token: str) -> str:
        """Convert individual math tokens"""
        token_lower = str(token).lower()

        # Convert operators
        if token_lower in self.operators:
            return self.operators[token_lower]

        # Handle special math symbols
        if token_lower == "times":
            return "×"
        if token_lower == "over":  # Added handling for "over"
            return "/"

        # Convert number words
        parsed_num = self.number_parser.parse(token_lower)
        if parsed_num:
            return parsed_num

        # Convert powers
        if token_lower == "squared":
            return "²"
        if token_lower == "cubed":
            return "³"

        # Handle Greek letters
        if token_lower == "lambda":
            return "λ"
        if token_lower == "pi":
            return "π"
        if token_lower == "theta":
            return "θ"
        if token_lower == "alpha":
            return "α"
        if token_lower == "beta":
            return "β"
        if token_lower == "gamma":
            return "γ"
        if token_lower == "delta":
            return "δ"

        # Preserve case for variables
        if str(token).isalpha():
            # Keep variables as-is (preserve original case)
            # Single letters like 'r', 'x', 'y' stay lowercase in math
            # Multi-letter variables preserve their original case
            return str(token)

        # Return as-is (other tokens)
        return str(token)

    def convert_currency(self, entity: Entity, full_text: str = "") -> str:
        """Convert currency like 'twenty five dollars' -> '$25' or 'five thousand pounds' -> '£5000'"""
        import re

        text = entity.text

        # Use currency mappings from constants

        # Currencies that go after the amount (post-position)
        post_position_currencies = {"won"}

        post_position_currencies.update({"cent", "cents"})

        # If it's already in currency format (e.g., "25.99" from SpaCy MONEY)
        # Check if there's already a dollar sign before the entity
        if re.match(r"^\d+\.?\d*$", text.strip()):
            # Check if dollar sign precedes this entity in the full text
            if full_text and entity.start > 0 and full_text[entity.start - 1] == "$":
                # Dollar sign already present, just return the number
                return text.strip()
            # No dollar sign, add it
            return f"${text.strip()}"

        # Handle spoken currency (e.g., "twenty five dollars", "five thousand pounds")
        # Check for trailing punctuation in the entity text
        trailing_punct = ""
        if text and text[-1] in ".!?":
            trailing_punct = text[-1]

        # Extract currency unit from metadata or text
        unit = None
        if entity.metadata and "unit" in entity.metadata:
            unit = entity.metadata["unit"].lower()
        else:
            # Try to extract unit from text
            text_lower = text.lower()
            if text_lower and text_lower[-1] in ".!?":
                text_lower = text_lower[:-1]

            # Find which currency word is in the text
            currency_map = self.resources.get("units", {}).get("currency_map", {})
            for currency_word in currency_map:
                if currency_word in text_lower:
                    unit = currency_word
                    break

        # Get the currency symbol
        currency_map = self.resources.get("units", {}).get("currency_map", {})
        symbol = currency_map.get(unit, "$")  # Default to $ if not found

        # Extract and parse the number
        number_text = None
        if entity.metadata and "number" in entity.metadata:
            number_text = entity.metadata["number"]
        else:
            # Remove currency word and parse
            text_lower = text.lower()
            if text_lower and text_lower[-1] in ".!?":
                text_lower = text_lower[:-1]

            if unit:
                # Use regex to remove the currency word at word boundaries
                # Create pattern that matches the currency word at word boundaries
                pattern = r"\b" + re.escape(unit) + r"s?\b"  # Handle plural forms
                number_text = re.sub(pattern, "", text_lower).strip()
            else:
                # Try removing any known currency words
                currency_map = self.resources.get("units", {}).get("currency_map", {})
                for currency_word in currency_map:
                    if currency_word in text_lower:
                        # Use regex for proper word boundary matching
                        pattern = r"\b" + re.escape(currency_word) + r"s?\b"
                        number_text = re.sub(pattern, "", text_lower).strip()
                        unit = currency_word
                        break

        if number_text:
            amount = self.number_parser.parse(number_text)
            if amount:
                # Format based on currency position
                if unit in post_position_currencies:
                    return f"{amount}{symbol}{trailing_punct}"
                return f"{symbol}{amount}{trailing_punct}"

        return entity.text  # Fallback

    def convert_dollar_cents(self, entity: Entity) -> str:
        """Convert 'X dollars and Y cents' to '$X.Y'"""
        if entity.metadata:
            dollars = self.number_parser.parse(entity.metadata.get("dollars", "0"))
            cents = self.number_parser.parse(entity.metadata.get("cents", "0"))
            if dollars and cents:
                # Ensure cents is zero-padded to 2 digits
                cents_str = str(cents).zfill(2)
                return f"${dollars}.{cents_str}"
        return entity.text

    def convert_percent(self, entity: Entity) -> str:
        """Convert numerical percent entities"""
        # Handle new version number detection format
        if entity.metadata and "groups" in entity.metadata and entity.metadata.get("is_percentage"):
            groups = entity.metadata["groups"]
            # Convert the numeric parts
            parts = []
            for group in groups:
                if group:
                    parsed = self.number_parser.parse(group)
                    if parsed:
                        parts.append(parsed)
                    elif group and group.isdigit():
                        parts.append(group)

            if parts:
                # Join with dots for decimal percentages
                percent_str = ".".join(parts)
                return f"{percent_str}%"

        # Original handling for SpaCy-detected percentages
        if entity.metadata and "number" in entity.metadata:
            number_text = entity.metadata["number"]
            # Parse the number text to convert words to digits
            parsed_number = self.number_parser.parse(number_text)
            if parsed_number is not None:
                return f"{parsed_number}%"
            # Fallback to original if parsing fails
            return f"{number_text}%"

        # Fallback: parse from text if no metadata available
        text = entity.text.lower()
        # Try to extract number from text
        match = re.search(r"(.+?)\s+percent", text)
        if match:
            number_text = match.group(1).strip()
            # Use the number parser to convert words to numbers
            number = self.number_parser.parse(number_text)
            if number is not None:
                return f"{number}%"

        return entity.text

    def convert_data_size(self, entity: Entity) -> str:
        """Convert data size entities like 'five megabytes' -> '5MB'"""
        if entity.metadata and "number" in entity.metadata and "unit" in entity.metadata:
            number_text = entity.metadata["number"]
            unit = entity.metadata["unit"].lower()

            # Try to parse the entire number text first
            number_str = self.number_parser.parse(number_text)

            # If that fails, try parsing individual words from the number text
            if number_str is None:
                # Split and try to find valid number words
                words = number_text.split()
                for i, word in enumerate(words):
                    # Try parsing from this word onwards
                    remaining_text = " ".join(words[i:])
                    parsed = self.number_parser.parse(remaining_text)
                    if parsed:
                        number_str = parsed
                        break

            # Final fallback
            if number_str is None:
                number_str = number_text

            unit_map = {
                "byte": "B",
                "bytes": "B",
                "kilobyte": "KB",
                "kilobytes": "KB",
                "kb": "KB",
                "megabyte": "MB",
                "megabytes": "MB",
                "mb": "MB",
                "gigabyte": "GB",
                "gigabytes": "GB",
                "gb": "GB",
                "terabyte": "TB",
                "terabytes": "TB",
                "tb": "TB",
            }
            standard_unit = unit_map.get(unit, unit.upper())
            return f"{number_str}{standard_unit}"  # No space
        return entity.text

    def convert_frequency(self, entity: Entity) -> str:
        """Convert frequency entities like 'two megahertz' -> '2MHz'"""
        if entity.metadata and "number" in entity.metadata and "unit" in entity.metadata:
            number_text = entity.metadata["number"]
            unit = entity.metadata["unit"].lower()

            # Try to parse the entire number text first
            number_str = self.number_parser.parse(number_text)

            # If that fails, try parsing individual words from the number text
            if number_str is None:
                # Split and try to find valid number words
                words = number_text.split()
                for i, word in enumerate(words):
                    # Try parsing from this word onwards
                    remaining_text = " ".join(words[i:])
                    parsed = self.number_parser.parse(remaining_text)
                    if parsed:
                        number_str = parsed
                        break

            # Final fallback
            if number_str is None:
                number_str = number_text

            unit_map = {
                "hertz": "Hz",
                "hz": "Hz",
                "kilohertz": "kHz",
                "khz": "kHz",
                "megahertz": "MHz",
                "mhz": "MHz",
                "gigahertz": "GHz",
                "ghz": "GHz",
            }

            standard_unit = unit_map.get(unit, unit.upper())
            return f"{number_str}{standard_unit}"  # No space

        return entity.text

    def convert_time_duration(self, entity: Entity) -> str:
        """Convert time duration entities."""
        if not entity.metadata:
            return entity.text

        # Unit abbreviation map for compact formatting
        unit_map = {
            "second": "s",
            "seconds": "s",
            "minute": "min",
            "minutes": "min",
            "hour": "h",
            "hours": "h",
            "day": "d",
            "days": "d",
            "week": "w",
            "weeks": "w",
            "month": "mo",
            "months": "mo",
            "year": "y",
            "years": "y",
        }

        # Check if the number part is an ordinal word - if so, this shouldn't be a TIME_DURATION
        if "number" in entity.metadata:
            number_text = entity.metadata["number"].lower()
            # Check if it's an ordinal word
            ordinal_words = self.resources.get("technical", {}).get("ordinal_words", [])
            if number_text in ordinal_words:
                # This is an ordinal + time unit (e.g., "fourth day"), not a duration
                # Return the original text unchanged
                return entity.text

        # Check if this is a compound duration
        if entity.metadata.get("is_compound"):
            # Handle compound durations like "5 hours 30 minutes"
            number1 = entity.metadata.get("number1", "")
            unit1 = entity.metadata.get("unit1", "").lower()
            number2 = entity.metadata.get("number2", "")
            unit2 = entity.metadata.get("unit2", "").lower()

            # Convert number words to digits
            num1_str = self.number_parser.parse(number1)
            if num1_str is None:
                num1_str = number1
            num2_str = self.number_parser.parse(number2)
            if num2_str is None:
                num2_str = number2

            # Get abbreviated units
            abbrev1 = unit_map.get(unit1, unit1)
            abbrev2 = unit_map.get(unit2, unit2)

            # Format as compact notation
            return f"{num1_str}{abbrev1} {num2_str}{abbrev2}"

        # Handle simple duration
        if "number" in entity.metadata and "unit" in entity.metadata:
            number_text = entity.metadata["number"]
            unit = entity.metadata["unit"].lower()

            # Try to parse the entire number text first
            number_str = self.number_parser.parse(number_text)

            # If that fails, try parsing individual words from the number text
            if number_str is None:
                # Split and try to find valid number words
                words = number_text.split()
                for i, word in enumerate(words):
                    # Try parsing from this word onwards
                    remaining_text = " ".join(words[i:])
                    parsed = self.number_parser.parse(remaining_text)
                    if parsed:
                        number_str = parsed
                        break

            # Final fallback
            if number_str is None:
                number_str = number_text

            # Get abbreviated unit
            abbrev = unit_map.get(unit, unit)

            # Use compact formatting for durations
            return f"{number_str}{abbrev}"  # No space for units like h, s, d

        return entity.text

    def convert_time_or_duration(self, entity: Entity) -> str:
        """Convert TIME entities detected by SpaCy.

        This handles both regular time expressions and compound durations.
        SpaCy detects phrases like "five hours thirty minutes" as TIME entities.
        """
        text = entity.text.lower()

        # Check if this is a compound duration pattern
        # Pattern: number + time_unit + number + time_unit
        # Numbers can be compound like "twenty four"
        compound_pattern = re.compile(
            r"\b((?:\w+\s+)*\w+)\s+(seconds?|minutes?|hours?|days?|weeks?|months?|years?)\s+"
            r"((?:\w+\s+)*\w+)\s+(seconds?|minutes?|hours?|days?|weeks?|months?|years?)\b",
            re.IGNORECASE,
        )

        match = compound_pattern.match(text)
        if match:
            # This is a compound duration
            number1 = match.group(1)
            unit1 = match.group(2)
            number2 = match.group(3)
            unit2 = match.group(4)

            # Convert number words to digits
            num1_str = self.number_parser.parse(number1)
            if num1_str:
                number1 = num1_str
            num2_str = self.number_parser.parse(number2)
            if num2_str:
                number2 = num2_str

            # Unit abbreviation map
            unit_map = {
                "second": "s",
                "seconds": "s",
                "minute": "min",
                "minutes": "min",
                "hour": "h",
                "hours": "h",
                "day": "d",
                "days": "d",
                "week": "w",
                "weeks": "w",
                "month": "mo",
                "months": "mo",
                "year": "y",
                "years": "y",
            }

            # Get abbreviated units
            abbrev1 = unit_map.get(unit1.lower(), unit1)
            abbrev2 = unit_map.get(unit2.lower(), unit2)

            # Format as compact notation
            return f"{number1}{abbrev1} {number2}{abbrev2}"

        # Check for simple duration pattern
        simple_pattern = re.compile(
            r"\b(\w+)\s+(seconds?|minutes?|hours?|days?|weeks?|months?|years?)\b", re.IGNORECASE
        )

        match = simple_pattern.match(text)
        if match:
            number = match.group(1)
            unit = match.group(2)

            # Convert number words to digits
            num_str = self.number_parser.parse(number)
            if num_str:
                number = num_str

            # Unit abbreviation map
            unit_map = {
                "second": "s",
                "seconds": "s",
                "minute": "min",
                "minutes": "min",
                "hour": "h",
                "hours": "h",
                "day": "d",
                "days": "d",
                "week": "w",
                "weeks": "w",
                "month": "mo",
                "months": "mo",
                "year": "y",
                "years": "y",
            }

            # Get abbreviated unit
            abbrev = unit_map.get(unit.lower(), unit)

            # Use compact formatting
            return f"{number}{abbrev}"

        # Not a duration pattern, return as-is
        return entity.text

    def convert_time(self, entity: Entity) -> str:
        """Convert time expressions"""
        if entity.metadata and "groups" in entity.metadata:
            groups = entity.metadata["groups"]

            time_words = {
                "one": "1",
                "two": "2",
                "three": "3",
                "four": "4",
                "five": "5",
                "six": "6",
                "seven": "7",
                "eight": "8",
                "nine": "9",
                "ten": "10",
                "eleven": "11",
                "twelve": "12",
                "oh": "0",
                "fifteen": "15",
                "thirty": "30",
                "forty five": "45",
            }

            if entity.type == EntityType.TIME_CONTEXT:
                # Handle 'meet at three thirty'
                context = groups[0]  # 'meet at' or 'at'
                hour = time_words.get(groups[1].lower(), groups[1])
                minute_word = groups[3].lower() if groups[3] else "00"
                minute = time_words.get(minute_word, minute_word)
                if minute.isdigit():
                    minute = minute.zfill(2)
                ampm = groups[4].upper() if len(groups) > 4 and groups[4] else ""

                time_str = f"{hour}:{minute}"
                if ampm:
                    time_str += f" {ampm}"
                return f"{context} {time_str}"

            if entity.type == EntityType.TIME_AMPM:
                # Handle different TIME_AMPM patterns based on group structure
                if len(groups) == 3:
                    if groups[0].lower() == "at":
                        # Pattern: "at three PM" -> groups: ["at", "three", "PM"]
                        hour = time_words.get(groups[1].lower(), groups[1])
                        ampm = groups[2].upper()
                        # Preserve the original case of "at" (might be "At" at sentence start)
                        at_word = groups[0]
                        return f"{at_word} {hour} {ampm}"
                    if groups[2] in ["AM", "PM"]:
                        # Pattern: "three thirty PM" -> groups: ["three", "thirty", "PM"]
                        hour = time_words.get(groups[0].lower(), groups[0])
                        minute_word = groups[1].lower()
                        minute = time_words.get(minute_word, minute_word)
                        if minute.isdigit():
                            minute = minute.zfill(2)
                        ampm = groups[2].upper()
                        return f"{hour}:{minute} {ampm}"
                elif len(groups) == 2:
                    if groups[1] in ["AM", "PM"]:
                        # Pattern: "three PM" -> groups: ["three", "PM"]
                        hour = time_words.get(groups[0].lower(), groups[0])
                        ampm = groups[1].upper()
                        return f"{hour} {ampm}"
                    if groups[1].lower() in ["a", "p"]:
                        # Pattern: "ten a m" -> groups: ["ten", "a"]
                        hour = time_words.get(groups[0].lower(), groups[0])
                        ampm = "AM" if groups[1].lower() == "a" else "PM"
                        return f"{hour} {ampm}"

        return entity.text

    def convert_phone_long(self, entity: Entity) -> str:
        """Convert long form phone numbers"""
        # Extract digit words
        digit_words = {
            "zero": "0",
            "one": "1",
            "two": "2",
            "three": "3",
            "four": "4",
            "five": "5",
            "six": "6",
            "seven": "7",
            "eight": "8",
            "nine": "9",
        }

        words = entity.text.lower().split()
        digits = []
        for word in words:
            if word in digit_words:
                digits.append(digit_words[word])

        if len(digits) == 10:
            return f"({digits[0]}{digits[1]}{digits[2]}) {digits[3]}{digits[4]}{digits[5]}-{digits[6]}{digits[7]}{digits[8]}{digits[9]}"

        return entity.text

    def convert_cardinal(self, entity: Entity, full_text: str = "") -> str:
        """Convert cardinal numbers - only convert standalone clear numbers"""
        # Don't convert numbers that are part of hyphenated compounds
        # Check if this entity is immediately followed by a hyphen (like "One-on-one")
        if full_text:
            # Check character after entity end
            if entity.end < len(full_text) and full_text[entity.end] == "-":
                return entity.text
            # Check character before entity start
            if entity.start > 0 and full_text[entity.start - 1] == "-":
                return entity.text

        # Use the more general parser
        parsed = self.number_parser.parse(entity.text)
        return parsed if parsed else entity.text

    def convert_ordinal(self, entity: Entity) -> str:
        """Convert ordinal numbers with context awareness (first -> 1st, but 1st -> first in conversational contexts)."""
        text_lower = entity.text.lower().replace("-", " ")
        original_text = entity.text

        # Check if input is already numeric (1st, 2nd, etc.)
        numeric_ordinal_pattern = re.compile(r"(\d+)(st|nd|rd|th)", re.IGNORECASE)
        numeric_match = numeric_ordinal_pattern.match(original_text)

        if numeric_match:
            # Input is already numeric - check context to see if we should convert to words
            if hasattr(entity, "parent_text") and entity.parent_text:
                # Context analysis for conversational vs positional usage
                context = entity.parent_text.lower()

                # Conversational patterns where numeric ordinals should become words
                conversational_patterns = [
                    r"\blet\'s\s+do\s+(?:this|that)\s+" + re.escape(original_text.lower()),
                    r"\bwe\s+(?:need|should)\s+(?:to\s+)?(?:handle|do)\s+(?:this|that)\s+"
                    + re.escape(original_text.lower()),
                    r"\b(?:first|1st)\s+(?:thing|step|priority|order|task)",
                    r"\bdo\s+(?:this|that)\s+" + re.escape(original_text.lower()),
                ]

                # Positional/ranking patterns where numeric ordinals should stay numeric
                positional_patterns = [
                    r"\bfinished\s+" + re.escape(original_text.lower()) + r"\s+place",
                    r"\bcame\s+in\s+" + re.escape(original_text.lower()),
                    r"\branked\s+" + re.escape(original_text.lower()),
                    r"\b" + re.escape(original_text.lower()) + r"\s+place",
                    r"\bin\s+the\s+" + re.escape(original_text.lower()),
                ]

                # Check for conversational patterns
                for pattern in conversational_patterns:
                    if re.search(pattern, context):
                        # Convert numeric to word form
                        num_str = numeric_match.group(1)
                        num = int(num_str)

                        # Reverse mapping from numbers to words
                        num_to_word = {
                            1: "first",
                            2: "second",
                            3: "third",
                            4: "fourth",
                            5: "fifth",
                            6: "sixth",
                            7: "seventh",
                            8: "eighth",
                            9: "ninth",
                            10: "tenth",
                            11: "eleventh",
                            12: "twelfth",
                            13: "thirteenth",
                            14: "fourteenth",
                            15: "fifteenth",
                            16: "sixteenth",
                            17: "seventeenth",
                            18: "eighteenth",
                            19: "nineteenth",
                            20: "twentieth",
                            30: "thirtieth",
                            40: "fortieth",
                            50: "fiftieth",
                            60: "sixtieth",
                            70: "seventieth",
                            80: "eightieth",
                            90: "ninetieth",
                            100: "hundredth",
                        }

                        if num in num_to_word:
                            return num_to_word[num]
                        break

                # Check for positional patterns - keep numeric
                for pattern in positional_patterns:
                    if re.search(pattern, context):
                        return original_text  # Keep numeric form

            # Default: keep numeric form if no clear context
            return original_text

        # Input is word form - convert to numeric (existing behavior)
        # First, try a direct lookup in a comprehensive map
        ordinal_map = {
            "first": "1st",
            "second": "2nd",
            "third": "3rd",
            "fourth": "4th",
            "fifth": "5th",
            "sixth": "6th",
            "seventh": "7th",
            "eighth": "8th",
            "ninth": "9th",
            "tenth": "10th",
            "eleventh": "11th",
            "twelfth": "12th",
            "thirteenth": "13th",
            "fourteenth": "14th",
            "fifteenth": "15th",
            "sixteenth": "16th",
            "seventeenth": "17th",
            "eighteenth": "18th",
            "nineteenth": "19th",
            "twentieth": "20th",
            "thirtieth": "30th",
            "fortieth": "40th",
            "fiftieth": "50th",
            "sixtieth": "60th",
            "seventieth": "70th",
            "eightieth": "80th",
            "ninetieth": "90th",
            "hundredth": "100th",
        }
        if text_lower in ordinal_map:
            return ordinal_map[text_lower]

        # If not found, parse the number and apply the suffix rule
        parsed_num_str = self.number_parser.parse_ordinal(text_lower)
        if parsed_num_str:
            num = int(parsed_num_str)
            if 11 <= num % 100 <= 13:
                suffix = "th"
            else:
                suffix = {1: "st", 2: "nd", 3: "rd"}.get(num % 10, "th")
            return f"{parsed_num_str}{suffix}"

        return entity.text

    def convert_time_relative(self, entity: Entity) -> str:
        """Convert relative time expressions (quarter past three -> 3:15)."""
        if not entity.metadata:
            return entity.text

        relative_expr = entity.metadata.get("relative_expr", "").lower()
        hour_word = entity.metadata.get("hour_word", "").lower()

        # Convert hour word to number
        hour_map = {
            "one": 1,
            "two": 2,
            "three": 3,
            "four": 4,
            "five": 5,
            "six": 6,
            "seven": 7,
            "eight": 8,
            "nine": 9,
            "ten": 10,
            "eleven": 11,
            "twelve": 12,
        }

        hour = hour_map.get(hour_word)
        if hour is None:
            # Try to parse as a number
            try:
                hour = int(hour_word)
            except:
                return entity.text

        # Convert relative expression to time
        if relative_expr == "quarter past":
            return f"{hour}:15"
        if relative_expr == "half past":
            return f"{hour}:30"
        if relative_expr == "quarter to":
            # Quarter to the next hour = current hour minus 15 minutes
            prev_hour = hour - 1 if hour > 1 else 12
            return f"{prev_hour}:45"
        if relative_expr == "five past":
            return f"{hour}:05"
        if relative_expr == "ten past":
            return f"{hour}:10"
        if relative_expr == "twenty past":
            return f"{hour}:20"
        if relative_expr == "twenty-five past":
            return f"{hour}:25"
        if relative_expr == "five to":
            # Five to the next hour = current hour minus 5 minutes
            prev_hour = hour - 1 if hour > 1 else 12
            return f"{prev_hour}:55"
        if relative_expr == "ten to":
            # Ten to the next hour = current hour minus 10 minutes
            prev_hour = hour - 1 if hour > 1 else 12
            return f"{prev_hour}:50"
        if relative_expr == "twenty to":
            # Twenty to the next hour = current hour minus 20 minutes
            prev_hour = hour - 1 if hour > 1 else 12
            return f"{prev_hour}:40"
        if relative_expr == "twenty-five to":
            # Twenty-five to the next hour = current hour minus 25 minutes
            prev_hour = hour - 1 if hour > 1 else 12
            return f"{prev_hour}:35"

        return entity.text

    def convert_fraction(self, entity: Entity) -> str:
        """Convert fraction expressions (one half -> ½) and decimal numbers (three point one four -> 3.14)."""
        if not entity.metadata:
            return entity.text

        # Handle decimal numbers (e.g., "three point one four" -> "3.14")
        if entity.metadata.get("is_decimal"):
            return self.number_parser.parse(entity.text) or entity.text

        numerator_word = entity.metadata.get("numerator_word", "").lower()
        denominator_word = entity.metadata.get("denominator_word", "").lower()

        # Map number words to digits
        num_map = {
            "one": "1",
            "two": "2",
            "three": "3",
            "four": "4",
            "five": "5",
            "six": "6",
            "seven": "7",
            "eight": "8",
            "nine": "9",
            "ten": "10",
        }

        # Map denominator words to numbers
        denom_map = {
            "half": "2",
            "halves": "2",
            "third": "3",
            "thirds": "3",
            "quarter": "4",
            "quarters": "4",
            "fourth": "4",
            "fourths": "4",
            "fifth": "5",
            "fifths": "5",
            "sixth": "6",
            "sixths": "6",
            "seventh": "7",
            "sevenths": "7",
            "eighth": "8",
            "eighths": "8",
            "ninth": "9",
            "ninths": "9",
            "tenth": "10",
            "tenths": "10",
        }

        numerator = num_map.get(numerator_word)
        denominator = denom_map.get(denominator_word)

        if numerator and denominator:
            # Create the x/y format first
            fraction_str = f"{numerator}/{denominator}"

            # Map common fractions to Unicode equivalents
            unicode_fractions = {
                "1/2": "½",
                "1/3": "⅓",
                "2/3": "⅔",
                "1/4": "¼",
                "3/4": "¾",
                "1/5": "⅕",
                "2/5": "⅖",
                "3/5": "⅗",
                "4/5": "⅘",
                "1/6": "⅙",
                "5/6": "⅚",
                "1/7": "⅐",
                "1/8": "⅛",
                "3/8": "⅜",
                "5/8": "⅝",
                "7/8": "⅞",
                "1/9": "⅑",
                "1/10": "⅒",
            }

            # Return Unicode character if available, otherwise return x/y format
            return unicode_fractions.get(fraction_str, fraction_str)

        return entity.text

    def convert_numeric_range(self, entity: Entity) -> str:
        """Convert numeric range expressions (ten to twenty -> 10-20)."""
        # Improved regex to handle number words and optional units
        match = re.match(
            r"(.+)\s+to\s+(.+?)(?:\s+(percent))?$", entity.text, re.IGNORECASE
        )
        if not match:
            return entity.text

        start_word, end_word, unit = match.groups()
        
        start_num = self.number_parser.parse(start_word)
        end_num = self.number_parser.parse(end_word)

        if start_num and end_num:
            result = f"{start_num}-{end_num}"
            if unit:
                result += "%"
            return result
        
        return entity.text

    def convert_version(self, entity: Entity) -> str:
        """Convert version numbers from spoken form to numeric form."""
        # Handle VERSION_THREE (keyword-only capitalization)
        if entity.type == EntityType.VERSION_THREE and entity.metadata and "capitalized" in entity.metadata:
            return entity.metadata["capitalized"]

        text = entity.text

        # Extract the prefix (version, python, etc.)
        prefix_match = re.match(r"^(\w+)\s+", text, re.IGNORECASE)
        if prefix_match:
            prefix = prefix_match.group(1)
            # Capitalize the prefix appropriately
            if prefix.lower() in [
                "v",
                "version",
                "python",
                "java",
                "node",
                "ruby",
                "php",
                "go",
                "rust",
                "dotnet",
                "gcc",
            ]:
                if prefix.lower() in ["v", "version"]:
                    prefix = prefix.lower()  # Keep lowercase for version and v
                elif prefix.lower() in ["php", "gcc"]:
                    prefix = prefix.upper()
                else:
                    prefix = prefix.capitalize()
        else:
            prefix = ""

        # Get the groups from metadata
        if entity.metadata and "groups" in entity.metadata:
            groups = entity.metadata["groups"]

            # Convert each component
            parts = []
            for i, group in enumerate(groups):
                if group:
                    # Handle multi-word decimals like "one four" -> "14"
                    if " " in group and i > 0:  # This is a decimal part
                        decimal_digits = []
                        for word in group.split():
                            digit = self.number_parser.parse(word)
                            if digit and len(digit) <= 2 and digit.isdigit():  # Single or double digit
                                decimal_digits.append(digit)
                        if decimal_digits:
                            parts.append("".join(decimal_digits))
                        else:
                            # Fallback to regular parsing
                            parsed = self.number_parser.parse(group)
                            if parsed:
                                parts.append(parsed)
                    else:
                        # Try to parse the number normally
                        parsed = self.number_parser.parse(group)
                        if parsed:
                            parts.append(parsed)
                        elif group.isdigit():
                            parts.append(group)

            # Join with dots
            if parts:
                version_str = ".".join(parts)
                if prefix:
                    # No space for "v" prefix, space for others
                    separator = "" if prefix.lower() == "v" else " "
                    return f"{prefix}{separator}{version_str}"
                return version_str

        # Fallback
        return entity.text

    def convert_measurement(self, entity: Entity, full_text: str = "") -> str:
        """Convert measurements to use proper symbols.

        Examples:
        - "six feet" → "6′"
        - "twelve inches" → "12″"
        - "5 foot 10" → "5′10″"
        - "three and a half feet" → "3.5′"
        - Also handles metric units and temperatures detected as QUANTITY

        """
        text = entity.text.lower()

        # First check if this is actually a temperature
        if "degrees" in text:
            # Check if this is an angle context (rotate, turn, angle, etc.) in the full text
            full_text_lower = full_text.lower() if full_text else ""
            angle_keywords = self.resources.get("context_words", {}).get("angle_keywords", [])
            if any(keyword in full_text_lower for keyword in angle_keywords):
                # This is an angle, not a temperature - return unchanged
                return entity.text
            # Also skip if there's no explicit unit (could be angle)
            if (
                not any(unit in text for unit in ["celsius", "centigrade", "fahrenheit", "c", "f"])
                and not full_text_lower
            ):
                return entity.text

            # Extract temperature parts
            import re

            temp_match = re.match(
                r"(?:(minus|negative)\s+)?"  # Optional sign
                r"(.*?)\s+degrees?"  # Number + degrees
                r"(?:\s+(celsius|centigrade|fahrenheit|c|f))?",  # Optional unit
                text,
                re.IGNORECASE,
            )
            if temp_match:
                sign = temp_match.group(1)
                number_text = temp_match.group(2)
                unit = temp_match.group(3)

                # Parse the number
                parsed_num = self.number_parser.parse(number_text)
                if parsed_num:
                    if sign:
                        parsed_num = f"-{parsed_num}"

                    if unit:
                        unit_lower = unit.lower()
                        if unit_lower in ["celsius", "centigrade", "c"]:
                            return f"{parsed_num}°C"
                        if unit_lower in ["fahrenheit", "f"]:
                            return f"{parsed_num}°F"

                    # No unit specified, just degrees symbol
                    return f"{parsed_num}°"

        # Check if this is a metric unit
        import re

        metric_match = re.match(
            r"(.*?)\s+(millimeters?|millimetres?|centimeters?|centimetres?|meters?|metres?|"
            r"kilometers?|kilometres?|milligrams?|grams?|kilograms?|metric\s+tons?|tonnes?|"
            r"milliliters?|millilitres?|liters?|litres?)",
            text,
            re.IGNORECASE,
        )
        if metric_match:
            number_text = metric_match.group(1)
            unit_text = metric_match.group(2).lower()

            # Handle decimal numbers
            decimal_match = re.match(r"(\w+)\s+point\s+(\w+)", number_text, re.IGNORECASE)
            if decimal_match:
                whole_part = self.number_parser.parse(decimal_match.group(1))
                decimal_part = self.number_parser.parse(decimal_match.group(2))
                if whole_part and decimal_part:
                    parsed_num = f"{whole_part}.{decimal_part}"
                else:
                    parsed_num = self.number_parser.parse(number_text)
            else:
                parsed_num = self.number_parser.parse(number_text)

            if parsed_num:
                # Map to standard abbreviations
                unit_map = {
                    # Length
                    "millimeter": "mm",
                    "millimeters": "mm",
                    "millimetre": "mm",
                    "millimetres": "mm",
                    "centimeter": "cm",
                    "centimeters": "cm",
                    "centimetre": "cm",
                    "centimetres": "cm",
                    "meter": "m",
                    "meters": "m",
                    "metre": "m",
                    "metres": "m",
                    "kilometer": "km",
                    "kilometers": "km",
                    "kilometre": "km",
                    "kilometres": "km",
                    # Weight
                    "milligram": "mg",
                    "milligrams": "mg",
                    "gram": "g",
                    "grams": "g",
                    "kilogram": "kg",
                    "kilograms": "kg",
                    "metric ton": "t",
                    "metric tons": "t",
                    "tonne": "t",
                    "tonnes": "t",
                    # Volume
                    "milliliter": "mL",
                    "milliliters": "mL",
                    "millilitre": "mL",
                    "millilitres": "mL",
                    "liter": "L",
                    "liters": "L",
                    "litre": "L",
                    "litres": "L",
                }

                standard_unit = unit_map.get(unit_text, unit_text.upper())
                return f"{parsed_num} {standard_unit}"

        # Original measurement conversion code continues...
        text = entity.text.lower()

        # Extract number and unit
        import re

        # Pattern for measurements with numbers (digits or words)
        # Match patterns like "six feet", "5 foot", "three and a half inches"
        patterns = [
            # "X and a half feet/inches"
            (r"(\w+)\s+and\s+a\s+half\s+(feet?|foot|inch(?:es)?)", "fraction"),
            # "X feet Y inches" (like "six feet two inches")
            (r"(\w+)\s+(feet?|foot)\s+(\w+)\s+(inch(?:es)?)", "feet_inches"),
            # "X foot Y" (like "5 foot 10" or "five foot ten")
            (r"(\w+)\s+foot\s+(\w+)", "height"),
            # "X miles/yards" (distance measurements)
            (r"(\w+)\s+(miles?|yards?)", "distance"),
            # "X pounds/ounces/lbs" (weight measurements)
            (r"(\w+)\s+(pounds?|lbs?|ounces?|oz)", "weight"),
            # "X feet/foot/inches/inch" (must come after compound patterns)
            (r"(\w+)\s+(feet?|foot|inch(?:es)?)", "simple"),
        ]

        for pattern, pattern_type in patterns:
            match = re.match(pattern, text, re.IGNORECASE)
            if match:
                if pattern_type == "fraction":
                    number_part = match.group(1)
                    unit = match.group(2)

                    # Parse the number
                    parsed_num = self.number_parser.parse(number_part)
                    if parsed_num:
                        # Add 0.5 for "and a half"
                        try:
                            num_value = float(parsed_num) + 0.5
                            number_str = str(num_value).rstrip("0").rstrip(".")
                        except:
                            number_str = f"{parsed_num}.5"
                    else:
                        return entity.text  # Fallback if can't parse

                    # Use proper symbols
                    if "inch" in unit:
                        return f"{number_str}″"
                    if "foot" in unit or "feet" in unit:
                        return f"{number_str}′"

                elif pattern_type == "simple":
                    number_part = match.group(1)
                    unit = match.group(2)

                    # Parse the number
                    parsed_num = self.number_parser.parse(number_part)
                    if not parsed_num:
                        return entity.text  # Fallback if can't parse

                    # Use proper symbols
                    if "inch" in unit:
                        return f"{parsed_num}″"
                    if "foot" in unit or "feet" in unit:
                        return f"{parsed_num}′"

                elif pattern_type == "feet_inches":
                    feet_part = match.group(1)
                    feet_unit = match.group(2)  # "feet" or "foot"
                    inches_part = match.group(3)
                    inches_unit = match.group(4)  # "inches" or "inch"

                    # Parse both parts
                    parsed_feet = self.number_parser.parse(feet_part)
                    parsed_inches = self.number_parser.parse(inches_part)

                    if parsed_feet and parsed_inches:
                        return f"{parsed_feet}′{parsed_inches}″"
                    return entity.text  # Fallback if can't parse

                elif pattern_type == "distance":
                    number_part = match.group(1)
                    unit = match.group(2)

                    # Parse the number
                    parsed_num = self.number_parser.parse(number_part)
                    if not parsed_num:
                        return entity.text  # Fallback if can't parse

                    # Convert to abbreviations
                    if "mile" in unit:
                        return f"{parsed_num} mi"
                    if "yard" in unit:
                        return f"{parsed_num} yd"

                elif pattern_type == "weight":
                    number_part = match.group(1)
                    unit = match.group(2)

                    # Parse the number
                    parsed_num = self.number_parser.parse(number_part)
                    if not parsed_num:
                        return entity.text  # Fallback if can't parse

                    # Convert to abbreviations (avoiding currency symbols)
                    if "pound" in unit or "lbs" in unit:
                        return f"{parsed_num} lbs"
                    if "ounce" in unit or "oz" in unit:
                        return f"{parsed_num} oz"

                elif pattern_type == "height":
                    feet_part = match.group(1)
                    inches_part = match.group(2)

                    # Parse both parts
                    parsed_feet = self.number_parser.parse(feet_part)
                    parsed_inches = self.number_parser.parse(inches_part)

                    if parsed_feet and parsed_inches:
                        return f"{parsed_feet}′{parsed_inches}″"
                    return entity.text  # Fallback if can't parse

        # Fallback
        return entity.text

    def convert_temperature(self, entity: Entity) -> str:
        """Convert temperature expressions to proper format.

        Examples:
        - "twenty degrees celsius" → "20°C"
        - "thirty two degrees fahrenheit" → "32°F"
        - "minus ten degrees" → "-10°"

        """
        if not entity.metadata:
            return entity.text

        sign = entity.metadata.get("sign")
        number_text = entity.metadata.get("number", "")
        unit = entity.metadata.get("unit")

        # Use the improved number parser that handles decimals automatically
        parsed_num = self.number_parser.parse(number_text)

        if not parsed_num:
            return entity.text

        # Add sign if present
        if sign:
            parsed_num = f"-{parsed_num}"

        # Format based on unit
        if unit:
            unit_lower = unit.lower()
            if unit_lower in ["celsius", "centigrade", "c"]:
                return f"{parsed_num}°C"
            if unit_lower in ["fahrenheit", "f"]:
                return f"{parsed_num}°F"

        # No unit specified, just degrees
        return f"{parsed_num}°"

    def convert_metric_unit(self, entity: Entity) -> str:
        """Convert metric units to standard abbreviations.

        Examples:
        - "five kilometers" → "5 km"
        - "two point five centimeters" → "2.5 cm"
        - "ten kilograms" → "10 kg"
        - "three liters" → "3 L"

        """
        if not entity.metadata:
            return entity.text

        number_text = entity.metadata.get("number", "")
        unit = entity.metadata.get("unit", "").lower()

        # Use the improved number parser that handles decimals automatically
        parsed_num = self.number_parser.parse(number_text)

        if not parsed_num:
            return entity.text

        # Unit mappings
        unit_map = {
            # Length
            "millimeter": "mm",
            "millimeters": "mm",
            "millimetre": "mm",
            "millimetres": "mm",
            "mm": "mm",
            "centimeter": "cm",
            "centimeters": "cm",
            "centimetre": "cm",
            "centimetres": "cm",
            "cm": "cm",
            "meter": "m",
            "meters": "m",
            "metre": "m",
            "metres": "m",
            "m": "m",
            "kilometer": "km",
            "kilometers": "km",
            "kilometre": "km",
            "kilometres": "km",
            "km": "km",
            # Weight
            "milligram": "mg",
            "milligrams": "mg",
            "mg": "mg",
            "gram": "g",
            "grams": "g",
            "g": "g",
            "kilogram": "kg",
            "kilograms": "kg",
            "kg": "kg",
            "metric ton": "t",
            "metric tons": "t",
            "tonne": "t",
            "tonnes": "t",
            # Volume
            "milliliter": "mL",
            "milliliters": "mL",
            "millilitre": "mL",
            "millilitres": "mL",
            "ml": "mL",
            "liter": "L",
            "liters": "L",
            "litre": "L",
            "litres": "L",
            "l": "L",
        }

        standard_unit = unit_map.get(unit, unit.upper())
        return f"{parsed_num} {standard_unit}"

    def convert_root_expression(self, entity: Entity) -> str:
        """Convert root expressions to mathematical notation.

        Examples:
        - "square root of sixteen" → "√16"
        - "cube root of twenty seven" → "∛27"
        - "square root of x plus one" → "√(x + 1)"

        """
        if not entity.metadata:
            return entity.text

        root_type = entity.metadata.get("root_type", "")
        expression = entity.metadata.get("expression", "")

        # Process the expression
        # First, try to parse it as a number
        parsed_num = self.number_parser.parse(expression)
        if parsed_num:
            # Simple number
            if root_type == "square":
                return f"√{parsed_num}"
            if root_type == "cube":
                return f"∛{parsed_num}"

        # Otherwise, it might be a more complex expression
        # Convert any number words in the expression
        words = expression.split()
        converted_words = []
        for word in words:
            # Try to parse as number
            num = self.number_parser.parse(word)
            if num:
                converted_words.append(num)
            # Convert operators
            elif word.lower() == "plus":
                converted_words.append("+")
            elif word.lower() == "minus":
                converted_words.append("-")
            elif word.lower() == "times":
                converted_words.append("×")
            elif word.lower() == "over":
                converted_words.append("/")
            else:
                converted_words.append(word)

        # Join the converted expression
        converted_expr = " ".join(converted_words)

        # Add parentheses if expression contains operators
        if any(op in converted_expr for op in ["+", "-", "×", "/"]):
            if root_type == "square":
                return f"√({converted_expr})"
            if root_type == "cube":
                return f"∛({converted_expr})"
        elif root_type == "square":
            return f"√{converted_expr}"
        elif root_type == "cube":
            return f"∛{converted_expr}"

        # Fallback
        return entity.text

    def convert_math_constant(self, entity: Entity) -> str:
        """Convert mathematical constants to their symbols.

        Examples:
        - "pi" → "π"
        - "infinity" → "∞"

        """
        if not entity.metadata:
            return entity.text

        constant = entity.metadata.get("constant", "").lower()

        # Constant mappings
        constant_map = {
            "pi": "π",
            "infinity": "∞",
            "inf": "∞",
        }

        return constant_map.get(constant, entity.text)

    def convert_scientific_notation(self, entity: Entity) -> str:
        """Convert scientific notation to proper format.

        Examples:
        - "two point five times ten to the sixth" → "2.5 × 10⁶"
        - "three times ten to the negative four" → "3 × 10⁻⁴"

        """
        if not entity.metadata:
            return entity.text

        base = entity.metadata.get("base", "")
        exponent = entity.metadata.get("exponent", "")

        # Parse the base number
        parsed_base = self.number_parser.parse(base)
        if not parsed_base:
            # Try handling "point" for decimals
            if "point" in base.lower():
                parts = base.lower().split("point")
                if len(parts) == 2:
                    whole = self.number_parser.parse(parts[0].strip())
                    # Handle decimal part that might be multiple digits like "zero two"
                    decimal_part = parts[1].strip()
                    decimal_digits = []
                    for word in decimal_part.split():
                        digit = self.number_parser.parse(word)
                        if digit:
                            decimal_digits.append(digit)
                    if whole and decimal_digits:
                        parsed_base = f"{whole}.{''.join(decimal_digits)}"

            if not parsed_base:
                return entity.text

        # Parse the exponent
        is_negative = False
        exp_text = exponent.lower()

        # Check for negative exponent
        if "negative" in exp_text or "minus" in exp_text:
            is_negative = True
            exp_text = exp_text.replace("negative", "").replace("minus", "").strip()

        # Parse the exponent number
        parsed_exp = self.number_parser.parse(exp_text)

        # If number parser fails, try ordinal parsing
        if not parsed_exp:
            parsed_exp = self.number_parser.parse_ordinal(exp_text)

        if not parsed_exp:
            return entity.text

        # Convert to superscript
        superscript_map = {
            "0": "⁰",
            "1": "¹",
            "2": "²",
            "3": "³",
            "4": "⁴",
            "5": "⁵",
            "6": "⁶",
            "7": "⁷",
            "8": "⁸",
            "9": "⁹",
            "-": "⁻",
        }

        # Build superscript exponent
        superscript_exp = ""
        if is_negative:
            superscript_exp = "⁻"

        for digit in str(parsed_exp):
            superscript_exp += superscript_map.get(digit, digit)

        # Format the result
        return f"{parsed_base} × 10{superscript_exp}"

    def convert_music_notation(self, entity: Entity) -> str:
        """Convert music notation to symbols.

        Examples:
        - "C sharp" → "C♯"
        - "B flat" → "B♭"
        - "E natural" → "E♮"

        """
        if not entity.metadata:
            return entity.text

        note = entity.metadata.get("note", "")
        accidental = entity.metadata.get("accidental", "")

        accidental_map = {"sharp": "♯", "flat": "♭", "natural": "♮"}

        symbol = accidental_map.get(accidental, "")
        if symbol:
            return f"{note}{symbol}"

        return entity.text

    def convert_spoken_emoji(self, entity: Entity) -> str:
        """Convert spoken emoji expressions to emoji characters.

        Examples:
        - "smiley face" → "🙂"
        - "rocket emoji" → "🚀"

        """
        if not entity.metadata:
            return entity.text

        emoji_key = entity.metadata.get("emoji_key", "").lower()
        is_implicit = entity.metadata.get("is_implicit", False)

        if is_implicit:
            # Look up in implicit map
            emoji = regex_patterns.SPOKEN_EMOJI_IMPLICIT_MAP.get(emoji_key)
        else:
            # Look up in explicit map
            emoji = regex_patterns.SPOKEN_EMOJI_EXPLICIT_MAP.get(emoji_key)

        if emoji:
            # The detection regex now captures trailing punctuation in the entity text
            # Preserve it after conversion.
            trailing_punct = re.search(r"([.!?]*)$", entity.text).group(1)
            return emoji + trailing_punct

        return entity.text