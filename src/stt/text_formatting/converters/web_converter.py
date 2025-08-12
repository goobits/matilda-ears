"""Web pattern converter for URLs, emails, and port numbers."""

import re
from typing import Dict

from stt.text_formatting.common import Entity, EntityType
from ..pattern_modules.utility_patterns import WHITESPACE_NORMALIZATION_PATTERN
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
                    value = parsed_value or value.replace(" ", "")
                else:
                    # For non-numeric values, always remove spaces for URL-friendliness
                    value = value.replace(" ", "")

                # Format as key=value with no spaces
                processed_parts.append(f"{key}={value}")

        return "&".join(processed_parts)

    def _convert_port_number(self, port_text: str) -> str:
        """Convert port number text to numeric format."""
        port_words = port_text.split()
        
        # Check if all words are single digits (for sequences like "eight zero eight zero")
        digit_words = {word: str(num) for word, num in self.number_parser.ones.items() if 0 <= num <= 9}
        all_single_digits = all(word in digit_words for word in port_words)
        
        if all_single_digits and port_words:
            # Use digit sequence logic
            port_digits = [digit_words[word] for word in port_words]
            return "".join(port_digits)
        
        # Use the number parser for compound numbers like "three thousand"
        parsed_port = self.number_parser.parse(port_text)
        if parsed_port and parsed_port.isdigit():
            return parsed_port
        
        # Fallback: return as is
        return port_text

    def convert_spoken_protocol_url(self, entity: Entity) -> str:
        """Convert spoken protocol URLs like 'http colon slash slash my app dot com slash login'"""
        text = entity.text.lower()

        # Get language-specific keywords
        colon_keywords = [k for k, v in self.url_keywords.items() if v == ":"]
        slash_keywords = [k for k, v in self.url_keywords.items() if v == "/"]
        dot_keywords = [k for k, v in self.url_keywords.items() if v == "."]
        at_keywords = [k for k, v in self.url_keywords.items() if v == "@"]
        question_keywords = [k for k, v in self.url_keywords.items() if v == "?"]

        # Build keyword patterns
        colon_pattern = "|".join(re.escape(k) for k in colon_keywords)
        slash_pattern = "|".join(re.escape(k) for k in slash_keywords)
        dot_pattern = "|".join(re.escape(k) for k in dot_keywords)
        at_pattern = "|".join(re.escape(k) for k in at_keywords)
        question_pattern = "|".join(re.escape(k) for k in question_keywords) if question_keywords else "question\\s+mark"

        # Try to find and replace "colon slash slash" pattern
        protocol_replaced = False
        for colon_kw in colon_keywords:
            for slash_kw in slash_keywords:
                pattern = f" {colon_kw} {slash_kw} {slash_kw}"
                if pattern in text:
                    text = text.replace(pattern, "://")
                    protocol_replaced = True
                    break
            if protocol_replaced:
                break

        if not protocol_replaced:
            # Fallback: try with regex
            pattern = rf"\s+(?:{colon_pattern})\s+(?:{slash_pattern})\s+(?:{slash_pattern})\s+"
            text = re.sub(pattern, "://", text)

        # Now we have something like "https://my app dot com slash login colon eight zero eight zero"
        # Parse the URL components manually

        # Split at :// to separate protocol from the rest
        if "://" in text:
            protocol_part, url_remainder = text.split("://", 1)
        else:
            # Fallback if protocol replacement failed
            return self.convert_spoken_url(Entity(start=0, end=len(text), text=text, type=EntityType.SPOKEN_URL), text)

        # Parse the URL remainder into components: domain, port, path, query
        domain_part = ""
        port_part = ""
        path_part = ""
        query_part = ""

        # Handle authentication (user at domain -> user@domain)
        auth_match = re.search(rf"^(.+?)\s+(?:{at_pattern})\s+(.+)", url_remainder, re.IGNORECASE)
        if auth_match:
            user_part = auth_match.group(1).strip()
            url_remainder = auth_match.group(2).strip()
            # Convert user part (remove spaces, handle numbers)
            user_part = self._convert_url_keywords(user_part)
            protocol_part = protocol_part + "://" + user_part + "@"
        else:
            protocol_part = protocol_part + "://"

        # Look for port numbers (domain colon port)
        # Port pattern: look for " colon " followed by number words
        port_match = re.search(rf"^(.+?)\s+(?:{colon_pattern})\s+(.+?)(?:\s+(?:{slash_pattern})\s+(.+?))?(?:\s+(?:{question_pattern})\s+(.+))?$", url_remainder, re.IGNORECASE)
        if port_match:
            domain_part = port_match.group(1).strip()
            port_part = port_match.group(2).strip()
            path_part = port_match.group(3) or ""
            query_part = port_match.group(4) or ""
        else:
            # No port, look for paths and queries
            path_match = re.search(rf"^(.+?)(?:\s+(?:{slash_pattern})\s+(.+?))?(?:\s+(?:{question_pattern})\s+(.+))?$", url_remainder, re.IGNORECASE)
            if path_match:
                domain_part = path_match.group(1).strip()
                path_part = path_match.group(2) or ""
                query_part = path_match.group(3) or ""
            else:
                # Just domain
                domain_part = url_remainder.strip()

        # Convert domain part: handle dots and remove spaces
        if domain_part:
            domain_part = self._convert_url_keywords(domain_part)

        # Convert port part: handle number words
        if port_part:
            port_part = self._convert_port_number(port_part)

        # Convert path part: handle slashes and remove spaces
        if path_part:
            path_part = self._convert_url_keywords(path_part.replace(f" {slash_keywords[0]} ", "/"))

        # Convert query part: handle parameters
        if query_part:
            query_part = self._process_url_params(query_part)

        # Assemble the final URL
        result = protocol_part + domain_part
        if port_part:
            result += ":" + port_part
        if path_part:
            if not path_part.startswith("/"):
                result += "/"
            result += path_part
        if query_part:
            result += "?" + query_part

        return result

    def convert_spoken_url(self, entity: Entity, full_text: str = "") -> str:
        """Convert spoken URL patterns by replacing keywords and removing spaces."""
        url_text = entity.text
        
        # ENTITY BOUNDARY FIX: Check if URL starts with article words that should be removed
        # This fixes cases like "the dot com" -> ".com" where "the" is not part of the URL
        leading_articles = ["the ", "a ", "an "]
        
        for article in leading_articles:
            if url_text.lower().startswith(article):
                # Check if this is a real article before a URL (vs part of domain name)
                remainder = url_text[len(article):].lower()
                # If remainder contains URL keywords, this is likely "the domain.com"
                url_keywords_in_remainder = any(keyword in remainder for keyword in self.url_keywords.keys())
                if url_keywords_in_remainder:
                    # Remove the article from the URL text - the entity reconstruction will handle spacing
                    url_text = url_text[len(article):]
                break
        
        # Remove command prefixes that shouldn't be part of the URL, but preserve action words
        # Sort by length (longest first) to avoid partial matches
        # NOTE: Be careful not to strip action words that should be preserved in the sentence
        command_prefixes = ["navigate to ", "browse ", "open "]  # Removed "go to ", "visit ", "check ", "to "
        for prefix in command_prefixes:
            if url_text.lower().startswith(prefix):
                url_text = url_text[len(prefix):]
                break
        # Check for trailing punctuation and remove it (don't add it back)
        if url_text and url_text[-1] in ".!?":
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

        return url_text

    def _convert_url_keywords(self, url_text: str) -> str:
        """Convert URL keywords in base URL text, properly handling numbers."""
        # Strategy: Convert number words first, then apply URL keyword conversions
        # This ensures number words are properly merged with adjacent text before URL conversion
        
        words = url_text.split()
        converted_words = []
        i = 0
        
        while i < len(words):
            # Try to parse a number sequence starting at position i
            best_parse = None
            end_j = i
            
            # Look for the longest sequence that forms a valid number
            for j in range(len(words), i, -1):
                sub_phrase = " ".join(words[i:j])
                # Try parse_as_digits first for URL contexts (handles "one two three" -> "123")
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
                # We found a number - merge it with the previous word only in specific contexts
                should_merge = False
                if (converted_words and 
                    converted_words[-1].lower() not in self.url_keywords):
                    prev_word = converted_words[-1].lower()
                    # Only merge for specific technical domain contexts where concatenation is expected
                    # Be conservative - only merge for clear technical identifiers, not general words
                    technical_prefixes = {"api", "db", "www", "cdn", "ftp"}  # Removed: server, servidor, host, mail, app, site, web
                    # These are technical abbreviations that commonly merge with numbers in subdomains
                    
                    version_contexts = {"v", "version", "versión"}
                    # Explicitly list command/navigation words that should NOT merge (English + Spanish)
                    english_commands = {"to", "go", "visit", "check", "at", "from", "with", "on", "in", "for", "by"}
                    spanish_commands = {"a", "ir", "visita", "revisar", "en", "desde", "con", "sobre", "para", "por"}
                    command_words = english_commands.union(spanish_commands)
                    
                    if prev_word in technical_prefixes:
                        # Merge for technical domain names: "api" + "1" = "api1", "db" + "2" = "db2"  
                        should_merge = True
                    elif prev_word in version_contexts:
                        # Merge for versions: "v" + "2" = "v2"  
                        should_merge = True
                    elif prev_word in command_words:
                        # Never merge with command words: "to" + "1111" = "to 1111" (separate)
                        should_merge = False
                    else:
                        # For other words, be conservative and don't merge to avoid issues
                        should_merge = False
                
                if should_merge:
                    converted_words[-1] = converted_words[-1] + best_parse
                else:
                    # Add as separate word
                    converted_words.append(best_parse)
                i = end_j
            else:
                # Not a number word, add as-is
                converted_words.append(words[i])
                i += 1
        
        # Now convert URL keywords in the text with converted numbers
        text = " ".join(converted_words)
        
        # Apply URL keyword replacements with proper space handling for URL context
        # In URL context, keywords like "slash", "dot", etc. should not have spaces around them
        for keyword, replacement in self.url_keywords.items():
            # Match keyword with surrounding spaces (typical in spoken URLs)
            # e.g., "github.com slash project" -> "github.com/project"
            pattern = rf"\s+{re.escape(keyword)}\s+"
            text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
            
            # Also handle cases where keyword is at word boundaries but might not have spaces
            # This is a fallback for cases not caught by the first pattern
            pattern_boundary = rf"\b{re.escape(keyword)}\b"
            text = re.sub(pattern_boundary, replacement, text, flags=re.IGNORECASE)
        
        # Remove spaces around URL symbols, but preserve spaces in general text
        # This handles cases like "servidor 1.ejemplo.com" where we want to keep the space
        # but remove spaces around dots, slashes, etc.
        
        # Only remove spaces that are immediately adjacent to URL symbols
        # Common URL symbols that should not have spaces around them
        url_symbols = ['.', '/', ':', '@', '?', '=', '&', '-', '_']
        
        # Remove spaces before and after URL symbols ONLY in URL contexts
        # Be more conservative - only remove spaces when the symbols are clearly part of a URL structure
        for symbol in url_symbols:
            if symbol in text:
                # Remove space before symbol: "word ." -> "word."
                text = re.sub(rf'\s+{re.escape(symbol)}', symbol, text)
                # Remove space after symbol only for certain symbols that should connect: ". ", "/ ", "@ "
                if symbol in ['.', '/', '@']:
                    text = re.sub(rf'{re.escape(symbol)}\s+', symbol, text)
        
        # Additional consolidation for URL contexts - remove spaces between adjacent words
        # when they are clearly part of a domain name or URL path
        # Pattern: word space word -> wordword when followed by URL symbols
        if any(symbol in text for symbol in ['.', '/']):
            # More aggressive space removal for clear URL patterns
            # Remove spaces between words when we see URL structure indicators
            parts = text.split('.')
            consolidated_parts = []
            for part in parts:
                # In domain parts, remove internal spaces more aggressively
                if '/' not in part:  # Domain part
                    # Remove spaces between words in domain parts like "my app" -> "myapp"
                    part = re.sub(WHITESPACE_NORMALIZATION_PATTERN, '', part)
                else:  # Path part
                    # In path parts, be more selective
                    path_segments = part.split('/')
                    consolidated_segments = []
                    for segment in path_segments:
                        if segment.strip():  # Non-empty segment
                            # Remove spaces in path segments too, but preserve structure
                            segment = re.sub(WHITESPACE_NORMALIZATION_PATTERN, '', segment.strip())
                        consolidated_segments.append(segment)
                    part = '/'.join(consolidated_segments)
                consolidated_parts.append(part)
            text = '.'.join(consolidated_parts)
        
        return text

    def convert_url(self, entity: Entity) -> str:
        """Convert URL with proper formatting"""
        url_text = entity.text

        # Fix for http// or https// patterns
        url_text = re.sub(r"\b(https?)//", r"\1://", url_text)

        # Check for trailing punctuation and remove it (don't add it back)
        if url_text and url_text[-1] in ".!?":
            url_text = url_text[:-1]

        # For SpaCy-detected URLs, the text is already clean and formatted
        # We only need to normalize protocol to lowercase
        url_text = re.sub(r"^(HTTPS?|FTP)://", lambda m: m.group(0).lower(), url_text)

        return url_text

    def convert_email(self, entity: Entity) -> str:
        """Convert email patterns"""
        # Check for trailing punctuation and remove it (don't add it back)
        text = entity.text
        if text and text[-1] in ".!?":
            text = text[:-1]

        # For SpaCy-detected emails, the text is already clean and formatted
        # We can use metadata if available for validation, but the text is reliable
        if entity.metadata and "username" in entity.metadata and "domain" in entity.metadata:
            username = entity.metadata["username"]
            domain = entity.metadata["domain"]
            return f"{username}@{domain}"

        # For clean SpaCy-detected emails, just return the text as-is
        return text

    def convert_spoken_email(self, entity: Entity, full_text: str | None = None) -> str:
        """
        Convert 'user at example dot com' to 'user@example.com'.

        Note: The entity text should contain only the email part, not action phrases.
        Action phrases are handled separately by the formatter.
        """
        text = entity.text.strip()  # Strip leading/trailing spaces
        # Check for trailing punctuation and remove it (don't add it back)
        if text and text[-1] in ".!?":
            text = text[:-1]

        # ENTITY BOUNDARY FIX: Handle leading action/preposition words in email entities
        # This fixes cases like "to user at domain dot com" -> "to user@domain.com" where spacing should be preserved
        action_prepositions = ["to ", "for ", "from ", "with "]  # Removed "at " since it conflicts with email format
        preserve_leading_action = False
        
        for preposition in action_prepositions:
            if text.lower().startswith(preposition):
                # Check if remainder contains email keywords (at, dot) - indicating this is an email
                remainder = text[len(preposition):].lower()
                has_email_keywords = " at " in remainder and " dot " in remainder
                # Also check that it's not a complex case with multiple "at" keywords
                at_count = remainder.count(" at ")
                if has_email_keywords and at_count == 1:  # Single email, not complex case
                    preserve_leading_action = True
                    # Remove the preposition from the email text - we'll add it back at the end
                    text = text[len(preposition):]
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
                        # Look for consecutive number words - be more aggressive in collecting them
                        number_sequence = [part]
                        j = i + 1
                        while j < len(username_parts):
                            next_part = username_parts[j].lower()
                            # Include all number words, even if not strictly consecutive in number_parser
                            if next_part in self.number_parser.all_number_words:
                                number_sequence.append(username_parts[j])
                                j += 1
                            else:
                                break

                        # Try to parse the sequence as digits first (this handles "one two three" -> "123")
                        sequence_text = " ".join(number_sequence)
                        parsed = self.number_parser.parse_as_digits(sequence_text)
                        if parsed:
                            converted_parts.append(parsed)
                        else:
                            # Try regular parsing for compound numbers
                            parsed = self.number_parser.parse(sequence_text)
                            if parsed and parsed.isdigit():
                                converted_parts.append(parsed)
                            else:
                                # Parse each word individually and concatenate digits
                                digit_parts = []
                                for seq_part in number_sequence:
                                    individual_parsed = self.number_parser.parse_as_digits(seq_part)
                                    if individual_parsed:
                                        digit_parts.append(individual_parsed)
                                    else:
                                        # Try regular parsing
                                        individual_parsed = self.number_parser.parse(seq_part)
                                        if individual_parsed and individual_parsed.isdigit():
                                            digit_parts.append(individual_parsed)
                                        else:
                                            digit_parts.append(seq_part)
                                
                                # If we have digit parts, join them; otherwise keep original sequence
                                if digit_parts and all(p.isdigit() or len(p) == 1 for p in digit_parts):
                                    converted_parts.append(''.join(digit_parts))
                                else:
                                    converted_parts.extend(number_sequence)
                        i = j
                    else:
                        # Not a number word, keep as is
                        converted_parts.append(part)
                        i += 1

                # Check for action phrases that should be kept separate
                # This handles cases like "mi email es usuario" where we want "mi email es" + "usuario"
                action_words = {"email", "contact", "send", "forward", "reach", "notify", "message", "mail", "write", "communicate", "visit", "go", "check", "navigate"}
                spanish_words = {"mi", "tu", "su", "es", "envía", "enviar", "contacta", "contactar"}
                
                # Look for action phrase patterns at the beginning, but stop before number words
                action_phrase_end = 0
                for i in range(len(converted_parts)):
                    word = converted_parts[i].lower()
                    # Stop if we hit a number word - don't include it in the action phrase
                    if word in self.number_parser.all_number_words:
                        break
                    if word in action_words or word in spanish_words:
                        action_phrase_end = i + 1
                    else:
                        break
                
                if action_phrase_end > 0 and action_phrase_end < len(converted_parts):
                    # Split into action phrase and username
                    action_phrase = " ".join(converted_parts[:action_phrase_end])
                    username_parts = converted_parts[action_phrase_end:]
                    actual_username = "".join(username_parts)  # Join username without spaces
                    username = f"{action_phrase} {actual_username}"
                else:
                    # No action phrase, join without spaces for email usernames (normal case)
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
            domain = re.sub(WHITESPACE_NORMALIZATION_PATTERN, "", domain)

            result = f"{username}@{domain}"
            
            # ENTITY BOUNDARY FIX: Add preposition back if we removed it
            if preserve_leading_action:
                # Find which preposition we removed and add it back
                for preposition in action_prepositions:
                    if entity.text.lower().startswith(preposition):
                        result = preposition.strip() + " " + result
                        break
                
            return result

        # Fallback: use case-insensitive regex replacement for language-specific keywords
        dot_keywords = [k for k, v in self.url_keywords.items() if v == "."]
        at_keywords = [k for k, v in self.url_keywords.items() if v == "@"]
        for dot_keyword in dot_keywords:
            text = re.sub(rf"\s+{re.escape(dot_keyword)}\s+", ".", text, flags=re.IGNORECASE)
        for at_keyword in at_keywords:
            text = re.sub(rf"\s+{re.escape(at_keyword)}\s+", "@", text, flags=re.IGNORECASE)
        text = text.replace(" ", "")
        
        result = text
        
        # ENTITY BOUNDARY FIX: Add preposition back if we removed it (fallback case)
        if preserve_leading_action:
            # Find which preposition we removed and add it back
            for preposition in action_prepositions:
                if entity.text.lower().startswith(preposition):
                    result = preposition.strip() + " " + result
                    break
            
        return result

    def convert_port_number(self, entity: Entity) -> str:
        """Convert port numbers like 'localhost colon eight zero eight zero' to 'localhost:8080'
        Also handles spoken domains like 'api dot service dot com colon three thousand' to 'api.service.com:3000'
        Now also handles URL paths like 'api.com colon 8000 slash v two' to 'api.com:8000/v2'"""
        text = entity.text.lower()

        # Get language-specific keywords
        colon_keywords = [k for k, v in self.url_keywords.items() if v == ":"]
        slash_keywords = [k for k, v in self.url_keywords.items() if v == "/"]
        
        # Extract host, port, and optional path parts using language-specific colon keyword
        colon_pattern = None
        host_part = ""
        port_and_path_part = ""
        
        for colon_keyword in colon_keywords:
            colon_sep = f" {colon_keyword} "
            if colon_sep in text:
                host_part, port_and_path_part = text.split(colon_sep, 1)
                colon_pattern = colon_keyword
                break

        if colon_pattern:
            # Convert spoken domain in host part (e.g., "api dot service dot com" -> "api.service.com")
            host_part = self._convert_spoken_domain(host_part)

            # Separate port and path parts
            port_part = port_and_path_part
            path_part = ""
            
            # Look for slash keywords to separate port from path
            for slash_keyword in slash_keywords:
                slash_sep = f" {slash_keyword} "
                if slash_sep in port_and_path_part:
                    port_part, path_part = port_and_path_part.split(slash_sep, 1)
                    break

            # Convert port part
            port_words = port_part.split()

            # Check if all words are single digits (for sequences like "eight zero eight zero")
            # Use language-specific number words from the NumberParser
            digit_words = {word: str(num) for word, num in self.number_parser.ones.items() if 0 <= num <= 9}
            all_single_digits = all(word in digit_words for word in port_words)

            port_number = ""
            if all_single_digits and port_words:
                # Use digit sequence logic with language-specific digit words
                port_digits = [digit_words[word] for word in port_words]
                port_number = "".join(port_digits)
            else:
                # Use the number parser for compound numbers like "three thousand"
                parsed_port = self.number_parser.parse(port_part)
                if parsed_port and parsed_port.isdigit():
                    port_number = parsed_port

            # Convert path part if present
            converted_path = ""
            if path_part:
                # Use URL keyword conversion for the path
                converted_path = "/" + self._convert_url_keywords(path_part)

            # Assemble final result
            if port_number:
                result = f"{host_part}:{port_number}{converted_path}"
                return result

        # Fallback: replace colon word even if parsing fails
        result = entity.text
        for colon_keyword in colon_keywords:
            result = result.replace(f" {colon_keyword} ", ":")
        # Also try to convert slash keywords in fallback
        for slash_keyword in slash_keywords:
            result = result.replace(f" {slash_keyword} ", "/")
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