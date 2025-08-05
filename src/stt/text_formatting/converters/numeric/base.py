"""Base class and shared utilities for numeric converters."""

import re
from typing import Dict, Any, Optional
from abc import ABC, abstractmethod

from stt.core.config import setup_logging
from stt.text_formatting.common import Entity, EntityType

logger = setup_logging(__name__, log_filename="text_formatting.txt", include_console=False)


class BaseNumericConverter(ABC):
    """Base class for numeric converters with shared utilities and mappings."""
    
    def __init__(self, number_parser, language: str = "en"):
        """Initialize base numeric converter."""
        self.number_parser = number_parser
        self.language = language
        self.resources = {}  # Will be populated by subclasses
        
        # Initialize all mapping dictionaries
        self._init_mappings()
    
    def _init_mappings(self):
        """Initialize all hardcoded mapping dictionaries."""
        
        # Currency mappings - post-position currencies (go after the amount)
        self.post_position_currencies = {
            "won",
            "cent", 
            "cents"
        }
        
        # Data size unit abbreviations
        self.data_size_unit_map = {
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
        }
        
        # Frequency unit abbreviations
        self.frequency_unit_map = {
            "hertz": "Hz",
            "hz": "Hz",
            "kilohertz": "kHz",
            "khz": "kHz",
            "megahertz": "MHz",
            "mhz": "MHz",
            "gigahertz": "GHz",
            "ghz": "GHz",
        }
        
        # Time duration unit mappings
        self.time_duration_unit_map = {
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
        
        # Time word mappings
        self.time_word_mappings = {
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
        
        # Digit word mappings
        self.digit_word_mappings = {
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
        
        # Number word mappings (extended)
        self.number_word_mappings = {
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
        }
        
        # Denominator mappings for fractions
        self.denominator_mappings = {
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
        
        # Ordinal mappings (word to numeric)
        self.ordinal_word_to_numeric = {
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
        
        # Ordinal mappings (numeric to word) - reverse mapping
        self.ordinal_numeric_to_word = {
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
        
        # Unicode fraction mappings
        self.unicode_fraction_mappings = {
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
        
        # Math constant mappings
        self.math_constant_mappings = {
            "pi": "π",
            "infinity": "∞",
            "inf": "∞",
            "lambda": "λ",
            "theta": "θ",
            "alpha": "α",
            "beta": "β",
            "gamma": "γ",
            "delta": "δ",
        }
        
        # Superscript mappings for scientific notation
        self.superscript_mappings = {
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
            "-": "⁻",
        }
        
        # Operator mappings for math expressions
        self.operator_mappings = {
            "plus": "+",
            "minus": "-", 
            "times": "×",
            "divided by": "÷",
            "over": "/",
            "equals": "=",
            "plus plus": "++",
            "minus minus": "--",
            "equals equals": "==",
        }
        
        # Hour mappings for time relative expressions
        self.hour_mappings = {
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
    
    @abstractmethod
    def convert(self, entity: Entity, full_text: str = "") -> str:
        """Convert a numeric entity to its final form."""
        pass
    
    def get_converter_method(self, entity_type: EntityType) -> Optional[str]:
        """Get the converter method name for a given entity type."""
        # This will be implemented by subclasses that define supported_types
        return getattr(self, 'supported_types', {}).get(entity_type)
    
    def parse_trailing_punctuation(self, text: str) -> tuple[str, str]:
        """Extract trailing punctuation from text."""
        trailing_punct = ""
        if text and text[-1] in ".!?":
            trailing_punct = text[-1]
            text = text[:-1]
        return text, trailing_punct
    
    def format_with_currency_position(self, amount: str, symbol: str, unit: str, trailing_punct: str = "") -> str:
        """Format currency with proper symbol position."""
        if unit in self.post_position_currencies:
            return f"{amount}{symbol}{trailing_punct}"
        return f"{symbol}{amount}{trailing_punct}"
    
    def convert_number_words_in_text(self, text: str) -> str:
        """Convert number words to digits in a text string."""
        words = text.split()
        converted_words = []
        
        for word in words:
            # Try to parse as number
            num = self.number_parser.parse(word)
            if num:
                converted_words.append(num)
            # Convert operators
            elif word.lower() in self.operator_mappings:
                converted_words.append(self.operator_mappings[word.lower()])
            else:
                converted_words.append(word)
        
        return " ".join(converted_words)
    
    def get_ordinal_suffix(self, num: int) -> str:
        """Get the ordinal suffix for a number (st, nd, rd, th)."""
        if 11 <= num % 100 <= 13:
            return "th"
        return {1: "st", 2: "nd", 3: "rd"}.get(num % 10, "th")
    
    def convert_to_superscript(self, text: str) -> str:
        """Convert digits and minus sign to superscript characters."""
        result = ""
        for char in str(text):
            result += self.superscript_mappings.get(char, char)
        return result
    
    def is_conversational_context(self, entity: Entity, full_text: str) -> bool:
        """Check if the entity is in a conversational context."""
        if not full_text:
            return False
            
        context = full_text.lower()
        
        # Conversational patterns
        conversational_patterns = [
            r"\blet\'s\s+do\s+(?:this|that)\s+" + re.escape(entity.text.lower()),
            r"\bwe\s+(?:need|should)\s+(?:to\s+)?(?:handle|do)\s+(?:this|that)\s+" + re.escape(entity.text.lower()),
            r"\b(?:first|1st)\s+(?:thing|step|priority|order|task)",
            r"\bdo\s+(?:this|that)\s+" + re.escape(entity.text.lower()),
        ]
        
        for pattern in conversational_patterns:
            if re.search(pattern, context):
                return True
                
        return False
    
    def is_idiomatic_context(self, entity: Entity, full_text: str, ordinal_word: str) -> bool:
        """Check if the ordinal is in an idiomatic phrase context."""
        if not full_text:
            return False
            
        # Get idiomatic phrases from resources
        from ...constants import get_resources
        resources = get_resources(self.language)
        idiomatic_phrases = resources.get("technical", {}).get("idiomatic_phrases", {})
        
        if ordinal_word not in idiomatic_phrases:
            return False
            
        # Check if the word following the ordinal is in the idiomatic phrases list
        context = full_text.lower()
        entity_end = entity.end
        remaining_text = full_text[entity_end:].strip().lower()
        
        if remaining_text:
            words_after = remaining_text.split()
            if words_after and words_after[0] in idiomatic_phrases[ordinal_word]:
                return True
        
        # Also check for sentence-start patterns with comma
        if entity.start == 0 and remaining_text.startswith(','):
            return True
            
        return False
    
    def is_positional_context(self, entity: Entity, full_text: str) -> bool:
        """Check if the entity is in a positional/ranking context."""
        if not full_text:
            return False
            
        context = full_text.lower()
        
        # Positional/ranking patterns
        positional_patterns = [
            r"\bfinished\s+" + re.escape(entity.text.lower()) + r"\s+place",
            r"\bcame\s+in\s+" + re.escape(entity.text.lower()),
            r"\branked\s+" + re.escape(entity.text.lower()),
            r"\b" + re.escape(entity.text.lower()) + r"\s+place",
            r"\bin\s+the\s+" + re.escape(entity.text.lower()),
        ]
        
        for pattern in positional_patterns:
            if re.search(pattern, context):
                return True
                
        return False
    
    def is_natural_speech_context(self, entity: Entity, full_text: str) -> bool:
        """Check if a simple number should stay as words in natural speech."""
        if not full_text or entity.text.lower() not in ["one", "two", "three", "four", "five", "six", "seven", "eight", "nine"]:
            return False
            
        # Get surrounding context
        start_context = max(0, entity.start - 50)
        end_context = min(len(full_text), entity.end + 50)
        context = full_text[start_context:end_context].lower()
        
        # Natural speech patterns where numbers should stay as words
        natural_patterns = [
            r'\b(?:which|what)\s+(?:\w+\s+)*' + re.escape(entity.text.lower()) + r'\b',
            r'\b' + re.escape(entity.text.lower()) + r'\s+of\b',
            r'\b(?:how|which|what).*' + re.escape(entity.text.lower()) + r'.*(?:should|would|could|can)\b',
            r'\b(?:once|then|when).*' + re.escape(entity.text.lower()) + r'\b',
        ]
        
        for pattern in natural_patterns:
            if re.search(pattern, context):
                return True
                
        return False
    
    def is_hyphenated_compound(self, entity: Entity, full_text: str) -> bool:
        """Check if the entity is part of a hyphenated compound."""
        if not full_text:
            return False
            
        # Check character after entity end
        if entity.end < len(full_text) and full_text[entity.end] == "-":
            return True
            
        # Check character before entity start  
        if entity.start > 0 and full_text[entity.start - 1] == "-":
            return True
            
        return False