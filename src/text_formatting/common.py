#!/usr/bin/env python3
"""Common data structures and classes shared across text formatting modules."""

from typing import Optional, Dict, Any
from dataclasses import dataclass
from enum import Enum, auto


class EntityType(Enum):
    """Entity types for text formatting"""

    URL = auto()
    SPOKEN_URL = auto()
    SPOKEN_PROTOCOL_URL = auto()
    ASSIGNMENT = auto()
    MATH = auto()
    MATH_EXPRESSION = auto()
    INCREMENT_OPERATOR = auto()
    DECREMENT_OPERATOR = auto()
    CARDINAL = auto()
    EMAIL = auto()
    COMPARISON = auto()
    PHYSICS_SQUARED = auto()
    PHYSICS_TIMES = auto()
    CURRENCY = auto()
    MONEY = auto()
    PERCENT = auto()
    DATA_SIZE = auto()
    FREQUENCY = auto()
    TIME_DURATION = auto()
    TIME_CONTEXT = auto()
    TIME_AMPM = auto()
    PHONE_LONG = auto()
    PORT_NUMBER = auto()
    ABBREVIATION = auto()
    FILENAME = auto()
    SPOKEN_EMAIL = auto()
    DATE = auto()
    TIME = auto()
    QUANTITY = auto()
    ORDINAL = auto()
    TIME_RELATIVE = auto()
    FRACTION = auto()
    NUMERIC_RANGE = auto()
    COMMAND_FLAG = auto()
    # Legacy entity types that may still be used
    CENTS = auto()
    DOLLAR_CENTS = auto()
    DOLLARS = auto()
    POUNDS = auto()
    EUROS = auto()
    VERSION = auto()
    UNIX_PATH = auto()
    WINDOWS_PATH = auto()
    TEMPERATURE = auto()
    METRIC_LENGTH = auto()
    METRIC_WEIGHT = auto()
    METRIC_VOLUME = auto()
    ROOT_EXPRESSION = auto()
    MATH_CONSTANT = auto()
    SCIENTIFIC_NOTATION = auto()
    MUSIC_NOTATION = auto()
    SPOKEN_EMOJI = auto()
    SLASH_COMMAND = auto()
    UNDERSCORE_DELIMITER = auto()
    SIMPLE_UNDERSCORE_VARIABLE = auto()
    # Additional entity types for complete technical term coverage
    PROGRAMMING_KEYWORD = auto()
    CLI_COMMAND = auto()
    PROTOCOL = auto()


