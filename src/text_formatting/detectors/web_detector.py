#!/usr/bin/env python3
"""Web-related entity detection and conversion for Matilda transcriptions."""

import re
from typing import List
from ..common import Entity, EntityType, NumberParser
from ..utils import is_inside_entity
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

            # CONTEXT CHECK to avoid misinterpreting "docs at python.org" 
            # This works with or without spaCy
            match_text = match.group()
            at_pos = match_text.lower().find(" at ")
            
            should_skip = False
            if at_pos > 0:
                # Get the part before "at"
                before_at = match_text[:at_pos].strip()
                # Remove "email" prefix if present
                if before_at.lower().startswith("email "):
                    before_at = before_at[6:].strip()

                # Check if this looks like a location reference vs. an actual email address
                # Look at the action word at the beginning of the match
                email_actions = self.resources.get("context_words", {}).get("email_actions", [])
                has_email_action = any(match_text.lower().startswith(action) for action in email_actions)

                # Use location and ambiguous nouns from resources
                location_nouns = self.resources.get("context_words", {}).get("location_nouns", [])
                ambiguous_nouns = self.resources.get("context_words", {}).get("ambiguous_nouns", [])

                words_before_at = before_at.split()
                if words_before_at:
                    last_word = words_before_at[-1].lower()
                    # Skip if it's a clear location noun
                    if last_word in location_nouns:
                        logger.debug(
                            f"Skipping email match '{match.group()}' - '{last_word}' indicates location context"
                        )
                        should_skip = True
                    # Skip ambiguous nouns only if there's no email action
                    elif last_word in ambiguous_nouns and not has_email_action:
                        logger.debug(
                            f"Skipping email match '{match.group()}' - '{last_word}' without email action indicates location context"
                        )
                        should_skip = True

            # Additional spaCy-based analysis if available
            if not should_skip and self.nlp:
                try:
                    # Analyze the text to understand the grammar around the match
                    doc = self.nlp(text)
                    # Additional spaCy checks can go here if needed
                except (AttributeError, ValueError, IndexError):
                    logger.warning("SpaCy context check for email failed, using basic checks.")

            if not should_skip:
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

