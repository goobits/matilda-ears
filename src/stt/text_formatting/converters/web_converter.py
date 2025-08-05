"""Web pattern converter for URLs, emails, and port numbers."""

import re
from typing import Dict

from stt.text_formatting.common import Entity, EntityType
from .base import BasePatternConverter


class WebPatternConverter(BasePatternConverter):
    """Converter for web-related patterns like URLs, emails, and port numbers."""
    
    def __init__(self, number_parser, language: str = "en"):
        """Initialize web pattern converter."""
        super().__init__(number_parser, language)
        
        # Get URL keywords for web conversions
        self.url_keywords = self.resources["spoken_keywords"]["url"]
        
        # Define supported entity types and their converter methods
        self.supported_types: Dict[EntityType, str] = {
            EntityType.URL: "convert_url",
            EntityType.SPOKEN_URL: "convert_spoken_url",
            EntityType.SPOKEN_PROTOCOL_URL: "convert_spoken_protocol_url",
            EntityType.EMAIL: "convert_email",
            EntityType.SPOKEN_EMAIL: "convert_spoken_email",
            EntityType.PORT_NUMBER: "convert_port_number",
        }
        
    def convert(self, entity: Entity, full_text: str = "") -> str:
        """Convert a web entity to its final form."""
        converter_method = self.get_converter_method(entity.type)
        if converter_method and hasattr(self, converter_method):
            if entity.type == EntityType.SPOKEN_URL:
                return getattr(self, converter_method)(entity, full_text)
            elif entity.type == EntityType.SPOKEN_EMAIL:
                return getattr(self, converter_method)(entity, full_text)
            else:
                return getattr(self, converter_method)(entity)
        return entity.text

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
                    # If not a number, remove spaces for URL-friendliness
                    value = parsed_value or value.replace(" ", "")

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

    def convert_spoken_email(self, entity: Entity, full_text: str | None = None) -> str:
        """
        Convert 'user at example dot com' to 'user@example.com'.

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
        """Convert port numbers like 'localhost colon eight zero eight zero' to 'localhost:8080'
        Also handles spoken domains like 'api dot service dot com colon three thousand' to 'api.service.com:3000'"""
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
            # Convert spoken domain in host part (e.g., "api dot service dot com" -> "api.service.com")
            host_part = self._convert_spoken_domain(host_part)

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

    def _convert_spoken_domain(self, domain_text: str) -> str:
        """Convert spoken domain like 'api dot service dot com' to 'api.service.com'
        Also handles IP addresses like 'one two seven dot zero dot zero dot one' to '127.0.0.1'"""
        # Get dot keywords from URL keywords
        dot_keywords = [k for k, v in self.url_keywords.items() if v == "."]

        result = domain_text.strip()
        
        # First, replace spoken dots with actual dots to get the structure
        temp_result = result
        for dot_keyword in dot_keywords:
            temp_result = temp_result.replace(f" {dot_keyword} ", ".")
        
        # Check if this looks like an IP address (has 3 dots, creating 4 octets)
        parts = temp_result.split(".")
        if len(parts) == 4:
            # This might be an IP address - try to convert each octet
            converted_parts = []
            is_ip_address = True
            
            for part in parts:
                part = part.strip()
                # Try to convert this part as a digit sequence
                parsed_digits = self.number_parser.parse_as_digits(part)
                if parsed_digits is not None:
                    # Successfully parsed as digits
                    converted_parts.append(parsed_digits)
                elif part.isdigit():
                    # Already a digit
                    converted_parts.append(part)
                else:
                    # Try regular number parsing as fallback
                    parsed_number = self.number_parser.parse(part)
                    if parsed_number and parsed_number.isdigit():
                        converted_parts.append(parsed_number)
                    else:
                        # This part doesn't look like a number, so not an IP address
                        is_ip_address = False
                        break
            
            if is_ip_address and len(converted_parts) == 4:
                # All parts were successfully converted to numbers, treat as IP
                return ".".join(converted_parts)
        
        # Not an IP address, use original domain logic with dot replacement
        for dot_keyword in dot_keywords:
            result = result.replace(f" {dot_keyword} ", ".")

        return result