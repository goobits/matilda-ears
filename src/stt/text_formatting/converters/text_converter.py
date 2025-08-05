"""Text pattern converter for letters, emojis, and music notation."""

import re
from typing import Dict

from stt.text_formatting.common import Entity, EntityType
from stt.text_formatting import regex_patterns
from .base import BasePatternConverter


class TextPatternConverter(BasePatternConverter):
    """Converter for text-related patterns like letters, emojis, and music notation."""
    
    def __init__(self, number_parser, language: str = "en"):
        """Initialize text pattern converter."""
        super().__init__(number_parser, language)
        
        # Define supported entity types and their converter methods
        self.supported_types: Dict[EntityType, str] = {
            EntityType.MUSIC_NOTATION: "convert_music_notation",
            EntityType.SPOKEN_EMOJI: "convert_spoken_emoji",
            EntityType.SPOKEN_LETTER: "convert_spoken_letter",
            EntityType.LETTER_SEQUENCE: "convert_letter_sequence",
        }
        
    def convert(self, entity: Entity, full_text: str = "") -> str:
        """Convert a text entity to its final form."""
        converter_method = self.get_converter_method(entity.type)
        if converter_method and hasattr(self, converter_method):
            return getattr(self, converter_method)(entity)
        return entity.text
        
    def convert_music_notation(self, entity: Entity) -> str:
        """
        Convert music notation to symbols.

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
        """
        Convert spoken emoji expressions to emoji characters.

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

    def convert_spoken_letter(self, entity: Entity) -> str:
        """
        Convert spoken letters to their character form.

        Examples:
        - "capital A" → "A"
        - "lowercase b" → "b"

        """
        if not entity.metadata:
            return entity.text

        letter = entity.metadata.get("letter", "")
        case = entity.metadata.get("case", "")

        if not letter:
            return entity.text

        # Apply case conversion based on metadata
        if case == "uppercase":
            return letter.upper()
        elif case == "lowercase":
            return letter.lower()
        else:
            # Default to the letter as provided
            return letter

    def convert_letter_sequence(self, entity: Entity) -> str:
        """
        Convert letter sequences to their concatenated form.

        Examples:
        - "capital A B C" → "ABC"
        - "capital A lowercase b capital C" → "AbC"
        - Mixed case sequences handled properly

        """
        # Special handling for common abbreviations that should be left as-is for postprocessing
        entity_text = entity.text.lower().strip()
        if entity_text in ["i e", "e g", "v s"]:
            # Return the original text to be handled by abbreviation postprocessing
            return entity.text
            
        if not entity.metadata:
            return entity.text

        letters = entity.metadata.get("letters", [])
        case = entity.metadata.get("case", "")

        if not letters:
            return entity.text

        # Handle different case scenarios
        if case == "uppercase":
            # All letters should be uppercase
            return "".join(letter.upper() for letter in letters)
        elif case == "lowercase":
            # All letters should be lowercase
            return "".join(letter.lower() for letter in letters)
        elif case == "mixed":
            # Use letters as they are (case already determined by detector)
            return "".join(letters)
        else:
            # Default to joining letters as-is
            return "".join(letters)