#!/usr/bin/env python3
"""File and path-related entity detection for code transcriptions."""
from __future__ import annotations

from stt.core.config import setup_logging
from stt.text_formatting import regex_patterns
from stt.text_formatting.common import Entity, EntityType
from stt.text_formatting.constants import get_resources
from stt.text_formatting.utils import overlaps_with_entity

logger = setup_logging(__name__, log_filename="text_formatting.txt", include_console=False)


class FileDetector:
    """Detects file and path-related entities like filenames and packages."""

    def __init__(self, nlp=None, language: str = "en"):
        """
        Initialize FileDetector.

        Args:
            nlp: SpaCy NLP model instance. If None, will load from nlp_provider.
            language: Language code for resource loading (default: 'en')
        """
        if nlp is None:
            from stt.text_formatting.nlp_provider import get_nlp

            nlp = get_nlp()

        self.nlp = nlp
        self.language = language
        self.resources = get_resources(language)

    def detect_filenames(self, text: str, entities: list[Entity], all_entities: list[Entity] | None = None) -> None:
        """Detect filenames using a simple regex anchor and robust spaCy context analysis."""
        if all_entities is None:
            all_entities = entities

        # --- Part 1: Handle already-formatted files first (e.g., main.py, com.example.app) ---
        for match in regex_patterns.FILENAME_WITH_EXTENSION_PATTERN.finditer(text):
            if not overlaps_with_entity(match.start(), match.end(), all_entities):
                new_entity = Entity(start=match.start(), end=match.end(), text=match.group(0), type=EntityType.FILENAME)
                entities.append(new_entity)
                all_entities.append(new_entity)

        for match in regex_patterns.JAVA_PACKAGE_PATTERN.finditer(text):
            if not overlaps_with_entity(match.start(), match.end(), all_entities):
                package_text = match.group(1).lower()
                common_prefixes = ["com dot", "org dot", "net dot", "io dot", "gov dot", "edu dot"]
                if any(package_text.startswith(prefix) for prefix in common_prefixes):
                    new_entity = Entity(
                        start=match.start(),
                        end=match.end(),
                        text=match.group(0),
                        type=EntityType.FILENAME,
                        metadata={"is_package": True},
                    )
                    entities.append(new_entity)
                    all_entities.append(new_entity)

        # --- Part 2: Handle spoken filenames ("my file dot py") with a robust, non-greedy method ---
        if not self.nlp:
            logger.debug("SpaCy model not available. Using regex fallback for spoken filename detection.")
            self._detect_filenames_regex_fallback(text, entities, all_entities)
            return

        entities_before_spacy = len(entities)

        try:
            doc = self.nlp(text)
        except (AttributeError, ValueError, IndexError) as e:
            logger.warning(f"SpaCy filename detection failed: {e}")
            self._detect_filenames_regex_fallback(text, entities, all_entities)
            return

        end_char_to_token = {token.idx + len(token.text): token for token in doc}

        for match in regex_patterns.SPOKEN_DOT_FILENAME_PATTERN.finditer(text):
            if overlaps_with_entity(match.start(), match.end(), all_entities):
                continue

            logger.debug(
                f"SPACY FILENAME: Found 'dot extension' match: '{match.group()}' at {match.start()}-{match.end()}"
            )

            if " at " in text[max(0, match.start() - 10) : match.start()]:
                continue

            start_of_dot = match.start()
            if start_of_dot not in end_char_to_token:
                logger.debug(f"SPACY FILENAME: No token ends at position {start_of_dot}, skipping")
                continue

            current_token = end_char_to_token[start_of_dot]
            filename_tokens: list = []

            # Walk backwards from the token before "dot"
            for i in range(current_token.i, -1, -1):
                token = doc[i]

                # ** THE CRITICAL STOPPING LOGIC **
                # Get language-specific filename stop words from i18n resources
                filename_actions = self.resources.get("context_words", {}).get("filename_actions", [])
                filename_linking = self.resources.get("context_words", {}).get("filename_linking", [])
                filename_stop_words = self.resources.get("context_words", {}).get("filename_stop_words", [])

                is_action_verb = token.lemma_ in filename_actions
                is_linking_verb = token.lemma_ in filename_linking
                is_stop_word = token.text.lower() in filename_stop_words
                is_punctuation = token.is_punct
                is_separator = token.pos_ in ("ADP", "CCONJ", "SCONJ") and token.text.lower() != "v"

                # Special handling for "file" - stop if preceded by articles or stop words
                if token.text.lower() == "file" and i > 0:
                    prev_token = doc[i - 1].text.lower()
                    if prev_token in ["the", "a", "an", "this", "that"] or prev_token in filename_stop_words:
                        break

                # Don't treat "file" as a stop word if it's part of a compound filename
                # Allow "file" when it's at the start OR when it's clearly part of a filename phrase
                is_file_in_compound = token.text.lower() == "file" and (
                    len(filename_tokens) == 0  # At start (like "makefile")
                    or (
                        len(filename_tokens) > 0
                        and filename_tokens[-1].text.lower() not in ["the", "a", "an", "this", "that"]
                    )
                )
                is_stop_word_filtered = is_stop_word and not is_file_in_compound

                if is_action_verb or is_linking_verb or is_stop_word_filtered or is_punctuation or is_separator:
                    logger.debug(
                        f"SPACY FILENAME: Stopping at token '{token.text}' (action:{is_action_verb}, link:{is_linking_verb}, stop:{is_stop_word}, punc:{is_punctuation}, sep:{is_separator})"
                    )
                    break

                if len(filename_tokens) >= 8:
                    break

                filename_tokens.insert(0, token)

            if not filename_tokens:
                continue

            start_pos = filename_tokens[0].idx
            end_pos = match.end()
            entity_text = text[start_pos:end_pos]

            if not overlaps_with_entity(start_pos, end_pos, all_entities):
                new_entity = Entity(start=start_pos, end=end_pos, text=entity_text, type=EntityType.FILENAME)
                entities.append(new_entity)
                all_entities.append(new_entity)
                logger.debug(f"SPACY FILENAME: Created filename entity: '{entity_text}'")
            else:
                logger.debug("SPACY FILENAME: Entity overlaps with existing entity, skipping")

        if len(entities) == entities_before_spacy:
            logger.debug("SpaCy filename detection found no new entities, trying regex fallback")
            self._detect_filenames_regex_fallback(text, entities, all_entities)

    def _detect_filenames_regex_fallback(
        self, text: str, entities: list[Entity], all_entities: list[Entity] | None = None
    ) -> None:
        """Regex-based fallback for filename detection when spaCy is not available."""
        if all_entities is None:
            all_entities = entities

        logger.debug(f"REGEX FALLBACK: Processing text '{text}' for filename detection")

        # Use the comprehensive pattern that captures both filename and extension
        for match in regex_patterns.FULL_SPOKEN_FILENAME_PATTERN.finditer(text):
            if overlaps_with_entity(match.start(), match.end(), all_entities):
                continue

            full_filename = match.group(0)  # e.g., "my script dot py"
            filename_part = match.group(1)  # e.g., "my script"
            extension = match.group(2)  # e.g., "py"
            
            logger.debug(f"REGEX FALLBACK: Found match '{full_filename}' -> filename: '{filename_part}', ext: '{extension}'")

            # Skip if this looks like it includes command verbs
            # Get the context before the match to check for command patterns

            # Known filename action words that should not be part of the filename
            resources = get_resources(self.language)
            filename_actions = resources.get("context_words", {}).get("filename_actions", [])

            # Filter out filename stop words and action words from the filename part
            filename_words = filename_part.split()
            filename_stop_words = resources.get("context_words", {}).get("filename_stop_words", [])
            
            # Remove action words and stop words from the beginning
            filtered_words = []
            for i, word in enumerate(filename_words):
                word_lower = word.lower()
                
                # Remove action verbs from the beginning only
                if word_lower in filename_actions and not filtered_words:
                    continue  # Skip action verbs at the beginning
                
                # Special handling for certain stop words that might be part of filenames
                # Words like "script", "file", "document" can be part of filenames if not at the very beginning
                # or if they appear after we already have some content
                if word_lower in filename_stop_words:
                    # Skip generic stop words (articles, prepositions) always
                    if word_lower in ["the", "a", "an", "this", "that", "in", "on", "for", "is", "was", "called"]:
                        if not filtered_words:  # Only skip at the beginning
                            continue
                    # Allow descriptive words like "script", "file", "document" if we have context
                    elif word_lower in ["script", "file", "document"]:
                        # Always include these if they're not the very first word or if we already have content
                        if i > 0 or filtered_words:
                            filtered_words.append(word)
                            continue  # Important: continue here to avoid double-adding
                        else:
                            continue  # Skip only if it's the very first word
                    else:
                        # For other stop words, only skip at the beginning
                        if not filtered_words:
                            continue
                        else:
                            # If we already have content, add the stop word
                            filtered_words.append(word)
                            continue
                
                # Add all other words (only reached if not a stop word or action verb)
                filtered_words.append(word)
            
            logger.debug(f"REGEX FALLBACK: Filtered words: {filtered_words}")
            
            if filtered_words:
                actual_filename = " ".join(filtered_words)
                # Find where the actual filename starts in the original text
                actual_start = text.find(actual_filename, match.start())
                logger.debug(f"REGEX FALLBACK: Actual filename: '{actual_filename}', start: {actual_start}")
                if actual_start != -1:
                    actual_match_text = f"{actual_filename} dot {extension}"
                    actual_end = actual_start + len(actual_match_text)

                    entities.append(
                        Entity(
                            start=actual_start,
                            end=actual_end,
                            text=actual_match_text,
                            type=EntityType.FILENAME,
                            metadata={
                                "filename": actual_filename,
                                "extension": extension,
                                "method": "regex_fallback",
                            },
                        )
                    )
                    logger.debug(
                        f"Detected filename (regex fallback): '{actual_match_text}' -> filename: '{actual_filename}', ext: '{extension}'"
                    )
                    continue
            else:
                # If no words left after filtering, skip this match
                logger.debug(
                    f"Regex Fallback: Skipping '{full_filename}' because no filename words remain after filtering"
                )
                continue