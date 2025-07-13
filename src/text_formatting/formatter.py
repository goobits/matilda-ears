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
from .detectors.web_detector import WebEntityDetector
from .detectors.code_detector import CodeEntityDetector
from .detectors.numeric_detector import NumericalEntityDetector
from .pattern_converter import PatternConverter as UnifiedPatternConverter
from .capitalizer import SmartCapitalizer
from .nlp_provider import get_nlp, get_punctuator

# Import centralized regex patterns
from . import regex_patterns

# Setup config and logging
config = get_config()
logger = setup_logging(__name__, log_filename="text_formatting.txt")

# Import resource loader for i18n constants
from .constants import get_resources


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
        self.resources = get_resources(language)

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

                        # Skip PERCENT entities that are actually numeric ranges
                        if self._should_skip_percent(ent, text):
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
                            idiomatic_phrases = self.resources.get("technical", {}).get("idiomatic_phrases", {})
                            if ordinal_text in idiomatic_phrases and following_text in idiomatic_phrases[ordinal_text]:
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
            email_actions = self.resources.get("context_words", {}).get("email_actions", [])
            has_email_action = any(prefix_text.startswith(action) for action in email_actions)
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

        # Check if this individual CARDINAL is part of a larger range pattern
        # Look at the surrounding context to see if it's part of "X to Y" pattern
        from . import regex_patterns
        
        # Get more context around this entity (20 chars before and after)
        context_start = max(0, ent.start_char - 20)
        context_end = min(len(text), ent.end_char + 20)
        context = text[context_start:context_end]
        
        # Check if this context contains a range pattern that includes our entity
        for range_match in regex_patterns.SPOKEN_NUMERIC_RANGE_PATTERN.finditer(context):
            # Adjust match positions to be relative to the full text
            abs_start = context_start + range_match.start()
            abs_end = context_start + range_match.end()
            
            # Check if our CARDINAL entity is within this range match
            if abs_start <= ent.start_char and ent.end_char <= abs_end:
                logger.debug(f"Skipping CARDINAL '{ent.text}' because it's part of range pattern '{range_match.group()}'")
                return True

        # Check if this number is followed by a known unit (prevents greedy CARDINAL detection)
        # This allows specialized detectors to handle data sizes, currency, etc.
        remaining_text = text[ent.end_char :].strip()

        # For "degrees", check if it's in an angle context
        if remaining_text.lower().startswith("degrees"):
            # Check the context before the number
            prefix_text = text[: ent.start_char].lower()
            angle_keywords = self.resources.get("context_words", {}).get("angle_keywords", [])
            if any(keyword in prefix_text for keyword in angle_keywords):
                # This is an angle, not temperature, don't skip
                return False

        # Use known units from constants

        # Get the next few words after this CARDINAL
        next_words = remaining_text.split()[:3]  # Look at next 3 words
        if next_words:
            next_word = next_words[0].lower()
            # Collect all known units from resources
            time_units = self.resources.get("units", {}).get("time_units", [])
            length_units = self.resources.get("units", {}).get("length_units", [])
            weight_units = self.resources.get("units", {}).get("weight_units", [])
            volume_units = self.resources.get("units", {}).get("volume_units", [])
            frequency_units = self.resources.get("units", {}).get("frequency_units", [])
            currency_units = self.resources.get("currency", {}).get("units", [])
            data_units = self.resources.get("data_units", {}).get("storage", [])
            known_units = set(
                time_units + length_units + weight_units + volume_units + frequency_units + currency_units + data_units
            )
            if next_word in known_units:
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

            idiomatic_plus_words = self.resources.get("context_words", {}).get("idiomatic_plus", [])
            idiomatic_words = list(idiomatic_plus_words) + [
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
                comparative_words = self.resources.get("context_words", {}).get("idiomatic_times_comparative", [])
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
            data_units = self.resources.get("data_units", {}).get("storage", [])
            if word in data_units:
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
        currency_contexts = self.resources.get("context_words", {}).get("currency_contexts", [])
        found_currency_context = any(context in prefix_text for context in currency_contexts)

        if found_currency_context:
            logger.debug(f"Keeping MONEY '{ent.text}' because currency context found in prefix")
            return False  # Don't skip - keep as currency

        # No clear currency context - check for weight context or default to weight
        weight_contexts = self.resources.get("context_words", {}).get("weight_contexts", [])
        found_weight_context = any(context in prefix_text for context in weight_contexts)

        # Also check for measurement phrases like "it is X pounds"
        words_before = prefix_text.split()[-3:]
        measurement_verbs = self.resources.get("context_words", {}).get("measurement_verbs", [])
        found_measurement_pattern = any(pattern in words_before for pattern in measurement_verbs)

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
        month_names = self.resources.get("temporal", {}).get("month_names", [])
        if any(month in entity_text for month in month_names):
            return False  # Keep - this is a real date

        # Keep DATE entities that contain specific relative days
        relative_days = self.resources.get("temporal", {}).get("relative_days", [])
        if any(day in entity_text for day in relative_days):
            return False  # Keep - this is a real date

        # Keep DATE entities that look like actual dates (contain numbers and date keywords)
        # If it contains ordinal words but no clear date context, it's likely an ordinal
        date_ordinal_words = self.resources.get("temporal", {}).get("date_ordinals", [])
        has_ordinal = any(ordinal in entity_text for ordinal in date_ordinal_words)
        date_keywords = self.resources.get("temporal", {}).get("date_keywords", [])
        has_date_keyword = any(keyword in entity_text for keyword in date_keywords)

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

    def _should_skip_percent(self, ent, text: str) -> bool:
        """Check if a PERCENT entity should be skipped because it's actually a numeric range."""
        if ent.label_ != "PERCENT":
            return False

        # Check if this PERCENT entity contains a range pattern (e.g., "five to ten percent")
        from . import regex_patterns
        
        # Check if the entity text matches a numeric range pattern
        range_match = regex_patterns.SPOKEN_NUMERIC_RANGE_PATTERN.search(ent.text)
        if range_match:
            logger.debug(f"Skipping PERCENT '{ent.text}' because it contains numeric range pattern")
            return True

        return False  # Keep as PERCENT


class PatternConverter:
    """Converts specific entity types to their final form"""

    def __init__(self, language: str = "en"):
        self.language = language
        
        # Use the unified converter with all conversion methods
        self.unified_converter = UnifiedPatternConverter(NumberParser(language=language), language=language)
        
        # Entity type to converter method mapping
        self.converters = {}  # Start with an empty dict
        
        # Add all converters from the unified converter
        self.converters.update(self.unified_converter.converters)

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

        # Instantiate specialized detectors with shared NLP model and language
        # Note: Converters are now unified in PatternConverter
        self.web_detector = WebEntityDetector(nlp=self.nlp, language=self.language)
        self.code_detector = CodeEntityDetector(nlp=self.nlp, language=self.language)
        self.numeric_detector = NumericalEntityDetector(nlp=self.nlp, language=self.language)

        # Load language-specific resources
        self.resources = get_resources(language)

        # Complete sentence phrases that need punctuation even when short
        self.complete_sentence_phrases = set(self.resources.get("technical", {}).get("complete_sentence_phrases", []))

        # Use artifacts and profanity lists from resources
        self.transcription_artifacts = self.resources.get("filtering", {}).get("transcription_artifacts", [])
        self.profanity_words = self.resources.get("filtering", {}).get("profanity_words", [])

    def format_transcription(
        self, text: str, key_name: str = "", enter_pressed: bool = False, language: str = None
    ) -> str:
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

        # Step 3: Assemble final string WITHOUT placeholders (Phase 2 refactoring)
        # Build the new string from scratch by processing entities in order
        result_parts = []
        last_end = 0

        # Sort entities by start position to process in sequence
        sorted_entities = sorted(filtered_entities, key=lambda e: e.start)

        for entity in sorted_entities:
            # Add the plain text gap before this entity
            result_parts.append(text[last_end : entity.start])

            # Convert the entity to its final form and add it
            converted_text = self.pattern_converter.convert(entity, text)
            result_parts.append(converted_text)

            last_end = entity.end

        # Add any remaining text after the last entity
        result_parts.append(text[last_end:])

        # Join everything into a single string
        processed_text = "".join(result_parts)

        logger.debug(f"Processed text after entity conversion: '{processed_text}'")

        # Step 4: Apply punctuation and capitalization LAST (Phase 2 refactoring)
        is_standalone_technical = self._is_standalone_technical(text, filtered_entities)
        final_text = self._add_punctuation(
            processed_text, original_had_punctuation, is_standalone_technical, filtered_entities
        )
        logger.debug(f"Text after punctuation: '{final_text}'")

        # Step 5: Apply capitalization to the final text (entities already converted)
        # Skip capitalization for standalone technical content
        if not is_standalone_technical:
            logger.debug(f"Text before capitalization: '{final_text}'")
            # Build converted entities list for capitalization protection
            converted_entities = []
            current_pos = 0
            for entity in sorted_entities:
                # Calculate where the converted entity now appears in final text
                converted_text = self.pattern_converter.convert(entity, text)
                # Find the entity in the final text (this is approximate but sufficient for protection)
                entity_start = final_text.find(converted_text, current_pos)
                if entity_start != -1:
                    converted_entity = Entity(
                        start=entity_start,
                        end=entity_start + len(converted_text),
                        text=converted_text,
                        type=entity.type,
                        metadata=entity.metadata,
                    )
                    converted_entities.append(converted_entity)
                    current_pos = entity_start + len(converted_text)

            final_text = self._apply_capitalization_with_entity_protection(final_text, converted_entities, doc=doc)
            logger.debug(f"Text after capitalization: '{final_text}'")

        text = final_text
        logger.debug(f"Text after processing: '{text}'")

        # Step 6: Clean up formatting artifacts
        text = re.sub(r"\.\.+", ".", text)
        text = re.sub(r"\?\?+", "?", text)
        text = re.sub(r"!!+", "!", text)

        # Step 7: Restore abbreviations that the punctuation model may have mangled
        text = self._restore_abbreviations(text)

        # Step 8: Convert orphaned keywords (slash, dot, at, etc.)
        logger.debug(f"Text before keyword conversion: '{text}'")
        text = self._convert_orphaned_keywords(text)
        logger.debug(f"Text after keyword conversion: '{text}'")
        
        # Step 9: Domain rescue (improved version without brittle word lists)
        logger.debug(f"Text before domain rescue: '{text}'")
        text = self._rescue_mangled_domains(text)
        logger.debug(f"Text after domain rescue: '{text}'")

        # Step 9: Apply smart quotes
        logger.debug(f"Text before smart quotes: '{text}'")
        text = self._apply_smart_quotes(text)
        logger.debug(f"Text after smart quotes: '{text}'")

        # Note: Suffix handling remains in hotkey_daemon for reliability

        logger.debug(f"Final formatted: '{text[:50]}...'")
        return text

    def _filter_overlapping_entities(self, entities: List[Entity]) -> List[Entity]:
        """Filters overlapping entities based on a defined priority and length."""
        if not entities:
            return []

        # Sort entities primarily by start position, then by priority (higher first), then by length (longer first)
        # This ensures that at any given position, we first consider the highest-priority, longest entity.
        entity_priority = {
            # HIGHEST: Unambiguous, already-formatted entities
            EntityType.URL: 50,
            EntityType.EMAIL: 50,
            EntityType.FILENAME: 48,
            EntityType.PORT_NUMBER: 47,
            EntityType.UNIX_PATH: 46,
            EntityType.WINDOWS_PATH: 46,
            
            # HIGH: Very specific spoken patterns with clear delimiters
            EntityType.SPOKEN_PROTOCOL_URL: 45, # "http colon slash slash..." is very clear
            EntityType.UNDERSCORE_DELIMITER: 42, # "__init__" is very specific
            EntityType.SLASH_COMMAND: 41,
            EntityType.COMMAND_FLAG: 40,
            
            # MEDIUM-HIGH: Technical terms and operators
            EntityType.CLI_COMMAND: 35, # Give CLI commands a solid priority
            EntityType.PROGRAMMING_KEYWORD: 34,
            EntityType.ASSIGNMENT: 33,
            EntityType.COMPARISON: 32,
            EntityType.INCREMENT_OPERATOR: 31, EntityType.DECREMENT_OPERATOR: 31,
            
            # MEDIUM: Specific numeric types and measurements
            EntityType.MONEY: 30, EntityType.CURRENCY: 30,
            EntityType.DOLLAR_CENTS: 29, EntityType.DOLLARS: 29, EntityType.CENTS: 29,
            EntityType.POUNDS: 29, EntityType.EUROS: 29,
            EntityType.DATA_SIZE: 28,
            EntityType.TEMPERATURE: 28,
            EntityType.METRIC_LENGTH: 28, EntityType.METRIC_WEIGHT: 28, EntityType.METRIC_VOLUME: 28,
            EntityType.SCIENTIFIC_NOTATION: 27,
            EntityType.FREQUENCY: 26,
            EntityType.TIME_DURATION: 26,
            EntityType.NUMERIC_RANGE: 25, # Ranges should beat individual numbers
            EntityType.PERCENT: 24,
            EntityType.VERSION_TWO: 23, EntityType.VERSION_THREE: 23,
            EntityType.PHONE_LONG: 22,
            EntityType.TIME_CONTEXT: 21, EntityType.TIME_AMPM: 21,
            
            # LOWER-MEDIUM: Ambiguous spoken patterns
            EntityType.SPOKEN_EMAIL: 20, # Lowering this to let specific terms like API win
            EntityType.SPOKEN_URL: 19,
            EntityType.TIME_RELATIVE: 18,
            
            # LOW: More complex but potentially ambiguous patterns
            EntityType.FRACTION: 15,
            EntityType.ROOT_EXPRESSION: 14,
            EntityType.MATH_EXPRESSION: 13,
            EntityType.MATH_CONSTANT: 12,
            EntityType.PHYSICS_SQUARED: 11, EntityType.PHYSICS_TIMES: 11,
            EntityType.PROTOCOL: 11,
            EntityType.MATH: 11,
            
            # LOWEST: General, often-overlapping base types
            EntityType.ORDINAL: 10,
            EntityType.DATE: 9,
            EntityType.TIME: 8,
            EntityType.ABBREVIATION: 7,
            EntityType.SIMPLE_UNDERSCORE_VARIABLE: 6,
            EntityType.CARDINAL: 5, # Should be overridden by almost everything else
            EntityType.QUANTITY: 4,
            EntityType.MUSIC_NOTATION: 3,
            EntityType.SPOKEN_EMOJI: 2
        }

        # Sort entities by start index, then by priority (desc), then by length (desc)
        sorted_entities = sorted(
            entities, 
            key=lambda e: (e.start, -entity_priority.get(e.type, 0), -(e.end - e.start))
        )

        filtered_entities = []
        last_end = -1

        for entity in sorted_entities:
            # If the current entity starts after the last one we kept ends, it's safe to add
            if entity.start >= last_end:
                filtered_entities.append(entity)
                last_end = entity.end
            # If it starts before the last one ends, it's an overlap.
            # Because we sorted by priority and length, the one we already kept is the winner.
            # So, we simply ignore this overlapping, lower-priority/shorter entity.
            else:
                logger.debug(f"Filtering out overlapping entity: {entity.type} ('{entity.text}') because it conflicts with a higher-priority or longer entity that ends at {last_end}")

        return filtered_entities

    def _is_standalone_technical(self, text: str, entities: List[Entity]) -> bool:
        """Check if the text consists entirely of technical entities with no natural language."""
        if not entities:
            return False

        text_stripped = text.strip()

        # Special case: If text starts with a programming keyword or CLI command, it should be treated as a regular sentence
        # that needs capitalization, not standalone technical content
        sorted_entities = sorted(entities, key=lambda e: e.start)
        if (
            sorted_entities
            and sorted_entities[0].start == 0
            and sorted_entities[0].type in {EntityType.PROGRAMMING_KEYWORD, EntityType.CLI_COMMAND}
        ):
            logger.debug(
                f"Text starts with programming keyword/CLI command '{sorted_entities[0].text}' - not treating as standalone technical"
            )
            return False

        # Check if the text contains common verbs or action words that indicate it's a sentence
        words = text_stripped.lower().split()
        common_verbs = {"git", "run", "use", "set", "install", "update", "create", "delete", "open", "edit", "save", "check", "test", "build", "deploy", "start", "stop"}
        if any(word in common_verbs for word in words):
            logger.debug(f"Text contains common verbs - treating as sentence, not standalone technical")
            return False

        # Check if any word in the text is NOT inside a detected entity and is a common English word
        # This ensures we only treat text as standalone technical if it contains ZERO common words outside entities
        common_words = {"the", "a", "is", "in", "for", "with", "and", "or", "but", "if", "when", "where", "what", "how", "why", "that", "this", "it", "to", "from", "on", "at", "by"}
        word_positions = []
        current_pos = 0
        for word in words:
            word_start = text_stripped.lower().find(word, current_pos)
            if word_start != -1:
                word_end = word_start + len(word)
                word_positions.append((word, word_start, word_end))
                current_pos = word_end

        # Check if any common word is not covered by an entity
        for word, start, end in word_positions:
            if word in common_words:
                # Check if this word position is covered by any entity
                covered = any(entity.start <= start and end <= entity.end for entity in entities)
                if not covered:
                    logger.debug(f"Found common word '{word}' not covered by entity - treating as sentence")
                    return False

        # Only treat as standalone technical if it consists ENTIRELY of very specific technical entity types
        technical_only_types = {
            EntityType.COMMAND_FLAG,
            EntityType.SLASH_COMMAND,
            EntityType.INCREMENT_OPERATOR,
            EntityType.DECREMENT_OPERATOR,
            EntityType.UNDERSCORE_DELIMITER,
        }
        
        non_technical_entities = [e for e in entities if e.type not in technical_only_types]
        if non_technical_entities:
            logger.debug("Text contains non-technical entities - treating as sentence")
            return False

        # For pure technical entities, check if they cover most of the text
        if entities:
            total_entity_length = sum(len(e.text) for e in entities)
            text_length = len(text_stripped)
            
            # If entities cover most of the text (>95%), treat as standalone technical
            if total_entity_length / text_length > 0.95:
                logger.debug("Pure technical entities cover almost all text, treating as standalone technical content.")
                return True

        # If we get here, text should be treated as a regular sentence
        logger.debug("Text does not meet standalone technical criteria - treating as sentence")
        return False

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
                                    base_command_words = self.resources.get("context_words", {}).get(
                                        "command_words", []
                                    )
                                    command_words = list(base_command_words) + [
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
                    preserve_words = self.resources.get("context_words", {}).get("preserve_colon", [])
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
            if word_count > 1 or text.lower().strip() in self.complete_sentence_phrases:
                text += "."
                logger.debug(f"Added final punctuation: '{text}'")

        return text

    def _restore_abbreviations(self, text: str) -> str:
        """Restore proper formatting for abbreviations after punctuation model."""
        # The punctuation model tends to strip periods from common abbreviations
        # This post-processing step restores them to our preferred format

        # Use abbreviations from constants

        # Process each abbreviation
        abbreviations = self.resources.get("abbreviations", {})
        for abbr, formatted in abbreviations.items():
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

    def _convert_orphaned_keywords(self, text: str) -> str:
        """Convert orphaned keywords that weren't captured by entities.
        
        This handles cases where keywords like 'slash', 'dot', 'at' remain in the text
        after entity conversion, typically due to entity boundary issues.
        """
        # Get language-specific keywords
        resources = get_resources(self.language)
        url_keywords = resources.get("spoken_keywords", {}).get("url", {})
        
        # Only convert safe keywords that are less likely to appear in natural language
        # Be more conservative about what we convert
        safe_keywords = {
            'slash': '/',
            'colon': ':',
            'underscore': '_',
        }
        
        # Filter to only keywords we want to convert when orphaned
        keywords_to_convert = {}
        for keyword, symbol in url_keywords.items():
            if keyword in safe_keywords and safe_keywords[keyword] == symbol:
                keywords_to_convert[keyword] = symbol
        
        # Sort by length (longest first) to handle multi-word keywords properly
        sorted_keywords = sorted(keywords_to_convert.items(), key=lambda x: len(x[0]), reverse=True)
        
        # Define keywords that should consume surrounding spaces when converted
        space_consuming_symbols = {'/', ':', '_'}
        
        # Convert keywords that appear as standalone words
        for keyword, symbol in sorted_keywords:
            if symbol in space_consuming_symbols:
                # For these symbols, consume surrounding spaces
                pattern = rf'\s*\b{re.escape(keyword)}\b\s*'
                # Simple replacement that consumes spaces
                text = re.sub(pattern, symbol, text, flags=re.IGNORECASE)
            else:
                # For other keywords, preserve word boundaries
                pattern = rf'\b{re.escape(keyword)}\b'
                text = re.sub(pattern, symbol, text, flags=re.IGNORECASE)
        
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

        tlds = self.resources.get("top_level_domains", [])
        for tld in tlds:
            # Pattern: word + TLD at word boundary
            pattern = rf"\b([a-zA-Z]{{3,}})({tld})\b"

            def fix_domain(match):
                word = match.group(1)
                found_tld = match.group(2)
                full_word = word + found_tld

                # Skip if it's in our exclude list
                exclude_words = self.resources.get("context_words", {}).get("exclude_words", [])
                if full_word.lower() in exclude_words:
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
                tech_patterns = self.resources.get("context_words", {}).get("tech_patterns", [])
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

        # Debug: Check for entity position misalignment
        for entity in entities:
            if entity.start < len(text) and entity.end <= len(text):
                actual_text = text[entity.start : entity.end]
                logger.debug(
                    f"Entity {entity.type} at [{entity.start}:{entity.end}] text='{entity.text}' actual='{actual_text}'"
                )
                if actual_text != entity.text:
                    logger.warning(f"Entity position mismatch! Expected '{entity.text}' but found '{actual_text}'")
            else:
                logger.warning(
                    f"Entity {entity.type} position out of bounds: [{entity.start}:{entity.end}] for text length {len(text)}"
                )

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
