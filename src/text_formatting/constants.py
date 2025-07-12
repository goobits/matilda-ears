#!/usr/bin/env python3
"""Shared constants for text formatting modules."""

import json
import os
import threading
from typing import Dict, Any

# ==============================================================================
# I18N RESOURCE LOADER
# ==============================================================================

_RESOURCES: Dict[str, Dict[str, Any]] = {}  # Cache for loaded languages
_RESOURCE_PATH = os.path.join(os.path.dirname(__file__), "resources")
_LOCK = threading.Lock()  # For thread-safe lazy loading


def get_resources(language: str = "en") -> Dict[str, Any]:
    """
    Loads and caches language-specific resources from a JSON file.
    This is the single point of entry for all language-dependent constants.
    
    Args:
        language: Language code (e.g., 'en', 'es', 'fr')
        
    Returns:
        dict: Loaded language resources
        
    Raises:
        ValueError: If default language resource not found
    """
    # Return from cache if already loaded
    if language in _RESOURCES:
        return _RESOURCES[language]

    # Thread-safe block to load a new language
    with _LOCK:
        # Double-check if another thread loaded it while we were waiting
        if language in _RESOURCES:
            return _RESOURCES[language]

        try:
            filepath = os.path.join(_RESOURCE_PATH, f"{language}.json")
            with open(filepath, "r", encoding="utf-8") as f:
                resources = json.load(f)
                _RESOURCES[language] = resources
            return resources
        except FileNotFoundError:
            # Fallback to English if the requested language is not found
            if language != "en":
                print(f"Warning: Language resource '{language}.json' not found. Falling back to 'en'.")
                return get_resources("en")
            raise ValueError("Default language resource 'en.json' not found.")
        except json.JSONDecodeError:
            raise ValueError(f"Error decoding JSON from {language}.json")


# Legacy function for backward compatibility during transition
def load_resources(language: str = "en"):
    """Deprecated: Use get_resources() instead."""
    return get_resources(language)

# ==============================================================================
# LEGACY CONSTANTS (will be replaced by resource loader gradually)
# ==============================================================================

# Currency context words - used to identify when "pounds" refers to money vs weight
CURRENCY_CONTEXTS = [
    "cost",
    "costs",
    "costing",
    "price",
    "priced",
    "pricing",
    "buy",
    "buying",
    "bought",
    "sell",
    "selling",
    "sold",
    "pay",
    "paying",
    "paid",
    "spend",
    "spending",
    "spent",
    "worth",
    "value",
    "valued",
    "charge",
    "charged",
    "charging",
    "bill",
    "billed",
    "invoice",
    "invoiced",
    "fee",
    "fees",
    "money",
    "cash",
    "currency",
    "dollar",
    "sterling",
    "euro",
    "eur",
    "gbp",
    "usd",
    "$",
    "£",
    "€",
    "bank",
    "banking",
]

# Weight context words - used to identify when "pounds" refers to weight vs money
WEIGHT_CONTEXTS = [
    "weigh",
    "weighs",
    "weight",
    "weighted",
    "weighing",
    "mass",
    "heavy",
    "light",
    "lift",
    "lifting",
    "carry",
    "carrying",
    "hold",
    "holding",
    "push",
    "pushing",
    "pull",
    "pulling",
    "measure",
    "measuring",
    "scale",
    "scales",
    "ounce",
    "ounces",
    "kg",
    "kilogram",
    "kilograms",
    "gram",
    "grams",
    "ton",
    "tons",
    "tonne",
    "tonnes",
    "add",
    "mix",
    "use",
    "need",
    "recipe",
    "cook",
    "bake",
    "ingredient",
    "flour",
    "sugar",
    "butter",
    "meat",
    "chicken",
    "beef",
    "pork",
    "food",
]

