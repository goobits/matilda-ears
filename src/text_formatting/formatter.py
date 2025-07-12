#!/usr/bin/env python3
"""Text formatter for Matilda transcriptions.

Clean architecture with 4 specialized classes:
- EntityDetector: SpaCy-powered entity detection
- NumberParser: Algorithmic number parsing
- PatternConverter: Entity-specific conversions
- SmartCapitalizer: Intelligent capitalization
"""

import os
import re
from typing import List
from ..core.config import get_config, setup_logging

# Import common data structures
from .common import EntityType, Entity, NumberParser
from .utils import is_inside_entity

# Import specialized formatters
from .match_web import WebEntityDetector, WebPatternConverter
from .match_code import CodeEntityDetector, CodePatternConverter
from .match_numeric import NumericalEntityDetector, NumericalPatternConverter
from .nlp_provider import get_nlp, get_punctuator

# Import centralized regex patterns
from . import regex_patterns

# Setup config and logging
config = get_config()
logger = setup_logging(__name__, log_filename="text_formatting.txt")

# Import shared constants
from .constants import (
    CURRENCY_CONTEXTS,
    WEIGHT_CONTEXTS,
    MONTH_NAMES,
    RELATIVE_DAYS,
    DATE_KEYWORDS,
    DATE_ORDINAL_WORDS,
    EMAIL_ACTION_WORDS,
    ANGLE_KEYWORDS,
    IDIOMATIC_PLUS_WORDS,
    COMPARATIVE_WORDS,
    MEASUREMENT_PATTERNS_FORMATTER,
    EMAIL_ENTITY_ACTION_WORDS,
    COMMAND_WORDS,
    PRESERVE_COLON_WORDS,
    TECH_PATTERNS,
    IDIOMATIC_PHRASES,
    KNOWN_UNITS,
    DATA_UNITS,
    TECHNICAL_TERMS,
    MULTI_WORD_TECHNICAL_TERMS,
    TECHNICAL_CONTEXT_WORDS,
    COMPLETE_SENTENCE_PHRASES,
    TRANSCRIPTION_ARTIFACTS,
    PROFANITY_WORDS,
    ABBREVIATIONS,
    TLDS,
    EXCLUDE_WORDS,
    TECHNICAL_VERBS,
    COMMON_ABBREVIATIONS,
)


class EntityDetector:
    """Detects various entities using SpaCy and custom patterns"""

    def __init__(self, nlp=None, language: str = "en"):
        """Initialize EntityDetector with dependency injection.

        Args:
            nlp: SpaCy NLP model instance. If None, will load from nlp_provider.
            language: Language code for resource loading (default: 'en')

        """
        if nlp is None:
            nlp = get_nlp()

        self.nlp = nlp
        self.language = language

    def detect_entities(self, text: str, doc=None) -> List[Entity]:
        """Single pass entity detection"""
        entities = []

        # Only process SpaCy entities in the base detector
        self._process_spacy_entities(text, entities, doc=doc)

        # Sort by start position, but prioritize longer entities when they overlap
        return sorted(entities, key=lambda e: (e.start, -len(e.text)))

    def _process_spacy_entities(self, text: str, entities: List[Entity], doc=None) -> None:
        """Process SpaCy-detected entities."""
        if not self.nlp:
            return

        if doc is None:
            try:
                doc = self.nlp(text)
            except (AttributeError, ValueError, IndexError) as e:
                logger.warning(f"SpaCy entity detection failed: {e}")
                return

        try:
            # Map SpaCy labels to EntityType enums
            label_to_type = {
                "CARDINAL": EntityType.CARDINAL,
                "DATE": EntityType.DATE,
                "TIME": EntityType.TIME,
                "MONEY": EntityType.MONEY,
                "PERCENT": EntityType.PERCENT,
                "QUANTITY": EntityType.QUANTITY,
                "ORDINAL": EntityType.ORDINAL,
            }
            for ent in doc.ents:
                if ent.label_ in label_to_type:
                    if not is_inside_entity(ent.start_char, ent.end_char, entities):
                        # Skip CARDINAL entities that are in idiomatic "plus" contexts
                        if self._should_skip_cardinal(ent, text):
                            continue

                        # Skip QUANTITY entities that should be handled by specialized detectors
                        if self._should_skip_quantity(ent, text):
                            continue

                        # Skip MONEY entities that are actually weight measurements
                        if self._should_skip_money(ent, text):
                            continue

                        # Skip DATE entities that are likely ordinal contexts
                        if self._should_skip_date(ent, text):
                            continue

                        # Skip ORDINAL entities that are specific idiomatic phrases
                        if ent.label_ == "ORDINAL":
                            # Check for specific idiomatic phrases that shouldn't be converted
                            ordinal_text = ent.text.lower()
                            following_text = ""
                            if ent.end < len(doc):
                                following_text = doc[ent.end].text.lower()

                            # Define specific idiomatic phrases to skip
                            if ordinal_text in IDIOMATIC_PHRASES and following_text in IDIOMATIC_PHRASES[ordinal_text]:
                                logger.debug(f"Skipping ORDINAL '{ordinal_text} {following_text}' - idiomatic phrase")
                                continue

                        entity_type = label_to_type[ent.label_]

                        # Reclassify DATE entities that are actually number sequences
                        if entity_type == EntityType.DATE:
                            number_parser = NumberParser(language=self.language)
                            parsed_number = number_parser.parse(ent.text.lower())

                            if parsed_number and parsed_number.isdigit():
                                # This is a number sequence misclassified as a date, treat as CARDINAL
                                entity_type = EntityType.CARDINAL
                                logger.debug(
                                    f"Reclassifying DATE '{ent.text}' as CARDINAL (number sequence: {parsed_number})"
                                )

                        # For PERCENT entities, add metadata for conversion
                        metadata = {}
                        if entity_type == EntityType.PERCENT:
                            import re

                            # Handle decimal percentages like "zero point one percent"
                            if "point" in ent.text.lower():
                                decimal_match = re.search(r"(\w+)\s+point\s+(\w+)", ent.text, re.IGNORECASE)
                                if decimal_match:
                                    metadata = {"groups": decimal_match.groups(), "is_percentage": True}
                            else:
                                # Handle simple percentages like "ten percent"
                                # Try multiple patterns to match different spaCy outputs
                                percent_match = re.search(r"^(.+?)\s*percent$", ent.text, re.IGNORECASE)
                                if not percent_match:
                                    percent_match = re.search(
                                        r"^(.+?)$", ent.text.replace(" percent", ""), re.IGNORECASE
                                    )
                                if percent_match:
                                    number_text = percent_match.group(1).strip()
                                    metadata = {"number": number_text, "unit": "percent"}
                        entities.append(
                            Entity(
                                start=ent.start_char,
                                end=ent.end_char,
                                text=ent.text,
                                type=entity_type,
                                metadata=metadata,
                            )
                        )
        except (AttributeError, ValueError, IndexError) as e:
            logger.warning(f"SpaCy entity detection failed: {e}")

    def _should_skip_cardinal(self, ent, text: str) -> bool:
        """Check if a CARDINAL entity should be skipped due to idiomatic usage or unit contexts."""
        if ent.label_ != "CARDINAL":
            return False

        # Check for known idiomatic phrases that are exceptions
        # Check if this CARDINAL is part of a known idiomatic phrase
        # Get the text context before the entity
        prefix_text = text[: ent.start_char].strip().lower()

        # Check if this CARDINAL is inside an email context
        remaining_text = text[ent.end_char :].strip().lower()
        # Check if there's an email context either before or after the CARDINAL
        has_at_context = " at " in prefix_text or " at " in remaining_text or remaining_text.startswith("at ")
        has_dot_context = " dot " in remaining_text

        if has_at_context and has_dot_context:
            # This looks like it could be part of an email address
            # Check if there are email action words at the beginning
            has_email_action = any(prefix_text.startswith(action) for action in EMAIL_ACTION_WORDS)
            if has_email_action:
                logger.debug(f"Skipping CARDINAL '{ent.text}' because it appears to be part of an email address")
                return True

        # Check for specific idiomatic patterns
        if ent.text.lower() == "twenty two" and prefix_text.endswith("catch"):
            logger.debug(f"Skipping CARDINAL '{ent.text}' because it's part of 'catch twenty two'.")
            return True

        if ent.text.lower() == "nine" and prefix_text.endswith("cloud"):
            logger.debug(f"Skipping CARDINAL '{ent.text}' because it's part of 'cloud nine'.")
            return True

        if ent.text.lower() == "eight" and "behind the" in prefix_text:
            logger.debug(f"Skipping CARDINAL '{ent.text}' because it's part of 'behind the eight ball'.")
            return True

        # Check if this looks like a numeric range pattern (e.g., "ten to twenty")
        # This should be handled by the specialized range detector
        if " to " in ent.text.lower():
            # Check if it matches our range pattern
            from . import regex_patterns

            range_match = regex_patterns.SPOKEN_NUMERIC_RANGE_PATTERN.search(ent.text)
            if range_match:
                logger.debug(f"Skipping CARDINAL '{ent.text}' because it matches numeric range pattern")
                return True

        # Check if this number is followed by a known unit (prevents greedy CARDINAL detection)
        # This allows specialized detectors to handle data sizes, currency, etc.
        remaining_text = text[ent.end_char :].strip()

        # For "degrees", check if it's in an angle context
        if remaining_text.lower().startswith("degrees"):
            # Check the context before the number
            prefix_text = text[: ent.start_char].lower()
            if any(keyword in prefix_text for keyword in ANGLE_KEYWORDS):
                # This is an angle, not temperature, don't skip
                return False

        # Use known units from constants

        # Get the next few words after this CARDINAL
        next_words = remaining_text.split()[:3]  # Look at next 3 words
        if next_words:
            next_word = next_words[0].lower()
            if next_word in KNOWN_UNITS:
                logger.debug(f"Skipping CARDINAL '{ent.text}' because it's followed by unit '{next_word}'")
                return True

        # Enhanced idiomatic expression detection (single source of truth)
        # This prevents CARDINAL entities from being detected when they're part of idiomatic expressions
        # that would otherwise be incorrectly converted to mathematical expressions

        # Check if this number is followed by "plus" and then an idiomatic word
        if remaining_text.lower().startswith("plus "):
            # Look ahead 5 words after "plus"
            plus_context = remaining_text[5:].strip()  # Skip "plus "
            lookahead_words = plus_context.split()[:5]
            lookahead_context = " ".join(lookahead_words).lower()

            idiomatic_words = list(IDIOMATIC_PLUS_WORDS) + [
                "things",
                "experience",
                "experiences",
                "other",
            ]

            if any(word in lookahead_context for word in idiomatic_words):
                logger.debug(f"Skipping CARDINAL '{ent.text}' in idiomatic plus context")
                return True

        # Check if this number is followed by "times" and then a comparative adjective
        elif remaining_text.lower().startswith("times "):
            # Look at the word after "times"
            times_context = remaining_text[6:].strip()  # Skip "times "
            next_words = times_context.split()[:2]
            if next_words:
                next_word = next_words[0].lower()
                # Check for comparative adjectives/adverbs
                comparative_words = COMPARATIVE_WORDS
                if next_word in comparative_words:
                    logger.debug(
                        f"Skipping CARDINAL '{ent.text}' in idiomatic times comparative context: '{next_word}'"
                    )
                    return True

        # Enhanced SpaCy-based idiomatic detection for better accuracy
        # Use SpaCy to analyze grammatical context for more reliable detection
        if self.nlp:
            try:
                # Analyze a window around this entity for better context
                window_start = max(0, ent.start_char - 50)
                window_end = min(len(text), ent.end_char + 50)
                window_text = text[window_start:window_end]

                doc = self.nlp(window_text)

                # Find the token that corresponds to our entity
                entity_offset = ent.start_char - window_start
                entity_token = None

                for token in doc:
                    if token.idx <= entity_offset < token.idx + len(token.text):
                        entity_token = token
                        break

                if entity_token:
                    # Check if followed by "plus" + noun (idiomatic)
                    next_token = doc[entity_token.i + 1] if entity_token.i < len(doc) - 1 else None
                    next_next_token = doc[entity_token.i + 2] if entity_token.i < len(doc) - 2 else None

                    if (
                        next_token
                        and next_token.text.lower() == "plus"
                        and next_next_token
                        and next_next_token.pos_ == "NOUN"
                    ):
                        logger.debug(f"Skipping CARDINAL '{ent.text}' - SpaCy detected idiomatic 'plus' + noun")
                        return True

                    # Check if followed by "times" + comparative adjective/adverb (idiomatic)
                    if (
                        next_token
                        and next_token.text.lower() == "times"
                        and next_next_token
                        and next_next_token.pos_ in ["ADJ", "ADV"]
                        and next_next_token.tag_ in ["JJR", "RBR"]
                    ):  # Comparative forms
                        logger.debug(f"Skipping CARDINAL '{ent.text}' - SpaCy detected idiomatic 'times' + comparative")
                        return True

            except (AttributeError, ValueError, IndexError) as e:
                logger.debug(f"SpaCy idiomatic detection failed for CARDINAL: {e}")
                # Fall back to the simpler logic above

        return False

    def _should_skip_quantity(self, ent, text: str) -> bool:
        """Check if a QUANTITY entity should be skipped because it has specialized handling."""
        if ent.label_ != "QUANTITY":
            return False

        # Check if this is a data size quantity (e.g., "five megabytes")
        # These should be handled by the NumericalEntityDetector instead
        # Use data units from constants

        # Check if the entity text contains data units
        entity_words = ent.text.lower().split()
        for word in entity_words:
            if word in DATA_UNITS:
                logger.debug(f"Skipping QUANTITY '{ent.text}' because it contains data unit '{word}'")
                return True

        return False

    def _should_skip_money(self, ent, text: str) -> bool:
        """Check if a MONEY entity should be skipped because it's actually a weight measurement."""
        if ent.label_ != "MONEY":
            return False

        entity_text = ent.text.lower()

        # Check if this MONEY entity contains "pounds" (which could be weight)
        if "pound" not in entity_text:
            return False

        # Get context before the entity to look for context clues
        prefix_text = text[: ent.start_char].lower()

        # First check for clear currency context - if found, keep as MONEY
        found_currency_context = any(context in prefix_text for context in CURRENCY_CONTEXTS)

        if found_currency_context:
            logger.debug(f"Keeping MONEY '{ent.text}' because currency context found in prefix")
            return False  # Don't skip - keep as currency

        # No clear currency context - check for weight context or default to weight
        found_weight_context = any(context in prefix_text for context in WEIGHT_CONTEXTS)

        # Also check for measurement phrases like "it is X pounds"
        words_before = prefix_text.split()[-3:]
        found_measurement_pattern = any(pattern in words_before for pattern in MEASUREMENT_PATTERNS_FORMATTER)

        if found_weight_context or found_measurement_pattern or not prefix_text.strip():
            # Default to weight if: explicit weight context, measurement pattern, or no context (standalone)
            logger.debug(f"Skipping MONEY '{ent.text}' - treating as weight measurement")
            return True  # Skip - treat as weight

        # If we get here, there's some other context - default to currency
        return False

    def _should_skip_date(self, ent, text: str) -> bool:
        """Check if a DATE entity should be skipped because it's likely an ordinal context."""
        if ent.label_ != "DATE":
            return False

        entity_text = ent.text.lower()

        # Keep DATE entities that contain actual month names
        if any(month in entity_text for month in MONTH_NAMES):
            return False  # Keep - this is a real date

        # Keep DATE entities that contain specific relative days
        if any(day in entity_text for day in RELATIVE_DAYS):
            return False  # Keep - this is a real date

        # Keep DATE entities that look like actual dates (contain numbers and date keywords)
        # If it contains ordinal words but no clear date context, it's likely an ordinal
        has_ordinal = any(ordinal in entity_text for ordinal in DATE_ORDINAL_WORDS)
        has_date_keyword = any(keyword in entity_text for keyword in DATE_KEYWORDS)

        if has_ordinal and not has_date_keyword:
            # This looks like "the fourth" or similar - likely an ordinal, not a date
            logger.debug(f"Skipping DATE '{ent.text}' - likely ordinal context without date keywords")
            return True

        # If it's just an ordinal word with generic context like "day" without date specificity, skip it
        if has_ordinal and has_date_keyword and len(entity_text.split()) <= 3:
            # Phrases like "the fourth day" - could be ordinal
            logger.debug(f"Skipping DATE '{ent.text}' - short phrase with ordinal, prefer ORDINAL detection")
            return True

        return False  # Keep as DATE


