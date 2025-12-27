#!/usr/bin/env python3
"""Web-related entity detection and conversion for Matilda transcriptions."""

import re
from typing import List
from ..common import Entity, EntityType
from ..utils import is_inside_entity, overlaps_with_entity
from ...core.config import setup_logging
from .. import regex_patterns
from ..constants import get_resources

logger = setup_logging(__name__, log_filename="text_formatting.txt")


class WebEntityDetector:
    def __init__(self, nlp=None, language: str = "en"):
        """Initialize WebEntityDetector with dependency injection.

        Args:
            nlp: SpaCy NLP model instance. If None, will load from nlp_provider.
            language: Language code for resource loading (default: 'en')

        """
        if nlp is None:
            from ..nlp_provider import get_nlp

            nlp = get_nlp()

        self.nlp = nlp
        self.language = language

        # Load language-specific resources
        self.resources = get_resources(language)

        # Build patterns dynamically for the specified language
        self.spoken_url_pattern = regex_patterns.get_spoken_url_pattern(language)
        self.port_number_pattern = regex_patterns.get_port_number_pattern(language)
        self.spoken_protocol_pattern = regex_patterns.get_spoken_protocol_pattern(language)
        self.spoken_ip_pattern = regex_patterns.get_spoken_ip_pattern(language)
        # Note: _detect_spoken_emails builds its own pattern internally
        # Note: port_pattern is the same as port_number_pattern

    def detect(self, text: str, entities: List[Entity]) -> List[Entity]:
        """Detects all web-related entities."""
        web_entities: list[Entity] = []
        all_entities = list(entities)  # Copy to avoid mutating input

        # Helper to run detector and track new entities for overlap checking
        def run_detector(detector_fn):
            before = len(web_entities)
            detector_fn(text, web_entities, all_entities)
            all_entities.extend(web_entities[before:])

        # Detect in priority order (more specific patterns first)
        run_detector(self._detect_spoken_emails)
        run_detector(self._detect_spoken_protocol_urls)
        run_detector(self._detect_spoken_urls)
        run_detector(self._detect_spoken_ips)
        run_detector(self._detect_port_numbers)
        run_detector(self._detect_links)  # SpaCy fallback for well-formatted links

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

    def _detect_spoken_ips(self, text: str, web_entities: List[Entity], existing_entities: List[Entity]) -> None:
        """Detect spoken IP addresses."""
        for match in self.spoken_ip_pattern.finditer(text):
            if not is_inside_entity(match.start(), match.end(), existing_entities):
                web_entities.append(
                    Entity(start=match.start(), end=match.end(), text=match.group(), type=EntityType.SPOKEN_URL)
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
        # First, let's look for email patterns with a simpler approach
        # We'll search for patterns like "username at domain dot com"

        # Get keywords
        at_keywords = [k for k, v in self.resources.get("spoken_keywords", {}).get("url", {}).items() if v == "@"]
        at_pattern = "|".join(re.escape(k) for k in at_keywords)

        # More restrictive pattern: word(s) + at + domain
        # This avoids capturing action phrases and false positives
        simple_email_pattern = rf"""
        (?:^|(?<=\s))                       # Start or after space
        (                                   # Capture group for the whole email
            (?!(?:the|a|an|this|that|these|those|my|your|our|their|his|her|its|to|for|from|with|by|you|i|we|they|look|see|check|find|get|send|write|forward|reply|contact|email|is|are|was|were|be|have|has|had|do|does|did|or|and|but|notify|visit)\s+)  # Not preceded by these words
            (?!(?:is|are|was|were|be|have|has|had|do|does|did|or|and|but|email|notify|visit|check)\s) # Username cannot be these common verbs
            [a-zA-Z][a-zA-Z0-9]*            # Username starting with letter
            (?:                             # Optional username parts
                (?:\s+(?:underscore|dash)\s+|[._-])
                [a-zA-Z0-9]+
            |                               # OR allow space-separated words (e.g., "john doe", "user one")
                # But exclude common stop words to avoid capturing sentences like "visit the site"
                \s+(?!at\b|dot\b|the\b|a\b|an\b|this\b|that\b|to\b|for\b|in\b|on\b|with\b|by\b|our\b|my\b|your\b|visit\b|check\b|website\b|site\b|page\b|link\b)[a-zA-Z0-9]+
            )*
            \s+(?:{at_pattern})\s+          # "at" keyword
            [a-zA-Z0-9-]+                   # Domain must start with alphanumeric or hyphen
            (?:\s+(?!dot\b|at\b)[a-zA-Z0-9-]+)*  # Optional parts (excluding dot/at)
            (?:                             # Domain parts with dots (non-greedy)
                \s+dot\s+[a-zA-Z0-9-]+
            )+                              # One or more dot parts
        )
        (?=\s|$|[.!?])                      # End boundary
        """

        simple_pattern = re.compile(simple_email_pattern, re.VERBOSE | re.IGNORECASE)

        for match in simple_pattern.finditer(text):
            email_text = match.group(1)

            # Check if it overlaps with any existing entity
            if overlaps_with_entity(match.start(), match.end(), existing_entities):
                continue

            # Extract username from the email text
            at_match = re.search(rf"\s+(?:{at_pattern})\s+", email_text, re.IGNORECASE)
            if not at_match:
                continue

            username = email_text[:at_match.start()].strip()
            # domain = email_text[at_match.end():].strip()  # Unused variable

            # CONTEXT CHECK to avoid misinterpreting "docs at python.org"
            username_lower = username.lower()

            # Use location and ambiguous nouns from resources
            location_nouns = self.resources.get("context_words", {}).get("location_nouns", [])
            ambiguous_nouns = self.resources.get("context_words", {}).get("ambiguous_nouns", [])

            # Common email username patterns that should be treated as emails
            common_email_usernames = {"support", "help", "info", "admin", "contact", "sales", "hello"}

            should_skip = False
            # Skip if it's a clear location noun
            if username_lower in location_nouns:
                logger.debug(
                    f"Skipping email match '{email_text}' - '{username}' indicates location context"
                )
                should_skip = True
            # Skip ambiguous nouns only if it's not a common email username
            elif username_lower in ambiguous_nouns and username_lower not in common_email_usernames:
                # Check if there's an email action word before this match
                before_match = text[:match.start()].lower()
                email_actions = self.resources.get("context_words", {}).get("email_actions", [])
                has_email_action = any(before_match.endswith(action + " ") for action in email_actions)

                if not has_email_action:
                    logger.debug(
                        f"Skipping email match '{email_text}' - '{username}' without email action indicates location context"
                    )
                    should_skip = True

            # Additional spaCy-based analysis if available
            if not should_skip and self.nlp:
                try:
                    # Analyze the text to understand the grammar around the match
                    # doc = self.nlp(text)  # Unused variable
                    # Additional spaCy checks can go here if needed
                    pass
                except (AttributeError, ValueError, IndexError):
                    logger.warning("SpaCy context check for email failed, using basic checks.")

            if not should_skip:
                # Create an entity for just the email part, not including the action phrase
                web_entities.append(
                    Entity(
                        start=match.start(1),  # Start of the email text
                        end=match.end(1),      # End of the email text
                        text=email_text,
                        type=EntityType.SPOKEN_EMAIL
                    )
                )

    def _detect_port_numbers(self, text: str, web_entities: List[Entity], existing_entities: List[Entity]) -> None:
        """Detect port numbers like 'localhost colon eight zero eight zero'."""
        for match in self.port_number_pattern.finditer(text):
            if not is_inside_entity(match.start(), match.end(), existing_entities):
                web_entities.append(
                    Entity(start=match.start(), end=match.end(), text=match.group(), type=EntityType.PORT_NUMBER)
                )

    def _detect_links(self, text: str, entities: List[Entity], existing_entities: List[Entity]) -> None:
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

                if not is_inside_entity(start_pos, end_pos, existing_entities):
                    entities.append(Entity(start=start_pos, end=end_pos, text=token.text, type=EntityType.URL))

            # Check for email tokens
            elif token.like_email:
                # Get the exact character positions
                start_pos = token.idx
                end_pos = token.idx + len(token.text)

                if not is_inside_entity(start_pos, end_pos, existing_entities):
                    # Parse email to extract username and domain
                    parts = token.text.split("@")
                    metadata = {}
                    if len(parts) == 2:
                        metadata = {"username": parts[0], "domain": parts[1]}

                    entities.append(
                        Entity(start=start_pos, end=end_pos, text=token.text, type=EntityType.EMAIL, metadata=metadata)
                    )

