#!/usr/bin/env python3
"""Number, ordinal, fraction, and version converters."""

import re

from ..common import Entity


class NumberConverterMixin:
    """Mixin class providing number conversion methods.

    This mixin expects the host class to provide:
    - self.number_parser: NumberParser instance
    """

    def convert_cardinal(self, entity: Entity, full_text: str = "") -> str:
        """Convert cardinal numbers - only convert standalone clear numbers"""
        # Don't convert numbers that are part of hyphenated compounds
        # Check if this entity is immediately followed by a hyphen (like "One-on-one")
        if full_text:
            # Check character after entity end
            if entity.end < len(full_text) and full_text[entity.end] == "-":
                return entity.text
            # Check character before entity start
            if entity.start > 0 and full_text[entity.start - 1] == "-":
                return entity.text

        # Use the more general parser
        parsed = self.number_parser.parse(entity.text)
        return parsed if parsed else entity.text

    def convert_ordinal(self, entity: Entity) -> str:
        """Convert ordinal numbers with context awareness (first -> 1st, but 1st -> first in conversational contexts)."""
        text_lower = entity.text.lower().replace("-", " ")
        original_text = entity.text

        # Check if input is already numeric (1st, 2nd, etc.)
        numeric_ordinal_pattern = re.compile(r"(\d+)(st|nd|rd|th)", re.IGNORECASE)
        numeric_match = numeric_ordinal_pattern.match(original_text)

        if numeric_match:
            # Input is already numeric - check context to see if we should convert to words
            if hasattr(entity, "parent_text") and entity.parent_text:
                # Context analysis for conversational vs positional usage
                context = entity.parent_text.lower()

                # Conversational patterns where numeric ordinals should become words
                conversational_patterns = [
                    r"\blet\'s\s+do\s+(?:this|that)\s+" + re.escape(original_text.lower()),
                    r"\bwe\s+(?:need|should)\s+(?:to\s+)?(?:handle|do)\s+(?:this|that)\s+"
                    + re.escape(original_text.lower()),
                    r"\b(?:first|1st)\s+(?:thing|step|priority|order|task)",
                    r"\bdo\s+(?:this|that)\s+" + re.escape(original_text.lower()),
                ]

                # Positional/ranking patterns where numeric ordinals should stay numeric
                positional_patterns = [
                    r"\bfinished\s+" + re.escape(original_text.lower()) + r"\s+place",
                    r"\bcame\s+in\s+" + re.escape(original_text.lower()),
                    r"\branked\s+" + re.escape(original_text.lower()),
                    r"\b" + re.escape(original_text.lower()) + r"\s+place",
                    r"\bin\s+the\s+" + re.escape(original_text.lower()),
                ]

                # Check for conversational patterns
                for pattern in conversational_patterns:
                    if re.search(pattern, context):
                        # Convert numeric to word form
                        num_str = numeric_match.group(1)
                        num = int(num_str)

                        # Reverse mapping from numbers to words
                        num_to_word = {
                            1: "first",
                            2: "second",
                            3: "third",
                            4: "fourth",
                            5: "fifth",
                            6: "sixth",
                            7: "seventh",
                            8: "eighth",
                            9: "ninth",
                            10: "tenth",
                            11: "eleventh",
                            12: "twelfth",
                            13: "thirteenth",
                            14: "fourteenth",
                            15: "fifteenth",
                            16: "sixteenth",
                            17: "seventeenth",
                            18: "eighteenth",
                            19: "nineteenth",
                            20: "twentieth",
                            30: "thirtieth",
                            40: "fortieth",
                            50: "fiftieth",
                            60: "sixtieth",
                            70: "seventieth",
                            80: "eightieth",
                            90: "ninetieth",
                            100: "hundredth",
                        }

                        if num in num_to_word:
                            return num_to_word[num]
                        break

                # Check for positional patterns - keep numeric
                for pattern in positional_patterns:
                    if re.search(pattern, context):
                        return original_text  # Keep numeric form

            # Default: keep numeric form if no clear context
            return original_text

        # Input is word form - convert to numeric (existing behavior)
        # First, try a direct lookup in a comprehensive map
        ordinal_map = {
            "first": "1st",
            "second": "2nd",
            "third": "3rd",
            "fourth": "4th",
            "fifth": "5th",
            "sixth": "6th",
            "seventh": "7th",
            "eighth": "8th",
            "ninth": "9th",
            "tenth": "10th",
            "eleventh": "11th",
            "twelfth": "12th",
            "thirteenth": "13th",
            "fourteenth": "14th",
            "fifteenth": "15th",
            "sixteenth": "16th",
            "seventeenth": "17th",
            "eighteenth": "18th",
            "nineteenth": "19th",
            "twentieth": "20th",
            "thirtieth": "30th",
            "fortieth": "40th",
            "fiftieth": "50th",
            "sixtieth": "60th",
            "seventieth": "70th",
            "eightieth": "80th",
            "ninetieth": "90th",
            "hundredth": "100th",
        }
        if text_lower in ordinal_map:
            return ordinal_map[text_lower]

        # If not found, parse the number and apply the suffix rule
        parsed_num_str = self.number_parser.parse_ordinal(text_lower)
        if parsed_num_str:
            num = int(parsed_num_str)
            if 11 <= num % 100 <= 13:
                suffix = "th"
            else:
                suffix = {1: "st", 2: "nd", 3: "rd"}.get(num % 10, "th")
            return f"{parsed_num_str}{suffix}"

        return entity.text

    def convert_fraction(self, entity: Entity) -> str:
        """Convert fraction expressions (one half -> ½) and decimal numbers (three point one four -> 3.14)."""
        if not entity.metadata:
            return entity.text

        # Handle decimal numbers (e.g., "three point one four" -> "3.14")
        if entity.metadata.get("is_decimal"):
            return self.number_parser.parse(entity.text) or entity.text

        numerator_word = entity.metadata.get("numerator_word", "").lower()
        denominator_word = entity.metadata.get("denominator_word", "").lower()
        is_mixed = entity.metadata.get("is_mixed", False)
        whole_word = entity.metadata.get("whole_word", "").lower() if is_mixed else ""

        # Map number words to digits
        num_map = {
            "one": "1",
            "two": "2",
            "three": "3",
            "four": "4",
            "five": "5",
            "six": "6",
            "seven": "7",
            "eight": "8",
            "nine": "9",
            "ten": "10",
        }

        # Map denominator words to numbers
        denom_map = {
            "half": "2",
            "halves": "2",
            "third": "3",
            "thirds": "3",
            "quarter": "4",
            "quarters": "4",
            "fourth": "4",
            "fourths": "4",
            "fifth": "5",
            "fifths": "5",
            "sixth": "6",
            "sixths": "6",
            "seventh": "7",
            "sevenths": "7",
            "eighth": "8",
            "eighths": "8",
            "ninth": "9",
            "ninths": "9",
            "tenth": "10",
            "tenths": "10",
        }

        numerator = num_map.get(numerator_word)
        denominator = denom_map.get(denominator_word)
        whole = num_map.get(whole_word) if is_mixed else ""

        if numerator and denominator:
            # Create the x/y format first
            fraction_str = f"{numerator}/{denominator}"

            # Map common fractions to Unicode equivalents
            unicode_fractions = {
                "1/2": "½",
                "1/3": "⅓",
                "2/3": "⅔",
                "1/4": "¼",
                "3/4": "¾",
                "1/5": "⅕",
                "2/5": "⅖",
                "3/5": "⅗",
                "4/5": "⅘",
                "1/6": "⅙",
                "5/6": "⅚",
                "1/7": "⅐",
                "1/8": "⅛",
                "3/8": "⅜",
                "5/8": "⅝",
                "7/8": "⅞",
                "1/9": "⅑",
                "1/10": "⅒",
            }

            unicode_fraction = unicode_fractions.get(fraction_str, fraction_str)

            if is_mixed and whole:
                # For mixed fractions, concatenate whole number and fraction (e.g., "1½")
                return f"{whole}{unicode_fraction}"

            # Return Unicode character if available, otherwise return x/y format
            return unicode_fraction

        return entity.text

    def convert_numeric_range(self, entity: Entity) -> str:
        """Convert numeric range expressions (ten to twenty -> 10-20)."""
        if not entity.metadata:
            return entity.text

        start_word = entity.metadata.get("start_word", "")
        end_word = entity.metadata.get("end_word", "")
        unit = entity.metadata.get("unit")  # The detector now provides this

        start_num = self.number_parser.parse(start_word)
        end_num = self.number_parser.parse(end_word)

        if start_num and end_num:
            result = f"{start_num}-{end_num}"
            if unit:
                if "dollar" in unit:
                    return f"${result}"
                if "percent" in unit:
                    return f"{result}%"
                # Handle time units
                if unit in ["hour", "hours"]:
                    return f"{result}h"
                if unit in ["minute", "minutes"]:
                    return f"{result}min"
                if unit in ["second", "seconds"]:
                    return f"{result}s"
                # Handle weight units
                if unit in ["kilogram", "kilograms", "kg"]:
                    return f"{result} kg"
                if unit in ["gram", "grams", "g"]:
                    return f"{result} g"
                # Handle other units
                if unit:
                    return f"{result} {unit}"
            return result

        return entity.text

    def convert_version(self, entity: Entity) -> str:
        """Convert version numbers from spoken form to numeric form."""
        text = entity.text

        # Extract the prefix (version, python, etc.)
        prefix_match = re.match(r"^(\w+)\s+", text, re.IGNORECASE)
        if prefix_match:
            prefix = prefix_match.group(1)
            # Capitalize the prefix appropriately
            if prefix.lower() in [
                "v",
                "version",
                "python",
                "java",
                "node",
                "ruby",
                "php",
                "go",
                "rust",
                "dotnet",
                "gcc",
            ]:
                if prefix.lower() in ["v", "version"]:
                    prefix = prefix.lower()  # Keep lowercase for version and v
                elif prefix.lower() in ["php", "gcc"]:
                    prefix = prefix.upper()
                else:
                    prefix = prefix.capitalize()
        else:
            prefix = ""

        # Get the groups from metadata
        if entity.metadata and "groups" in entity.metadata:
            groups = entity.metadata["groups"]

            # Convert each component
            parts = []
            for i, group in enumerate(groups):
                if group:
                    # Handle multi-word decimals like "one four" -> "14"
                    if " " in group and i > 0:  # This is a decimal part
                        decimal_digits = []
                        for word in group.split():
                            digit = self.number_parser.parse(word)
                            if digit and len(digit) <= 2 and digit.isdigit():  # Single or double digit
                                decimal_digits.append(digit)
                        if decimal_digits:
                            parts.append("".join(decimal_digits))
                        else:
                            # Fallback to regular parsing
                            parsed = self.number_parser.parse(group)
                            if parsed:
                                parts.append(parsed)
                    else:
                        # Try to parse the number normally
                        parsed = self.number_parser.parse(group)
                        if parsed:
                            parts.append(parsed)
                        elif group.isdigit():
                            parts.append(group)

            # Join with dots
            if parts:
                version_str = ".".join(parts)
                if prefix:
                    # No space for "v" prefix, space for others
                    separator = "" if prefix.lower() == "v" else " "
                    return f"{prefix}{separator}{version_str}"
                return version_str

        # Fallback
        return entity.text

    def convert_phone_long(self, entity: Entity) -> str:
        """Convert long form phone numbers"""
        # Extract digit words
        digit_words = {
            "zero": "0",
            "one": "1",
            "two": "2",
            "three": "3",
            "four": "4",
            "five": "5",
            "six": "6",
            "seven": "7",
            "eight": "8",
            "nine": "9",
        }

        words = entity.text.lower().split()
        digits = []
        for word in words:
            if word in digit_words:
                digits.append(digit_words[word])

        if len(digits) == 10:
            return f"({digits[0]}{digits[1]}{digits[2]}) {digits[3]}{digits[4]}{digits[5]}-{digits[6]}{digits[7]}{digits[8]}{digits[9]}"

        return entity.text