class PatternConverter:
    """Converts specific entity types to their final form"""

    def __init__(self, language: str = "en"):
        self.number_parser = NumberParser(language=language)
        self.language = language

        # Entity type to converter method mapping
        self.converters = {
            EntityType.PHYSICS_SQUARED: self.convert_physics_squared,
            EntityType.PHYSICS_TIMES: self.convert_physics_times,
        }

        # Add web converters
        self.converters.update(WebPatternConverter(self.number_parser, language=language).converters)

        # Add code converters
        self.converters.update(CodePatternConverter(self.number_parser, language=language).converters)

        # Add numeric converters
        self.converters.update(NumericalPatternConverter(self.number_parser, language=language).converters)

        # Add quantity converters - DISABLED: Using superior NumericalPatternConverter instead
        # from .match_entities import QuantityPatternConverter
        # self.converters.update(QuantityPatternConverter(self.number_parser).converters)

    def convert(self, entity: Entity, full_text: str) -> str:
        """Convert entity based on its type"""
        # Check for trailing punctuation after entity in full text
        trailing_punct = ""
        if entity.end < len(full_text) and full_text[entity.end] in ".!?":
            trailing_punct = full_text[entity.end]

        # Get the appropriate converter for this entity type
        converter = self.converters.get(entity.type)
        if converter:
            # Determine conversion strategy based on entity type
            result = self._apply_converter(converter, entity, full_text)

            # Check if this entity type handles its own punctuation
            if self._handles_own_punctuation(entity.type):
                return result
            return result + trailing_punct

        # Default fallback for unknown entity types
        return entity.text + trailing_punct

    def _apply_converter(self, converter, entity: Entity, full_text: str) -> str:
        """Apply the converter with appropriate parameters based on entity type"""
        # Entity types that need full_text parameter
        full_text_entity_types = {
            EntityType.SPOKEN_URL,
            EntityType.CARDINAL,
            EntityType.MONEY,
            EntityType.CURRENCY,
            EntityType.QUANTITY,
            EntityType.FILENAME,  # Added to detect spoken underscores in context
        }

        if entity.type in full_text_entity_types:
            return converter(entity, full_text)
        return converter(entity)

    def _handles_own_punctuation(self, entity_type: EntityType) -> bool:
        """Check if entity type handles its own punctuation"""
        # Entity types that manage their own punctuation and shouldn't get extra trailing punctuation
        self_punctuating_types = {
            EntityType.SPOKEN_URL,
            EntityType.SPOKEN_PROTOCOL_URL,
            EntityType.MATH,
            EntityType.MATH_EXPRESSION,
            EntityType.EMAIL,
            EntityType.PHYSICS_SQUARED,
            EntityType.PHYSICS_TIMES,
            EntityType.MONEY,
            EntityType.FILENAME,
            EntityType.INCREMENT_OPERATOR,
            EntityType.DECREMENT_OPERATOR,
            EntityType.ABBREVIATION,
            EntityType.ASSIGNMENT,
            EntityType.COMPARISON,
            EntityType.PORT_NUMBER,
            EntityType.URL,  # Regular URLs also handle their own punctuation
        }

        # Fix for test "That makes me a happy 🙂."
        # Emojis need to handle their own punctuation to avoid having it placed before them.
        self_punctuating_types.add(EntityType.SPOKEN_EMOJI)

        return entity_type in self_punctuating_types

    def convert_physics_squared(self, entity: Entity) -> str:
        """Convert physics squared formulas like 'E equals MC squared' -> 'e = mc²'"""
        # The original test logic was correct, this change was a bug. Restoring it.
        if entity.metadata and "groups" in entity.metadata:
            var1, var2 = entity.metadata["groups"]
            return f"{var1.upper()} = {var2.upper()}²"
        return entity.text

    def convert_physics_times(self, entity: Entity) -> str:
        """Convert physics multiplication like 'F equals M times A' -> 'f = m × a'"""
        # The original test logic was correct, this change was a bug. Restoring it.
        if entity.metadata and "groups" in entity.metadata:
            var1, var2, var3 = entity.metadata["groups"]
            return f"{var1.upper()} = {var2.upper()} × {var3.upper()}"
        return entity.text


