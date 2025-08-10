#!/usr/bin/env python3
"""Web-related entity detection and conversion for Matilda transcriptions."""
from __future__ import annotations

import re

from stt.core.config import setup_logging
from stt.text_formatting import regex_patterns
from stt.text_formatting.common import Entity, EntityType
from stt.text_formatting.constants import get_resources
from stt.text_formatting.pattern_cache import cached_pattern
from stt.text_formatting.utils import is_inside_entity, overlaps_with_entity

logger = setup_logging(__name__)


# Cached pattern helper functions
@cached_pattern
def build_simple_email_pattern(email_pattern: str) -> re.Pattern[str]:
    """Build simple email pattern from dynamic pattern string."""
    return re.compile(email_pattern, re.VERBOSE | re.IGNORECASE)


@cached_pattern
def build_url_with_protocol_pattern() -> re.Pattern[str]:
    """Build URL with protocol pattern."""
    return re.compile(r'\b(?:https?://|www\.)[a-zA-Z0-9\-._~:/?#[\]@!$&\'()*+,;=%]+\b')


@cached_pattern
def build_domain_pattern() -> re.Pattern[str]:
    """Build domain pattern."""
    return re.compile(
        r'\b[a-zA-Z0-9][a-zA-Z0-9\-]*(?:\.[a-zA-Z0-9\-]+)*\.'
        r'(?:com|org|net|edu|gov|mil|co|io|dev|app|ai|me|info|biz|'
        r'tv|cc|ws|name|mobi|asia|uk|eu|ca|au|jp|de|fr|it|es|ru|cn|'
        r'in|br|mx|nl|se|no|dk|fi|pl|gr|tr|za|kr|th|vn|tw|hk|sg|'
        r'my|ph|id|be|ch|at|cz|sk|hu|bg|ro|hr|si|ee|lv|lt|lu|mt|'
        r'cy|is|ie|pt|ar|cl|pe|co|ve|uy|py|bo|ec|gt|hn|sv|ni|cr|'
        r'pa|do|cu|jm|tt|bb|gd|vc|lc|dm|ag|kn|bs|bz|gy|sr|gf|'
        r'fk|gs|sh|ac|tc|vg|ms|ai|ky|bm|pr|vi|as|gu|mp|pw|fm|mh|'
        r'ki|nr|to|tv|vu|ws|sb|fj|nc|nf|cx|cc|ck|nu|tk|pf|wf|'
        r'local|localhost)\b'
    )


