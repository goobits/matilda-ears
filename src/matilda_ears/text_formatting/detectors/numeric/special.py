#!/usr/bin/env python3
"""Special entity detection: ordinals, music notation, emojis, and cardinal fallback."""

import re
from ...common import Entity, EntityType, NumberParser
from ...utils import is_inside_entity
from ....core.config import setup_logging
from ... import regex_patterns

logger = setup_logging(__name__, log_filename="text_formatting.txt")


class SpecialDetector:
    """Detector for ordinals, music notation, spoken emojis, and cardinal number fallback."""

    def __init__(self, nlp=None, number_parser: NumberParser = None, resources: dict = None, language: str = "en"):
        """Initialize SpecialDetector.

        Args:
            nlp: SpaCy NLP model instance.
            number_parser: NumberParser instance for number word handling.
            resources: Language-specific resources dictionary.
            language: Language code (default: 'en').

        """
        self.nlp = nlp
        self.number_parser = number_parser
        self.resources = resources or {}
        self.language = language

    def detect_ordinals(
        self, text: str, entities: list[Entity], all_entities: list[Entity] | None = None
    ) -> None:
        """Detect ordinal numbers (first, second, third, etc.)."""
        # First, run the SpaCy analysis once if available.
        doc = None
        if self.nlp:
            try:
                doc = self.nlp(text)
            except Exception as e:
                logger.warning(f"SpaCy ordinal analysis failed: {e}")

        for match in regex_patterns.SPOKEN_ORDINAL_PATTERN.finditer(text):
            # If we have a SpaCy doc, use it for grammatical context checking.
            if doc:
                ordinal_token = None
                next_token = None
                for token in doc:
                    if token.idx == match.start():
                        ordinal_token = token
                        if token.i + 1 < len(doc):
                            next_token = doc[token.i + 1]
                        break

                # Check for specific idiomatic contexts
                if ordinal_token and next_token:
                    # Skip if it's an adjective followed by a specific idiomatic noun from our resources.
                    if ordinal_token.pos_ == "ADJ" and next_token.pos_ == "NOUN":
                        # This is the key: we check our i18n file for specific exceptions.
                        idiomatic_phrases = self.resources.get("technical", {}).get("idiomatic_phrases", {})
                        if ordinal_token.text.lower() in idiomatic_phrases and next_token.text.lower() in idiomatic_phrases[ordinal_token.text.lower()]:
                            logger.debug(f"Skipping ORDINAL '{match.group()}' due to idiomatic follower noun '{next_token.text}'.")
                            continue

                    # Skip if it's at sentence start and followed by comma ("First, we...")
                    if (ordinal_token.i == 0 or ordinal_token.sent.start == ordinal_token.i) and next_token.text == ",":
                        logger.debug(f"Skipping ORDINAL '{match.group()}' - sentence starter with comma")
                        continue

            # Your existing logic for checking overlaps is good. Keep it.
            check_entities = all_entities if all_entities else entities
            overlaps_high_priority = False
            for existing in check_entities:
                if not (match.end() <= existing.start or match.start() >= existing.end):
                    if existing.type not in [
                        EntityType.CARDINAL,
                        EntityType.DATE,
                        EntityType.QUANTITY,
                    ]:
                        overlaps_high_priority = True
                        break

            if not overlaps_high_priority:
                entities.append(
                    Entity(
                        start=match.start(),
                        end=match.end(),
                        text=match.group(),
                        type=EntityType.ORDINAL,
                        metadata={"ordinal_word": match.group(0)},
                    )
                )

    def detect_music_notation(
        self, text: str, entities: list[Entity], all_entities: list[Entity] | None = None
    ) -> None:
        """Detect music notation expressions.

        Examples:
        - "C sharp" -> "C#"
        - "B flat" -> "Bb"
        - "E natural" -> "E"

        """
        # Pattern for music notes with accidentals - supports both space and hyphen separation
        music_pattern = re.compile(r"\b([A-G])[-\s]+(sharp|flat|natural)\b", re.IGNORECASE)

        for match in music_pattern.finditer(text):
            check_entities = all_entities if all_entities else entities
            if not is_inside_entity(match.start(), match.end(), check_entities):
                note = match.group(1).upper()  # Capitalize the note
                accidental = match.group(2).lower()

                entities.append(
                    Entity(
                        start=match.start(),
                        end=match.end(),
                        text=match.group(0),
                        type=EntityType.MUSIC_NOTATION,
                        metadata={"note": note, "accidental": accidental},
                    )
                )

    def detect_spoken_emojis(
        self, text: str, entities: list[Entity], all_entities: list[Entity] | None = None
    ) -> None:
        """Detect spoken emoji expressions using a tiered system.

        Tier 1 (Implicit): Can be used without "emoji" trigger
        - "smiley face" -> corresponding emoji

        Tier 2 (Explicit): Must be followed by "emoji", "icon", or "emoticon"
        - "rocket emoji" -> corresponding emoji
        """
        # Build patterns from the emoji mappings
        implicit_keys = list(regex_patterns.SPOKEN_EMOJI_IMPLICIT_MAP.keys())
        explicit_keys = list(regex_patterns.SPOKEN_EMOJI_EXPLICIT_MAP.keys())

        # Sort keys by length (longest first) to avoid greedy matching issues
        explicit_keys.sort(key=len, reverse=True)

        # Pattern for explicit emojis (must have trigger word)
        if explicit_keys:
            explicit_pattern = re.compile(
                r"(\b(?:"
                + "|".join(re.escape(key) for key in explicit_keys)
                + r")\s+(?:emoji|icon|emoticon)\b)([.!?]*)",
                re.IGNORECASE,
            )

            for match in explicit_pattern.finditer(text):
                check_entities = all_entities if all_entities else entities
                if not is_inside_entity(match.start(), match.end(), check_entities):
                    # Get the emoji key (group 1) and the full text including punctuation (group 0)
                    emoji_key_full = match.group(1).lower().strip()
                    # Remove the trigger word from the key
                    emoji_key = re.sub(r"\s+(?:emoji|icon|emoticon)$", "", emoji_key_full)

                    entities.append(
                        Entity(
                            start=match.start(),
                            end=match.end(),
                            text=match.group(0),
                            type=EntityType.SPOKEN_EMOJI,
                            metadata={"emoji_key": emoji_key, "is_implicit": False},
                        )
                    )

        # Pattern for implicit emojis (no trigger word needed)
        implicit_keys.sort(key=len, reverse=True)
        if implicit_keys:
            implicit_pattern = re.compile(
                r"(\b(?:" + "|".join(re.escape(key) for key in implicit_keys) + r")\b)([.!?]*)", re.IGNORECASE
            )

            for match in implicit_pattern.finditer(text):
                check_entities = all_entities if all_entities else entities
                if not is_inside_entity(match.start(), match.end(), check_entities):
                    entities.append(
                        Entity(
                            start=match.start(),
                            end=match.end(),
                            text=match.group(0),
                            type=EntityType.SPOKEN_EMOJI,
                            metadata={"emoji_key": match.group(1).lower(), "is_implicit": True},
                        )
                    )

    def detect_cardinal_numbers_fallback(
        self, text: str, entities: list[Entity], all_entities: list[Entity] | None = None
    ) -> None:
        """Fallback detection for cardinal numbers when SpaCy is not available or for non-English languages."""
        if not self.number_parser:
            return

        # Run this if SpaCy failed to load OR if we're not using English
        # (SpaCy's multilingual support for number recognition is limited)
        if self.nlp and self.language == "en":
            return  # SpaCy is available and we're using English, let it handle CARDINAL detection

        # Build a comprehensive pattern for number words
        number_words = sorted(self.number_parser.all_number_words, key=len, reverse=True)
        number_pattern = "|".join(re.escape(word) for word in number_words)

        # Pattern for sequences of number words
        # Matches: "two thousand five hundred", "twenty three", "four", etc.
        cardinal_pattern = re.compile(
            rf"\b(?:{number_pattern})(?:\s+(?:and\s+)?(?:{number_pattern}))*\b", re.IGNORECASE
        )

        for match in cardinal_pattern.finditer(text):
            check_entities = all_entities if all_entities else entities
            if not is_inside_entity(match.start(), match.end(), check_entities):
                # Try to parse this number sequence
                number_text = match.group(0)
                parsed_number = self.number_parser.parse(number_text)

                # Only create entity if it parses to a valid number
                if parsed_number and parsed_number.isdigit():
                    entities.append(
                        Entity(
                            start=match.start(),
                            end=match.end(),
                            text=number_text,
                            type=EntityType.CARDINAL,
                            metadata={"parsed_value": parsed_number},
                        )
                    )