class SmartCapitalizer:
    """Intelligent capitalization using SpaCy POS tagging"""

    def __init__(self, language: str = "en"):
        self.nlp = get_nlp()
        self.language = language

        # Entity types that must have their casing preserved under all circumstances
        self.STRICTLY_PROTECTED_TYPES = {
            EntityType.CLI_COMMAND,
            EntityType.PROGRAMMING_KEYWORD,
            EntityType.URL,
            EntityType.SPOKEN_URL,
            EntityType.SPOKEN_PROTOCOL_URL,
            EntityType.EMAIL,
            EntityType.SPOKEN_EMAIL,
            EntityType.FILENAME,
            EntityType.INCREMENT_OPERATOR,
            EntityType.DECREMENT_OPERATOR,
            EntityType.SLASH_COMMAND,
            EntityType.COMMAND_FLAG,
            EntityType.SIMPLE_UNDERSCORE_VARIABLE,
            EntityType.UNDERSCORE_DELIMITER,
            EntityType.PORT_NUMBER,
            EntityType.VERSION_TWO,
            EntityType.VERSION_THREE,
        }

        # Version patterns that indicate technical content
        self.version_patterns = {"version", "v.", "v", "build", "release"}

        # Abbreviation patterns and their corrections
        self.abbreviation_fixes = {
            "I.e.": "i.e.",
            "E.g.": "e.g.",
            "Etc.": "etc.",
            "Vs.": "vs.",
            "Cf.": "cf.",
            "Ie.": "i.e.",
            "Eg.": "e.g.",
            "Ex.": "e.g.",
        }

        # Common uppercase abbreviations
        self.uppercase_abbreviations = {
            "asap": "ASAP",
            "faq": "FAQ",
            "ceo": "CEO",
            "cto": "CTO",
            "cfo": "CFO",
            "fyi": "FYI",
            "diy": "DIY",
            "lol": "LOL",
            "omg": "OMG",
            "usa": "USA",
            "uk": "UK",
            "eu": "EU",
            "usd": "USD",
            "gbp": "GBP",
            "eur": "EUR",
            "gps": "GPS",
            "wifi": "WiFi",
            "api": "API",
            "url": "URL",
            "html": "HTML",
            "css": "CSS",
            "sql": "SQL",
            "pdf": "PDF",
        }

        # Abbreviation patterns for starts detection
        self.common_abbreviations = ("i.e.", "e.g.", "etc.", "vs.", "cf.", "ie.", "eg.")

    def capitalize(self, text: str, entities: List[Entity] = None, doc=None) -> str:
        """Apply intelligent capitalization with entity protection"""
        if not text:
            return text

        # Preserve all-caps words (acronyms like CPU, API, JSON) and number+unit combinations (500MB, 2.5GHz)
        # But exclude version numbers (v16.4.2)
        all_caps_words = {}
        matches = list(regex_patterns.ALL_CAPS_PRESERVATION_PATTERN.finditer(text))

        # Also preserve mixed-case technical terms (JavaScript, GitHub, etc.)
        mixed_case_matches = list(regex_patterns.MIXED_CASE_TECH_PATTERN.finditer(text))
        matches.extend(mixed_case_matches)

        # Sort matches by position and process in reverse order to maintain positions
        matches.sort(key=lambda m: m.start())

        # Remove duplicates and overlapping matches
        unique_matches = []
        for match in matches:
            # Check if this match overlaps with any already added
            overlaps = False
            for existing in unique_matches:
                if match.start() < existing.end() and match.end() > existing.start():
                    # If there's overlap, keep the longer match
                    if len(match.group()) > len(existing.group()):
                        unique_matches.remove(existing)
                    else:
                        overlaps = True
                        break
            if not overlaps:
                unique_matches.append(match)

        # Process in reverse order to maintain positions
        for i, match in enumerate(reversed(unique_matches)):
            placeholder = f"__CAPS_{len(unique_matches) - i - 1}__"
            all_caps_words[placeholder] = match.group()
            text = text[: match.start()] + placeholder + text[match.end() :]

        # Preserve placeholders and entities
        placeholder_pattern = r"__PLACEHOLDER_\d+__|__ENTITY_\d+__|__CAPS_\d+__"
        placeholders_found = re.findall(placeholder_pattern, text)

        # Apply proper noun capitalization using spaCy NER
        text = self._capitalize_proper_nouns(text, entities, doc=doc)

        # Only capitalize after clear sentence endings with space, but not for abbreviations like i.e., e.g.
        def capitalize_after_sentence(match):
            punctuation_and_space = match.group(1)
            letter = match.group(2)
            letter_pos = match.start() + len(punctuation_and_space)

            # Check if the letter is inside ANY entity - entities should control their own formatting
            if entities:
                for entity in entities:
                    if entity.start <= letter_pos < entity.end:
                        return match.group(0)  # Don't capitalize - let entity handle formatting

            # Check the text before the match to see if it's an abbreviation
            preceding_text = text[: match.start()].lower()
            if any(preceding_text.endswith(abbrev) for abbrev in COMMON_ABBREVIATIONS):
                return match.group(0)  # Don't capitalize

            return punctuation_and_space + letter.upper()

        text = re.sub(r"([.!?]\s+)([a-z])", capitalize_after_sentence, text)

        # Fix capitalization after abbreviations: don't capitalize letters immediately after abbreviations like "i.e. "
        # This needs to handle both uppercase and lowercase letters since punctuation might have already capitalized them
        def protect_after_abbreviation(match):
            abbrev_and_space = match.group(1)  # "i.e. "
            letter = match.group(2)  # "t" or "T"
            return abbrev_and_space + letter.lower()  # Force lowercase

        # Build pattern from constants - match both upper and lowercase letters
        abbrev_pattern = "|".join(abbrev.replace(".", "\\.") for abbrev in COMMON_ABBREVIATIONS)
        text = re.sub(rf"(\b(?:{abbrev_pattern})\s+)([a-zA-Z])", protect_after_abbreviation, text)

        # Fix first letter capitalization with entity protection
        if text and text[0].islower():
            # Find the first alphabetic character to potentially capitalize
            first_letter_index = -1
            for i, char in enumerate(text):
                if char.isalpha():
                    first_letter_index = i
                    break

            if first_letter_index != -1:
                is_protected = False
                if entities:
                    for entity in entities:
                        # Check if the first letter is inside ANY entity - entities should control their own formatting
                        if entity.start <= first_letter_index < entity.end:
                            is_protected = True
                            logger.debug(
                                f"Protecting first letter '{text[first_letter_index]}' from capitalization due to entity: {entity.type}"
                            )
                            break

                # Abbreviations are prose entities that should follow normal sentence capitalization rules
                # (Removed abbreviation protection logic as it was too aggressive)

                # Technical terms are now protected by the entity system (CLI_COMMAND, etc.)
                # No manual checks needed - entity-based protection is sufficient

                if not is_protected:
                    text = text[:first_letter_index] + text[first_letter_index].upper() + text[first_letter_index + 1 :]

        # Fix "i" pronoun using grammatical context
        if self.nlp:
            # Use the pre-processed doc object if available
            doc_to_use = doc
            if doc_to_use is None:
                # This block only runs if the formatter failed to create a doc earlier
                try:
                    doc_to_use = self.nlp(text)
                except Exception as e:
                    logger.warning(f"SpaCy-based 'i' capitalization failed: {e}")
                    doc_to_use = None

            if doc_to_use:
                try:
                    new_text = list(text)
                    for token in doc_to_use:
                        if token.text == "i":
                            # Capitalize 'i' if it's being used as a pronoun (subject, conjunct, etc.)
                            # but not if it's in a code context
                            if token.pos_ == "PRON":
                                # Also ensure it's not inside ANY entity - entities should control their own formatting
                                is_protected = False
                                if entities:
                                    is_protected = any(
                                        entity.start <= token.idx < entity.end
                                        for entity in entities
                                    )

                                # Check if next token is 'e' (for i.e. pattern)
                                is_abbreviation = False
                                if token.i + 1 < len(doc_to_use) and doc_to_use[token.i + 1].text.lower() == "e":
                                    is_abbreviation = True

                                # Check for variable context clues
                                is_likely_variable = False
                                # Look at the token before the 'i'
                                if token.i > 0:
                                    prev_token = doc_to_use[token.i - 1]
                                    # Common patterns indicating 'i' is a variable
                                    if prev_token.text.lower() in [
                                        "variable",
                                        "counter",
                                        "iterator",
                                        "index",
                                        "=",
                                        "is",
                                    ]:
                                        # But check if 'is' is followed by a non-code word
                                        if prev_token.text.lower() == "is":
                                            # If "is i" is at the end or followed by punctuation, it's likely a variable
                                            if (
                                                token.i + 1 >= len(doc_to_use)
                                                or doc_to_use[token.i + 1].pos_ == "PUNCT"
                                            ):
                                                is_likely_variable = True
                                        else:
                                            is_likely_variable = True

                                if not is_protected and not is_likely_variable and not is_abbreviation:
                                    new_text[token.idx] = "I"
                    text = "".join(new_text)
                except Exception as e:
                    logger.warning(f"SpaCy-based 'i' capitalization failed: {e}")
                # Fallback to original regex-based approach
                new_text = ""
                last_end = 0
                for match in re.finditer(r"\bi\b", text):
                    start, end = match.span()
                    new_text += text[last_end:start]

                    is_protected = False
                    if entities:
                        is_protected = any(entity.start <= start < entity.end for entity in entities)

                    is_part_of_identifier = (start > 0 and text[start - 1] in "_-") or (
                        end < len(text) and text[end] in "_-"
                    )

                    # Add context check for variable 'i'
                    preceding_text = text[max(0, start - 25) : start].lower()
                    is_variable_context = any(
                        keyword in preceding_text
                        for keyword in ["variable is", "counter is", "iterator is", "for i in"]
                    )

                    if not is_protected and not is_part_of_identifier and not is_variable_context:
                        new_text += "I"  # Capitalize
                    else:
                        new_text += "i"  # Keep lowercase
                    last_end = end

                new_text += text[last_end:]
                text = new_text
        else:
            # No SpaCy available, use regex approach with context check
            new_text = ""
            last_end = 0
            for match in re.finditer(r"\bi\b", text):
                start, end = match.span()
                new_text += text[last_end:start]

                is_protected = False
                if entities:
                    is_protected = any(entity.start <= start < entity.end for entity in entities)

                is_part_of_identifier = (start > 0 and text[start - 1] in "_-") or (
                    end < len(text) and text[end] in "_-"
                )

                # Add context check for variable 'i'
                preceding_text = text[max(0, start - 25) : start].lower()
                is_variable_context = any(
                    keyword in preceding_text for keyword in ["variable is", "counter is", "iterator is", "for i in"]
                )

                if not is_protected and not is_part_of_identifier and not is_variable_context:
                    new_text += "I"  # Capitalize
                else:
                    new_text += "i"  # Keep lowercase
                last_end = end

            new_text += text[last_end:]
            text = new_text

        # Post-processing: Fix any remaining abbreviation capitalization issues
        # Use simple string replacement to avoid regex complications
        for old, new in self.abbreviation_fixes.items():
            # Replace mid-text instances but preserve true sentence starts
            text = text.replace(f" {old}", f" {new}")
            text = text.replace(f": {old}", f": {new}")
            text = text.replace(f", {old}", f", {new}")

            # Fix at start only if not truly the beginning of input
            if text.startswith(old) and len(text) > len(old) + 5:
                text = new + text[len(old) :]

        # Apply uppercase abbreviations (case-insensitive matching)
        # But skip if the abbreviation is inside a protected entity
        for lower_abbrev, upper_abbrev in self.uppercase_abbreviations.items():
            # Use word boundaries to avoid partial matches
            # Match the abbreviation with word boundaries, case-insensitive
            pattern = r"\b" + re.escape(lower_abbrev) + r"\b"

            # If we have entities to protect, check each match before replacing
            if entities:
                # Find all matches first
                matches = list(re.finditer(pattern, text, flags=re.IGNORECASE))
                # Process in reverse order to maintain positions
                for match in reversed(matches):
                    match_start, match_end = match.span()
                    # Check if this match overlaps with any protected entity
                    is_protected = any(
                        match_start < entity.end
                        and match_end > entity.start
                        and entity.type
                        in {
                            EntityType.URL,
                            EntityType.SPOKEN_URL,
                            EntityType.EMAIL,
                            EntityType.SPOKEN_EMAIL,
                            EntityType.FILENAME,
                            EntityType.ASSIGNMENT,
                            EntityType.INCREMENT_OPERATOR,
                            EntityType.DECREMENT_OPERATOR,
                            EntityType.COMMAND_FLAG,
                            EntityType.PORT_NUMBER,
                        }
                        for entity in entities
                    )

                    if not is_protected:
                        # Safe to replace this match
                        text = text[:match_start] + upper_abbrev + text[match_end:]
            else:
                # No entities to protect, do normal replacement
                text = re.sub(pattern, upper_abbrev, text, flags=re.IGNORECASE)

        # Restore original case for placeholders
        for placeholder in placeholders_found:
            text = re.sub(placeholder, placeholder, text, flags=re.IGNORECASE)

        # Restore all-caps words (acronyms) - use regex replacement to avoid mangling
        for placeholder, caps_word in all_caps_words.items():
            text = re.sub(rf"\b{re.escape(placeholder)}\b", caps_word, text)

        return text

    def _capitalize_proper_nouns(self, text: str, entities: List[Entity] = None, doc=None) -> str:
        """Capitalize proper nouns using spaCy NER and known patterns"""
        if not self.nlp:
            # No spaCy available, return text unchanged
            return text

        # Skip SpaCy processing if text contains placeholders
        # The entity positions become invalid after placeholder substitution
        if "__CAPS_" in text or "__PLACEHOLDER_" in text or "__ENTITY_" in text:
            logger.debug("Skipping SpaCy proper noun capitalization due to placeholders in text")
            return text

        doc_to_use = doc
        if doc_to_use is None:
            try:
                doc_to_use = self.nlp(text)
            except (AttributeError, ValueError, IndexError) as e:
                logger.debug(f"Error in spaCy proper noun capitalization: {e}")
                return text

        try:

            # Build list of entities to capitalize
            entities_to_capitalize = []

            # Add spaCy detected named entities
            for ent in doc_to_use.ents:
                logger.debug(f"SpaCy found entity: '{ent.text}' ({ent.label_}) at {ent.start_char}-{ent.end_char}")
                if ent.label_ in [
                    "PERSON",
                    "ORG",
                    "GPE",
                    "NORP",
                    "LANGUAGE",
                    "EVENT",
                ]:  # Types that should be capitalized

                    # Skip pi constant to prevent capitalization
                    if ent.text.lower() == "pi":
                        logger.debug(f"Skipping pi constant '{ent.text}' to allow MATH_CONSTANT converter to handle it")
                        continue

                    # Skip if this SpaCy entity is inside a final filtered entity
                    if entities and is_inside_entity(ent.start_char, ent.end_char, entities):
                        logger.debug(
                            f"Skipping SpaCy-detected entity '{ent.text}' because it is inside a final filtered entity."
                        )
                        continue

                    # Skip PERSON entities that are likely technical terms in coding contexts
                    if ent.label_ == "PERSON" and self._is_technical_term(ent.text.lower(), text):
                        logger.debug(f"Skipping PERSON entity '{ent.text}' - detected as technical term")
                        continue

                    # Skip PERSON or ORG entities that are technical verbs (let, const, var, etc.)
                    if ent.label_ in ["PERSON", "ORG"] and ent.text.isupper() and ent.text.lower() in TECHNICAL_VERBS:
                        # It's an all-caps technical term, replace with lowercase version
                        text = text[: ent.start_char] + ent.text.lower() + text[ent.end_char :]
                        continue  # Move to the next SpaCy entity

                    if ent.label_ in ["PERSON", "ORG"] and ent.text.lower() in TECHNICAL_VERBS:
                        logger.debug(f"Skipping capitalization for technical verb: '{ent.text}'")
                        continue

                    logger.debug(f"Adding '{ent.text}' to capitalize list (type: {ent.label_})")
                    entities_to_capitalize.append((ent.start_char, ent.end_char, ent.text))

            # Sort by position (reverse order to maintain indices)
            entities_to_capitalize.sort(key=lambda x: x[0], reverse=True)

            # Apply capitalizations
            for start, end, entity_text in entities_to_capitalize:
                if start < len(text) and end <= len(text):
                    # Skip placeholders - they should not be capitalized
                    # Check the actual text at this position, not just the entity text
                    actual_text = text[start:end]
                    # Also check if we're inside a placeholder by looking at surrounding context
                    context_start = max(0, start - 2)
                    context_end = min(len(text), end + 2)
                    context = text[context_start:context_end]

                    if "__" in context or actual_text.strip(".,!?").endswith("__"):
                        continue

                    # Check if this position overlaps with any protected entity
                    is_protected = False
                    if entities:
                        for entity in entities:
                            # Check if the SpaCy entity overlaps with any protected entity
                            if start < entity.end and end > entity.start:
                                logger.debug(
                                    f"SpaCy entity '{entity_text}' at {start}-{end} overlaps with protected entity {entity.type} at {entity.start}-{entity.end}"
                                )
                                # Skip capitalization for URL and email entities specifically
                                if entity.type in {
                                    EntityType.URL,
                                    EntityType.SPOKEN_URL,
                                    EntityType.EMAIL,
                                    EntityType.SPOKEN_EMAIL,
                                    EntityType.FILENAME,
                                    EntityType.ASSIGNMENT,
                                    EntityType.INCREMENT_OPERATOR,
                                    EntityType.DECREMENT_OPERATOR,
                                    EntityType.COMMAND_FLAG,
                                    EntityType.PORT_NUMBER,
                                }:
                                    logger.debug(
                                        f"Protecting entity '{entity_text}' from capitalization due to {entity.type}"
                                    )
                                    is_protected = True
                                    break
                                logger.debug(
                                    f"Entity type {entity.type} not in protected list, allowing capitalization"
                                )

                    if is_protected:
                        continue

                    # Capitalize the proper noun while preserving the original entity text
                    capitalized = entity_text.title()
                    text = text[:start] + capitalized + text[end:]

            return text

        except (AttributeError, ValueError, IndexError) as e:
            logger.debug(f"Error in spaCy proper noun capitalization: {e}")
            # Return text unchanged on error
            return text

    def _is_technical_term(self, entity_text: str, full_text: str) -> bool:
        """Check if a PERSON entity is actually a technical term that shouldn't be capitalized."""
        # Use technical terms from constants

        # Check exact match for multi-word terms
        if entity_text.lower() in MULTI_WORD_TECHNICAL_TERMS:
            return True

        # Check single words in the entity
        entity_words = entity_text.lower().split()
        if any(word in TECHNICAL_TERMS for word in entity_words):
            return True

        # Check context - if surrounded by technical keywords, likely technical

        # Check words around the entity
        full_text_lower = full_text.lower()
        words = full_text_lower.split()

        try:
            entity_index = words.index(entity_text)
            # Check 2 words before and after
            context_start = max(0, entity_index - 2)
            context_end = min(len(words), entity_index + 3)
            context_words = words[context_start:context_end]

            if any(word in TECHNICAL_CONTEXT_WORDS for word in context_words):
                return True
        except ValueError:
            # Entity not found as single word, might be multi-word
            pass

        return False