# Month names - used to identify real dates vs ordinal contexts
MONTH_NAMES = [
    "january",
    "february",
    "march",
    "april",
    "may",
    "june",
    "july",
    "august",
    "september",
    "october",
    "november",
    "december",
    "jan",
    "feb",
    "mar",
    "apr",
    "may",
    "jun",
    "jul",
    "aug",
    "sep",
    "oct",
    "nov",
    "dec",
]

# Relative day names - used to identify real dates
RELATIVE_DAYS = [
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
    "mon",
    "tue",
    "wed",
    "thu",
    "fri",
    "sat",
    "sun",
    "today",
    "tomorrow",
    "yesterday",
    "weekend",
    "weekday",
]

# Date keywords - used to identify real dates
DATE_KEYWORDS = ["day", "week", "month", "year", "date"]

# Ordinal words used in date context (includes compound ordinals)
DATE_ORDINAL_WORDS = [
    "first",
    "second",
    "third",
    "fourth",
    "fifth",
    "sixth",
    "seventh",
    "eighth",
    "ninth",
    "tenth",
    "eleventh",
    "twelfth",
    "thirteenth",
    "fourteenth",
    "fifteenth",
    "sixteenth",
    "seventeenth",
    "eighteenth",
    "nineteenth",
    "twentieth",
    "twenty first",
    "twenty second",
    "twenty third",
    "thirtieth",
    "thirty first",
]

# Email action words - used to identify email contexts
EMAIL_ACTION_WORDS = ["email", "contact", "write to", "send to", "notify", "reach"]

# Angle/rotation keywords - used to distinguish degrees as angles vs temperature
ANGLE_KEYWORDS = ["rotate", "turn", "angle", "tilt", "spin", "pivot"]

# Idiomatic words used with "plus" that indicate non-mathematical context
IDIOMATIC_PLUS_WORDS = ["years", "days", "weeks", "months", "people", "guests", "members", "items"]

# Comparative words used with "times" in non-mathematical context
COMPARATIVE_WORDS = ["better", "worse", "faster", "slower", "bigger", "smaller", "more", "less"]

# Measurement patterns for weight/mass detection
MEASUREMENT_PATTERNS_FORMATTER = ["is", "are", "was", "were", "measures", "weighs"]

# Action words for email entities
EMAIL_ENTITY_ACTION_WORDS = ["email", "send", "write", "mail", "contact", "notify", "reach"]

# Command words for colon removal context
COMMAND_WORDS = ["edit", "open", "run", "build", "play", "start", "stop", "create", "delete", "install"]

# Words to preserve colons after
PRESERVE_COLON_WORDS = ["contact", "email", "phone", "fax", "website", "address", "from", "to", "subject"]

# Tech company patterns for domain rescue
TECH_PATTERNS = ["google", "github", "stack", "reddit", "amazon", "face", "open", "micro", "apple"]

# Ordinal words that should not be treated as numbers in duration contexts
ORDINAL_WORDS = {
    "first",
    "second",
    "third",
    "fourth",
    "fifth",
    "sixth",
    "seventh",
    "eighth",
    "ninth",
    "tenth",
    "eleventh",
    "twelfth",
    "thirteenth",
    "fourteenth",
    "fifteenth",
    "sixteenth",
    "seventeenth",
    "eighteenth",
    "nineteenth",
    "twentieth",
    "thirtieth",
    "fortieth",
    "fiftieth",
    "sixtieth",
    "seventieth",
    "eightieth",
    "ninetieth",
    "hundredth",
    "thousandth",
}

# Measurement patterns that indicate weight rather than currency
MEASUREMENT_PATTERNS = ["is", "are", "was", "were", "measures", "weighs"]

# Currency units for detection
CURRENCY_UNITS = {
    "dollar",
    "dollars",
    "cent",
    "cents",
    "euro",
    "euros",
    "pound",
    "pounds",
    "yen",
    "rupee",
    "rupees",
    "yuan",
    "renminbi",
    "won",
    "peso",
    "pesos",
    "ruble",
    "rubles",
    "franc",
    "francs",
    "lira",
    "shekel",
    "shekels",
    "real",
    "reais",
}

