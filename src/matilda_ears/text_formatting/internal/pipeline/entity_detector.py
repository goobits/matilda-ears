#!/usr/bin/env python3
"""Entity detection using SpaCy and custom patterns."""


from ...common import Entity, EntityType, NumberParser
from ...constants import get_resources
from ..nlp_provider import get_nlp
from ...utils import is_inside_entity
from ... import regex_patterns
from ....core.config import setup_logging

logger = setup_logging(__name__, log_filename="text_formatting.txt")


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

    def detect_entities(self, text: str, existing_entities: list[Entity], doc=None) -> list[Entity]:
        """Single pass entity detection"""
        entities: list[Entity] = []

        # Only process SpaCy entities in the base detector
        # Pass the existing_entities list for the overlap check
        self._process_spacy_entities(text, entities, existing_entities, doc=doc)

        # Sorting is no longer needed here as the main formatter will sort the final list.
        return entities

    def _process_spacy_entities(self, text: str, entities: list[Entity], existing_entities: list[Entity], doc=None) -> None:
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
                    if not is_inside_entity(ent.start_char, ent.end_char, existing_entities):
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
                            # Find the corresponding token and next token
                            ordinal_token = None
                            next_token = None
                            for token in doc:
                                if token.idx == ent.start_char:
                                    ordinal_token = token
                                    if token.i + 1 < len(doc):
                                        next_token = doc[token.i + 1]
                                    break

                            # Check for specific idiomatic contexts using POS tags
                            if ordinal_token and next_token:
                                # RULE 1: Skip if it's an adjective followed by a specific idiomatic noun from our resources.
                                if ordinal_token.pos_ == "ADJ" and next_token.pos_ == "NOUN":
                                    # This is the key: we check our i18n file for specific exceptions.
                                    idiomatic_phrases = self.resources.get("technical", {}).get("idiomatic_phrases", {})
                                    if ordinal_token.text.lower() in idiomatic_phrases and next_token.text.lower() in idiomatic_phrases[ordinal_token.text.lower()]:
                                        logger.debug(f"Skipping ORDINAL '{ent.text}' due to idiomatic follower noun '{next_token.text}'.")
                                        continue

                                # RULE 2: Skip if it's at sentence start and followed by comma ("First, we...")
                                if (ordinal_token.i == 0 or ordinal_token.sent.start == ordinal_token.i) and next_token.text == ",":
                                    logger.debug(f"Skipping ORDINAL '{ent.text}' - sentence starter with comma")
                                    continue

                            # RULE 3: Check the i18n resource file for specific phrases as fallback
                            ordinal_text = ent.text.lower()
                            following_text = ""
                            if next_token:
                                following_text = next_token.text.lower()

                            idiomatic_phrases = self.resources.get("technical", {}).get("idiomatic_phrases", {})
                            if ordinal_text in idiomatic_phrases and following_text in idiomatic_phrases[ordinal_text]:
                                logger.debug(f"Skipping ORDINAL '{ordinal_text} {following_text}' - idiomatic phrase from resources")
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

        # Check for contextual number words (one/two) in natural speech
        if self._is_contextual_number_word(ent, text):
            return True

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
            from ... import regex_patterns

            range_match = regex_patterns.SPOKEN_NUMERIC_RANGE_PATTERN.search(ent.text)
            if range_match:
                logger.debug(f"Skipping CARDINAL '{ent.text}' because it matches numeric range pattern")
                return True

        # Check if this individual CARDINAL is part of a larger range pattern
        # Look at the surrounding context to see if it's part of "X to Y" pattern
        from ... import regex_patterns

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

        # Note: Idiomatic "plus" and "times" filtering is handled here using SpaCy POS tagging.
        # This prevents conversion of phrases like "five plus years" or "two times better".
        entity_text_lower = ent.text.lower()
        if self.nlp and (" plus " in entity_text_lower or " times " in entity_text_lower):
            try:
                doc = self.nlp(text) # Ensure we have the doc object

                # Find the first token that starts at or after the end of our entity.
                next_token = None
                for token in doc:
                    if token.idx >= ent.end_char:
                        next_token = token
                        break

                if next_token:
                    # RULE: If a CARDINAL like "five plus" is followed by a NOUN ("years"), it's idiomatic.
                    if next_token.pos_ == "NOUN":
                        logger.debug(f"Skipping CARDINAL '{ent.text}' because it's followed by a NOUN ('{next_token.text}').")
                        return True

                    # RULE: If a CARDINAL like "two times" is followed by a comparative ("better"), it's idiomatic.
                    if next_token.tag_ in ["JJR", "RBR"]: # JJR = Adj, Comparative; RBR = Adv, Comparative
                         logger.debug(f"Skipping CARDINAL '{ent.text}' because it's followed by a comparative ('{next_token.text}').")
                         return True

            except Exception as e:
                logger.warning(f"SpaCy idiomatic check failed for '{ent.text}': {e}")

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

        # Check if the entity text matches a numeric range pattern
        range_match = regex_patterns.SPOKEN_NUMERIC_RANGE_PATTERN.search(ent.text)
        if range_match:
            logger.debug(f"Skipping PERCENT '{ent.text}' because it contains numeric range pattern")
            return True

        return False  # Keep as PERCENT

    def _is_contextual_number_word(self, ent, text: str) -> bool:
        """Check if a number word (one, two) should remain as text in natural speech contexts."""
        # Only check for common number words that often appear in natural speech
        ent_lower = ent.text.lower()
        if ent_lower not in ["one", "two"]:
            return False

        # Get the spaCy doc if available
        doc = None
        if self.nlp:
            try:
                doc = self.nlp(text)
            except Exception:
                pass  # Ignore spaCy errors
        # Get context before and after the entity
        prefix_text = text[: ent.start_char].strip().lower()
        suffix_text = text[ent.end_char :].strip().lower()

        # Get immediate preceding and following words
        prefix_words = prefix_text.split()
        suffix_words = suffix_text.split()

        # Check for determiner context (the one, which one, etc.)
        if prefix_words:
            last_word = prefix_words[-1]
            if last_word in ["the", "which", "any", "every", "each", "either", "neither"]:
                logger.debug(f"Skipping CARDINAL '{ent.text}' - preceded by determiner '{last_word}'")
                return True

        # Check for "one/two of" pattern (one of us, two of them)
        # But NOT for patterns like "page one of ten"
        if suffix_words and suffix_words[0] == "of":
            # Check if preceded by words that indicate enumeration/counting
            if prefix_words:
                last_word = prefix_words[-1]
                # Don't skip if preceded by enumeration words
                if last_word in ["page", "chapter", "section", "part", "volume", "item", "step", "line", "row", "column"]:
                    return False  # This is enumeration context, convert to number
            # Otherwise, it's likely natural speech
            logger.debug(f"Skipping CARDINAL '{ent.text}' - part of '{ent.text} of' pattern")
            return True

        # Check for "or the other" pattern
        if ent_lower == "one" and suffix_text.startswith("or the other"):
            logger.debug(f"Skipping CARDINAL '{ent.text}' - part of 'one or the other'")
            return True

        # Check for "one or two" pattern - common in estimates
        if suffix_words and len(suffix_words) >= 2:
            if suffix_words[0] == "or" and suffix_words[1] in ["one", "two", "three"]:
                logger.debug(f"Skipping CARDINAL '{ent.text}' - part of '{ent.text} or {suffix_words[1]}' pattern")
                return True

        # Also check if preceded by "or" and followed by a general noun
        if prefix_words and suffix_words:
            if prefix_words[-1] == "or" and ent_lower in ["one", "two", "three"]:
                # Check if followed by a plural noun (examples, things, items, etc.)
                if suffix_words[0] in ["examples", "things", "items", "options", "choices", "ways", "methods"]:
                    logger.debug(f"Skipping CARDINAL '{ent.text}' - part of 'X or {ent.text} {suffix_words[0]}' pattern")
                    return True

        # Check if it's followed by a unit (indicates numeric context)
        if suffix_words:
            first_word = suffix_words[0]
            # Check common units
            time_units = self.resources.get("units", {}).get("time_units", [])
            if first_word in time_units or first_word in ["dollar", "dollars", "cent", "cents", "percent"]:
                return False  # This is numeric context, don't skip

        # Check for "X test/thing/item for" pattern - common in natural speech
        if suffix_words and len(suffix_words) >= 2:
            first_word = suffix_words[0]
            second_word = suffix_words[1]
            if first_word in ["test", "tests", "thing", "things", "item", "items", "example", "examples", "issue", "issues", "problem", "problems"] and second_word in ["for", "of"]:
                logger.debug(f"Skipping CARDINAL '{ent.text}' - part of '{ent.text} {first_word} {second_word}' pattern")
                return True

        # Check for "those NUMBER things/issues" pattern
        if prefix_words and prefix_words[-1] == "those":
            if suffix_words and suffix_words[0] in ["things", "items", "issues", "problems", "examples", "cases"]:
                logger.debug(f"Skipping CARDINAL '{ent.text}' - part of 'those {ent.text} {suffix_words[0]}' pattern")
                return True

        # Use SpaCy analysis if available
        if doc and hasattr(ent, "start") and hasattr(ent, "end"):
            try:
                # Find the token(s) that correspond to this entity
                for token in doc:
                    if token.idx == ent.start_char:
                        # Check grammatical role
                        # Skip if it's a determiner or part of a noun phrase (not numeric)
                        if token.dep_ in ["det", "nsubj", "dobj", "pobj"]:
                            # But allow if followed by a unit
                            if token.i + 1 < len(doc):
                                next_token = doc[token.i + 1]
                                if next_token.text.lower() not in time_units:
                                    logger.debug(f"Skipping CARDINAL '{ent.text}' - grammatical role: {token.dep_}")
                                    return True
                        break
            except Exception as e:
                logger.debug(f"SpaCy analysis failed: {e}")

        # Additional patterns for "two"
        if ent_lower == "two":
            # "between the two" pattern
            if prefix_text.endswith("between the"):
                logger.debug(f"Skipping CARDINAL '{ent.text}' - part of 'between the two'")
                return True
            # "the two of" pattern
            if prefix_text.endswith("the") and suffix_text.startswith("of"):
                logger.debug(f"Skipping CARDINAL '{ent.text}' - part of 'the two of'")
                return True

        # Check for subject position at sentence start
        if ent.start_char == 0 or (ent.start_char > 0 and text[ent.start_char - 1] in ".!?"):
            # At sentence start - check if followed by a verb (indicates subject)
            if suffix_words and len(suffix_words) > 1:
                # Simple heuristic: if followed by "can", "should", "will", etc., it's likely a subject
                if suffix_words[0] in ["can", "should", "will", "would", "might", "could", "must", "may"]:
                    logger.debug(f"Skipping CARDINAL '{ent.text}' - sentence subject before modal verb")
                    return True

        return False


