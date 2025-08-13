#!/usr/bin/env python3
"""Format detection functionality for numeric entities - phone numbers, versions, music notation, and emojis."""
from __future__ import annotations

import re
from typing import Any

from stt.core.config import setup_logging
from stt.text_formatting.pattern_modules.numeric_patterns import SPOKEN_PHONE_PATTERN
from stt.text_formatting.pattern_modules.text_patterns import (
    SPOKEN_EMOJI_IMPLICIT_MAP,
    SPOKEN_EMOJI_EXPLICIT_MAP,
)
from stt.text_formatting.common import Entity, EntityType, NumberParser
from stt.text_formatting.utils import is_inside_entity

logger = setup_logging(__name__)


class FormatDetector:
    """Detects formatted patterns like phone numbers, version numbers, music notation, and spoken emojis."""
    
    def __init__(self, language: str = "en"):
        """
        Initialize FormatDetector.

        Args:
            language: Language code for resource loading (default: 'en')
        """
        self.language = language
        # Initialize NumberParser for robust number word detection
        self.number_parser = NumberParser(language=self.language)

    def detect_phone_numbers(
        self, text: str, entities: list[Entity], all_entities: list[Entity] | None = None
    ) -> None:
        """Detect phone numbers spoken as individual digits."""
        # Use centralized phone pattern
        for match in SPOKEN_PHONE_PATTERN.finditer(text):
            check_entities = all_entities if all_entities else entities
            if not is_inside_entity(match.start(), match.end(), check_entities):
                entities.append(
                    Entity(start=match.start(), end=match.end(), text=match.group(), type=EntityType.PHONE_LONG)
                )

    def detect_version_numbers(
        self, text: str, entities: list[Entity], all_entities: list[Entity] | None = None
    ) -> None:
        """Detect version numbers in spoken form (e.g., 'version two point five')."""
        # Skip if text already contains properly formatted version numbers (e.g., "2.0.1")
        if re.search(r"\b\d+\.\d+(?:\.\d+)*\b", text):
            # Don't process - leave as is
            return

        # Pattern for version numbers with "version" prefix
        version_pattern = re.compile(
            r"\b(?:v|V|version|Version|python|Python|java|Java|node|Node|ruby|Ruby|php|PHP|go|Go|rust|Rust|dotnet|DotNet|gcc|GCC)\s+"
            r"(" + "|".join(self.number_parser.all_number_words) + r")"
            r"(?:\s+(?:point|dot)\s+"
            r"(" + "|".join(self.number_parser.all_number_words) + r"))?"
            r"(?:\s+(?:point|dot)\s+"
            r"(" + "|".join(self.number_parser.all_number_words) + r"))?"
            r"(?:\s+(?:percent|percentage))?"
            r"\b",
            re.IGNORECASE,
        )

        for match in version_pattern.finditer(text):
            check_entities = all_entities if all_entities else entities
            if not is_inside_entity(match.start(), match.end(), check_entities):
                # Extract the components
                full_match = match.group(0)
                groups = match.groups()

                # Check if this is a percentage (e.g., "rate is zero point five percent")
                is_percentage = "percent" in full_match.lower()

                entity_type = EntityType.PERCENT if is_percentage else EntityType.VERSION

                entities.append(
                    Entity(
                        start=match.start(),
                        end=match.end(),
                        text=full_match,
                        type=entity_type,
                        metadata={"groups": groups, "is_percentage": is_percentage},
                    )
                )

        # Also detect standalone decimal numbers that might be versions or percentages
        # Pattern for spoken decimal numbers like "three point one four"
        decimal_pattern = re.compile(
            r"\b(" + "|".join(self.number_parser.all_number_words) + r"|\d+)"
            r"\s+(?:point|dot)\s+"
            r"((?:"
            + "|".join(self.number_parser.all_number_words)
            + r"|\d+)(?:\s+(?:"
            + "|".join(self.number_parser.all_number_words)
            + r"|\d+))*)"
            r"(?:\s+(?:percent|percentage))?"
            r"\b",
            re.IGNORECASE,
        )

        for match in decimal_pattern.finditer(text):
            check_entities = all_entities if all_entities else entities
            if not is_inside_entity(match.start(), match.end(), check_entities):
                # Check context to determine if this is likely a version number
                prefix_context = text[max(0, match.start() - 20) : match.start()].lower()

                # Skip if already captured by version pattern
                if any(
                    word in prefix_context
                    for word in ["version", "python", "java", "node", "ruby", "php", "go", "rust", "dotnet", "gcc"]
                ):
                    continue

                # This is a standalone decimal, check if it's a percentage
                full_match = match.group(0)
                is_percentage = "percent" in full_match.lower()

                if is_percentage:
                    entities.append(
                        Entity(
                            start=match.start(),
                            end=match.end(),
                            text=full_match,
                            type=EntityType.PERCENT,
                            metadata={"groups": match.groups(), "is_percentage": True},
                        )
                    )
                else:
                    # Create a FRACTION entity for decimal numbers
                    entities.append(
                        Entity(
                            start=match.start(),
                            end=match.end(),
                            text=full_match,
                            type=EntityType.FRACTION,
                            metadata={"groups": match.groups(), "is_decimal": True},
                        )
                    )

    def detect_music_notation(
        self, text: str, entities: list[Entity], all_entities: list[Entity] | None = None
    ) -> None:
        """
        Detect music notation expressions.

        Examples:
        - "C sharp" → "C♯"
        - "B flat" → "B♭"
        - "E natural" → "E♮"

        """
        import re

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
        """
        Detect spoken emoji expressions using a tiered system.

        Tier 1 (Implicit): Can be used without "emoji" trigger
        - "smiley face" → 🙂

        Tier 2 (Explicit): Must be followed by "emoji", "icon", or "emoticon"
        - "rocket emoji" → 🚀
        """
        # Build patterns from the emoji mappings
        implicit_keys = list(SPOKEN_EMOJI_IMPLICIT_MAP.keys())
        explicit_keys = list(SPOKEN_EMOJI_EXPLICIT_MAP.keys())

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