# Data storage units
DATA_UNITS = {
    "byte",
    "bytes",
    "kilobyte",
    "kilobytes",
    "megabyte",
    "megabytes",
    "gigabyte",
    "gigabytes",
    "terabyte",
    "terabytes",
    "petabyte",
    "petabytes",
    "kb",
    "mb",
    "gb",
    "tb",
    "pb",
}

# Time units
TIME_UNITS = {
    "second",
    "seconds",
    "minute",
    "minutes",
    "hour",
    "hours",
    "day",
    "days",
    "week",
    "weeks",
    "month",
    "months",
    "year",
    "years",
    "millisecond",
    "milliseconds",
    "microsecond",
    "microseconds",
}

# Frequency units
FREQUENCY_UNITS = {"hertz", "kilohertz", "megahertz", "gigahertz", "hz", "khz", "mhz", "ghz"}

# Percentage units
PERCENT_UNITS = {"percent", "percentage"}

# Units that indicate NOT a time expression
NON_TIME_UNITS = {
    "gigahertz",
    "megahertz",
    "kilohertz",
    "hertz",
    "ghz",
    "mhz",
    "khz",
    "hz",
    "gigabytes",
    "megabytes",
    "kilobytes",
    "bytes",
    "gb",
    "mb",
    "kb",
    "milliseconds",
    "microseconds",
    "nanoseconds",
    "ms",
    "us",
    "ns",
    "meters",
    "kilometers",
    "miles",
    "feet",
    "inches",
    "volts",
    "watts",
    "amps",
    "ohms",
}

# Idiomatic patterns where "over" doesn't mean mathematical comparison
IDIOMATIC_OVER_PATTERNS = [
    # Phrases where "over" means "finished"
    "game over",
    "over par",
    "it's over",
    "start over",
    "do over",
    "all over",
    # Phrases where "over" means "about/concerning"
    "fight over",
    "argue over",
    "debate over",
    "think over",
    # Phrases where "over" means "above/across"
    "over the",
    "over there",
    "over here",
    # Emotional states
    "over it",
    "over him",
    "over her",
    "over them",
    # Common verb phrases
    "get over",
    "be over",
    "i'm over",
    "i am over",
    "getting over",
]

# Angle keywords for temperature vs angle disambiguation
ANGLE_KEYWORDS_NUMERIC = ["rotate", "turn", "angle", "tilt", "spin", "pivot"]

# Action verbs that indicate the end of a filename
FILENAME_ACTION_VERBS = {
    "open",
    "edit",
    "create",
    "run",
    "save",
    "load",
    "check",
    "view",
    "update",
    "visit",
    "import",
    "export",
    "define",
    "call",
}

# Linking verbs that separate the subject from the filename
FILENAME_LINKING_VERBS = {"be", "is", "are", "was", "were"}

# Metric length units
LENGTH_UNITS = {
    "millimeter",
    "millimeters",
    "millimetre",
    "millimetres",
    "mm",
    "centimeter",
    "centimeters",
    "centimetre",
    "centimetres",
    "cm",
    "meter",
    "meters",
    "metre",
    "metres",
    "m",
    "kilometer",
    "kilometers",
    "kilometre",
    "kilometres",
    "km",
}

# Metric weight units
WEIGHT_UNITS = {
    "milligram",
    "milligrams",
    "mg",
    "gram",
    "grams",
    "g",
    "kilogram",
    "kilograms",
    "kg",
    "metric ton",
    "metric tons",
    "tonne",
    "tonnes",
}

# Metric volume units
VOLUME_UNITS = {
    "milliliter",
    "milliliters",
    "millilitre",
    "millilitres",
    "ml",
    "liter",
    "liters",
    "litre",
    "litres",
    "l",
}

