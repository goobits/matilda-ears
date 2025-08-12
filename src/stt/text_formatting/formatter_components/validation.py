#!/usr/bin/env python3
"""
Entity validation and filtering module.

This module contains logic for validating and filtering entities based on context,
extracted from entity_detector.py for better modularity and maintainability.
"""
from __future__ import annotations

import contextlib
import re

from ...core.config import setup_logging
from ..constants import get_resources

# Setup logging
logger = setup_logging(__name__)


class EntityValidator:
    """Handles entity validation and filtering based on context."""

    def __init__(self, nlp, language: str = "en"):
        """
        Initialize EntityValidator.

        Args:
            nlp: SpaCy NLP model instance
            language: Language code for resource loading (default: 'en')
        """
        self.nlp = nlp
        self.language = language
        self.resources = get_resources(language)

    def should_skip_cardinal(self, ent, text: str) -> bool:
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

        # Check for specific idiomatic patterns (existing patterns)
        if ent.text.lower() == "twenty two" and prefix_text.endswith("catch"):
            logger.debug(f"Skipping CARDINAL '{ent.text}' because it's part of 'catch twenty two'.")
            return True

        if ent.text.lower() == "nine" and prefix_text.endswith("cloud"):
            logger.debug(f"Skipping CARDINAL '{ent.text}' because it's part of 'cloud nine'.")
            return True

        if ent.text.lower() == "eight" and "behind the" in prefix_text:
            logger.debug(f"Skipping CARDINAL '{ent.text}' because it's part of 'behind the eight ball'.")
            return True
        
        # Comprehensive idiom protection using resource patterns
        if self._is_in_protected_idiom(ent, text):
            return True

        # Check if this looks like a numeric range pattern (e.g., "ten to twenty")
        # This should be handled by the specialized range detector
        if " to " in ent.text.lower():
            # Check if it matches our range pattern
            from .. import regex_patterns

            range_match = regex_patterns.SPOKEN_NUMERIC_RANGE_PATTERN.search(ent.text)
            if range_match:
                logger.debug(f"Skipping CARDINAL '{ent.text}' because it matches numeric range pattern")
                return True

        # Check if this individual CARDINAL is part of a larger range pattern
        # Look at the surrounding context to see if it's part of "X to Y" pattern
        from .. import regex_patterns

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
                logger.debug(
                    f"Skipping CARDINAL '{ent.text}' because it's part of range pattern '{range_match.group()}'"
                )
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
        
        # Check if the entity text contains "plus" or "times", OR if it's followed by them
        remaining_text = text[ent.end_char:].strip().lower()
        has_plus_times_in_entity = " plus " in entity_text_lower or " times " in entity_text_lower
        has_plus_times_after = remaining_text.startswith("plus ") or remaining_text.startswith("times ")
        
        if has_plus_times_in_entity or has_plus_times_after:
            # If SpaCy is available, use POS tagging for more accurate detection
            if self.nlp:
                try:
                    doc = self.nlp(text)  # Ensure we have the doc object

                    # Find the first token that starts at or after the end of our entity.
                    next_token = None
                    for token in doc:
                        if token.idx >= ent.end_char:
                            next_token = token
                            break

                    if next_token:
                        # RULE: If a CARDINAL like "five plus" is followed by a NOUN ("years"), it's idiomatic.
                        if next_token.pos_ == "NOUN":
                            logger.debug(
                                f"Skipping CARDINAL '{ent.text}' because it's followed by a NOUN ('{next_token.text}')."
                            )
                            return True

                        # RULE: If a CARDINAL like "two times" is followed by a comparative ("better"), it's idiomatic.
                        if next_token.tag_ in ["JJR", "RBR"]:  # JJR = Adj, Comparative; RBR = Adv, Comparative
                            logger.debug(
                                f"Skipping CARDINAL '{ent.text}' because it's followed by a comparative ('{next_token.text}')."
                            )
                            return True

                except Exception as e:
                    logger.warning(f"SpaCy idiomatic check failed for '{ent.text}': {e}")
            
            # Fallback: Simple word-based detection when SpaCy is not available
            else:
                remaining_words = remaining_text.split()
                if remaining_words:
                    # If followed by "plus" or "times" and then common words that indicate idiomatic usage
                    if (remaining_words[0] in ["plus", "times"] and len(remaining_words) > 1):
                        next_word = remaining_words[1]
                        # Common words that follow "plus" or "times" in idiomatic expressions
                        idiomatic_words = ["years", "months", "weeks", "days", "hours", "minutes", "experience", 
                                         "better", "faster", "stronger", "larger", "smaller", "more"]
                        if next_word in idiomatic_words:
                            logger.debug(f"Skipping CARDINAL '{ent.text}' because it's followed by idiomatic '{remaining_words[0]} {next_word}' pattern")
                            return True

        return False
    
    def _is_in_protected_idiom(self, ent, text: str) -> bool:
        """
        Check if the entity is part of a protected idiom using comprehensive patterns.
        """
        # Get wider context around the entity
        context_start = max(0, ent.start_char - 50)
        context_end = min(len(text), ent.end_char + 50)
        context = text[context_start:context_end].lower()
        
        # Check idiom patterns from resources
        idiom_patterns = self.resources.get("idiom_protection", {}).get("idiom_context_patterns", [])
        for pattern in idiom_patterns:
            # Remove double backslashes from the pattern (they're for JSON escaping)
            clean_pattern = pattern.replace('\\\\', '\\')
            if re.search(clean_pattern, context, re.IGNORECASE):
                logger.debug(f"Skipping CARDINAL '{ent.text}' because it's part of protected idiom pattern: {clean_pattern}")
                return True
        
        # Check specific exception phrases that might contain this entity
        number_unit_exceptions = self.resources.get("idiom_protection", {}).get("number_unit_exceptions", {})
        for exception_phrase in number_unit_exceptions.keys():
            if exception_phrase.lower() in context:
                # Check if our entity is actually part of this exception phrase
                phrase_start = context.find(exception_phrase.lower())
                if phrase_start != -1:
                    # Convert back to original text coordinates
                    abs_phrase_start = context_start + phrase_start
                    abs_phrase_end = abs_phrase_start + len(exception_phrase)
                    
                    # Check if our entity overlaps with this phrase
                    if not (ent.end_char <= abs_phrase_start or ent.start_char >= abs_phrase_end):
                        logger.debug(f"Skipping CARDINAL '{ent.text}' because it's part of protected idiom: '{exception_phrase}'")
                        return True
        
        return False

    def should_skip_quantity(self, ent, text: str) -> bool:
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

    def should_skip_money(self, ent, text: str) -> bool:
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

    def should_skip_date(self, ent, text: str) -> bool:
        """Check if a DATE entity should be skipped because it's likely an ordinal context."""
        if ent.label_ != "DATE":
            return False

        entity_text = ent.text.lower()

        # Keep DATE entities that contain actual month names
        month_names = self.resources.get("temporal", {}).get("month_names", [])
        if any(month in entity_text for month in month_names):
            # However, check if this is a context where we want ordinal conversion
            # (e.g., "January first meeting" -> "January 1st meeting")
            date_ordinal_words = self.resources.get("temporal", {}).get("date_ordinals", [])
            has_ordinal = any(ordinal in entity_text for ordinal in date_ordinal_words)
            
            if has_ordinal:
                # Check the context after the DATE entity to see if it's non-date context
                suffix_text = text[ent.end_char:].strip().lower()
                non_date_contexts = ["meeting", "conference", "report", "quarter", "generation", "party", "place", "winner", "performance", "time", "item", "agenda", "step", "process", "option", "available", "deadline"]
                
                if any(context in suffix_text for context in non_date_contexts):
                    logger.debug(f"Skipping DATE '{ent.text}' - contains month but followed by non-date context '{suffix_text[:20]}'")
                    return True  # Skip this DATE to allow ORDINAL processing
            
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

    def should_skip_percent(self, ent, text: str) -> bool:
        """Check if a PERCENT entity should be skipped because it's actually a numeric range."""
        if ent.label_ != "PERCENT":
            return False

        # Check if this PERCENT entity contains a range pattern (e.g., "five to ten percent")
        from .. import regex_patterns

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
            with contextlib.suppress(Exception):
                doc = self.nlp(text)

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
                if last_word in [
                    "page",
                    "chapter",
                    "section",
                    "part",
                    "volume",
                    "item",
                    "step",
                    "line",
                    "row",
                    "column",
                ]:
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
                    logger.debug(
                        f"Skipping CARDINAL '{ent.text}' - part of 'X or {ent.text} {suffix_words[0]}' pattern"
                    )
                    return True

        # Check if it's followed by a unit (indicates numeric context)
        if suffix_words:
            first_word = suffix_words[0]
            # Check common units
            time_units = self.resources.get("units", {}).get("time_units", [])
            if first_word in time_units or first_word in ["dollar", "dollars", "cent", "cents", "percent"]:
                return False  # This is numeric context, don't skip

        # Check for "X test/thing/item for" pattern - common in natural speech
        if suffix_words and len(suffix_words) >= 1:
            first_word = suffix_words[0]
            if first_word in [
                "test",
                "tests",
                "thing",
                "things",
                "item",
                "items",
                "example",
                "examples",
                "issue",
                "issues",
                "problem",
                "problems",
            ]:
                # For most words, require specific context words after them
                if len(suffix_words) >= 2:
                    second_word = suffix_words[1]
                    if second_word in ["for", "of"]:
                        logger.debug(
                            f"Skipping CARDINAL '{ent.text}' - part of '{ent.text} {first_word} {second_word}' pattern"
                        )
                        return True
                
                # Special case for "thing" - can be followed by any word in natural speech
                if first_word in ["thing", "things"]:
                    logger.debug(
                        f"Skipping CARDINAL '{ent.text}' - part of '{ent.text} {first_word}' pattern"
                    )
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
                                time_units = self.resources.get("units", {}).get("time_units", [])
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