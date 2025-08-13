#!/usr/bin/env python3
"""File and path-related entity detection for code transcriptions."""
from __future__ import annotations

import re

from stt.core.config import setup_logging
from stt.text_formatting.pattern_modules.code_patterns import (
    FILENAME_WITH_EXTENSION_PATTERN,
    JAVA_PACKAGE_PATTERN,
    SPOKEN_DOT_FILENAME_PATTERN,
    FULL_SPOKEN_FILENAME_PATTERN,
)
from stt.text_formatting.common import Entity, EntityType
from stt.text_formatting.constants import get_resources
from stt.text_formatting.utils import overlaps_with_entity

logger = setup_logging(__name__)


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

    def detect_filenames(self, text: str, entities: list[Entity], all_entities: list[Entity] | None = None, pipeline_state=None) -> None:
        """Detect filenames using a simple regex anchor and robust spaCy context analysis with Theory 7 intelligence."""
        if all_entities is None:
            all_entities = entities

        # --- Part 1: Handle already-formatted files first (e.g., main.py, com.example.app) ---
        for match in FILENAME_WITH_EXTENSION_PATTERN.finditer(text):
            if not overlaps_with_entity(match.start(), match.end(), all_entities):
                new_entity = Entity(start=match.start(), end=match.end(), text=match.group(0), type=EntityType.FILENAME)
                entities.append(new_entity)
                all_entities.append(new_entity)

        for match in JAVA_PACKAGE_PATTERN.finditer(text):
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

        # Use shared document processor for optimal caching
        from ..spacy_doc_cache import get_or_create_shared_doc
        try:
            doc = get_or_create_shared_doc(text, nlp_model=self.nlp)
            if doc is None:
                raise ValueError("SpaCy document creation failed")
        except (AttributeError, ValueError, IndexError) as e:
            logger.warning(f"SpaCy filename detection failed: {e}")
            self._detect_filenames_regex_fallback(text, entities, all_entities)
            return

        end_char_to_token = {token.idx + len(token.text): token for token in doc}

        for match in SPOKEN_DOT_FILENAME_PATTERN.finditer(text):
            if overlaps_with_entity(match.start(), match.end(), all_entities):
                continue

            # THEORY 7 FIX: Improved action word handling
            # Check if this match includes action words at the beginning that should be separate
            match_text = text[match.start():match.end()]
            action_pattern = r'^(create|edit|open|run|import|check|save|load|delete|remove)\s+(.+)$'
            action_match = re.match(action_pattern, match_text, re.IGNORECASE)
            
            if action_match:
                action_word = action_match.group(1)
                filename_part = action_match.group(2)
                
                # Check if the filename part still contains a valid extension pattern
                if ' dot ' in filename_part.lower():
                    # Adjust the match to exclude the action word
                    action_end = match.start() + len(action_word)
                    # Find the start of the filename part (skip whitespace after action word)
                    filename_start = action_end
                    while filename_start < match.end() and text[filename_start].isspace():
                        filename_start += 1
                    
                    if filename_start < match.end():
                        # Create filename entity without the action word
                        class AdjustedSpacyMatch:
                            def __init__(self, start, end, text):
                                self._start = start
                                self._end = end
                                self._text = text
                            
                            def start(self):
                                return self._start
                            
                            def end(self):
                                return self._end
                            
                            def group(self):
                                return self._text
                        
                        match = AdjustedSpacyMatch(filename_start, match.end(), text[filename_start:match.end()])
                        logger.debug(f"THEORY7 FIX: Adjusted filename match to exclude action word '{action_word}': '{match.group()}'")
            
            # THEORY 7: Check pipeline state for intelligent context override
            if pipeline_state and hasattr(pipeline_state, 'filename_contexts'):
                filename_context = pipeline_state.get_filename_context_at((match.start() + match.end()) // 2)
                if filename_context and filename_context.should_use_dots:
                    # High-confidence filename context detected by Theory 7
                    # Create a simplified entity that preserves the natural filename structure
                    logger.debug(f"THEORY 7: High-confidence filename context detected: '{filename_context.text}'")
                    
                    new_entity = Entity(
                        start=filename_context.start, 
                        end=filename_context.end, 
                        text=filename_context.text, 
                        type=EntityType.FILENAME,
                        metadata={
                            "theory7_context": True,
                            "confidence_score": filename_context.confidence_score,
                            "context_type": filename_context.context_type,
                            "action_word": filename_context.action_word
                        }
                    )
                    entities.append(new_entity)
                    all_entities.append(new_entity)
                    logger.debug(f"THEORY 7: Created intelligent filename entity: '{filename_context.text}'")
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

            # Walk backwards from the token before "dot" with 4-token distance limit
            for i in range(current_token.i, max(-1, current_token.i - 4), -1):
                token = doc[i]

                # Conservative stopping - be more restrictive
                # Stop at determiners (articles) when we already have filename content
                if token.pos_ == 'DET' and len(filename_tokens) > 0:  # Articles: the/der/le/el
                    break
                # Stop at prepositions, but allow special handling of "file" below
                if token.pos_ == 'ADP' and token.text.lower() != "file":  # Prepositions: in/en/dans/в
                    break

                # ** THE CRITICAL STOPPING LOGIC WITH SPACY DEPENDENCY PARSING **
                # Get language-specific filename stop words from i18n resources
                filename_actions = self.resources.get("context_words", {}).get("filename_actions", [])
                filename_linking = self.resources.get("context_words", {}).get("filename_linking", [])
                filename_stop_words = self.resources.get("context_words", {}).get("filename_stop_words", [])

                is_action_verb = token.lemma_ in filename_actions
                is_linking_verb = token.lemma_ in filename_linking
                is_stop_word = token.text.lower() in filename_stop_words
                is_punctuation = token.is_punct
                is_separator = token.pos_ in ("ADP", "CCONJ", "SCONJ") and token.text.lower() != "v"

                # Enhanced context-aware stopping using dependency parsing
                is_context_word = self._is_context_word_using_dependencies(token, filename_tokens)

                # Special handling for "file" using dependency parsing
                if token.text.lower() == "file":
                    # Use dependency parsing to determine if "file" is a descriptor vs part of filename
                    should_stop_at_file = self._should_stop_at_file_word(token, doc, filename_tokens)
                    if should_stop_at_file:
                        logger.debug(f"SPACY FILENAME: Stopping at 'file' - determined to be context word via dependency parsing")
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

                if is_action_verb or is_linking_verb or is_stop_word_filtered or is_punctuation or is_separator or is_context_word:
                    logger.debug(
                        f"SPACY FILENAME: Stopping at token '{token.text}' (action:{is_action_verb}, link:{is_linking_verb}, stop:{is_stop_word}, punc:{is_punctuation}, sep:{is_separator}, context:{is_context_word})"
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

        # Check if we should run regex fallback
        # Run it if: 1) SpaCy found no entities, or 2) SpaCy entities are poor quality
        should_run_fallback = len(entities) == entities_before_spacy
        poor_quality_entities = []
        
        if not should_run_fallback:
            # Check if SpaCy entities are poor quality (very short filename parts)
            new_entities = entities[entities_before_spacy:]
            for entity in new_entities:
                if entity.type == EntityType.FILENAME:
                    # Extract the filename part (before the extension)
                    filename_text = entity.text
                    if " dot " in filename_text.lower():
                        filename_part = filename_text.lower().split(" dot ")[0].strip()
                        filename_words = filename_part.split()
                        
                        # Check for poor quality indicators:
                        # 1. Very short (1-2 words)
                        # 2. Partial dunder patterns (starts/ends with "underscore")
                        is_short = len(filename_words) <= 2
                        is_partial_dunder = (filename_part.startswith("underscore ") or 
                                           filename_part.endswith(" underscore"))
                        
                        if is_short or is_partial_dunder:
                            logger.debug(f"SpaCy entity '{entity.text}' has poor quality filename part '{filename_part}' (words: {len(filename_words)}, partial_dunder: {is_partial_dunder}), marking for replacement")
                            poor_quality_entities.append(entity)
                            should_run_fallback = True
        
        if should_run_fallback:
            # Remove poor quality entities before running fallback
            for poor_entity in poor_quality_entities:
                if poor_entity in entities:
                    entities.remove(poor_entity)
                if poor_entity in all_entities:
                    all_entities.remove(poor_entity)
                    
            if len(entities) == entities_before_spacy:
                logger.debug("SpaCy filename detection found no new entities, trying regex fallback")
            else:
                logger.debug(f"SpaCy filename detection found {len(poor_quality_entities)} poor quality entities, removed them and trying regex fallback")
            self._detect_filenames_regex_fallback(text, entities, all_entities)

    def _detect_filenames_regex_fallback(
        self, text: str, entities: list[Entity], all_entities: list[Entity] | None = None
    ) -> None:
        """Regex-based fallback for filename detection when spaCy is not available."""
        if all_entities is None:
            all_entities = entities

        logger.debug(f"REGEX FALLBACK: Processing text '{text}' for filename detection")

        # Use the comprehensive pattern that captures both filename and extension
        for match in FULL_SPOKEN_FILENAME_PATTERN.finditer(text):
            if overlaps_with_entity(match.start(), match.end(), all_entities):
                continue

            full_filename = match.group(0)  # e.g., "my script dot py"
            filename_part = match.group(1)  # e.g., "my script"
            extension = match.group(2)  # e.g., "py"
            
            logger.debug(f"REGEX FALLBACK: Found match '{full_filename}' -> filename: '{filename_part}', ext: '{extension}'")
            
            # THEORY 7 FIX: Handle action words in regex fallback too
            action_pattern = r'^(create|edit|open|run|import|check|save|load|delete|remove)\s+(.+)$'
            action_match = re.match(action_pattern, full_filename, re.IGNORECASE)
            
            if action_match:
                action_word = action_match.group(1)
                remaining_text = action_match.group(2)
                
                # Extract the actual filename part from the remaining text
                remaining_match = re.match(r'^(.+?)\s+dot\s+(.+)$', remaining_text, re.IGNORECASE)
                if remaining_match:
                    filename_part = remaining_match.group(1)
                    extension = remaining_match.group(2)
                    
                    # Adjust match positions to exclude the action word
                    action_end = match.start() + len(action_word)
                    # Find the start of the filename part (skip whitespace after action word)
                    filename_start = action_end
                    while filename_start < match.end() and text[filename_start].isspace():
                        filename_start += 1
                    
                    if filename_start < match.end():
                        # Create a new match object for the adjusted range
                        adjusted_start = filename_start
                        adjusted_end = match.end()
                        full_filename = text[adjusted_start:adjusted_end]
                        
                        # Update match positions
                        class AdjustedMatch:
                            def __init__(self, start, end, full_text, filename_part, ext):
                                self._start = start
                                self._end = end
                                self._full_text = full_text
                                self._filename_part = filename_part
                                self._ext = ext
                            
                            def start(self):
                                return self._start
                            
                            def end(self):
                                return self._end
                            
                            def group(self, i=0):
                                if i == 0:
                                    return self._full_text
                                elif i == 1:
                                    return self._filename_part
                                elif i == 2:
                                    return self._ext
                                return self._full_text
                        
                        match = AdjustedMatch(adjusted_start, adjusted_end, full_filename, filename_part, extension)
                        
                        logger.debug(f"REGEX FALLBACK THEORY7 FIX: Adjusted to exclude action word '{action_word}': '{full_filename}' -> filename: '{filename_part}', ext: '{extension}'")

            # Known filename action words that should not be part of the filename
            resources = get_resources(self.language)
            filename_actions = resources.get("context_words", {}).get("filename_actions", [])

            # Filter out filename stop words and action words from the filename part
            filename_words = filename_part.split()
            filename_stop_words = resources.get("context_words", {}).get("filename_stop_words", [])
            
            # Determine if this is a clear filename pattern (extension is recognized)
            is_clear_filename_pattern = extension in ["py", "js", "ts", "java", "cpp", "c", "h", "rb", "php", "go", "rs", "json", "xml", "html", "css", "md", "txt", "csv"]
            
            # Enhanced context-aware filtering for regex fallback
            filtered_words = []
            for i, word in enumerate(filename_words):
                word_lower = word.lower()
                
                # Remove action verbs from the beginning only
                if word_lower in filename_actions and not filtered_words:
                    continue  # Skip action verbs at the beginning
                
                # Always skip common navigation words that are clearly not part of filenames
                if word_lower in ["go", "to", "open", "edit", "run", "execute"] and not filtered_words:
                    continue  # Skip navigation/action words at the beginning
                
                # ENHANCED: Special handling for "file" word - check if it's a descriptor
                if word_lower == "file":
                    # Skip "file" if it appears after articles or action verbs
                    context_before = " ".join(text[:match.start()].lower().split()[-3:]) if match.start() > 0 else ""
                    
                    # Skip if preceded by articles indicating it's a descriptor: "the file", "a file"
                    if any(phrase in context_before for phrase in ["the file", "a file", "an file", "this file", "that file"]):
                        continue
                        
                    # Skip if preceded by action verbs: "open file", "edit file"
                    if any(phrase in context_before for phrase in ["open file", "edit file", "check file", "save file", "run file"]):
                        continue
                        
                    # Skip if we already have substantial filename content (likely descriptor)
                    if len(filtered_words) >= 2:
                        continue
                
                # Special handling for other stop words that might be part of filenames
                if word_lower in filename_stop_words:
                    # Always skip generic stop words (articles, prepositions) except "file" which we handled above
                    if word_lower in ["the", "a", "an", "this", "that", "in", "on", "for", "is", "was", "called"]:
                        continue  # Always skip these words, they're never part of filenames
                    
                    # Context-aware handling for descriptive words like "script", "document" (but not "file")
                    elif word_lower in ["script", "document"]:
                        # If this is a clear filename pattern with a code extension, be more permissive
                        if is_clear_filename_pattern:
                            # Allow these descriptive words as they're likely part of the filename
                            filtered_words.append(word)
                            continue
                        else:
                            # Original conservative logic: only include if we already have other filename content
                            if filtered_words:
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
                # Try full filtered string first
                actual_filename = " ".join(filtered_words)
                actual_start = text.find(actual_filename, match.start())
                
                # If full string not found, try the longest contiguous suffix that could be a filename
                if actual_start == -1 and len(filtered_words) > 1:
                    # Try progressively smaller suffixes (e.g., "error main" -> "main")
                    for i in range(1, len(filtered_words)):
                        suffix = " ".join(filtered_words[i:])
                        suffix_start = text.find(suffix, match.start())
                        if suffix_start != -1:
                            actual_filename = suffix
                            actual_start = suffix_start
                            break
                
                logger.debug(f"REGEX FALLBACK: Actual filename: '{actual_filename}', start: {actual_start}")
                if actual_start != -1:
                    # Calculate the end position based on the original full match, not reconstructed text
                    # Find the actual end position in the original text
                    actual_end = text.find(f" dot {extension}", actual_start)
                    if actual_end != -1:
                        actual_end = actual_end + len(f" dot {extension}")
                        actual_match_text = text[actual_start:actual_end]
                    else:
                        # Fallback: use the original match boundaries
                        actual_match_text = match.group(0)
                        actual_end = match.end()

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

    def _is_context_word_using_dependencies(self, token, filename_tokens: list) -> bool:
        """
        Use spaCy dependency parsing to determine if a token is a context word rather than part of filename.
        
        Args:
            token: spaCy token to analyze
            filename_tokens: List of tokens already collected for filename
            
        Returns:
            True if token should be treated as context word (stop collection)
        """
        try:
            # Check dependency relations that indicate context rather than filename content
            
            # If this token is the root of a verb phrase, it's likely a command verb
            if token.dep_ == "ROOT" and token.pos_ == "VERB":
                return True
                
            # If this token is the subject of a sentence, it's likely not part of filename  
            if token.dep_ in ["nsubj", "nsubj:pass"]:
                return True
                
            # If this token is a determiner (the, a, an) it's context
            if token.pos_ == "DET":
                return True
                
            # If this token has children that are determiners, it's likely a noun phrase header
            if any(child.pos_ == "DET" for child in token.children):
                return True
                
            # Check if this token is syntactically distant from potential filename content
            if filename_tokens:
                last_filename_token = filename_tokens[-1]
                
                # If there's no direct syntactic relationship, this might be context
                if not self._tokens_are_syntactically_related(token, last_filename_token):
                    # Additional check: if this looks like a separate noun phrase
                    if token.pos_ in ["NOUN", "PROPN"] and token.dep_ in ["pobj", "dobj", "attr"]:
                        return True
            
            return False
            
        except (AttributeError, IndexError):
            # If dependency parsing fails, fall back to conservative approach
            return False

    def _should_stop_at_file_word(self, file_token, doc, filename_tokens: list) -> bool:
        """
        Use spaCy dependency parsing to determine if "file" should stop filename collection.
        
        Args:
            file_token: The spaCy token for "file"
            doc: The spaCy document
            filename_tokens: List of tokens already collected for filename
            
        Returns:
            True if we should stop at this "file" token
        """
        try:
            # Case 1: "the file config.py" - "file" is modified by "the" 
            # Check if "file" has a determiner child or is preceded by determiner
            if any(child.pos_ == "DET" for child in file_token.children):
                return True
                
            if file_token.i > 0:
                prev_token = doc[file_token.i - 1]
                if prev_token.pos_ == "DET":  # the, a, an
                    return True
                    
            # Case 2: "open file config.py" - "file" is the object of "open"
            # Check if "file" is the direct object of a verb
            if file_token.dep_ == "dobj" and file_token.head.pos_ == "VERB":
                return True
                
            # Case 3: "edit the config file" - "file" is the head noun of a noun phrase
            # Check if "file" is modified by other nouns (indicating it's the container)
            noun_modifiers = [child for child in file_token.children if child.pos_ in ["NOUN", "PROPN", "ADJ"]]
            if noun_modifiers:
                return True
                
            # Case 4: If we already have filename content and "file" appears later, 
            # it's likely descriptive: "config data file" -> want "config" not "config_data_file"
            if len(filename_tokens) >= 2:  # Already have substantial filename content
                return True
                
            return False
            
        except (AttributeError, IndexError):
            # If dependency parsing fails, use conservative heuristics
            if file_token.i > 0:
                prev_token = doc[file_token.i - 1]
                if prev_token.text.lower() in ["the", "a", "an", "this", "that"]:
                    return True
            return False

    def _tokens_are_syntactically_related(self, token1, token2) -> bool:
        """
        Check if two tokens are syntactically related in the dependency tree.
        
        Args:
            token1: First spaCy token
            token2: Second spaCy token
            
        Returns:
            True if tokens are directly related in dependency tree
        """
        try:
            # Check if one is ancestor/descendant of the other
            if token1.is_ancestor(token2) or token2.is_ancestor(token1):
                return True
                
            # Check if they share a common parent (siblings)
            if token1.head == token2.head and token1.head != token1 and token2.head != token2:
                return True
                
            # Check if they are in the same noun compound
            if (token1.dep_ in ["compound", "amod"] and token2.dep_ in ["compound", "amod"] and
                token1.head == token2.head):
                return True
                
            return False
            
        except (AttributeError, IndexError):
            return False