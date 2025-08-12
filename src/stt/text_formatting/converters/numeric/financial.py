"""Financial converter for currency and monetary numeric entities."""

import re
from typing import Dict

from stt.text_formatting.common import Entity, EntityType
from stt.text_formatting.constants import get_resources
from .base import BaseNumericConverter


class FinancialConverter(BaseNumericConverter):
    """Converter for financial patterns like currency, dollar-cents, and cents."""
    
    def __init__(self, number_parser, language: str = "en"):
        """Initialize financial converter."""
        super().__init__(number_parser, language)
        self.resources = get_resources(language)
        
        # Define supported entity types and their converter methods
        self.supported_types: Dict[EntityType, str] = {
            EntityType.CURRENCY: "convert_currency",
            EntityType.MONEY: "convert_currency",  # SpaCy detected money entity
            EntityType.DOLLAR_CENTS: "convert_dollar_cents",
            EntityType.EURO_CENTS: "convert_euro_cents",
            EntityType.POUND_PENCE: "convert_pound_pence",
            EntityType.CENTS: "convert_cents",
        }
        
    def convert(self, entity: Entity, full_text: str = "") -> str:
        """Convert a financial entity to its final form."""
        converter_method = self.get_converter_method(entity.type)
        if converter_method and hasattr(self, converter_method):
            if converter_method == "convert_currency":
                # Currency conversion method needs full_text parameter
                return getattr(self, converter_method)(entity, full_text)
            else:
                return getattr(self, converter_method)(entity)
        return entity.text

    def convert_currency(self, entity: Entity, full_text: str = "") -> str:
        """Convert currency like 'twenty five dollars' -> '$25' or 'five thousand pounds' -> '£5000'"""
        text = entity.text

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
        text, trailing_punct = self.parse_trailing_punctuation(text)

        # Extract currency unit from metadata or text
        unit = None
        if entity.metadata and "unit" in entity.metadata:
            unit = entity.metadata["unit"].lower()
        else:
            # Try to extract unit from text
            text_lower = text.lower()

            # Find which currency word is in the text
            currency_map = self.mapping_registry.get_currency_map()
            for currency_word in currency_map:
                if currency_word in text_lower:
                    unit = currency_word
                    break

        # Get the currency symbol
        currency_map = self.mapping_registry.get_currency_map()
        symbol = currency_map.get(unit, "$")  # Default to $ if not found

        # Extract and parse the number
        number_text = None
        if entity.metadata and "number" in entity.metadata:
            number_text = entity.metadata["number"]
        else:
            # Remove currency word and parse
            text_lower = text.lower()

            if unit:
                # Use regex to remove the currency word at word boundaries
                # Create pattern that matches the currency word at word boundaries
                pattern = r"\b" + re.escape(unit) + r"s?\b"  # Handle plural forms
                number_text = re.sub(pattern, "", text_lower).strip()
            else:
                # Try removing any known currency words
                currency_map = self.mapping_registry.get_currency_map()
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
                return self.format_with_currency_position(amount, symbol, unit, trailing_punct)

        return entity.text  # Fallback

    def convert_dollar_cents(self, entity: Entity) -> str:
        """Convert 'X dollars and Y cents' to '$X.Y'"""
        if entity.metadata:
            # The metadata already contains parsed values as strings
            dollars = entity.metadata.get("dollars", "0")
            cents = entity.metadata.get("cents", "0")
            if dollars and cents:
                # Convert to integers for proper formatting
                try:
                    dollars_int = int(dollars) if isinstance(dollars, str) else dollars
                    cents_int = int(cents) if isinstance(cents, str) else cents
                    # Ensure cents is zero-padded to 2 digits
                    cents_str = str(cents_int).zfill(2)
                    return f"${dollars_int}.{cents_str}"
                except (ValueError, TypeError):
                    pass
        return entity.text

    def convert_cents(self, entity: Entity) -> str:
        """Convert 'X cents' to '¢X' or '$0.XX'"""
        if entity.metadata:
            # The metadata contains parsed value as string
            cents = entity.metadata.get("cents", "0")
            if cents:
                # Convert to integer for proper formatting
                try:
                    cents_int = int(cents) if isinstance(cents, str) else cents
                    # Format as cents symbol (preferred)
                    return f"{cents_int}¢"
                except (ValueError, TypeError):
                    pass
        return entity.text

    def convert_euro_cents(self, entity: Entity) -> str:
        """Convert 'X euros and Y cents' to '€X.Y'"""
        if entity.metadata:
            # The metadata already contains parsed values as strings
            euros = entity.metadata.get("euros", "0")
            cents = entity.metadata.get("cents", "0")
            if euros and cents:
                # Convert to integers for proper formatting
                try:
                    euros_int = int(euros) if isinstance(euros, str) else euros
                    cents_int = int(cents) if isinstance(cents, str) else cents
                    # Ensure cents is zero-padded to 2 digits
                    cents_str = str(cents_int).zfill(2)
                    return f"€{euros_int}.{cents_str}"
                except (ValueError, TypeError):
                    pass
        return entity.text

    def convert_pound_pence(self, entity: Entity) -> str:
        """Convert 'X pounds and Y pence' to '£X.Y'"""
        if entity.metadata:
            # The metadata already contains parsed values as strings
            pounds = entity.metadata.get("pounds", "0")
            pence = entity.metadata.get("pence", "0")
            if pounds and pence:
                # Convert to integers for proper formatting
                try:
                    pounds_int = int(pounds) if isinstance(pounds, str) else pounds
                    pence_int = int(pence) if isinstance(pence, str) else pence
                    # Ensure pence is zero-padded to 2 digits
                    pence_str = str(pence_int).zfill(2)
                    return f"£{pounds_int}.{pence_str}"
                except (ValueError, TypeError):
                    pass
        return entity.text