# Currency symbols mapping
CURRENCY_MAP = {
    "dollar": "$",
    "dollars": "$",
    "cent": "¢",
    "cents": "¢",
    "pound": "£",
    "pounds": "£",
    "euro": "€",
    "euros": "€",
    "yen": "¥",
    "rupee": "₹",
    "rupees": "₹",
    "yuan": "¥",
    "renminbi": "¥",
    "won": "₩",
    "peso": "₱",
    "pesos": "₱",
    "ruble": "₽",
    "rubles": "₽",
    "franc": "₣",
    "francs": "₣",
    "lira": "₺",
    "shekel": "₪",
    "shekels": "₪",
    "real": "R$",
    "reais": "R$",
}

# Known measurement and data units
KNOWN_UNITS = {
    "megabytes",
    "megabyte",
    "mb",
    "gigabytes",
    "gigabyte",
    "gb",
    "kilobytes",
    "kilobyte",
    "kb",
    "terabytes",
    "terabyte",
    "tb",
    "dollars",
    "dollar",
    "cents",
    "cent",
    "pounds",
    "pound",
    "percent",
    "percentage",
    "hertz",
    "hz",
    "khz",
    "mhz",
    "ghz",
    "degrees",
    "celsius",
    "fahrenheit",
    "millimeters",
    "millimeter",
    "centimeters",
    "centimeter",
    "meters",
    "meter",
    "kilometers",
    "kilometer",
    "grams",
    "gram",
    "kilograms",
    "kilogram",
    "liters",
    "liter",
    "milliliters",
    "milliliter",
}

# Idiomatic phrases dictionary for ordinal disambiguation
IDIOMATIC_PHRASES = {
    "first": ["class", "rate", "person", "aid", "hand", "base", "string", "impression"],
    "second": ["nature", "hand", "string", "thoughts", "class", "rate", "person"],
    "third": ["party", "person", "string", "wheel", "base", "class", "rate"],
    "fourth": ["wall", "estate", "dimension"],
    "fifth": ["wheel", "column", "amendment"],
    "sixth": ["sense"],
    "seventh": ["heaven"],
    "eighth": ["wonder"],
    "ninth": ["inning"],
    "tenth": ["amendment"],
}

# Technical terms for capitalization protection
TECHNICAL_TERMS = {
    # Git commands and concepts
    "git",
    "commit",
    "push",
    "pull",
    "merge",
    "branch",
    "checkout",
    "clone",
    "fetch",
    "rebase",
    "stash",
    "reset",
    "log",
    "diff",
    "status",
    "init",
    "add",
    "rm",
    # Package managers and CLI tools
    "npm",
    "yarn",
    "pip",
    "cargo",
    "composer",
    "gem",
    "brew",
    "apt",
    "yum",
    "conda",
    "docker",
    "kubectl",
    "helm",
    "terraform",
    "ansible",
    "vagrant",
    "make",
    "cmake",
    # Programming terms
    "max",
    "min",
    "sum",
    "count",
    "avg",
    "len",
    "size",
    "width",
    "height",
    "start",
    "end",
    "begin",
    "stop",
    "pause",
    "run",
    "execute",
    "build",
    "test",
    "debug",
    "compile",
    "deploy",
    "install",
    "update",
    "delete",
    "create",
    "save",
    "load",
    "read",
    "write",
    "copy",
    "move",
    "sort",
    "filter",
    # Common variable/function names
    "user",
    "admin",
    "guest",
    "root",
    "config",
    "settings",
    "options",
    "params",
    "data",
    "info",
    "result",
    "output",
    "input",
    "temp",
    "cache",
    "buffer",
    # File operations
    "file",
    "folder",
    "directory",
    "path",
    "backup",
    "restore",
    "sync",
}

# Multi-word technical terms
MULTI_WORD_TECHNICAL_TERMS = {
    "git commit",
    "git push",
    "git pull",
    "git merge",
    "git branch",
    "git checkout",
    "git clone",
    "git fetch",
    "git rebase",
    "git stash",
    "git reset",
    "git log",
    "git diff",
    "git status",
    "git init",
    "git add",
}

