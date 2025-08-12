"""
Centralized mapping registry for all text formatting conversions.

This module consolidates all mapping dictionaries that were previously scattered
across various converter classes, reducing duplication and improving maintainability.
"""

from typing import Dict, Set, Optional, Any
from functools import lru_cache
import json
import os


class MappingRegistry:
    """
    Central registry for all text formatting mappings.
    
    This class consolidates ~400 lines of duplicated mapping dictionaries
    that were scattered across various converter classes.
    """
    
    def __init__(self, language: str = "en"):
        """Initialize the mapping registry for a specific language."""
        self.language = language
        self._mappings: Dict[str, Any] = {}
        self._load_all_mappings()
        
    def _load_all_mappings(self) -> None:
        """Load all mapping dictionaries."""
        # Initialize unit mappings
        self._init_unit_mappings()
        # Initialize number word mappings  
        self._init_number_mappings()
        # Initialize ordinal mappings
        self._init_ordinal_mappings()
        # Initialize mathematical mappings
        self._init_mathematical_mappings()
        # Initialize currency mappings
        self._init_currency_mappings()
        # Initialize miscellaneous mappings
        self._init_misc_mappings()
        
    def _init_unit_mappings(self) -> None:
        """Initialize all unit-related mappings."""
        # Data size units
        self._mappings["data_size_unit_map"] = {
            "byte": "B",
            "bytes": "B",
            "kilobyte": "KB",
            "kilobytes": "KB",
            "kb": "KB",
            "megabyte": "MB",
            "megabytes": "MB",
            "mb": "MB",
            "gigabyte": "GB",
            "gigabytes": "GB",
            "gb": "GB",
            "terabyte": "TB",
            "terabytes": "TB",
            "tb": "TB",
            "petabyte": "PB",
            "petabytes": "PB",
            "bit": "bit",
            "bits": "bit",
            "kilobit": "Kbit",
            "kilobits": "Kbit",
            "megabit": "Mbit",
            "megabits": "Mbit",
            "gigabit": "Gbit",
            "gigabits": "Gbit",
        }
        
        # Frequency units
        self._mappings["frequency_unit_map"] = {
            "hertz": "Hz",
            "hz": "Hz",
            "kilohertz": "kHz",
            "khz": "kHz",
            "megahertz": "MHz",
            "mhz": "MHz",
            "gigahertz": "GHz",
            "ghz": "GHz",
            "terahertz": "THz",
            "rpm": "RPM",
            "rpms": "RPM",
            "bpm": "BPM",
            "bpms": "BPM",
        }
        
        # Time duration units
        self._mappings["time_duration_unit_map"] = {
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
            "millisecond": "ms",
            "milliseconds": "ms",
            "microsecond": "μs",
            "microseconds": "μs",
            "nanosecond": "ns",
            "nanoseconds": "ns",
        }
        
        # Measurement units (consolidated from duplicated dictionaries)
        self._mappings["measurement_unit_map"] = {
            # Length units
            "millimeter": "mm",
            "millimeters": "mm",
            "centimeter": "cm",
            "centimeters": "cm",
            "meter": "m",
            "meters": "m",
            "kilometer": "km",
            "kilometers": "km",
            "inch": "in",
            "inches": "in",
            "foot": "ft",
            "feet": "ft",
            "yard": "yd",
            "yards": "yd",
            "mile": "mi",
            "miles": "mi",
            # Weight units
            "milligram": "mg",
            "milligrams": "mg",
            "gram": "g",
            "grams": "g",
            "kilogram": "kg",
            "kilograms": "kg",
            "ton": "t",
            "tons": "t",
            "tonne": "t",
            "tonnes": "t",
            "pound": "lbs",
            "pounds": "lbs",
            "ounce": "oz",
            "ounces": "oz",
            # Volume units
            "milliliter": "mL",
            "milliliters": "mL",
            "liter": "L",
            "liters": "L",
            "gallon": "gal",
            "gallons": "gal",
            "quart": "qt",
            "quarts": "qt",
            "pint": "pt",
            "pints": "pt",
            "cup": "cup",
            "cups": "cup",
            "tablespoon": "tbsp",
            "tablespoons": "tbsp",
            "teaspoon": "tsp",
            "teaspoons": "tsp",
            "fluid ounce": "fl oz",
            "fluid ounces": "fl oz",
            # Temperature units
            "celsius": "°C",
            "fahrenheit": "°F",
            "kelvin": "K",
            # Speed units
            "mph": "mph",
            "kph": "km/h",
            "kmh": "km/h",
            # Area units
            "square meter": "m²",
            "square meters": "m²",
            "square foot": "ft²",
            "square feet": "ft²",
            "square kilometer": "km²",
            "square kilometers": "km²",
            "square mile": "mi²",
            "square miles": "mi²",
            "hectare": "ha",
            "hectares": "ha",
            "acre": "ac",
            "acres": "ac",
        }
        
    def _init_number_mappings(self) -> None:
        """Initialize all number-related word mappings from resources."""
        # Load number mappings from resources
        try:
            resource_path = os.path.join(
                os.path.dirname(__file__),
                "resources",
                f"{self.language}.json"
            )
            with open(resource_path, "r", encoding="utf-8") as f:
                resources = json.load(f)
                
                number_words = resources.get("number_words", {})
                
                # Load digit word mappings from resources
                self._mappings["digit_word_mappings"] = number_words.get("digit_words", {
                    "zero": "0", "one": "1", "two": "2", "three": "3", "four": "4",
                    "five": "5", "six": "6", "seven": "7", "eight": "8", "nine": "9"
                })
                
                # Build number word mappings from ones resource
                ones_data = number_words.get("ones", {})
                self._mappings["number_word_mappings"] = {k: str(v) for k, v in ones_data.items() if v <= 12}
                
                # Build time-specific word mappings
                self._mappings["time_word_mappings"] = {
                    "one": "1", "two": "2", "three": "3", "four": "4", "five": "5",
                    "six": "6", "seven": "7", "eight": "8", "nine": "9", "ten": "10",
                    "eleven": "11", "twelve": "12", "fifteen": "15", "twenty": "20",
                    "thirty": "30", "forty five": "45", "forty-five": "45", "oh": "0",
                    "o'clock": "o'clock", "oclock": "o'clock"
                }
                
        except (FileNotFoundError, json.JSONDecodeError):
            # Fallback to hardcoded mappings for backward compatibility
            self._mappings["digit_word_mappings"] = {
                "zero": "0", "one": "1", "two": "2", "three": "3", "four": "4",
                "five": "5", "six": "6", "seven": "7", "eight": "8", "nine": "9"
            }
            
            self._mappings["number_word_mappings"] = {
                "one": "1", "two": "2", "three": "3", "four": "4", "five": "5",
                "six": "6", "seven": "7", "eight": "8", "nine": "9", "ten": "10",
                "eleven": "11", "twelve": "12"
            }
            
            self._mappings["time_word_mappings"] = {
                "one": "1", "two": "2", "three": "3", "four": "4", "five": "5",
                "six": "6", "seven": "7", "eight": "8", "nine": "9", "ten": "10",
                "eleven": "11", "twelve": "12", "fifteen": "15", "twenty": "20",
                "thirty": "30", "forty five": "45", "forty-five": "45", "oh": "0",
                "o'clock": "o'clock", "oclock": "o'clock"
            }
        
        # Denominator mappings for fractions
        self._mappings["denominator_mappings"] = {
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
            "hundredth": "100",
            "hundredths": "100",
            "thousandth": "1000",
            "thousandths": "1000",
        }
        
        # Hour mappings
        self._mappings["hour_mappings"] = {
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
        
    def _init_ordinal_mappings(self) -> None:
        """Initialize ordinal number mappings from resources."""
        # Load ordinal mappings from resources
        try:
            resource_path = os.path.join(
                os.path.dirname(__file__),
                "resources",
                f"{self.language}.json"
            )
            with open(resource_path, "r", encoding="utf-8") as f:
                resources = json.load(f)
                
                # Get ordinal words and suffixes from resources
                technical = resources.get("technical", {})
                ordinal_words = technical.get("ordinal_words", [])
                ordinal_suffixes = technical.get("ordinal_suffixes", {})
                
                # Build ordinal word to numeric mapping
                self._mappings["ordinal_word_to_numeric"] = {}
                
                # Map ordinal words to their numeric forms using suffixes from resources
                for i, word in enumerate(ordinal_words, 1):
                    if str(i) in ordinal_suffixes:
                        self._mappings["ordinal_word_to_numeric"][word] = ordinal_suffixes[str(i)]
                    else:
                        # Fallback to computed suffix
                        suffix = self._get_ordinal_suffix(i)
                        self._mappings["ordinal_word_to_numeric"][word] = f"{i}{suffix}"
                
                # Add common compound ordinals using resources
                compound_ordinals = {
                    "twenty first": "21", "twenty-first": "21",
                    "twenty second": "22", "twenty-second": "22", 
                    "twenty third": "23", "twenty-third": "23",
                    "thirty first": "31", "thirty-first": "31"
                }
                
                for word, num in compound_ordinals.items():
                    if num in ordinal_suffixes:
                        self._mappings["ordinal_word_to_numeric"][word] = ordinal_suffixes[num]
                    else:
                        suffix = self._get_ordinal_suffix(int(num))
                        self._mappings["ordinal_word_to_numeric"][word] = f"{num}{suffix}"
                        
        except (FileNotFoundError, json.JSONDecodeError):
            # Fallback to hardcoded ordinals for backward compatibility
            self._mappings["ordinal_word_to_numeric"] = {
                "first": "1st", "second": "2nd", "third": "3rd", "fourth": "4th",
                "fifth": "5th", "sixth": "6th", "seventh": "7th", "eighth": "8th",
                "ninth": "9th", "tenth": "10th", "eleventh": "11th", "twelfth": "12th",
                "thirteenth": "13th", "fourteenth": "14th", "fifteenth": "15th",
                "sixteenth": "16th", "seventeenth": "17th", "eighteenth": "18th",
                "nineteenth": "19th", "twentieth": "20th", "twenty first": "21st",
                "twenty-first": "21st", "twenty second": "22nd", "twenty-second": "22nd",
                "twenty third": "23rd", "twenty-third": "23rd", "thirtieth": "30th",
                "fortieth": "40th", "fiftieth": "50th", "sixtieth": "60th",
                "seventieth": "70th", "eightieth": "80th", "ninetieth": "90th",
                "hundredth": "100th",
            }
        
        # Numeric to word ordinals (reverse mapping)
        self._mappings["ordinal_numeric_to_word"] = {
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
            21: "twenty-first",
            22: "twenty-second",
            23: "twenty-third",
            30: "thirtieth",
            40: "fortieth",
            50: "fiftieth",
            60: "sixtieth",
            70: "seventieth",
            80: "eightieth",
            90: "ninetieth",
            100: "hundredth",
        }
        
    def _get_ordinal_suffix(self, num: int) -> str:
        """Get the ordinal suffix for a number (st, nd, rd, th)."""
        if 11 <= num % 100 <= 13:
            return "th"
        return {1: "st", 2: "nd", 3: "rd"}.get(num % 10, "th")
        
    def _init_mathematical_mappings(self) -> None:
        """Initialize mathematical symbol and operator mappings."""
        # Unicode fraction mappings
        self._mappings["unicode_fraction_mappings"] = {
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
            # Common percentages as fractions
            "1/100": "1%",
            "1/1000": "0.1%",
        }
        
        # Mathematical constant mappings
        self._mappings["math_constant_mappings"] = {
            "pi": "π",
            "Pi": "π",
            "PI": "π",
            "tau": "τ",
            "e": "e",
            "E": "e",
            "infinity": "∞",
            "Infinity": "∞",
            "INFINITY": "∞",
            "phi": "φ",
            "golden ratio": "φ",
        }
        
        # Superscript mappings
        self._mappings["superscript_mappings"] = {
            "0": "⁰",
            "1": "¹",
            "2": "²",
            "3": "³",
            "4": "⁴",
            "5": "⁵",
            "6": "⁶",
            "7": "⁷",
            "8": "⁸",
            "9": "⁹",
            "+": "⁺",
            "-": "⁻",
        }
        
        # Mathematical operator mappings
        self._mappings["operator_mappings"] = {
            "plus": "+",
            "minus": "-",
            "times": "×",
            "multiplied by": "×",
            "divided by": "÷",
            "over": "/",
            "equals": "=",
            "plus or minus": "±",
            "approximately": "≈",
            "not equal": "≠",
            "less than": "<",
            "greater than": ">",
        }
        
    def _init_currency_mappings(self) -> None:
        """Initialize currency-related mappings."""
        # Load currency mappings from resources
        try:
            resource_path = os.path.join(
                os.path.dirname(__file__),
                "resources",
                f"{self.language}.json"
            )
            with open(resource_path, "r", encoding="utf-8") as f:
                resources = json.load(f)
                self._mappings["currency_map"] = resources.get("units", {}).get("currency_map", {})
        except (FileNotFoundError, json.JSONDecodeError):
            # Fallback to default currency mappings
            self._mappings["currency_map"] = {
                "dollar": "$",
                "dollars": "$",
                "cent": "¢",
                "cents": "¢",
                "pound": "£",
                "pounds": "£",
                "euro": "€",
                "euros": "€",
                "yen": "¥",
                "yuan": "¥",
                "rupee": "₹",
                "rupees": "₹",
                "won": "₩",
                "peso": "₱",
                "pesos": "₱",
                "ruble": "₽",
                "rubles": "₽",
                "bitcoin": "₿",
                "bitcoins": "₿",
                "ethereum": "Ξ",
                "franc": "₣",
                "francs": "₣",
                "lira": "₺",
                "real": "R$",
                "reais": "R$",
                "rand": "R",
                "shilling": "Sh",
                "shillings": "Sh",
                "baht": "฿",
                "dirham": "د.إ",
                "dirhams": "د.إ",
            }
            
        # Post-position currencies (appear after the amount)
        self._mappings["post_position_currencies"] = {"won", "cent", "cents"}
        
    def _init_misc_mappings(self) -> None:
        """Initialize miscellaneous mappings."""
        # Musical accidentals
        self._mappings["accidental_map"] = {
            "sharp": "♯",
            "flat": "♭",
            "natural": "♮",
        }
        
    # Public getter methods with caching
    
    @lru_cache(maxsize=1)
    def get_data_size_unit_map(self) -> Dict[str, str]:
        """Get data size unit mappings."""
        return self._mappings.get("data_size_unit_map", {})
        
    @lru_cache(maxsize=1)
    def get_frequency_unit_map(self) -> Dict[str, str]:
        """Get frequency unit mappings."""
        return self._mappings.get("frequency_unit_map", {})
        
    @lru_cache(maxsize=1)
    def get_time_duration_unit_map(self) -> Dict[str, str]:
        """Get time duration unit mappings."""
        return self._mappings.get("time_duration_unit_map", {})
        
    @lru_cache(maxsize=1)
    def get_measurement_unit_map(self) -> Dict[str, str]:
        """Get measurement unit mappings (length, weight, volume, etc.)."""
        return self._mappings.get("measurement_unit_map", {})
        
    @lru_cache(maxsize=1)
    def get_time_word_mappings(self) -> Dict[str, str]:
        """Get time-specific word mappings."""
        return self._mappings.get("time_word_mappings", {})
        
    @lru_cache(maxsize=1)
    def get_digit_word_mappings(self) -> Dict[str, str]:
        """Get digit word mappings."""
        return self._mappings.get("digit_word_mappings", {})
        
    @lru_cache(maxsize=1)
    def get_number_word_mappings(self) -> Dict[str, str]:
        """Get number word mappings."""
        return self._mappings.get("number_word_mappings", {})
        
    @lru_cache(maxsize=1)
    def get_denominator_mappings(self) -> Dict[str, str]:
        """Get fraction denominator mappings."""
        return self._mappings.get("denominator_mappings", {})
        
    @lru_cache(maxsize=1)
    def get_hour_mappings(self) -> Dict[str, int]:
        """Get hour word to number mappings."""
        return self._mappings.get("hour_mappings", {})
        
    @lru_cache(maxsize=1)
    def get_ordinal_word_to_numeric(self) -> Dict[str, str]:
        """Get ordinal word to numeric mappings."""
        return self._mappings.get("ordinal_word_to_numeric", {})
        
    @lru_cache(maxsize=1)
    def get_ordinal_numeric_to_word(self) -> Dict[int, str]:
        """Get ordinal numeric to word mappings."""
        return self._mappings.get("ordinal_numeric_to_word", {})
        
    @lru_cache(maxsize=1)
    def get_unicode_fraction_mappings(self) -> Dict[str, str]:
        """Get Unicode fraction mappings."""
        return self._mappings.get("unicode_fraction_mappings", {})
        
    @lru_cache(maxsize=1)
    def get_math_constant_mappings(self) -> Dict[str, str]:
        """Get mathematical constant mappings."""
        return self._mappings.get("math_constant_mappings", {})
        
    @lru_cache(maxsize=1)
    def get_superscript_mappings(self) -> Dict[str, str]:
        """Get superscript mappings."""
        return self._mappings.get("superscript_mappings", {})
        
    @lru_cache(maxsize=1)
    def get_operator_mappings(self) -> Dict[str, str]:
        """Get mathematical operator mappings."""
        return self._mappings.get("operator_mappings", {})
        
    @lru_cache(maxsize=1)
    def get_currency_map(self) -> Dict[str, str]:
        """Get currency symbol mappings."""
        return self._mappings.get("currency_map", {})
        
    @lru_cache(maxsize=1)
    def get_post_position_currencies(self) -> Set[str]:
        """Get currencies that appear after the amount."""
        return self._mappings.get("post_position_currencies", set())
        
    @lru_cache(maxsize=1)
    def get_accidental_map(self) -> Dict[str, str]:
        """Get musical accidental mappings."""
        return self._mappings.get("accidental_map", {})
        
    # Utility methods
    
    def get_all_unit_maps(self) -> Dict[str, Dict[str, str]]:
        """Get all unit-related mappings in one call."""
        return {
            "data_size": self.get_data_size_unit_map(),
            "frequency": self.get_frequency_unit_map(),
            "time_duration": self.get_time_duration_unit_map(),
            "measurement": self.get_measurement_unit_map(),
        }
        
    def get_all_number_maps(self) -> Dict[str, Dict[str, Any]]:
        """Get all number-related mappings in one call."""
        return {
            "time_words": self.get_time_word_mappings(),
            "digit_words": self.get_digit_word_mappings(),
            "number_words": self.get_number_word_mappings(),
            "denominators": self.get_denominator_mappings(),
            "hours": self.get_hour_mappings(),
        }


# Singleton instance for easy import
_default_registry: Optional[MappingRegistry] = None


def get_mapping_registry(language: str = "en") -> MappingRegistry:
    """Get the singleton mapping registry instance."""
    global _default_registry
    if _default_registry is None or _default_registry.language != language:
        _default_registry = MappingRegistry(language)
    return _default_registry