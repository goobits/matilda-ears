#!/usr/bin/env python3
"""Web-related entity detection and conversion for Matilda transcriptions."""

import re
from typing import List
from .common import Entity, EntityType, NumberParser
from .utils import is_inside_entity
from ..core.config import setup_logging
from . import regex_patterns
from .constants import EMAIL_ACTION_WORDS, LOCATION_NOUNS, AMBIGUOUS_NOUNS, DIGIT_WORDS, get_resources

logger = setup_logging(__name__, log_filename="text_formatting.txt")


class WebEntityDetector:
    def __init__(self, nlp=None, language: str = "en"):
        """Initialize WebEntityDetector with dependency injection.

        Args:
            nlp: SpaCy NLP model instance. If None, will load from nlp_provider.
            language: Language code for resource loading (default: 'en')

        """
        if nlp is None:
            from .nlp_provider import get_nlp

            nlp = get_nlp()

        self.nlp = nlp
        self.language = language
        
        # Build patterns dynamically for the specified language
        self.spoken_url_pattern = regex_patterns.get_spoken_url_pattern(language)
        self.port_number_pattern = regex_patterns.get_port_number_pattern(language)
        self.spoken_protocol_pattern = regex_patterns.get_spoken_protocol_pattern(language)
        self.spoken_email_pattern = regex_patterns.get_spoken_email_pattern(language)
        # Note: port_pattern is the same as port_number_pattern

    def detect(self, text: str, entities: List[Entity]) -> List[Entity]:
        """Detects all web-related entities."""
        web_entities = []
        self._detect_spoken_protocol_urls(text, web_entities, entities)
        self._detect_spoken_urls(text, web_entities, entities)
        self._detect_spoken_emails(text, web_entities, entities)
        self._detect_port_numbers(text, web_entities, entities)
        self._detect_links(text, web_entities)
        return web_entities

    def _detect_spoken_protocol_urls(
        self, text: str, web_entities: List[Entity], existing_entities: List[Entity]
    ) -> None:
        """Detect spoken protocols like 'http colon slash slash'."""
        for match in self.spoken_protocol_pattern.finditer(text):
            if not is_inside_entity(match.start(), match.end(), existing_entities):
                web_entities.append(
                    Entity(
                        start=match.start(), end=match.end(), text=match.group(), type=EntityType.SPOKEN_PROTOCOL_URL
                    )
                )

    def _detect_spoken_urls(self, text: str, web_entities: List[Entity], existing_entities: List[Entity]) -> None:
        """Detect spoken URLs like 'example dot com slash path'."""
        for match in self.spoken_url_pattern.finditer(text):
            if not is_inside_entity(match.start(), match.end(), existing_entities):
                # Include trailing punctuation in the entity if present
                full_match = match.group(0)  # Full match including punctuation
                web_entities.append(
                    Entity(start=match.start(), end=match.end(), text=full_match, type=EntityType.SPOKEN_URL)
                )

    def _detect_spoken_emails(self, text: str, web_entities: List[Entity], existing_entities: List[Entity]) -> None:
        """Detect spoken emails like 'john at example.com' using spaCy for context."""
        for match in self.spoken_email_pattern.finditer(text):
            if is_inside_entity(match.start(), match.end(), existing_entities):
                continue

            # spaCy CONTEXT CHECK to avoid misinterpreting "docs at python.org"
            if self.nlp:
                try:
                    # Analyze the text to understand the grammar around the match
                    doc = self.nlp(text)
                    at_token = None
                    # Find the "at" token within the matched text
                    for token in doc:
                        if token.text.lower() == "at" and match.start() <= token.idx < match.end():
                            at_token = token
                            break

                    if at_token:
                        # Find the word that comes before "at" in the match
                        match_text = match.group()
                        at_pos = match_text.lower().find(" at ")
                        if at_pos > 0:
                            # Get the part before "at"
                            before_at = match_text[:at_pos].strip()
                            # Remove "email" prefix if present
                            if before_at.lower().startswith("email "):
                                before_at = before_at[6:].strip()

                            # Check if this looks like a location reference vs. an actual email address
                            # Look at the action word at the beginning of the match
                            has_email_action = any(
                                match_text.lower().startswith(action) for action in EMAIL_ACTION_WORDS
                            )

                            # Use location and ambiguous nouns from constants

                            words_before_at = before_at.split()
                            if words_before_at:
                                last_word = words_before_at[-1].lower()
                                # Skip if it's a clear location noun
                                if last_word in LOCATION_NOUNS:
                                    logger.debug(
                                        f"Skipping email match '{match.group()}' - '{last_word}' indicates location context"
                                    )
                                    continue
                                # Skip ambiguous nouns only if there's no email action
                                if last_word in AMBIGUOUS_NOUNS and not has_email_action:
                                    logger.debug(
                                        f"Skipping email match '{match.group()}' - '{last_word}' without email action indicates location context"
                                    )
                                    continue
                except (AttributeError, ValueError, IndexError):
                    logger.warning("SpaCy context check for email failed, falling back to regex.")
                    # Fallback to regex-only if spaCy fails

            web_entities.append(
                Entity(start=match.start(), end=match.end(), text=match.group(), type=EntityType.SPOKEN_EMAIL)
            )

    def _detect_port_numbers(self, text: str, web_entities: List[Entity], existing_entities: List[Entity]) -> None:
        """Detect port numbers like 'localhost colon eight zero eight zero'."""
        for match in self.port_number_pattern.finditer(text):
            if not is_inside_entity(match.start(), match.end(), existing_entities):
                web_entities.append(
                    Entity(start=match.start(), end=match.end(), text=match.group(), type=EntityType.PORT_NUMBER)
                )

    def _detect_links(self, text: str, entities: List[Entity]) -> None:
        """Detect URLs and emails using SpaCy's built-in token attributes.

        This method replaces the regex-based URL and email detection with
        SpaCy's more accurate token-level detection.
        """
        if not self.nlp:
            return
        try:
            doc = self.nlp(text)
        except (AttributeError, ValueError, IndexError) as e:
            logger.warning(f"SpaCy link detection failed: {e}")
            return

        # Iterate through tokens to find URLs and emails
        for token in doc:
            # Check for URL tokens
            if token.like_url:
                # Get the exact character positions
                start_pos = token.idx
                end_pos = token.idx + len(token.text)

                if not is_inside_entity(start_pos, end_pos, entities):
                    entities.append(Entity(start=start_pos, end=end_pos, text=token.text, type=EntityType.URL))

            # Check for email tokens
            elif token.like_email:
                # Get the exact character positions
                start_pos = token.idx
                end_pos = token.idx + len(token.text)

                if not is_inside_entity(start_pos, end_pos, entities):
                    # Parse email to extract username and domain
                    parts = token.text.split("@")
                    metadata = {}
                    if len(parts) == 2:
                        metadata = {"username": parts[0], "domain": parts[1]}

                    entities.append(
                        Entity(start=start_pos, end=end_pos, text=token.text, type=EntityType.EMAIL, metadata=metadata)
                    )