# Technical context words
TECHNICAL_CONTEXT_WORDS = {
    "set",
    "get",
    "use",
    "run",
    "execute",
    "call",
    "invoke",
    "trigger",
    "function",
    "method",
    "variable",
    "parameter",
    "argument",
    "value",
    "command",
    "script",
    "program",
    "application",
    "service",
    "process",
    "dash",
    "flag",
    "option",
    "underscore",
    "dot",
    "slash",
    "colon",
}

# Complete sentence phrases that should not be modified
COMPLETE_SENTENCE_PHRASES = {
    "yes",
    "no",
    "okay",
    "thanks",
    "hello",
    "goodbye",
    "hi",
    "bye",
    "thank you",
    "sure",
    "please",
    "sorry",
}

# Transcription artifacts to filter out
TRANSCRIPTION_ARTIFACTS = [
    "thanks for watching",
    "thank you for watching",
    "please subscribe",
    "like and subscribe",
    "don't forget to subscribe",
    "see you next time",
    "in the next video",
    "we'll be right back",
]

# Profanity words to filter
PROFANITY_WORDS = [
    "fuck",
    "shit",
    "damn",
    "bitch",
    "ass",
    "bastard",
    "cunt",
    "dick",
    "piss",
    "cock",
    "hell",
]

# Abbreviations mapping (from resources)
ABBREVIATIONS = get_resources("en")["abbreviations"]

# Top-level domains (from resources)
TLDS = get_resources("en")["top_level_domains"]

# Words to exclude from TLD detection
EXCLUDE_WORDS = {
    "become",
    "income",
    "welcome",
    "outcome",
    "overcome",  # -come
    "inform",
    "perform",
    "transform",
    "platform",
    "uniform",  # -form
    "internet",
    "cabinet",
    "planet",
    "magnet",
    "helmet",  # -net
    "video",
    "radio",
    "studio",
    "ratio",
    "audio",  # -io
    "to",
    "do",
    "go",
    "so",
    "no",  # -o
}

# Web-related location and ambiguous nouns
LOCATION_NOUNS = {"docs", "documentation", "api", "site", "website", "page", "server"}
AMBIGUOUS_NOUNS = {"help", "support"}

# ==============================================================================
# RESOURCE-LOADED DICTIONARIES (using i18n system)
# ==============================================================================

# Load default English resources for backward compatibility
_DEFAULT_RESOURCES = get_resources("en")

# URL keywords mapping (spoken words → symbols for URL construction)
URL_KEYWORDS = _DEFAULT_RESOURCES["spoken_keywords"]["url"]

# Code-related keywords mapping (symbols and operators used in programming)
CODE_KEYWORDS = _DEFAULT_RESOURCES["spoken_keywords"]["code"]

# Operator keywords mapping (compound operators and mathematical symbols)
OPERATOR_KEYWORDS = _DEFAULT_RESOURCES["spoken_keywords"]["operators"]

# Action prefixes for email formatting
ACTION_PREFIXES = {"email ": "Email ", "contact ": "Contact ", "write to ": "Write to ", "send to ": "Send to "}

# Digit words to numbers mapping
DIGIT_WORDS = {
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

# Technical verbs that should not be capitalized
TECHNICAL_VERBS = {
    "commit",
    "run",
    "build",
    "deploy",
    "test",
    "debug",
    "compile",
    "install",
    "update",
    "delete",
    "create",
    "save",
    "load",
    "read",
    "write",
    "copy",
    "move",
    "sort",
    "filter",
    "push",
    "pull",
    "merge",
    "branch",
    "checkout",
    "clone",
    "fetch",
    "rebase",
    "stash",
    "reset",
    "init",
    "add",
    "rm",
    "start",
    "stop",
    "pause",
    "execute",
    "backup",
    "restore",
    "sync",
}

# Common abbreviations that need special capitalization handling
COMMON_ABBREVIATIONS = ["i.e.", "e.g.", "etc.", "vs.", "cf."]
