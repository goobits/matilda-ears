#!/usr/bin/env python3
"""Web pattern converters for URLs, emails, and related entities."""

import re

from ..common import Entity, EntityType
from ...core.config import setup_logging

logger = setup_logging(__name__, log_filename="text_formatting.txt")


class WebConverterMixin:
    """Mixin class providing web entity conversion methods.

    This mixin expects the host class to provide:
    - self.number_parser: NumberParser instance
    - self.url_keywords: dict of URL keywords
    """

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
        logger.info(f"Converting protocol URL: '{text}'")

        # Get language-specific keywords
        colon_keywords = [k for k, v in self.url_keywords.items() if v == ":"]
        slash_keywords = [k for k, v in self.url_keywords.items() if v == "/"]

        # Try to find and replace "colon slash slash" pattern using regex for flexibility
        for colon_kw in colon_keywords:
            for slash_kw in slash_keywords:
                # Match colon, slash, slash with flexible whitespace
                # Allow start of string or whitespace before colon
                pattern = rf"(?:^|\s+){re.escape(colon_kw)}\s+{re.escape(slash_kw)}\s+{re.escape(slash_kw)}\s*"
                if re.search(pattern, text):
                    logger.info(f"Found protocol pattern: '{pattern}' in '{text}'")
                    text = re.sub(pattern, "://", text)
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

        # Special handling for IP addresses (sequences of numbers and dots)
        # If we detect this is an IP address (e.g. "one two seven dot zero..."), convert using digit parsing
        if "dot" in url_text.lower() and not any(
            tld in url_text.lower() for tld in ["com", "org", "net", "edu", "gov", "io"]
        ):
            # Check for port number (split by colon)
            port_part = None
            ip_text = url_text
            if " colon " in url_text.lower():
                parts = re.split(r"\s+colon\s+", url_text, maxsplit=1, flags=re.IGNORECASE)
                if len(parts) == 2:
                    ip_text = parts[0]
                    port_text = parts[1]
                    # Parse port
                    parsed_port = self.number_parser.parse_as_digits(port_text.strip())
                    if not parsed_port:
                        parsed_port = self.number_parser.parse(port_text.strip())
                    if not parsed_port:
                        # Fallback for multi-word numbers
                        sub_parts = []
                        for word in port_text.split():
                            digit = self.number_parser.parse(word)
                            if digit and digit.isdigit():
                                sub_parts.append(digit)
                        if sub_parts:
                            parsed_port = "".join(sub_parts)

                    if parsed_port:
                        port_part = parsed_port

            # Split IP by 'dot'
            parts = re.split(r"\s+dot\s+", ip_text, flags=re.IGNORECASE)
            if len(parts) == 4:  # IPv4
                # Check if parts look like numbers
                converted_parts = []
                all_valid = True
                for part in parts:
                    # Use parse_as_digits which handles "one two seven" -> "127"
                    parsed = self.number_parser.parse_as_digits(part.strip())
                    if not parsed:
                        parsed = self.number_parser.parse(part.strip())

                    if parsed and parsed.isdigit():
                        converted_parts.append(parsed)
                    else:
                        # Fallback: try parsing individual words and joining them
                        # e.g. "one two seven" -> "1" "2" "7" -> "127"
                        sub_parts = []
                        for word in part.split():
                            digit = self.number_parser.parse(word)
                            if digit and digit.isdigit():
                                sub_parts.append(digit)
                            else:
                                sub_parts = []
                                break
                        if sub_parts:
                            converted_parts.append("".join(sub_parts))
                        else:
                            all_valid = False
                            break

                if all_valid:
                    ip_str = ".".join(converted_parts)
                    if port_part:
                        return f"{ip_str}:{port_part}{trailing_punct}"
                    return ip_str + trailing_punct

        # Check for port number (split by colon) in regular URLs
        port_part = None
        if " colon " in url_text.lower():
            # Split by colon, but only if it's likely a port (at the end)
            parts = re.split(r"\s+colon\s+", url_text, maxsplit=1, flags=re.IGNORECASE)
            if len(parts) == 2:
                url_text = parts[0]
                port_text = parts[1]
                # Parse port
                parsed_port = self.number_parser.parse_as_digits(port_text.strip())
                if not parsed_port:
                    parsed_port = self.number_parser.parse(port_text.strip())
                if not parsed_port:
                    # Fallback for multi-word numbers
                    sub_parts = []
                    for word in port_text.split():
                        digit = self.number_parser.parse(word)
                        if digit and digit.isdigit():
                            sub_parts.append(digit)
                    if sub_parts:
                        parsed_port = "".join(sub_parts)

                if parsed_port:
                    port_part = parsed_port

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

        if port_part:
            return f"{url_text}:{port_part}{trailing_punct}"

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

    def convert_spoken_email(self, entity: Entity, full_text: str | None = None) -> str:
        """Convert 'user at example dot com' to 'user@example.com'.

        Note: The entity text should contain only the email part, not action phrases.
        Action phrases are handled separately by the formatter.
        """
        text = entity.text.strip()  # Strip leading/trailing spaces
        trailing_punct = ""
        if text and text[-1] in ".!?":
            trailing_punct = text[-1]
            text = text[:-1]

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

            return f"{username}@{domain}{trailing_punct}"

        # Fallback: use case-insensitive regex replacement for language-specific keywords
        dot_keywords = [k for k, v in self.url_keywords.items() if v == "."]
        at_keywords = [k for k, v in self.url_keywords.items() if v == "@"]
        for dot_keyword in dot_keywords:
            text = re.sub(rf"\s+{re.escape(dot_keyword)}\s+", ".", text, flags=re.IGNORECASE)
        for at_keyword in at_keywords:
            text = re.sub(rf"\s+{re.escape(at_keyword)}\s+", "@", text, flags=re.IGNORECASE)
        text = text.replace(" ", "")
        return text + trailing_punct

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