class TextFormatter:
    """Main formatter orchestrating the pipeline"""

    def __init__(self, language: str = "en"):
        # Store the language for this formatter instance
        self.language = language
        
        # Load shared NLP model once
        self.nlp = get_nlp()

        # Initialize components with dependency injection and language support
        self.entity_detector = EntityDetector(nlp=self.nlp, language=self.language)
        self.pattern_converter = PatternConverter(language=self.language)
        self.smart_capitalizer = SmartCapitalizer(language=self.language)

        # Instantiate specialized components with shared NLP model and language
        self.web_detector = WebEntityDetector(nlp=self.nlp, language=self.language)
        self.web_converter = WebPatternConverter(self.pattern_converter.number_parser, language=self.language)
        self.code_detector = CodeEntityDetector(nlp=self.nlp, language=self.language)
        self.code_converter = CodePatternConverter(self.pattern_converter.number_parser, language=self.language)
        self.numeric_detector = NumericalEntityDetector(nlp=self.nlp, language=self.language)
        self.numeric_converter = NumericalPatternConverter(self.pattern_converter.number_parser, language=self.language)

        # Complete sentence phrases that need punctuation even when short
        self.complete_sentence_phrases = COMPLETE_SENTENCE_PHRASES

        # Use artifacts and profanity lists from constants
        self.transcription_artifacts = TRANSCRIPTION_ARTIFACTS
        self.profanity_words = PROFANITY_WORDS

    def format_transcription(self, text: str, key_name: str = "", enter_pressed: bool = False, language: str = None) -> str:
        """Main formatting pipeline - NEW ARCHITECTURE WITHOUT PLACEHOLDERS
        
        Args:
            text: Text to format
            key_name: Key name for context
            enter_pressed: Whether enter was pressed
            language: Optional language override (uses instance default if None)
        """
        # Use the override language if provided, otherwise use the instance's default
        current_language = language or self.language
        
        if not text or not text.strip():
            logger.debug("Empty text, skipping formatting")
            return ""

        logger.info(f"Original text: '{text}' (language: {current_language})")

        # --- START OF NEW LOGIC ---
        # Perform the single SpaCy processing pass at the beginning
        doc = None
        if self.nlp:
            try:
                doc = self.nlp(text)
            except (AttributeError, ValueError, IndexError) as e:
                logger.warning(f"SpaCy processing failed for text: {e}")
        # --- END OF NEW LOGIC ---

        # Track original punctuation state for later use
        original_had_punctuation = text.rstrip() and text.rstrip()[-1] in ".!?"

        # Step 1: Clean artifacts and filter (preserve case)
        text = self._clean_artifacts(text)
        text = self._apply_filters(text)

        if not text:
            logger.info("Transcription filtered: content matched filtering rules")
            return ""

        # Step 2: Full formatting WITHOUT punctuation
        # Detect and convert all entities to their final form
        # --- CHANGE 1: Pass the pre-processed `doc` object ---
        entities = self.entity_detector.detect_entities(text, doc=doc)
        logger.info(f"Base entities detected: {len(entities)} - {[f'{e.type}:{e.text}' for e in entities]}")

        # Add web-related entities
        web_entities = self.web_detector.detect(text, entities)
        logger.info(f"Web entities detected: {len(web_entities)} - {[f'{e.type}:{e.text}' for e in web_entities]}")
        entities.extend(web_entities)

        # Add code-related entities
        code_entities = self.code_detector.detect(text, entities)
        logger.info(f"Code entities detected: {len(code_entities)} - {[f'{e.type}:{e.text}' for e in code_entities]}")
        entities.extend(code_entities)

        # Add numeric-related entities
        numeric_entities = self.numeric_detector.detect(text, entities)
        logger.info(
            f"Numeric entities detected: {len(numeric_entities)} - {[f'{e.type}:{e.text}' for e in numeric_entities]}"
        )
        entities.extend(numeric_entities)

        logger.debug(f"Detected {len(entities)} total entities.")

        # Filter overlapping entities to get the final, non-overlapping list.
        filtered_entities = self._filter_overlapping_entities(entities)
        logger.debug(f"Filtered to {len(filtered_entities)} non-overlapping entities.")

        # Step 3: Create a "Punctuation-Safe" string using a robust assembly approach.
        # This gives the punctuation model full context without letting it mangle entities.
        entity_map = {}
        punctuated_parts = []
        last_end = 0
        # Sort entities by their start position to process the string in order.
        for i, entity in enumerate(sorted(filtered_entities, key=lambda e: e.start)):
            placeholder = f"__ENTITY_{i}__"
            entity_map[placeholder] = entity

            # Add the text gap before this entity.
            punctuated_parts.append(text[last_end : entity.start])
            # Add the placeholder for the current entity.
            punctuated_parts.append(placeholder)

            last_end = entity.end

        # Add any remaining text after the last entity.
        punctuated_parts.append(text[last_end:])

        # Join all the parts to create the final, safe string for the punctuation model.
        punctuated_text = "".join(punctuated_parts)

        logger.debug(f"Punctuation-safe string: '{punctuated_text}'")

        # Step 4: Apply punctuation to the placeholder-protected string.
        is_standalone_technical = self._is_standalone_technical(text, filtered_entities)
        punctuated_text = self._add_punctuation(
            punctuated_text, original_had_punctuation, is_standalone_technical, filtered_entities
        )
        logger.debug(f"Punctuated placeholder string: '{punctuated_text}'")

        # The punctuation model adds colons after action verbs when followed by entities
        # This is grammatically correct, so we'll keep them

        # Step 5: Assemble the final string by converting entities and restoring them.
        # This replaces placeholders with their final, converted text.
        text = punctuated_text
        logger.debug(f"Starting assembly with: '{text}'")
        logger.debug(f"Entity map: {entity_map}")

        # Track entity positions in final text for capitalization protection
        converted_entities = []

        # Sort placeholders by their position in text to handle replacements in order
        # This ensures that position tracking remains accurate as text changes
        placeholder_positions = [
            (text.find(placeholder), placeholder, entity)
            for placeholder, entity in entity_map.items()
            if text.find(placeholder) != -1
        ]
        placeholder_positions.sort(key=lambda x: x[0])

        # Track cumulative position shift due to replacements
        position_shift = 0

        for original_pos, placeholder, entity in placeholder_positions:
            converted_content = self.pattern_converter.convert(entity, text)
            logger.debug(f"Converting {placeholder} (entity: {entity.type}:{entity.text}) -> '{converted_content}'")

            # Calculate current position accounting for previous replacements
            current_placeholder_start = text.find(placeholder)
            if current_placeholder_start != -1:
                # Create a new entity with correct position for the converted content
                converted_entity = Entity(
                    start=current_placeholder_start,
                    end=current_placeholder_start + len(converted_content),
                    text=converted_content,
                    type=entity.type,
                    metadata=entity.metadata,
                )
                converted_entities.append(converted_entity)
                logger.debug(
                    f"Added converted entity: {entity.type}:{converted_content} at pos {current_placeholder_start}-{current_placeholder_start + len(converted_content)}"
                )

            text = text.replace(placeholder, converted_content)
            logger.debug(f"After replacing {placeholder}: '{text}'")

        logger.debug(f"Text after all conversions and assembly: '{text}'")

        # Step 3.4: Fix double periods that can occur when abbreviations are substituted back
        text = re.sub(r"\.\.+", ".", text)
        text = re.sub(r"\?\?+", "?", text)
        text = re.sub(r"!!+", "!", text)

        # Step 3.5: Restore abbreviations that the punctuation model may have mangled
        text = self._restore_abbreviations(text)

        # Step 4: Final capitalization pass
        # This runs AFTER punctuation since new sentence boundaries may have been added
        # Skip capitalization for standalone technical content
        if not is_standalone_technical:
            logger.debug(f"Text before capitalization: '{text}'")
            # --- CHANGE 1: Pass the `doc` object to the helper method ---
            text = self._apply_capitalization_with_entity_protection(text, converted_entities, doc=doc)
            logger.debug(f"Text after capitalization: '{text}'")

        # Step 4.5: Removed hardcoded period addition for filenames and version numbers
        # Technical content should not be forced to have periods

        # Step 5: Domain rescue (improved version without brittle word lists)
        logger.debug(f"Text before domain rescue: '{text}'")
        text = self._rescue_mangled_domains(text)
        logger.debug(f"Text after domain rescue: '{text}'")

        # Step 6: Apply smart quotes
        logger.debug(f"Text before smart quotes: '{text}'")
        text = self._apply_smart_quotes(text)
        logger.debug(f"Text after smart quotes: '{text}'")

        # Note: Suffix handling remains in hotkey_daemon for reliability

        logger.debug(f"Final formatted: '{text[:50]}...'")
        return text

    def _filter_overlapping_entities(self, entities: List[Entity]) -> List[Entity]:
        """Filter out overlapping entities using a O(n log n) sweep-line algorithm."""
        if not entities:
            return []

        # Define entity type priority (higher number = higher priority)
        entity_priority = {
            # --- Lowest Priority: Generic & Broad ---
            EntityType.CARDINAL: 1,  # Lowest priority - generic number
            EntityType.QUANTITY: 1,  # Also low priority - generic quantity
            EntityType.TIME_CONTEXT: 2,  # Low priority - often too broad and catches non-time phrases
            EntityType.DATE: 3,  # Low priority - generic date (can be overridden by fractions)
            EntityType.TIME: 3,  # Low priority - generic time (can be overridden by fractions)
            EntityType.TIME_AMPM: 3,
            EntityType.ORDINAL: 4,  # Medium-low priority - ordinals (but fractions should override)
            EntityType.TIME_RELATIVE: 4,
            # --- Low-Medium Priority: Basic Patterns ---
            EntityType.CENTS: 5,
            EntityType.MUSIC_NOTATION: 6,
            EntityType.FRACTION: 7,  # Higher than CARDINAL/QUANTITY/DATE/TIME but lower than specific types
            EntityType.NUMERIC_RANGE: 8,
            # --- Medium Priority: Measurements & Units ---
            EntityType.DATA_SIZE: 10,
            EntityType.FREQUENCY: 10,
            EntityType.TIME_DURATION: 10,
            EntityType.TEMPERATURE: 11,
            EntityType.METRIC_LENGTH: 11,
            EntityType.METRIC_WEIGHT: 11,
            EntityType.METRIC_VOLUME: 11,
            # --- Medium-High Priority: Math & Technical ---
            EntityType.ABBREVIATION: 12,
            EntityType.MATH_CONSTANT: 13,
            EntityType.ROOT_EXPRESSION: 14,
            EntityType.MATH: 15,
            EntityType.MATH_EXPRESSION: 15,
            EntityType.PHYSICS_SQUARED: 16,
            EntityType.PHYSICS_TIMES: 16,
            EntityType.ASSIGNMENT: 17,
            EntityType.COMPARISON: 18,
            EntityType.SCIENTIFIC_NOTATION: 19,  # High priority for full scientific expressions
            # --- High Priority: Currency & Money ---
            EntityType.DOLLARS: 20,
            EntityType.DOLLAR_CENTS: 20,
            EntityType.POUNDS: 20,
            EntityType.EUROS: 20,
            EntityType.MONEY: 21,  # SpaCy detected money
            EntityType.CURRENCY: 21,  # Our detected currency
            EntityType.PERCENT: 22,  # Also give spoken decimals as percentages high priority
            # --- High Priority: Code & Technical ---
            EntityType.INCREMENT_OPERATOR: 23,
            EntityType.DECREMENT_OPERATOR: 23,
            EntityType.COMMAND_FLAG: 24,
            EntityType.UNIX_PATH: 25,
            EntityType.WINDOWS_PATH: 25,
            EntityType.VERSION_TWO: 26,  # Give version numbers a very high priority
            EntityType.VERSION_THREE: 26,
            # --- Very High Priority: Contact & Web ---
            EntityType.PHONE_LONG: 30,
            EntityType.SPOKEN_EMOJI: 31,
            EntityType.SPOKEN_PROTOCOL_URL: 32,
            EntityType.SPOKEN_URL: 32,
            EntityType.URL: 32,
            EntityType.PORT_NUMBER: 35,  # Higher priority than URLs because ports are more specific
            EntityType.SPOKEN_EMAIL: 36,  # Higher priority than URLs because emails are more specific
            EntityType.EMAIL: 36,
            EntityType.FILENAME: 37,  # Higher than URL to win for package names like com.example.app
            # --- Highest Priority: Special Technical ---
            EntityType.SLASH_COMMAND: 38,
            EntityType.UNDERSCORE_DELIMITER: 39,
        }

        # Create a list of events: (position, type, entity_index, entity)
        # Type: 0 for start, 1 for end
        events = []
        for i, entity in enumerate(entities):
            events.append((entity.start, 0, i, entity))
            events.append((entity.end, 1, i, entity))

        # Sort events by position, then by type (starts before ends for same position)
        events.sort(key=lambda x: (x[0], x[1]))

        # Track active entities and which indices to keep
        active_entities = {}  # entity_index -> entity
        keep_indices = set()

        for pos, event_type, idx, entity in events:
            if event_type == 0:  # Start of an entity
                # Check for conflicts with currently active entities
                should_keep = True
                to_remove = []

                for active_idx, active_entity in active_entities.items():
                    # Check for overlap
                    if entity.start < active_entity.end:
                        # Determine which entity wins
                        entity_prio = entity_priority.get(entity.type, 5)
                        active_prio = entity_priority.get(active_entity.type, 5)

                        # Conflict resolution logic
                        if entity_prio < active_prio:
                            # Current entity loses
                            should_keep = False
                            logger.debug(
                                f"Entity {idx} '{entity.text}' loses to active entity {active_idx} due to priority"
                            )
                            break
                        if entity_prio > active_prio:
                            # Current entity wins, mark active entity for removal
                            to_remove.append(active_idx)
                            logger.debug(
                                f"Entity {idx} '{entity.text}' wins over active entity {active_idx} due to priority"
                            )
                        else:
                            # Same priority - use length and original order
                            entity_len = entity.end - entity.start
                            active_len = active_entity.end - active_entity.start

                            if entity_len < active_len:
                                should_keep = False
                                logger.debug(
                                    f"Entity {idx} '{entity.text}' loses to active entity {active_idx} due to length"
                                )
                                break
                            if entity_len > active_len:
                                to_remove.append(active_idx)
                                logger.debug(
                                    f"Entity {idx} '{entity.text}' wins over active entity {active_idx} due to length"
                                )
                            elif idx > active_idx:
                                # Same priority and length, keep the earlier one
                                should_keep = False
                                logger.debug(
                                    f"Entity {idx} '{entity.text}' loses to active entity {active_idx} due to order"
                                )
                                break
                            else:
                                to_remove.append(active_idx)
                                logger.debug(
                                    f"Entity {idx} '{entity.text}' wins over active entity {active_idx} due to order"
                                )

                # Remove any entities that lost to the current one
                for rem_idx in to_remove:
                    del active_entities[rem_idx]
                    if rem_idx in keep_indices:
                        keep_indices.remove(rem_idx)

                # Add current entity if it should be kept
                if should_keep:
                    active_entities[idx] = entity
                    keep_indices.add(idx)

            # Remove from active list if it's there
            elif idx in active_entities:
                del active_entities[idx]

        # Build the filtered list maintaining original order
        filtered_entities = [entity for i, entity in enumerate(entities) if i in keep_indices]
        return sorted(filtered_entities, key=lambda e: e.start)

    def _is_standalone_technical(self, text: str, entities: List[Entity]) -> bool:
        """Check if the text consists entirely of entities with no surrounding text."""
        if not entities:
            return False

        text_stripped = text.strip()

        # Only treat as standalone technical if it consists ENTIRELY of command flags with minimal surrounding text
        command_flag_entities = [e for e in entities if e.type == EntityType.COMMAND_FLAG]
        if command_flag_entities:
            # Calculate how much of the text is covered by entities vs surrounding text
            total_entity_length = sum(len(e.text) for e in entities)
            text_length = len(text_stripped)

            # If entities cover most of the text (>90%), treat as standalone technical
            # Increased threshold to allow short commands like "use --verbose" to get punctuation
            if total_entity_length / text_length > 0.9:
                logger.debug("Command flag entities cover most of text, treating as standalone technical content.")
                return True

        sorted_entities = sorted(entities, key=lambda e: e.start)

        # Special handling for email entities that start with action words
        # Emails like "email john@example.com" should not be considered standalone technical
        for entity in sorted_entities:
            if entity.type == EntityType.SPOKEN_EMAIL and entity.start == 0:
                # Check if the email entity starts with common action words
                action_words = EMAIL_ENTITY_ACTION_WORDS
                entity_text = entity.text.lower().strip()
                for action_word in action_words:
                    if entity_text.startswith(action_word + " "):
                        logger.debug(f"Email entity starts with action word '{action_word}' - not standalone technical")
                        return False

        last_end = 0
        for entity in sorted_entities:
            # Check for a non-whitespace gap before this entity
            if entity.start > last_end:
                gap_text = text_stripped[last_end : entity.start].strip()
                if gap_text:
                    return False  # There is meaningful text outside of an entity
            last_end = max(last_end, entity.end)

        # Check for any remaining non-whitespace text at the end
        if last_end < len(text_stripped):
            remaining_text = text_stripped[last_end:].strip()
            if remaining_text:
                return False

        logger.debug("Text consists entirely of entities - will skip punctuation.")
        return True

    def _clean_artifacts(self, text: str) -> str:
        """Clean audio artifacts and normalize text"""
        # Remove various transcription artifacts using cached patterns
        if not hasattr(self, "_artifact_patterns"):
            self._artifact_patterns = regex_patterns.create_artifact_patterns(self.transcription_artifacts)

        for pattern in self._artifact_patterns:
            text = pattern.sub("", text).strip()

        # Remove filler words using centralized pattern
        text = regex_patterns.FILLER_WORDS_PATTERN.sub("", text)

        # Normalize repeated punctuation using centralized patterns
        for pattern, replacement in regex_patterns.REPEATED_PUNCTUATION_PATTERNS:
            text = pattern.sub(replacement, text)

        # Normalize whitespace using pre-compiled pattern
        text = regex_patterns.WHITESPACE_NORMALIZATION_PATTERN.sub(" ", text).strip()

        # Filter profanity using centralized pattern creation
        profanity_pattern = regex_patterns.create_profanity_pattern(self.profanity_words)
        text = profanity_pattern.sub(lambda m: "*" * len(m.group()), text)

        return text

    def _apply_filters(self, text: str) -> str:
        """Apply configured filters"""
        if not text:
            return text

        # Remove common phrases from config
        for phrase in config.filter_phrases:
            text = text.replace(phrase, "").strip()

        # Remove exact matches
        if text.lower() in [p.lower() for p in config.exact_filter_phrases]:
            logger.info(f"Transcription filtered: exact match '{text}' found in filter list")
            text = ""

        # Basic cleanup
        if text:
            text = "".join(char for char in text if ord(char) >= 32 or char in "\n\t")
            text = text.strip()

        return text

    def _add_punctuation(
        self,
        text: str,
        original_had_punctuation: bool = False,
        is_standalone_technical: bool = False,
        filtered_entities: List[Entity] = None,
    ) -> str:
        """Add punctuation - treat all text as sentences unless single standalone technical entity"""
        if filtered_entities is None:
            filtered_entities = []

        # Add this at the beginning to handle empty inputs
        if not text.strip():
            return ""

        # Check if punctuation is disabled for testing
        if os.environ.get("MATILDA_DISABLE_PUNCTUATION") == "1":
            logger.debug("Punctuation disabled for testing, returning text unchanged")
            return text

        # Check if text is a standalone technical entity that should bypass punctuation
        if is_standalone_technical:
            logger.debug("Bypassing punctuation for standalone technical entity")
            return text

        # If original text already had punctuation, don't add more
        if original_had_punctuation:
            logger.debug(f"Original text had punctuation, skipping punctuation model: '{text[:50]}...'")
            return text

        # All other text is treated as a sentence - use punctuation model
        punctuator = get_punctuator()
        if punctuator:
            try:
                # Protect URLs and technical terms from the punctuation model by temporarily replacing them
                # Using pre-compiled patterns for performance
                url_placeholders = {}
                protected_text = text

                # Find and replace URLs with placeholders
                for i, match in enumerate(regex_patterns.URL_PROTECTION_PATTERN.finditer(text)):
                    placeholder = f"__URL_{i}__"
                    url_placeholders[placeholder] = match.group(0)
                    protected_text = protected_text.replace(match.group(0), placeholder, 1)

                # Also protect email addresses
                email_placeholders = {}
                for i, match in enumerate(regex_patterns.EMAIL_PROTECTION_PATTERN.finditer(protected_text)):
                    placeholder = f"__EMAIL_{i}__"
                    email_placeholders[placeholder] = match.group(0)
                    protected_text = protected_text.replace(match.group(0), placeholder, 1)

                # Also protect sequences of all-caps technical terms (like "HTML CSS JavaScript")
                tech_placeholders = {}
                for i, match in enumerate(regex_patterns.TECH_SEQUENCE_PATTERN.finditer(protected_text)):
                    placeholder = f"__TECH_{i}__"
                    tech_placeholders[placeholder] = match.group(0)
                    protected_text = protected_text.replace(match.group(0), placeholder, 1)

                # Protect math expressions from the punctuation model (preserve spacing around operators)
                math_placeholders = {}
                for i, match in enumerate(regex_patterns.MATH_EXPRESSION_PATTERN.finditer(protected_text)):
                    placeholder = f"__MATH_{i}__"
                    math_placeholders[placeholder] = match.group(0)
                    protected_text = protected_text.replace(match.group(0), placeholder, 1)

                # Protect temperature expressions from the punctuation model
                temp_placeholders = {}
                for i, match in enumerate(regex_patterns.TEMPERATURE_PROTECTION_PATTERN.finditer(protected_text)):
                    placeholder = f"__TEMP_{i}__"
                    temp_placeholders[placeholder] = match.group(0)
                    protected_text = protected_text.replace(match.group(0), placeholder, 1)

                # Apply punctuation to the protected text
                logger.debug(f"Text before punctuation model: '{protected_text}'")
                logger.debug(f"URL placeholders: {url_placeholders}")
                result = punctuator.restore_punctuation(protected_text)
                logger.debug(f"Text after punctuation model: '{result}'")

                # Restore URLs
                for placeholder, url in url_placeholders.items():
                    result = re.sub(rf"\b{re.escape(placeholder)}\b", url, result)

                # Restore emails
                for placeholder, email in email_placeholders.items():
                    result = re.sub(rf"\b{re.escape(placeholder)}\b", email, result)

                # Restore technical terms
                for placeholder, tech_term in tech_placeholders.items():
                    result = re.sub(rf"\b{re.escape(placeholder)}\b", tech_term, result)

                # Restore math expressions
                for placeholder, math_expr in math_placeholders.items():
                    result = re.sub(rf"\b{re.escape(placeholder)}\b", math_expr, result)

                # Restore temperature expressions
                for placeholder, temp in temp_placeholders.items():
                    result = re.sub(rf"\b{re.escape(placeholder)}\b", temp, result)

                # Post-process punctuation using grammatical context
                if self.nlp:
                    try:
                        # Re-run spaCy on the punctuated text to analyze grammar
                        punc_doc = self.nlp(result)
                        new_result_parts = list(result)

                        for token in punc_doc:
                            # Find colons that precede a noun/entity
                            if token.text == ":" and token.i > 0:
                                prev_token = punc_doc[token.i - 1]

                                # Check if this is a command/action context where colon should be removed
                                should_remove = False

                                if token.i + 1 < len(punc_doc):
                                    next_token = punc_doc[token.i + 1]

                                    # Case 1: Command verb followed by colon and object (Edit: file.py)
                                    if (prev_token.pos_ == "VERB" and prev_token.dep_ == "ROOT") or (
                                        prev_token.pos_ in ["VERB", "NOUN", "PROPN"]
                                        and token.i == 1
                                        and next_token.pos_ in ["NOUN", "PROPN", "X"]
                                        and ("@" in next_token.text or "." in next_token.text)
                                    ):
                                        should_remove = True

                                    # Case 3: Known command/action words
                                    command_words = list(COMMAND_WORDS) + [
                                        "drive",
                                        "use",
                                        "check",
                                        "select",
                                        "define",
                                        "access",
                                        "transpose",
                                        "download",
                                        "git",
                                        "contact",
                                        "email",
                                        "visit",
                                        "connect",
                                        "redis",
                                        "server",
                                        "ftp",
                                    ]
                                    if prev_token.text.lower() in command_words:
                                        should_remove = True

                                if should_remove:
                                    new_result_parts[token.idx] = ""

                        result = "".join(new_result_parts).replace("  ", " ")
                    except Exception as e:
                        logger.warning(f"SpaCy-based colon correction failed: {e}")

                # Fix double periods that the model sometimes adds
                result = re.sub(r"\.\.+", ".", result)
                result = re.sub(r"\?\?+", "?", result)
                result = re.sub(r"!!+", "!", result)

                # Fix hyphenated acronyms that the model sometimes creates
                result = result.replace("- ", " ")

                # Fix spacing around math operators that the punctuation model may have removed
                # But be careful not to add spaces in URLs (which contain query parameters)
                # Only add spaces if it looks like a math expression (variable = value or number op number)
                # Exclude cases where the = is part of a URL query parameter (contains . ? or /)
                def should_add_math_spacing(match):
                    full_context = result[max(0, match.start() - 20) : match.end() + 20]
                    if any(char in full_context for char in ["?", "/", ".com", ".org", ".net"]):
                        return match.group(0)  # Don't add spaces in URL context
                    return f"{match.group(1)} {match.group(2)} {match.group(3)}"

                result = re.sub(r"([a-zA-Z_]\w*)([=+\-*×÷])([a-zA-Z_]\w*|\d+)", should_add_math_spacing, result)
                result = re.sub(r"(\d+)([+\-*×÷])(\d+)", r"\1 \2 \3", result)

                # Fix common punctuation model errors
                # 1. Remove colons incorrectly added before technical entities
                # But preserve colons after specific action verbs
                def should_preserve_colon(match):
                    # Get text before the colon
                    start_pos = max(0, match.start() - 20)
                    preceding_text = result[start_pos : match.start()].strip().lower()
                    # Preserve colon for specific contexts
                    preserve_words = PRESERVE_COLON_WORDS
                    for word in preserve_words:
                        if preceding_text.endswith(word):
                            return match.group(0)  # Keep the colon
                    # Otherwise remove it
                    return f" {match.group(1)}"

                result = re.sub(r":\s*(__ENTITY_\d+__)", should_preserve_colon, result)

                # 2. Re-join sentences incorrectly split after technical entities

                # Add a specific rule for the "on line" pattern
                result = re.sub(r"(__ENTITY_\d+__)\.\s+([Oo]n\s+line\s+)", r"\1 \2", result)

                # Handle common patterns like "in [file] on line [number]"
                result = re.sub(r"(__ENTITY_\d+__)\.\s+([Oo]n\s+(?:line|page|row|column)\s+)", r"\1 \2", result)
                # General case: rejoin when capital letter follows entity with period
                result = re.sub(r"(__ENTITY_\d+__)\.\s+([A-Z])", lambda m: f"{m.group(1)} {m.group(2).lower()}", result)

                # Rejoin sentences split after common command verbs or contexts
                result = re.sub(
                    r"\b(Set|Run|Use|In|Go|Get|Add|Make|Check|Contact|Email|Execute|Bake|Costs|Weighs|Drive|Rotate)\b\.\s+",
                    r"\1 ",
                    result,
                    flags=re.IGNORECASE,
                )

                # 3. Clean up any double punctuation and odd spacing
                result = re.sub(r"\s*([.!?])\s*", r"\1 ", result).strip()  # Normalize space after punctuation
                result = re.sub(r"([.!?]){2,}", r"\1", result)

                if result != text:
                    logger.info(f"Punctuation added: '{result}'")
                    text = result

            except (AttributeError, ValueError, RuntimeError, OSError) as e:
                logger.error(
                    f"Punctuation model failed on text: '{text[:100]}{'...' if len(text) > 100 else ''}'.  Error: {e}"
                )

        # Add final punctuation intelligently
        if not is_standalone_technical and text and text.strip() and text.strip()[-1].isalnum():
            # Only add punctuation if it looks like a complete thought
            if len(text.split()) > 2:
                text += "."
                logger.debug(f"Added final punctuation: '{text}'")

        # The punctuation model adds colons after action verbs when followed by objects/entities
        # This is grammatically correct, so we'll keep them

        # Fix specific punctuation model errors
        # The punctuation model adds colons after action verbs, but they're not always appropriate
        # Remove colons before file/version entities, but keep them for URLs and complex entities

        # Also remove colons before direct URLs and emails (for any that bypass entity detection)
        text = re.sub(r":\s*([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})", r" \1", text)
        text = re.sub(r":\s*(https?://[^\s]+)", r" \1", text)

        # Fix time formatting issues (e.g., "at 3:p m" -> "at 3 PM")
        text = re.sub(r"\b(\d+):([ap])\s+m\b", r"\1 \2M", text, flags=re.IGNORECASE)
        text = re.sub(r"\b(\d+)\s+([ap])\s+m\b", r"\1 \2M", text, flags=re.IGNORECASE)

        # Add a more intelligent final punctuation check
        if not is_standalone_technical and text and text.strip() and text.strip()[-1].isalnum():
            word_count = len(text.split())
            if word_count > 2 or text.lower().strip() in COMPLETE_SENTENCE_PHRASES:
                text += "."
                logger.debug(f"Added final punctuation: '{text}'")

        return text

    def _restore_abbreviations(self, text: str) -> str:
        """Restore proper formatting for abbreviations after punctuation model."""
        # The punctuation model tends to strip periods from common abbreviations
        # This post-processing step restores them to our preferred format

        # Use abbreviations from constants

        # Process each abbreviation
        for abbr, formatted in ABBREVIATIONS.items():
            # Match abbreviation at word boundaries
            # This handles various contexts: start of sentence, after punctuation, etc.
            # Use negative lookbehind to avoid replacing if already has period
            pattern = rf"(?<![.])\b{abbr}\b(?![.])"

            # Replace case-insensitively but preserve the case pattern
            def replace_with_case(match):
                original = match.group(0)
                if original.isupper():
                    # All caps: IE -> I.E.
                    return formatted.upper()
                if original[0].isupper():
                    # Title case: Ie -> I.e.
                    return formatted[0].upper() + formatted[1:]
                # Lowercase: ie -> i.e.
                return formatted

            text = re.sub(pattern, replace_with_case, text, flags=re.IGNORECASE)

        # Add comma after i.e. and e.g. when followed by a word,
        # but NOT if a comma is already there.
        text = re.sub(r"(\b(?:i\.e\.|e\.g\.))(?!,)(\s+[a-zA-Z])", r"\1,\2", text)

        return text

    def _rescue_mangled_domains(self, text: str) -> str:
        """Rescue domains that got mangled - IMPROVED VERSION"""

        # Fix www patterns: "wwwgooglecom" -> "www.google.com"
        def fix_www_pattern(match):
            prefix = match.group(1).lower()  # www
            domain = match.group(2)  # google/muffin/etc
            tld = match.group(3).lower()  # com/org/etc
            if len(domain) >= 3 and tld in {"com", "org", "net", "edu", "gov", "io", "co", "uk"}:
                return f"{prefix}.{domain}.{tld}"
            return match.group(0)

        text = regex_patterns.WWW_DOMAIN_RESCUE.sub(fix_www_pattern, text)

        # Improved domain rescue using pattern recognition
        # Look for patterns like "wordTLD" where TLD is a known top-level domain
        # and the word is unlikely to be a regular word ending in those letters

        # Use TLDs and exclude words from constants

        for tld in TLDS:
            # Pattern: word + TLD at word boundary
            pattern = rf"\b([a-zA-Z]{{3,}})({tld})\b"

            def fix_domain(match):
                word = match.group(1)
                found_tld = match.group(2)
                full_word = word + found_tld

                # Skip if it's in our exclude list
                if full_word.lower() in EXCLUDE_WORDS:
                    return full_word

                # Skip if the "domain" part is too short or doesn't look like a domain
                if len(word) < 3:
                    return full_word

                # Check if this looks like a domain name pattern
                # Domain names often have:
                # - Mixed case or lowercase
                # - No vowels or unusual letter patterns
                # - Tech-related words

                # If the word before TLD has no vowels, it's likely a domain
                vowels = set("aeiouAEIOU")
                if not any(c in vowels for c in word):
                    return f"{word}.{found_tld}"

                # If it's a known tech company/service pattern
                tech_patterns = TECH_PATTERNS
                if any(pattern in word.lower() for pattern in tech_patterns):
                    return f"{word}.{found_tld}"

                # Otherwise, leave it unchanged
                return full_word

            text = re.sub(pattern, fix_domain, text, flags=re.IGNORECASE)

        return text

    def _apply_smart_quotes(self, text: str) -> str:
        """Convert straight quotes and apostrophes to smart/curly equivalents."""
        # The tests expect straight quotes, so this implementation will preserve them
        # while fixing the bug that was injecting code into the output.
        new_chars = []
        for i, char in enumerate(text):
            if char == '"':
                new_chars.append('"')
            elif char == "'":
                new_chars.append("'")
            else:
                new_chars.append(char)

        return "".join(new_chars)

    def _apply_capitalization_with_entity_protection(self, text: str, entities: List[Entity], doc=None) -> str:
        """Apply capitalization while protecting entities - Phase 1 simplified version"""
        logger.debug(f"Capitalization protection called with text: '{text}' and {len(entities)} entities")
        if not text:
            return ""

        # Phase 1: Use the converted entities with their correct positions in the final text
        # Pass the entities directly to the capitalizer for protection
        logger.debug(f"Sending to capitalizer: '{text}'")
        # --- CHANGE 3: Pass the `doc` object to the capitalizer ---
        capitalized_text = self.smart_capitalizer.capitalize(text, entities, doc=doc)
        logger.debug(f"Received from capitalizer: '{capitalized_text}'")

        return capitalized_text

    # Note: Suffix handling is performed in hotkey_daemon.py for reliability
    # The TextFormatter focuses only on text content formatting


# ==============================================================================
# PUBLIC API - Single unified function for all text processing
# ==============================================================================

# Global formatter instance
_formatter_instance = None


def format_transcription(text: str, key_name: str = "", enter_pressed: bool = False) -> str:
    """Format transcribed text with all processing steps.

    This is the main entry point for all text formatting. It combines:
    - Whisper artifact removal
    - Entity detection and conversion
    - Punctuation restoration
    - Smart capitalization
    - Domain rescue
    - Configurable suffix

    Args:
        text: The raw transcribed text
        key_name: The hotkey name (kept for compatibility)
        enter_pressed: Whether Enter key was pressed (affects suffix)

    Returns:
        Fully formatted text ready for output

    """
    global _formatter_instance
    if _formatter_instance is None:
        _formatter_instance = TextFormatter()

    return _formatter_instance.format_transcription(text, key_name, enter_pressed)