class WebPatternConverter:
    def __init__(self, number_parser: NumberParser, language: str = "en"):
        self.number_parser = number_parser
        self.language = language

        # Use URL keywords from resources for the specified language
        self.url_keywords = get_resources(language)["spoken_keywords"]["url"]

        self.converters = {
            EntityType.SPOKEN_PROTOCOL_URL: self.convert_spoken_protocol_url,
            EntityType.SPOKEN_URL: self.convert_spoken_url,
            EntityType.SPOKEN_EMAIL: self.convert_spoken_email,
            EntityType.PORT_NUMBER: self.convert_port_number,
            EntityType.URL: self.convert_url,
            EntityType.EMAIL: self.convert_email,
        }

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
        text = entity.text.lower().replace(" colon slash slash", "://")
        # The rest can be handled by the robust spoken URL converter
        return self.convert_spoken_url(Entity(start=0, end=len(text), text=text, type=EntityType.SPOKEN_URL), text)

    def convert_spoken_url(self, entity: Entity, full_text: str) -> str:
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
        email_actions = get_resources(self.language).get("context_words", {}).get("email_actions", [])
        text_lower = text.lower()
        for action in email_actions:
            action_with_space = f"{action} "
            if text_lower.startswith(action_with_space):
                # Capitalize first letter of action for prefix
                prefix = action.capitalize() + " "
                text = text[len(action_with_space):]
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

            # Check if all words are single digits (for sequences like "eight zero eight zero")
            all_single_digits = all(word in DIGIT_WORDS for word in port_words)

            if all_single_digits and port_words:
                # Use digit sequence logic
                port_digits = [DIGIT_WORDS[word] for word in port_words]
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