@dataclass
class Entity:
    """Represents a detected entity in the text"""

    start: int
    end: int
    text: str
    type: EntityType
    metadata: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class NumberParser:
    """Algorithmic number parsing with multilingual support"""

    def __init__(self, language: str = "en"):
        from .constants import get_resources

        # Load language-specific number words
        resources = get_resources(language)
        number_resources = resources.get("number_words", {})

        # Use language-specific words or fall back to English defaults
        if number_resources:
            self.ones = number_resources.get("ones", {})
            self.tens = number_resources.get("tens", {})
            self.scales = number_resources.get("scales", {})
        else:
            # Fallback to hardcoded English for backward compatibility
            self.ones = {
                "zero": 0,
                "one": 1,
                "two": 2,
                "three": 3,
                "four": 4,
                "five": 5,
                "six": 6,
                "seven": 7,
                "eight": 8,
                "nine": 9,
                "ten": 10,
                "eleven": 11,
                "twelve": 12,
                "thirteen": 13,
                "fourteen": 14,
                "fifteen": 15,
                "sixteen": 16,
                "seventeen": 17,
                "eighteen": 18,
                "nineteen": 19,
            }
            self.tens = {
                "twenty": 20,
                "thirty": 30,
                "forty": 40,
                "fifty": 50,
                "sixty": 60,
                "seventy": 70,
                "eighty": 80,
                "ninety": 90,
            }
            self.scales = {
                "hundred": 100,
                "thousand": 1000,
                "million": 1000000,
                "billion": 1000000000,
                "trillion": 1000000000000,
            }

        # Combine all number words for easy checking
        self.all_number_words = set(self.ones.keys()) | set(self.tens.keys()) | set(self.scales.keys())

    def parse(self, text: str) -> Optional[str]:
        """Parse number words to digits algorithmically, handling compound numbers."""
        if not text:
            return None

        # Clean and normalize the input text
        text = text.strip().lower().replace("-", " ")

        # Check if it's already a number
        if text.replace(".", "", 1).isdigit():
            return text

        # Handle decimal numbers with "point" or "dot"
        if " point " in text or " dot " in text:
            # Normalize to " point "
            text = text.replace(" dot ", " point ")
            parts = text.split(" point ", 1)
            left_num_str = self.parse(parts[0])
            if left_num_str is None:
                return None

            right_digits = self.parse_as_digits(parts[1])
            if right_digits:
                return f"{left_num_str}.{right_digits}"
            return None

        words = text.split()
        current_val = 0
        total_val = 0

        # Check if no scale words are present - handle as sequence
        if not any(word in self.scales for word in words):
            parsed_sequence = self.parse_as_sequence(words)
            if parsed_sequence is not None:
                return parsed_sequence

        for word in words:
            if word in self.ones:
                current_val += self.ones[word]
            elif word in self.tens:
                current_val += self.tens[word]
            elif word in self.scales:
                scale_val = self.scales[word]
                # If current_val is 0, it implies a standalone scale word
                multiplier = current_val if current_val > 0 else 1
                if scale_val == 100:
                    current_val = multiplier * scale_val
                else:
                    total_val += multiplier * scale_val
                    current_val = 0
            elif word.isdigit():
                current_val += int(word)
            elif word != "and":
                return None

        total_val += current_val
        return str(total_val) if total_val > 0 or text == "zero" else None

    def parse_as_sequence(self, words: list) -> Optional[str]:
        """Tries to parse a list of words as a sequence of numbers."""
        try:
            # Special case for year patterns like "twenty twenty four" -> "2024"
            if len(words) == 3 and all(w in self.tens for w in words[:2]) and words[2] in self.ones:
                # Pattern: tens tens ones (e.g., twenty twenty four)
                first_tens = self.tens[words[0]]
                second_tens = self.tens[words[1]]
                ones = self.ones[words[2]]
                # Construct as year: 20 + 20 + 4 -> 2024 (concatenation, not addition)
                return f"{first_tens}{second_tens // 10}{ones}"

            # Special case for "twenty twenty" -> "2020"
            if len(words) == 2 and all(w in self.tens for w in words):
                first_tens = self.tens[words[0]]
                second_tens = self.tens[words[1]]
                return f"{first_tens}{second_tens // 10}0"

            parts = []
            i = 0
            while i < len(words):
                # Greedily parse the longest possible number from current position
                best_parse = None
                best_j = i
                for j in range(len(words), i, -1):
                    chunk = words[i:j]
                    parsed_chunk = self._parse_simple_number(" ".join(chunk))
                    if parsed_chunk is not None:
                        best_parse = parsed_chunk
                        best_j = j
                        break

                if best_parse is not None:
                    parts.append(str(best_parse))
                    i = best_j
                else:
                    return None
            return "".join(parts)
        except RecursionError:
            return None

    def _parse_simple_number(self, text: str) -> Optional[int]:
        """A non-recursive helper to parse numbers up to 999."""
        words = text.split()
        current_val = 0
        total_val = 0
        for word in words:
            if word in self.ones:
                current_val += self.ones[word]
            elif word in self.tens:
                current_val += self.tens[word]
            elif word == "hundred":
                current_val *= 100
            elif word != "and":
                return None
        total_val += current_val
        return total_val if total_val > 0 or text == "zero" else None

    def parse_ordinal(self, text: str) -> Optional[str]:
        """Parse ordinal words to digits (e.g., 'first' -> '1', 'twenty third' -> '23')"""
        if not text:
            return None

        text = text.strip().lower().replace("-", " ")

        # Handle special cases first
        special_ordinals = {
            "first": "1",
            "second": "2",
            "third": "3",
            "fourth": "4",
            "fifth": "5",
            "sixth": "6",
            "seventh": "7",
            "eighth": "8",
            "ninth": "9",
            "tenth": "10",
            "eleventh": "11",
            "twelfth": "12",
            "thirteenth": "13",
            "fourteenth": "14",
            "fifteenth": "15",
            "sixteenth": "16",
            "seventeenth": "17",
            "eighteenth": "18",
            "nineteenth": "19",
            "twentieth": "20",
            "thirtieth": "30",
            "fortieth": "40",
            "fiftieth": "50",
            "sixtieth": "60",
            "seventieth": "70",
            "eightieth": "80",
            "ninetieth": "90",
            "hundredth": "100",
            "thousandth": "1000",
        }

        if text in special_ordinals:
            return special_ordinals[text]

        # Handle compound ordinals like "twenty first", "one hundred first"
        words = text.split()
        # Find the last word that is an ordinal
        last_word = words[-1] if words else ""

        if last_word in special_ordinals:
            # Get the cardinal part of the text
            cardinal_part_text = " ".join(words[:-1])
            if cardinal_part_text:
                cardinal_num_str = self.parse(cardinal_part_text)
                if cardinal_num_str:
                    cardinal_value = int(cardinal_num_str)
                    ordinal_value = int(special_ordinals[last_word])

                    # For any compound ordinal like "twenty-first" or "hundred-first", the value is the sum.
                    if cardinal_value > 0 and cardinal_value % 10 == 0:
                        return str(cardinal_value + ordinal_value)

        # Fallback to cardinal parsing for the whole phrase if ordinal parsing fails
        cardinal_num = self.parse(text)
        if cardinal_num:
            return cardinal_num

        return None

    def parse_as_digits(self, text: str) -> Optional[str]:
        """Parse text as a sequence of spoken digits, returning concatenated string.

        For example: "one two three" -> "123", "ocho cero ocho cero" -> "8080"
        This is useful for URLs, port numbers, and other contexts where we want
        digit concatenation rather than arithmetic sum.
        """
        if not text:
            return None

        text = text.strip().lower()
        words = text.split()

        # Check if every word is a single digit word (0-9)
        digit_sequence = []
        for word in words:
            # Check if word is a number word that represents a single digit (0-9)
            if word in self.ones and 0 <= self.ones[word] <= 9:
                digit_sequence.append(str(self.ones[word]))
            elif word.isdigit() and len(word) == 1:
                # Also handle already-converted digits
                digit_sequence.append(word)
            else:
                # If any word is not a single digit, this isn't a digit sequence
                return None

        if digit_sequence:
            return "".join(digit_sequence)

        return None

    def parse_with_validation(self, text: str) -> Optional[str]:
        """Parse numbers with additional validation for context"""
        if not text:
            return None

        # Don't convert single letters that might be variables or identifiers
        if len(text.strip()) == 1 and text.strip().isalpha():
            return None

        # Don't convert if it looks like it might be part of a compound word
        if any(char in text for char in ".-_"):
            return None

        return self.parse(text)
