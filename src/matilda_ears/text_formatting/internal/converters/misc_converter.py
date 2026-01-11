#!/usr/bin/env python3
"""Miscellaneous converters for music notation and emoji."""

import re

from ...common import Entity
from ... import regex_patterns


class MiscConverterMixin:
    """Mixin class providing miscellaneous conversion methods.

    This mixin provides conversion methods for:
    - Music notation (sharps, flats, naturals)
    - Spoken emoji expressions
    """

    def convert_music_notation(self, entity: Entity) -> str:
        """Convert music notation to symbols.

        Examples:
        - "C sharp" → "C♯"
        - "B flat" → "B♭"
        - "E natural" → "E♮"

        """
        if not entity.metadata:
            return entity.text

        note = entity.metadata.get("note", "")
        accidental = entity.metadata.get("accidental", "")

        accidental_map = {"sharp": "♯", "flat": "♭", "natural": "♮"}

        symbol = accidental_map.get(accidental, "")
        if symbol:
            return f"{note}{symbol}"

        return entity.text

    def convert_spoken_emoji(self, entity: Entity) -> str:
        """Convert spoken emoji expressions to emoji characters.

        Examples:
        - "smiley face" → "🙂"
        - "rocket emoji" → "🚀"

        """
        if not entity.metadata:
            return entity.text

        emoji_key = entity.metadata.get("emoji_key", "").lower()
        is_implicit = entity.metadata.get("is_implicit", False)

        if is_implicit:
            # Look up in implicit map
            emoji = regex_patterns.SPOKEN_EMOJI_IMPLICIT_MAP.get(emoji_key)
        else:
            # Look up in explicit map
            emoji = regex_patterns.SPOKEN_EMOJI_EXPLICIT_MAP.get(emoji_key)

        if emoji:
            # The detection regex now captures trailing punctuation in the entity text
            # Preserve it after conversion.
            match = re.search(r"([.!?]*)$", entity.text)
            trailing_punct = match.group(1) if match else ""
            return emoji + trailing_punct

        return entity.text
