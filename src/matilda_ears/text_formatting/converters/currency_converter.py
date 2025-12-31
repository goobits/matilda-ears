#!/usr/bin/env python3
"""Currency and financial expression converters."""

import re

from ..common import Entity


class CurrencyConverterMixin:
    """Mixin class providing currency and financial conversion methods.

    This mixin expects the host class to provide:
    - self.number_parser: NumberParser instance
    - self.resources: dict
    """

    def convert_currency(self, entity: Entity, full_text: str = "") -> str:
        """Convert currency like 'twenty five dollars' -> '$25' or 'five thousand pounds' -> '£5000'"""
        text = entity.text

        # Use currency mappings from constants

        # Currencies that go after the amount (post-position)
        post_position_currencies = {"won"}

        post_position_currencies.update({"cent", "cents"})

        # If it's already in currency format (e.g., "25.99" from SpaCy MONEY)
        # Check if there's already a dollar sign before the entity
        if re.match(r"^\d+\.?\d*$", text.strip()):
            # Check if dollar sign precedes this entity in the full text
            if full_text and entity.start > 0 and full_text[entity.start - 1] == "$":
                # Dollar sign already present, just return the number
                return text.strip()
            # No dollar sign, add it
            return f"${text.strip()}"

        # Handle spoken currency (e.g., "twenty five dollars", "five thousand pounds")
        # Check for trailing punctuation in the entity text
        trailing_punct = ""
        if text and text[-1] in ".!?":
            trailing_punct = text[-1]

        # Extract currency unit from metadata or text
        unit = None
        if entity.metadata and "unit" in entity.metadata:
            unit = entity.metadata["unit"].lower()
        else:
            # Try to extract unit from text
            text_lower = text.lower()
            if text_lower and text_lower[-1] in ".!?":
                text_lower = text_lower[:-1]

            # Find which currency word is in the text
            currency_map = self.resources.get("units", {}).get("currency_map", {})
            for currency_word in currency_map:
                if currency_word in text_lower:
                    unit = currency_word
                    break

        # Get the currency symbol
        currency_map = self.resources.get("units", {}).get("currency_map", {})
        symbol = currency_map.get(unit, "$")  # Default to $ if not found

        # Extract and parse the number
        number_text = None
        if entity.metadata and "number" in entity.metadata:
            number_text = entity.metadata["number"]
        else:
            # Remove currency word and parse
            text_lower = text.lower()
            if text_lower and text_lower[-1] in ".!?":
                text_lower = text_lower[:-1]

            if unit:
                # Use regex to remove the currency word at word boundaries
                # Create pattern that matches the currency word at word boundaries
                pattern = r"\b" + re.escape(unit) + r"s?\b"  # Handle plural forms
                number_text = re.sub(pattern, "", text_lower).strip()
            else:
                # Try removing any known currency words
                currency_map = self.resources.get("units", {}).get("currency_map", {})
                for currency_word in currency_map:
                    if currency_word in text_lower:
                        # Use regex for proper word boundary matching
                        pattern = r"\b" + re.escape(currency_word) + r"s?\b"
                        number_text = re.sub(pattern, "", text_lower).strip()
                        unit = currency_word
                        break

        if number_text:
            amount = self.number_parser.parse(number_text)
            if amount:
                # Format based on currency position
                if unit in post_position_currencies:
                    return f"{amount}{symbol}{trailing_punct}"
                return f"{symbol}{amount}{trailing_punct}"

        return entity.text  # Fallback

    def convert_dollar_cents(self, entity: Entity) -> str:
        """Convert 'X dollars and Y cents' to '$X.Y'"""
        if entity.metadata:
            dollars = self.number_parser.parse(entity.metadata.get("dollars", "0"))
            cents = self.number_parser.parse(entity.metadata.get("cents", "0"))
            if dollars and cents:
                # Ensure cents is zero-padded to 2 digits
                cents_str = str(cents).zfill(2)
                return f"${dollars}.{cents_str}"
        return entity.text

    def convert_percent(self, entity: Entity) -> str:
        """Convert numerical percent entities"""
        # Handle new version number detection format
        if entity.metadata and "groups" in entity.metadata and entity.metadata.get("is_percentage"):
            groups = entity.metadata["groups"]
            # Convert the numeric parts
            parts = []
            for group in groups:
                if group:
                    parsed = self.number_parser.parse(group)
                    if parsed:
                        parts.append(parsed)
                    elif group and group.isdigit():
                        parts.append(group)

            if parts:
                # Join with dots for decimal percentages
                percent_str = ".".join(parts)
                return f"{percent_str}%"

        # Original handling for SpaCy-detected percentages
        if entity.metadata and "number" in entity.metadata:
            number_text = entity.metadata["number"]
            # Parse the number text to convert words to digits
            parsed_number = self.number_parser.parse(number_text)
            if parsed_number is not None:
                return f"{parsed_number}%"
            # Fallback to original if parsing fails
            return f"{number_text}%"

        # Fallback: parse from text if no metadata available
        text = entity.text.lower()
        # Try to extract number from text
        match = re.search(r"(.+?)\s+percent", text)
        if match:
            number_text = match.group(1).strip()
            # Use the number parser to convert words to numbers
            number = self.number_parser.parse(number_text)
            if number is not None:
                return f"{number}%"

        return entity.text
