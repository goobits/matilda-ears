#!/usr/bin/env python3
"""Time and duration expression converters."""

import re

from ..common import Entity, EntityType


class TimeConverterMixin:
    """Mixin class providing time and duration conversion methods.

    This mixin expects the host class to provide:
    - self.number_parser: NumberParser instance
    - self.resources: dict
    """

    def convert_time_duration(self, entity: Entity) -> str:
        """Convert time duration entities."""
        if not entity.metadata:
            return entity.text

        # Unit abbreviation map for compact formatting
        unit_map = {
            "second": "s",
            "seconds": "s",
            "minute": "min",
            "minutes": "min",
            "hour": "h",
            "hours": "h",
            "day": "d",
            "days": "d",
            "week": "w",
            "weeks": "w",
            "month": "mo",
            "months": "mo",
            "year": "y",
            "years": "y",
        }

        # Check if the number part is an ordinal word - if so, this shouldn't be a TIME_DURATION
        if "number" in entity.metadata:
            number_text = entity.metadata["number"].lower()
            # Check if it's an ordinal word
            ordinal_words = self.resources.get("technical", {}).get("ordinal_words", [])
            if number_text in ordinal_words:
                # This is an ordinal + time unit (e.g., "fourth day"), not a duration
                # Return the original text unchanged
                return entity.text

        # Check if this is a compound duration
        if entity.metadata.get("is_compound"):
            # Handle compound durations like "5 hours 30 minutes"
            number1 = entity.metadata.get("number1", "")
            unit1 = entity.metadata.get("unit1", "").lower()
            number2 = entity.metadata.get("number2", "")
            unit2 = entity.metadata.get("unit2", "").lower()

            # Convert number words to digits
            num1_str = self.number_parser.parse(number1)
            if num1_str is None:
                num1_str = number1
            num2_str = self.number_parser.parse(number2)
            if num2_str is None:
                num2_str = number2

            # Get abbreviated units
            abbrev1 = unit_map.get(unit1, unit1)
            abbrev2 = unit_map.get(unit2, unit2)

            # Format as compact notation
            return f"{num1_str}{abbrev1} {num2_str}{abbrev2}"

        # Handle simple duration
        if "number" in entity.metadata and "unit" in entity.metadata:
            number_text = entity.metadata["number"]
            unit = entity.metadata["unit"].lower()

            # Try to parse the entire number text first
            number_str = self.number_parser.parse(number_text)

            # If that fails, try parsing individual words from the number text
            if number_str is None:
                # Split and try to find valid number words
                words = number_text.split()
                for i, word in enumerate(words):
                    # Try parsing from this word onwards
                    remaining_text = " ".join(words[i:])
                    parsed = self.number_parser.parse(remaining_text)
                    if parsed:
                        number_str = parsed
                        break

            # Final fallback
            if number_str is None:
                number_str = number_text

            # Get abbreviated unit
            abbrev = unit_map.get(unit, unit)

            # Use compact formatting for durations
            return f"{number_str}{abbrev}"  # No space for units like h, s, d

        return entity.text

    def convert_time_or_duration(self, entity: Entity) -> str:
        """Convert TIME entities detected by SpaCy.

        This handles both regular time expressions and compound durations.
        SpaCy detects phrases like "five hours thirty minutes" as TIME entities.
        """
        text = entity.text.lower()

        # Check if this is a compound duration pattern
        # Pattern: number + time_unit + number + time_unit
        # Numbers can be compound like "twenty four"
        compound_pattern = re.compile(
            r"\b((?:\w+\s+)*\w+)\s+(seconds?|minutes?|hours?|days?|weeks?|months?|years?)\s+"
            r"((?:\w+\s+)*\w+)\s+(seconds?|minutes?|hours?|days?|weeks?|months?|years?)\b",
            re.IGNORECASE,
        )

        match = compound_pattern.match(text)
        if match:
            # This is a compound duration
            number1 = match.group(1)
            unit1 = match.group(2)
            number2 = match.group(3)
            unit2 = match.group(4)

            # Convert number words to digits
            num1_str = self.number_parser.parse(number1)
            if num1_str:
                number1 = num1_str
            num2_str = self.number_parser.parse(number2)
            if num2_str:
                number2 = num2_str

            # Unit abbreviation map
            unit_map = {
                "second": "s",
                "seconds": "s",
                "minute": "min",
                "minutes": "min",
                "hour": "h",
                "hours": "h",
                "day": "d",
                "days": "d",
                "week": "w",
                "weeks": "w",
                "month": "mo",
                "months": "mo",
                "year": "y",
                "years": "y",
            }

            # Get abbreviated units
            abbrev1 = unit_map.get(unit1.lower(), unit1)
            abbrev2 = unit_map.get(unit2.lower(), unit2)

            # Format as compact notation
            return f"{number1}{abbrev1} {number2}{abbrev2}"

        # Check for simple duration pattern
        simple_pattern = re.compile(
            r"\b(\w+)\s+(seconds?|minutes?|hours?|days?|weeks?|months?|years?)\b", re.IGNORECASE
        )

        match = simple_pattern.match(text)
        if match:
            number = match.group(1)
            unit = match.group(2)

            # Convert number words to digits
            num_str = self.number_parser.parse(number)
            if num_str:
                number = num_str

            # Unit abbreviation map
            unit_map = {
                "second": "s",
                "seconds": "s",
                "minute": "min",
                "minutes": "min",
                "hour": "h",
                "hours": "h",
                "day": "d",
                "days": "d",
                "week": "w",
                "weeks": "w",
                "month": "mo",
                "months": "mo",
                "year": "y",
                "years": "y",
            }

            # Get abbreviated unit
            abbrev = unit_map.get(unit.lower(), unit)

            # Use compact formatting
            return f"{number}{abbrev}"

        # Not a duration pattern, return as-is
        return entity.text

    def convert_time(self, entity: Entity) -> str:
        """Convert time expressions"""
        if entity.metadata and "groups" in entity.metadata:
            groups = entity.metadata["groups"]

            time_words = {
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
                "eleven": "11",
                "twelve": "12",
                "oh": "0",
                "fifteen": "15",
                "thirty": "30",
                "forty five": "45",
            }

            if entity.type == EntityType.TIME_CONTEXT:
                # Handle 'meet at three thirty'
                context = groups[0]  # 'meet at' or 'at'
                hour = time_words.get(groups[1].lower(), groups[1])
                minute_word = groups[3].lower() if groups[3] else "00"
                minute = time_words.get(minute_word, minute_word)
                if minute.isdigit():
                    minute = minute.zfill(2)
                ampm = groups[4].upper() if len(groups) > 4 and groups[4] else ""

                time_str = f"{hour}:{minute}"
                if ampm:
                    time_str += f" {ampm}"
                return f"{context} {time_str}"

            if entity.type == EntityType.TIME_AMPM:
                # Handle different TIME_AMPM patterns based on group structure
                if len(groups) == 3:
                    if groups[0].lower() == "at":
                        # Pattern: "at three PM" -> groups: ["at", "three", "PM"]
                        hour = time_words.get(groups[1].lower(), groups[1])
                        ampm = groups[2].upper()
                        # Preserve the original case of "at" (might be "At" at sentence start)
                        at_word = groups[0]
                        return f"{at_word} {hour} {ampm}"
                    if groups[2] in ["AM", "PM"]:
                        # Pattern: "three thirty PM" -> groups: ["three", "thirty", "PM"]
                        hour = time_words.get(groups[0].lower(), groups[0])
                        minute_word = groups[1].lower()
                        minute = time_words.get(minute_word, minute_word)
                        if minute.isdigit():
                            minute = minute.zfill(2)
                        ampm = groups[2].upper()
                        return f"{hour}:{minute} {ampm}"
                elif len(groups) == 2:
                    if groups[1] in ["AM", "PM"]:
                        # Pattern: "three PM" -> groups: ["three", "PM"]
                        hour = time_words.get(groups[0].lower(), groups[0])
                        ampm = groups[1].upper()
                        return f"{hour} {ampm}"
                    if groups[1].lower() in ["a", "p"]:
                        # Pattern: "ten a m" -> groups: ["ten", "a"]
                        hour = time_words.get(groups[0].lower(), groups[0])
                        ampm = "AM" if groups[1].lower() == "a" else "PM"
                        return f"{hour} {ampm}"

        return entity.text

    def convert_time_relative(self, entity: Entity) -> str:
        """Convert relative time expressions (quarter past three -> 3:15)."""
        if not entity.metadata:
            return entity.text

        relative_expr = entity.metadata.get("relative_expr", "").lower()
        hour_word = entity.metadata.get("hour_word", "").lower()

        # Convert hour word to number
        hour_map = {
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
        }

        hour = hour_map.get(hour_word)
        if hour is None:
            # Try to parse as a number
            try:
                hour = int(hour_word)
            except (ValueError, TypeError):
                return entity.text

        # Convert relative expression to time
        if relative_expr == "quarter past":
            return f"{hour}:15"
        if relative_expr == "half past":
            return f"{hour}:30"
        if relative_expr == "quarter to":
            # Quarter to the next hour = current hour minus 15 minutes
            prev_hour = hour - 1 if hour > 1 else 12
            return f"{prev_hour}:45"
        if relative_expr == "five past":
            return f"{hour}:05"
        if relative_expr == "ten past":
            return f"{hour}:10"
        if relative_expr == "twenty past":
            return f"{hour}:20"
        if relative_expr == "twenty-five past":
            return f"{hour}:25"
        if relative_expr == "five to":
            # Five to the next hour = current hour minus 5 minutes
            prev_hour = hour - 1 if hour > 1 else 12
            return f"{prev_hour}:55"
        if relative_expr == "ten to":
            # Ten to the next hour = current hour minus 10 minutes
            prev_hour = hour - 1 if hour > 1 else 12
            return f"{prev_hour}:50"
        if relative_expr == "twenty to":
            # Twenty to the next hour = current hour minus 20 minutes
            prev_hour = hour - 1 if hour > 1 else 12
            return f"{prev_hour}:40"
        if relative_expr == "twenty-five to":
            # Twenty-five to the next hour = current hour minus 25 minutes
            prev_hour = hour - 1 if hour > 1 else 12
            return f"{prev_hour}:35"

        return entity.text