class WebEntityDetector:
    def __init__(self, nlp=None, language: str = "en", use_spacy_matcher: bool = True):
        """
        Initialize WebEntityDetector with dependency injection.

        Args:
            nlp: SpaCy NLP model instance. If None, will load from nlp_provider.
            language: Language code for resource loading (default: 'en')
            use_spacy_matcher: Whether to use SpacyWebMatcher for intelligent detection (default: True)

        """
        if nlp is None:
            from stt.text_formatting.nlp_provider import get_nlp

            nlp = get_nlp()

        self.nlp = nlp
        self.language = language
        self.use_spacy_matcher = use_spacy_matcher

        # Load language-specific resources
        self.resources = get_resources(language)

        # Initialize SpacyWebMatcher for intelligent detection
        if self.use_spacy_matcher and self.nlp:
            try:
                from stt.text_formatting.spacy_utils.spacy_web_matcher import create_spacy_web_matcher
                self.spacy_web_matcher = create_spacy_web_matcher(self.nlp, language)
                logger.info("SpacyWebMatcher initialized successfully")
            except Exception as e:
                logger.warning(f"Failed to initialize SpacyWebMatcher: {e}, falling back to regex patterns")
                self.spacy_web_matcher = None
                self.use_spacy_matcher = False
        else:
            self.spacy_web_matcher = None
            logger.info("Using traditional regex patterns for web entity detection")

        # Build patterns dynamically for the specified language (fallback)
        self.spoken_url_pattern = regex_patterns.get_spoken_url_pattern(language)
        self.port_number_pattern = regex_patterns.get_port_number_pattern(language)
        self.spoken_protocol_pattern = regex_patterns.get_spoken_protocol_pattern(language)
        # Note: _detect_spoken_emails builds its own pattern internally
        # Note: port_pattern is the same as port_number_pattern

    def detect(self, text: str, entities: list[Entity], doc=None) -> list[Entity]:
        """Detects all web-related entities."""
        web_entities: list[Entity] = []
        # Create a combined list for overlap checking that includes both existing and newly detected entities
        all_entities = entities[:]

        # Detect port numbers FIRST to prevent email interference with domain:port patterns
        self._detect_port_numbers(text, web_entities, all_entities)
        all_entities = entities + web_entities  # Update with all detected so far

        # Detect emails after port numbers but before URLs to maintain specificity
        self._detect_spoken_emails(text, web_entities, all_entities)
        all_entities = entities + web_entities  # Update with all detected so far

        # Detect protocol URLs
        self._detect_spoken_protocol_urls(text, web_entities, all_entities)
        all_entities = entities + web_entities  # Update with all detected so far

        # Detect regular spoken URLs
        self._detect_spoken_urls(text, web_entities, all_entities)
        all_entities = entities + web_entities  # Update with all detected so far

        # Finally, use SpaCy for any remaining well-formatted links.
        # This will catch things like "example.com" that the spoken detectors miss.
        # Pass the combined list of all entities found so far to prevent overlap.
        self._detect_links(text, web_entities, all_entities, doc)
        return web_entities

    def _detect_spoken_protocol_urls(
        self, text: str, web_entities: list[Entity], existing_entities: list[Entity]
    ) -> None:
        """Detect spoken protocols like 'http colon slash slash'."""
        for match in self.spoken_protocol_pattern.finditer(text):
            if not is_inside_entity(match.start(), match.end(), existing_entities):
                web_entities.append(
                    Entity(
                        start=match.start(), end=match.end(), text=match.group(), type=EntityType.SPOKEN_PROTOCOL_URL
                    )
                )

    def _detect_spoken_urls(self, text: str, web_entities: list[Entity], existing_entities: list[Entity]) -> None:
        """Detect spoken URLs like 'example dot com slash path'."""
        
        # Try SpacyWebMatcher first if available
        if self.spacy_web_matcher:
            try:
                spacy_url_spans = self.spacy_web_matcher.detect_urls(text)
                for start, end, url_text in spacy_url_spans:
                    # Check for overlaps with existing entities
                    if not is_inside_entity(start, end, existing_entities):
                        web_entities.append(
                            Entity(start=start, end=end, text=url_text, type=EntityType.SPOKEN_URL)
                        )
                        logger.debug(f"SpacyWebMatcher detected URL: {url_text}")
                
                # If SpacyWebMatcher found URLs, we can return early
                if spacy_url_spans:
                    logger.debug(f"SpacyWebMatcher found {len(spacy_url_spans)} URL(s), skipping regex fallback")
                    return
                    
            except Exception as e:
                logger.warning(f"SpacyWebMatcher URL detection failed: {e}, falling back to regex")
        
        # Fallback to regex-based detection
        logger.debug("Using regex fallback for URL detection")
        for match in self.spoken_url_pattern.finditer(text):
            if not is_inside_entity(match.start(), match.end(), existing_entities):
                # Include trailing punctuation in the entity if present
                full_match = match.group(0)  # Full match including punctuation
                
                # Trim action words from the beginning of the URL entity
                # Common action words that should not be part of the URL entity
                action_words = ["go to", "visit", "check", "navigate to", "browse", "open", "to"]
                
                trimmed_start = match.start()
                trimmed_text = full_match
                
                for action in action_words:
                    if full_match.lower().startswith(action + " "):
                        # Calculate the new start position
                        action_len = len(action) + 1  # +1 for the space
                        trimmed_start = match.start() + action_len
                        trimmed_text = full_match[action_len:]
                        logger.debug(f"Trimmed action word '{action}' from URL entity")
                        break
                
                web_entities.append(
                    Entity(start=trimmed_start, end=match.end(), text=trimmed_text, type=EntityType.SPOKEN_URL)
                )

    def _detect_spoken_emails(self, text: str, web_entities: list[Entity], existing_entities: list[Entity]) -> None:
        """Detect spoken emails like 'john at example.com' using spaCy for context."""
        
        # Try SpacyWebMatcher first if available
        if self.spacy_web_matcher:
            try:
                spacy_email_spans = self.spacy_web_matcher.detect_emails(text)
                for start, end, email_text in spacy_email_spans:
                    # Check for overlaps with existing entities
                    if not overlaps_with_entity(start, end, existing_entities):
                        web_entities.append(
                            Entity(start=start, end=end, text=email_text, type=EntityType.SPOKEN_EMAIL)
                        )
                        logger.debug(f"SpacyWebMatcher detected email: {email_text}")
                
                # If SpacyWebMatcher found emails, we can return early
                # or continue with regex as additional fallback
                if spacy_email_spans:
                    logger.debug(f"SpacyWebMatcher found {len(spacy_email_spans)} email(s), skipping regex fallback")
                    return
                    
            except Exception as e:
                logger.warning(f"SpacyWebMatcher email detection failed: {e}, falling back to regex")
        
        # Fallback to regex-based detection
        logger.debug("Using regex fallback for email detection")
        
        # Get keywords
        at_keywords = [k for k, v in self.resources.get("spoken_keywords", {}).get("url", {}).items() if v == "@"]
        at_pattern = "|".join(re.escape(k) for k in at_keywords)
        
        # Get dot keywords for the language
        dot_keywords = [k for k, v in self.resources.get("spoken_keywords", {}).get("url", {}).items() if v == "."]
        dot_pattern = "|".join(re.escape(k) for k in dot_keywords) if dot_keywords else "dot"

        # Contextual email pattern that handles action phrases correctly
        # Pattern matches: [optional_action_phrase] username_words + at + domain
        # IMPORTANT: Use context-based filtering to avoid URL conflicts instead of requiring actions
        simple_email_pattern = rf"""
        (?:                                 # Optional context words (email action phrases)
            (?:email|contact|send\s+to|forward\s+to|reach\s+out\s+to|notify|send\s+the\s+report\s+to|forward\s+this\s+to)\s+
        )?
        (                                   # Capture group for the whole email only
            [a-zA-Z]\w*                     # Username starting with letter, then word chars
            (?:\s+[a-zA-Z0-9_-]+){{0,1}}    # Optional 1 additional username word (max 2 words total)
            \s+(?:{at_pattern})\s+          # "at" keyword
            [a-zA-Z0-9-]+                   # First domain part
            (?:\s+[a-zA-Z0-9]+)*            # Optional additional domain words (handles "help one")
            (?:\s+(?:{dot_pattern})\s+[a-zA-Z0-9-]+)+     # Must have "dot" + domain part
            (?:\s+(?:{dot_pattern})\s+[a-zA-Z0-9-]+)*     # Optional additional dots
        )
        (?=\s+(?:about|is|will|sent|and|or|but)|[.!?]|$)  # End at common words, punctuation, or end of string
        """

        simple_pattern = build_simple_email_pattern(simple_email_pattern)

        for match in simple_pattern.finditer(text):
            email_text = match.group(1)

            # Check if it overlaps with any existing entity
            if overlaps_with_entity(match.start(), match.end(), existing_entities):
                continue

            # Extract username from the email text
            at_match = re.search(rf"\s+(?:{at_pattern})\s+", email_text, re.IGNORECASE)
            if not at_match:
                continue

            username = email_text[: at_match.start()].strip()
            # domain = email_text[at_match.end():].strip()  # Unused variable

            # CONTEXT CHECK to avoid misinterpreting "docs at python.org"
            username_lower = username.lower()

            # Use location and ambiguous nouns from resources
            location_nouns = self.resources.get("context_words", {}).get("location_nouns", [])
            ambiguous_nouns = self.resources.get("context_words", {}).get("ambiguous_nouns", [])

            # Common email username patterns that should be treated as emails
            common_email_usernames = {"support", "help", "info", "admin", "contact", "sales", "hello"}
            
            # URL action words that suggest this should be a URL, not email
            url_actions = {"visit", "go to", "check", "navigate to", "browse", "open", "website at", "site at", "page at"}

            should_skip = False
            
            # Check if the username contains location nouns (e.g., "the docs" contains "docs")
            username_words = username_lower.split()
            contains_location_noun = any(word in location_nouns for word in username_words)
            
            # Check if username contains website-related terms
            website_terms = {"website", "site", "page", "docs", "documentation", "api", "server"}
            contains_website_terms = any(term in username_lower for term in website_terms)
            
            # Check if username itself contains URL action words (e.g., "visit user")
            username_contains_url_action = any(action in username_lower for action in url_actions)
            
            # Check what comes before this match (larger context)
            before_match = text[: match.start()].lower().strip()
            
            # Check for URL action words before this match
            has_url_action = any(before_match.endswith(action) for action in url_actions)
            
            # Also check for URL context phrases that include "at"
            url_context_phrases = {"website at", "site at", "page at", "docs at", "documentation at", "api at"}
            has_url_context_phrase = any(phrase in before_match for phrase in url_context_phrases)
            
            # Check for email action words before this match  
            email_actions = self.resources.get("context_words", {}).get("email_actions", [])
            has_email_action = any(before_match.endswith(action) for action in email_actions)
            
            # Skip if it's a clear location noun
            if username_lower in location_nouns:
                logger.debug(f"Skipping email match '{email_text}' - '{username}' is a location noun")
                should_skip = True
            # Skip if the username contains location nouns (even without explicit URL action)
            elif contains_location_noun:
                logger.debug(f"Skipping email match '{email_text}' - contains location noun '{username}'")
                should_skip = True
            # Skip if the username contains website-related terms (high priority)
            elif contains_website_terms:
                logger.debug(f"Skipping email match '{email_text}' - contains website terms in '{username}'")
                should_skip = True
            # Skip if there's a URL context phrase like "website at"
            elif has_url_context_phrase:
                logger.debug(f"Skipping email match '{email_text}' - URL context phrase detected")
                should_skip = True
            # Skip if there's a URL action and no explicit email action
            elif has_url_action and not has_email_action:
                logger.debug(f"Skipping email match '{email_text}' - URL action detected without email action")
                should_skip = True
            # Skip if the username itself contains URL action words, but allow "visit [user] at [domain]" pattern  
            elif username_contains_url_action and not has_email_action:
                # Special case: "visit user at domain" could be an email contact instruction
                if (username_contains_url_action and 
                    'visit' in username_lower and 
                    len(username_words) == 2 and 
                    username_words[0] == 'visit'):
                    # This is "visit [username]" pattern - allow as email
                    logger.debug(f"Allowing email match '{email_text}' - 'visit [user] at domain' pattern")
                else:
                    logger.debug(f"Skipping email match '{email_text}' - username contains URL action without email action")
                    should_skip = True
            # Skip ambiguous nouns only if it's not a common email username
            elif username_lower in ambiguous_nouns and username_lower not in common_email_usernames:
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
                        end=match.end(1),  # End of the email text
                        text=email_text,
                        type=EntityType.SPOKEN_EMAIL,
                    )
                )

    def _detect_port_numbers(self, text: str, web_entities: list[Entity], existing_entities: list[Entity]) -> None:
        """Detect port numbers like 'localhost colon eight zero eight zero'."""
        for match in self.port_number_pattern.finditer(text):
            if not is_inside_entity(match.start(), match.end(), existing_entities):
                web_entities.append(
                    Entity(start=match.start(), end=match.end(), text=match.group(), type=EntityType.PORT_NUMBER)
                )

    def _detect_links(self, text: str, entities: list[Entity], existing_entities: list[Entity], doc=None) -> None:
        """
        Detect URLs and emails using SpaCy's built-in token attributes.

        This method replaces the regex-based URL and email detection with
        SpaCy's more accurate token-level detection.
        """
        # Use shared doc if available, otherwise get from global document processor
        if doc is None:
            if not self.nlp:
                # Fallback to regex-based detection when SpaCy is not available
                self._detect_links_regex_fallback(text, entities, existing_entities)
                return
            # Use shared document processor for optimal caching
            from ..spacy_doc_cache import get_or_create_shared_doc
            try:
                doc = get_or_create_shared_doc(text, nlp_model=self.nlp)
                if doc is None:
                    raise ValueError("SpaCy document creation failed")
            except (AttributeError, ValueError, IndexError) as e:
                logger.warning(f"SpaCy link detection failed: {e}")
                # Use regex fallback on SpaCy failure
                self._detect_links_regex_fallback(text, entities, existing_entities)
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

    def _detect_links_regex_fallback(self, text: str, entities: list[Entity], existing_entities: list[Entity]) -> None:
        """
        Fallback regex-based detection for URLs and emails when SpaCy is not available.
        """
        # Import the email pattern from regex_patterns
        from stt.text_formatting import regex_patterns
        
        # Detect emails using the EMAIL_PROTECTION_PATTERN
        for match in regex_patterns.EMAIL_PROTECTION_PATTERN.finditer(text):
            start_pos = match.start()
            end_pos = match.end()
            email_text = match.group()
            
            if not is_inside_entity(start_pos, end_pos, existing_entities):
                # Parse email to extract username and domain
                parts = email_text.split("@")
                metadata = {}
                if len(parts) == 2:
                    metadata = {"username": parts[0], "domain": parts[1]}
                
                entities.append(
                    Entity(start=start_pos, end=end_pos, text=email_text, type=EntityType.EMAIL, metadata=metadata)
                )
                logger.debug(f"Regex fallback detected email: {email_text}")
        
        # Detect URLs using multiple patterns
        # Pattern 1: URLs with protocol or www
        url_with_protocol_pattern = build_url_with_protocol_pattern()
        
        for match in url_with_protocol_pattern.finditer(text):
            start_pos = match.start()
            end_pos = match.end()
            url_text = match.group()
            
            if not is_inside_entity(start_pos, end_pos, existing_entities):
                entities.append(
                    Entity(start=start_pos, end=end_pos, text=url_text, type=EntityType.URL)
                )
                logger.debug(f"Regex fallback detected URL with protocol: {url_text}")
        
        # Pattern 2: Simple domain patterns (e.g., github.com, example.org)
        # This pattern is more permissive to catch domains without protocol
        domain_pattern = build_domain_pattern()
        
        for match in domain_pattern.finditer(text):
            start_pos = match.start()
            end_pos = match.end()
            url_text = match.group()
            
            # Don't detect if it's already covered by another entity
            if not is_inside_entity(start_pos, end_pos, existing_entities) and \
               not any(e.start <= start_pos < e.end for e in entities):
                entities.append(
                    Entity(start=start_pos, end=end_pos, text=url_text, type=EntityType.URL)
                )
                logger.debug(f"Regex fallback detected domain: {url_text}")
