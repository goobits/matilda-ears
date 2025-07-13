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
    VERSION_THREE = auto()
    VERSION_TWO = auto()
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
    metadata: Dict[str, Any] = None

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
        """Parse number words to digits algorithmically"""
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
            left_part, right_part = text.split(" point ", 1)

            left_num_str = self.parse(left_part)
            if left_num_str is None:
                return None

            # For the decimal part, parse each word as a single digit
            right_digits = []
            for word in right_part.split():
                digit = self.ones.get(word)
                if digit is not None and digit < 10:
                    right_digits.append(str(digit))
                # Allow for already-digitized parts
                elif word.isdigit():
                    right_digits.append(word)
                else:
                    # Try parsing as a number for multi-word decimals
                    break

            if right_digits:
                return f"{left_num_str}.{''.join(right_digits)}"
            # Fallback if right part is not single digits
            right_num_str = self.parse(right_part)
            if right_num_str:
                return f"{left_num_str}.{right_num_str}"
            return None  # Invalid decimal part

        # Handle large numbers by splitting on spaces
        words = text.split()

        current_val = 0
        total_val = 0

        for word in words:
            if word in self.ones:
                current_val += self.ones[word]
            elif word in self.tens:
                current_val += self.tens[word]
            elif word in self.scales:
                scale_val = self.scales[word]
                if scale_val == 100:
                    # Handle "hundred" - multiply current value or default to 1 if standalone
                    if current_val == 0:
                        current_val = scale_val  # Standalone "hundred" = 100
                    else:
                        current_val *= scale_val  # "five hundred" = 5 * 100
                else:
                    # Handle "thousand", "million", etc.
                    if current_val == 0:
                        current_val = 1  # Standalone "thousand" = 1 * 1000
                    total_val += current_val * scale_val
                    current_val = 0
            elif word.isdigit():
                # Handle cases where part of the number is already a digit
                current_val += int(word)
            elif word == "and":
                # Handle "and" in compound numbers
                # If we have accumulated a value and "and" is not at the end,
                # this might be the end of a number part (like "one and" in "one and one half")
                if current_val > 0 and len(words) > 1:
                    # Check if this is likely the end of a number sequence
                    word_index = words.index(word) if word in words else -1
                    if word_index >= 0 and word_index < len(words) - 1:
                        # Look ahead to see if next word starts a fraction or other construct
                        next_word = words[word_index + 1]
                        # If next word is a number that could start a fraction,
                        # treat this "and" as a separator
                        if next_word in self.ones and self.ones[next_word] <= 10:
                            # This could be "one and one half" - end number here
                            break
                # Otherwise, skip "and" in numbers like "one hundred and twenty"
                continue
            else:
                # If a word is not a number word, return None
                return None

        total_val += current_val

        # Return the result if we parsed a valid number
        if total_val > 0 or text == "zero":
            return str(total_val)

        # Fallback for simple sequences of digits spoken as words
        if len(words) > 1:
            digit_sequence = []
            all_digits = True
            for word in words:
                if word in self.ones and self.ones[word] < 10:
                    digit_sequence.append(str(self.ones[word]))
                else:
                    all_digits = False
                    break
            if all_digits:
                return "".join(digit_sequence)

        return None  # Return None if no valid number could be parsed

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
                cardinal_part_num = self.parse(cardinal_part_text)
                if cardinal_part_num:
                    # Check if it's a tens/hundreds boundary
                    cardinal_value = int(cardinal_part_num)
                    ordinal_value = int(special_ordinals[last_word])

                    if cardinal_value % 10 == 0 and ordinal_value < 10:
                        # It's a compound like "twenty first" (20 + 1)
                        return str(cardinal_value + ordinal_value)
                    if cardinal_value % 100 == 0 and ordinal_value < 100:
                        # It's a compound like "one hundred first" (100 + 1)
                        return str(cardinal_value + ordinal_value)
                    if cardinal_value % 1000 == 0 and ordinal_value < 1000:
                        # It's a compound like "one thousand first" (1000 + 1)
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
