#!/usr/bin/env python3
"""Numeric pattern converters for math, currency, measurements, and related entities.

This module provides the NumericConverterMixin class which combines all numeric
conversion functionality from specialized sub-modules:

- MathConverterMixin: Math expressions, scientific notation, roots, constants
- CurrencyConverterMixin: Currency, dollar/cents, percentages
- TimeConverterMixin: Time durations, time expressions, relative time
- MeasurementConverterMixin: Data sizes, frequencies, temperatures, metric units
- NumberConverterMixin: Cardinals, ordinals, fractions, ranges, versions, phones
- MiscConverterMixin: Music notation, spoken emoji

This facade pattern allows for better code organization while maintaining
backward compatibility with existing code that imports NumericConverterMixin.
"""

from .math_converter import MathConverterMixin
from .currency_converter import CurrencyConverterMixin
from .time_converter import TimeConverterMixin
from .measurement_converter import MeasurementConverterMixin
from .number_converter import NumberConverterMixin
from .misc_converter import MiscConverterMixin


class NumericConverterMixin(
    MathConverterMixin,
    CurrencyConverterMixin,
    TimeConverterMixin,
    MeasurementConverterMixin,
    NumberConverterMixin,
    MiscConverterMixin,
):
    """Combined mixin class providing all numeric entity conversion methods.

    This mixin expects the host class to provide:
    - self.number_parser: NumberParser instance
    - self.language: str
    - self.resources: dict
    - self.operators: dict

    Methods provided by each sub-mixin:

    MathConverterMixin:
        - convert_math_expression: Math expressions like "x squared plus y"
        - convert_root_expression: "square root of sixteen" → "√16"
        - convert_math_constant: "pi" → "π"
        - convert_scientific_notation: "two times ten to the sixth" → "2 × 10⁶"

    CurrencyConverterMixin:
        - convert_currency: "twenty five dollars" → "$25"
        - convert_dollar_cents: "five dollars and fifty cents" → "$5.50"
        - convert_percent: "fifty percent" → "50%"

    TimeConverterMixin:
        - convert_time_duration: "five hours" → "5h"
        - convert_time_or_duration: SpaCy TIME entities
        - convert_time: "three thirty PM" → "3:30 PM"
        - convert_time_relative: "quarter past three" → "3:15"

    MeasurementConverterMixin:
        - convert_data_size: "five megabytes" → "5MB"
        - convert_frequency: "two megahertz" → "2MHz"
        - convert_measurement: "six feet" → "6′"
        - convert_temperature: "twenty degrees celsius" → "20°C"
        - convert_metric_unit: "five kilometers" → "5 km"

    NumberConverterMixin:
        - convert_cardinal: "twenty five" → "25"
        - convert_ordinal: "first" → "1st"
        - convert_fraction: "one half" → "½"
        - convert_numeric_range: "ten to twenty" → "10-20"
        - convert_version: "Python three point eleven" → "Python 3.11"
        - convert_phone_long: Long-form phone numbers

    MiscConverterMixin:
        - convert_music_notation: "C sharp" → "C♯"
        - convert_spoken_emoji: "smiley face" → "🙂"
    """

    # All functionality inherited from mixins


# Re-export individual mixins for granular imports
__all__ = [
    "NumericConverterMixin",
    "MathConverterMixin",
    "CurrencyConverterMixin",
    "TimeConverterMixin",
    "MeasurementConverterMixin",
    "NumberConverterMixin",
    "MiscConverterMixin",
]
