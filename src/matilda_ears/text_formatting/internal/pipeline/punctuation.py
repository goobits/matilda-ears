#!/usr/bin/env python3
"""Punctuation processing: restoration and abbreviation handling."""

import os
import re
from typing import List, Optional

from ...common import Entity, EntityType
from ...constants import get_resources
from ..nlp_provider import get_punctuator
from ... import regex_patterns
from ....core.config import setup_logging

logger = setup_logging(__name__, log_filename="text_formatting.txt")


class PunctuationProcessor:
    """Handles punctuation restoration and abbreviation formatting."""

    def __init__(self, language: str = "en", nlp=None):
        self.language = language
        self.nlp = nlp
        self.resources = get_resources(language)

        # Complete sentence phrases that need punctuation even when short
        self.complete_sentence_phrases = set(
            self.resources.get("technical", {}).get("complete_sentence_phrases", [])
        )

    def add_punctuation(
        self,
        text: str,
        original_had_punctuation: bool = False,
        is_standalone_technical: bool = False,
        entities: Optional[List[Entity]] = None,
    ) -> str:
        """Add punctuation - treat all text as sentences unless single standalone technical entity."""
        if entities is None:
            entities = []

        # Add this at the beginning to handle empty inputs
        if not text.strip():
            return ""

        # Check if punctuation is disabled for testing
        if os.environ.get("STT_DISABLE_PUNCTUATION") == "1":
            logger.debug("Punctuation disabled for testing, returning text unchanged")
            return text

        # Check if text is a standalone technical entity that should bypass punctuation
        if is_standalone_technical:
            logger.debug("Bypassing punctuation for standalone technical entity")
            return text

        # If original text already had punctuation, don't add more
        if original_had_punctuation:
            logger.debug(f"Original text had punctuation, skipping punctuation model: '{text[:50]}...'")
            return text

        # All other text is treated as a sentence - use punctuation model
        punctuator = get_punctuator()
        if punctuator:
            try:
                logger.info(f"Text passed to _add_punctuation: '{text}'")

                # Entities to protect from punctuation model
                # Use the passed entities (which should be converted entities with correct positions)
                entity_placeholders = {}
                protected_text = text

                # Entity types to protect
                protected_types = {
                    EntityType.NUMERIC_RANGE,
                    EntityType.FRACTION,
                    EntityType.SCIENTIFIC_NOTATION,
                    EntityType.MATH_EXPRESSION,
                    EntityType.MATH_CONSTANT,
                    EntityType.METRIC_LENGTH,
                    EntityType.METRIC_WEIGHT,
                    EntityType.METRIC_VOLUME,
                    EntityType.TEMPERATURE,
                    EntityType.DATA_SIZE,
                    EntityType.FREQUENCY,
                    EntityType.URL,
                    EntityType.EMAIL,
                    EntityType.SPOKEN_URL,
                    EntityType.SPOKEN_EMAIL,
                    EntityType.FILENAME,
                    EntityType.IP_ADDRESS if hasattr(EntityType, "IP_ADDRESS") else None,
                }

                # Sort entities descending by start position to replace without invalidating indices
                sorted_entities = sorted(
                    [e for e in entities if e.type in protected_types], key=lambda e: e.start, reverse=True
                )

                for i, entity in enumerate(sorted_entities):
                    # Verify boundaries match text
                    if entity.end <= len(protected_text) and protected_text[entity.start : entity.end] == entity.text:
                        placeholder = f"__ENT_{i}__"
                        entity_placeholders[placeholder] = entity.text
                        # Replace the specific span
                        protected_text = protected_text[: entity.start] + placeholder + protected_text[entity.end :]
                        logger.debug(f"Protected entity {entity.type}: '{entity.text}' as '{placeholder}'")

                # Protect URLs and technical terms from the punctuation model by temporarily replacing them
                # Using pre-compiled patterns for performance (Legacy fallback and other patterns)
                url_placeholders = {}

                # Find and replace URLs with placeholders (if not already protected via entities)
                # We re-scan the protected text which now has entity placeholders
                for i, match in enumerate(regex_patterns.URL_PROTECTION_PATTERN.finditer(protected_text)):
                    placeholder = f"__URL_{i}__"
                    url_placeholders[placeholder] = match.group(0)
                    protected_text = protected_text.replace(match.group(0), placeholder, 1)
                    logger.info(f"Protected URL: '{match.group(0)}' as '{placeholder}'")

                # Also protect email addresses
                email_placeholders = {}
                for i, match in enumerate(regex_patterns.EMAIL_PROTECTION_PATTERN.finditer(protected_text)):
                    placeholder = f"__EMAIL_{i}__"
                    email_placeholders[placeholder] = match.group(0)
                    protected_text = protected_text.replace(match.group(0), placeholder, 1)
                    logger.info(f"Protected Email: '{match.group(0)}' as '{placeholder}'")

                # Also protect sequences of all-caps technical terms (like "HTML CSS JavaScript")
                tech_placeholders = {}
                for i, match in enumerate(regex_patterns.TECH_SEQUENCE_PATTERN.finditer(protected_text)):
                    placeholder = f"__TECH_{i}__"
                    tech_placeholders[placeholder] = match.group(0)
                    protected_text = protected_text.replace(match.group(0), placeholder, 1)

                # Protect math expressions from the punctuation model (preserve spacing around operators)
                # Note: Detected MATH_EXPRESSION entities are already protected above
                math_placeholders = {}
                for i, match in enumerate(regex_patterns.MATH_EXPRESSION_PATTERN.finditer(protected_text)):
                    placeholder = f"__MATH_{i}__"
                    math_placeholders[placeholder] = match.group(0)
                    protected_text = protected_text.replace(match.group(0), placeholder, 1)

                # Protect temperature expressions from the punctuation model
                temp_placeholders = {}
                for i, match in enumerate(regex_patterns.TEMPERATURE_PROTECTION_PATTERN.finditer(protected_text)):
                    placeholder = f"__TEMP_{i}__"
                    temp_placeholders[placeholder] = match.group(0)
                    protected_text = protected_text.replace(match.group(0), placeholder, 1)

                # Apply punctuation to the protected text
                logger.debug(f"Text before punctuation model: '{protected_text}'")
                result = punctuator.restore_punctuation(protected_text)
                logger.debug(f"Text after punctuation model: '{result}'")

                # Clean up any double punctuation and odd spacing BEFORE restoration
                # This prevents destructive regex from affecting restored URLs/IPs
                result = re.sub(r"\s*([.!?])\s*", r"\1 ", result).strip()
                result = re.sub(r"([.!?]){2,}", r"\1", result)

                # Restore entities (placeholders might have been moved by punctuation)
                for placeholder, original_text in entity_placeholders.items():
                    result = re.sub(rf"\b{re.escape(placeholder)}\b", lambda m: original_text, result)

                # Restore URLs
                for placeholder, url in url_placeholders.items():
                    result = re.sub(rf"\b{re.escape(placeholder)}\b", url, result)

                # Restore emails
                for placeholder, email in email_placeholders.items():
                    result = re.sub(rf"\b{re.escape(placeholder)}\b", email, result)

                # Restore technical terms
                for placeholder, tech_term in tech_placeholders.items():
                    result = re.sub(rf"\b{re.escape(placeholder)}\b", tech_term, result)

                # Restore math expressions
                for placeholder, math_expr in math_placeholders.items():
                    result = re.sub(rf"\b{re.escape(placeholder)}\b", math_expr, result)

                # Restore temperature expressions
                for placeholder, temp in temp_placeholders.items():
                    result = re.sub(rf"\b{re.escape(placeholder)}\b", temp, result)

                # Post-process punctuation using grammatical context
                if self.nlp:
                    try:
                        # Re-run spaCy on the punctuated text to analyze grammar
                        punc_doc = self.nlp(result)
                        new_result_parts = list(result)

                        for token in punc_doc:
                            # Find colons that precede a noun/entity
                            if token.text == ":" and token.i > 0:
                                prev_token = punc_doc[token.i - 1]

                                # Check if this is a command/action context where colon should be removed
                                should_remove = False

                                if token.i + 1 < len(punc_doc):
                                    next_token = punc_doc[token.i + 1]

                                    # Case 1: Command verb followed by colon and object (Edit: file.py)
                                    if (prev_token.pos_ == "VERB" and prev_token.dep_ == "ROOT") or (
                                        prev_token.pos_ in ["VERB", "NOUN", "PROPN"]
                                        and token.i == 1
                                        and next_token.pos_ in ["NOUN", "PROPN", "X"]
                                        and ("@" in next_token.text or "." in next_token.text)
                                    ):
                                        should_remove = True

                                    # Case 3: Known command/action words
                                    base_command_words = self.resources.get("context_words", {}).get("command_words", [])
                                    command_words = list(base_command_words) + [
                                        "drive",
                                        "use",
                                        "check",
                                        "select",
                                        "define",
                                        "access",
                                        "transpose",
                                        "download",
                                        "git",
                                        "contact",
                                        "email",
                                        "visit",
                                        "connect",
                                        "redis",
                                        "server",
                                        "ftp",
                                    ]
                                    if prev_token.text.lower() in command_words:
                                        should_remove = True

                                if should_remove:
                                    new_result_parts[token.idx] = ""

                        result = "".join(new_result_parts).replace("  ", " ")
                    except Exception as e:
                        logger.warning(f"SpaCy-based colon correction failed: {e}")

                # Fix double periods that the model sometimes adds
                result = re.sub(r"\.\.+", ".", result)
                result = re.sub(r"\?\?+", "?", result)
                result = re.sub(r"!!+", "!", result)

                # Fix hyphenated acronyms that the model sometimes creates
                result = result.replace("- ", " ")

                # Fix spacing around hyphens in numbers (e.g. phone numbers "555 - 123" -> "555-123")
                result = re.sub(r"(\d)\s*[-–—]\s*(\d)", r"\1-\2", result)

                # Fix spacing around math operators that the punctuation model may have removed
                # But be careful not to add spaces in URLs (which contain query parameters)
                # Only add spaces if it looks like a math expression (variable = value or number op number)
                # Exclude cases where the = is part of a URL query parameter (contains . ? or /)
                def should_add_math_spacing(match):
                    full_context = result[max(0, match.start() - 20) : match.end() + 20]
                    if any(char in full_context for char in ["?", "/", ".com", ".org", ".net"]):
                        return match.group(0)  # Don't add spaces in URL context
                    return f"{match.group(1)} {match.group(2)} {match.group(3)}"

                result = re.sub(r"([a-zA-Z_]\w*)([=+\-*×÷])([a-zA-Z_]\w*|\d+)", should_add_math_spacing, result)
                result = re.sub(r"(\d+)([+\-*×÷])(\d+)", r"\1 \2 \3", result)

                # Fix common punctuation model errors
                # 1. Remove colons incorrectly added before technical entities
                # But preserve colons after specific action verbs
                def should_preserve_colon(match):
                    # Get text before the colon
                    start_pos = max(0, match.start() - 20)
                    preceding_text = result[start_pos : match.start()].strip().lower()
                    # Preserve colon for specific contexts
                    preserve_words = self.resources.get("context_words", {}).get("preserve_colon", [])
                    for word in preserve_words:
                        if preceding_text.endswith(word):
                            return match.group(0)  # Keep the colon
                    # Otherwise remove it
                    return f" {match.group(1)}"

                result = re.sub(r":\s*(__ENTITY_\d+__)", should_preserve_colon, result)

                # Fix URLs that got split (e.g. "http://example. com")
                result = re.sub(r"(https?://[^\s]*[^\s.])\.\s+([a-z]{2,})", r"\1.\2", result)

                # Fix emails that got split (e.g. "user@example. com")
                result = re.sub(r"([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]*[a-zA-Z0-9-])\.\s+([a-z]{2,})", r"\1.\2", result)

                # Fix IP addresses that got split (e.g. "127. 0. 0. 1")
                for _ in range(3):  # Max 3 dots in IPv4
                    result = re.sub(r"(\d+)\.\s+(\d+)", r"\1.\2", result)

                # 2. Re-join sentences incorrectly split after technical entities
                result = re.sub(r"(__ENTITY_\d+__)\.\s+([Oo]n\s+line\s+)", r"\1 \2", result)
                result = re.sub(r"(__ENTITY_\d+__)\.\s+([Oo]n\s+(?:line|page|row|column)\s+)", r"\1 \2", result)
                result = re.sub(
                    r"(__ENTITY_\d+__)\.\s+([A-Z])", lambda m: f"{m.group(1)} {m.group(2).lower()}", result
                )

                # Rejoin sentences split after common command verbs or contexts
                result = re.sub(
                    r"\b(Set|Run|Use|In|Go|Get|Add|Make|Check|Contact|Email|Execute|Bake|Costs|Weighs|Drive|Rotate)\b\.\s+",
                    r"\1 ",
                    result,
                    flags=re.IGNORECASE,
                )

                if result != text:
                    logger.info(f"Punctuation added: '{result}'")
                    text = result

            except (AttributeError, ValueError, RuntimeError, OSError) as e:
                logger.error(
                    f"Punctuation model failed on text: '{text[:100]}{'...' if len(text) > 100 else ''}'.  Error: {e}"
                )

        # Add final punctuation intelligently
        if not is_standalone_technical and text and text.strip() and text.strip()[-1].isalnum():
            # Only add punctuation if it looks like a complete thought
            if len(text.split()) > 2:
                text += "."
                logger.debug(f"Added final punctuation: '{text}'")

        # Fix specific punctuation model errors
        # Remove colons before direct URLs and emails (for any that bypass entity detection)
        def should_remove_colon_before_link(match):
            # Get text before the colon
            start_pos = max(0, match.start() - 20)
            preceding_text = text[start_pos : match.start()].strip().lower()
            # Preserve colon for specific contexts
            preserve_words = self.resources.get("context_words", {}).get("preserve_colon", [])
            for word in preserve_words:
                if preceding_text.endswith(word):
                    return match.group(0)  # Keep the colon
            # Otherwise remove it
            return f" {match.group(1)}"

        text = re.sub(r":\s*([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})", should_remove_colon_before_link, text)
        text = re.sub(r":\s*(https?://[^\s]+)", should_remove_colon_before_link, text)

        # Fix time formatting issues (e.g., "at 3:p m" -> "at 3 PM")
        text = re.sub(r"\b(\d+):([ap])\s+m\b", r"\1 \2M", text, flags=re.IGNORECASE)
        text = re.sub(r"\b(\d+)\s+([ap])\s+m\b", r"\1 \2M", text, flags=re.IGNORECASE)

        # Add a more intelligent final punctuation check
        if not is_standalone_technical and text and text.strip() and text.strip()[-1].isalnum():
            word_count = len(text.split())
            if word_count > 1 or text.lower().strip() in self.complete_sentence_phrases:
                text += "."
                logger.debug(f"Added final punctuation: '{text}'")

        return text

    def restore_abbreviations(self, text: str) -> str:
        """Restore proper formatting for abbreviations after punctuation model."""
        # The punctuation model tends to strip periods from common abbreviations
        # This post-processing step restores them to our preferred format

        # Process each abbreviation
        abbreviations = self.resources.get("abbreviations", {})
        for abbr, formatted in abbreviations.items():
            # Match abbreviation at word boundaries
            # Use negative lookbehind to avoid replacing if already has period
            pattern = rf"(?<![.])\b{abbr}\b(?![.])"

            # Replace case-insensitively but preserve the case pattern
            def replace_with_case(match):
                original = match.group(0)
                if original.isupper():
                    # All caps: IE -> I.E.
                    return formatted.upper()
                if original[0].isupper():
                    # Title case: Ie -> I.e.
                    return formatted[0].upper() + formatted[1:]
                # Lowercase: ie -> i.e.
                return formatted

            text = re.sub(pattern, replace_with_case, text, flags=re.IGNORECASE)

        # Add comma after i.e. and e.g. when followed by a word,
        # but NOT if a comma is already there.
        text = re.sub(r"(\b(?:i\.e\.|e\.g\.))(?!,)(\s+[a-zA-Z])", r"\1,\2", text)

        return text
