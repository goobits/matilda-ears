#!/usr/bin/env python3
"""
Step 4: Punctuation Pipeline

This module handles punctuation addition and standalone entity punctuation cleanup.
Extracted from the main formatter to modularize the pipeline processing.

This is Step 4 of the 4-step formatting pipeline:
1. Cleanup (step1_cleanup.py)
2. Detection (step2_detection.py) 
3. Conversion (step3_conversion.py)
4. Punctuation (step4_punctuation.py) ← This module
"""

from __future__ import annotations

import logging
import os
import re

from ... import regex_patterns
from stt.text_formatting.common import Entity, EntityType
from ...constants import get_resources
from ...nlp_provider import get_punctuator

# Setup logging
logger = logging.getLogger(__name__)


def add_punctuation(
    text: str,
    original_had_punctuation: bool = False,
    is_standalone_technical: bool = False,
    filtered_entities: list[Entity] | None = None,
    nlp=None,
    language: str = "en",
    doc=None,
    pipeline_state=None
) -> str:
    """Add punctuation - treat all text as sentences unless single standalone technical entity"""
    if filtered_entities is None:
        filtered_entities = []
        

    # Add this at the beginning to handle empty inputs
    if not text.strip():
        return ""

    # SPECIAL CASE: Email punctuation cleanup - this should work even when punctuation is disabled
    # Check if there are EMAIL entities and original text had punctuation to remove
    if original_had_punctuation and filtered_entities:
        from stt.text_formatting.common import EntityType as ET
        if any(entity.type == ET.EMAIL for entity in filtered_entities):
            # Remove trailing punctuation when email entities are present
            text_stripped = text.rstrip()
                
            # Check for escaped punctuation first (backslash + punctuation)
            if text_stripped and len(text_stripped) >= 2 and text_stripped[-2:] in ["\\!", "\\?", "\\."]:
                # Handle escaped punctuation marks - remove both backslash and punctuation
                trailing_whitespace = text[len(text_stripped):]
                text = text_stripped[:-2] + trailing_whitespace
            elif text_stripped and text_stripped[-1] in ".!?":
                # Remove the trailing punctuation but preserve any trailing whitespace structure
                trailing_whitespace = text[len(text_stripped):]
                text = text_stripped[:-1] + trailing_whitespace
            elif text_stripped and text_stripped[-1] == '\\':
                # Handle standalone trailing backslash
                trailing_whitespace = text[len(text_stripped):]
                text = text_stripped[:-1] + trailing_whitespace

    # Check if punctuation is disabled for testing
    stt_disable = os.environ.get("STT_DISABLE_PUNCTUATION")
    if stt_disable == "1":
        return text

    # Check if text is a standalone technical entity that should bypass punctuation
    if is_standalone_technical:
        return text

    # If original text already had punctuation, don't add more
    if original_had_punctuation:
        return text

    # Add comma insertion for common introductory phrases BEFORE punctuation model processing
    # THEORY 8: Pass pipeline state for universal entity coordination
    original_text = text
    text = _add_comma_for_introductory_phrases(text, language, pipeline_state)
    
    # POSITION TRACKING: Update entity positions if comma insertion changed text
    if pipeline_state and text != original_text:
        logger.debug(f"POSITION_TRACKING: Comma insertion changed text: '{original_text}' -> '{text}'")
        # Find all the changes and update positions accordingly
        # For now, we'll update the pipeline state text - more precise tracking could be added
        pipeline_state.text = text
    
    # Initialize filename placeholders outside the try block (Theory 7 fix)
    filename_placeholders = {}

    # All other text is treated as a sentence - use punctuation model
    punctuator = get_punctuator()
    if punctuator:
        try:
            # Protect filenames FIRST (Theory 7 fix) - must come before URL protection
            # since filenames like "app.js" can be mistaken for domains
            protected_text = text
            filename_matches = list(regex_patterns.FILENAME_WITH_EXTENSION_PATTERN.finditer(text))
            for i, match in enumerate(filename_matches):
                placeholder = f"__FILENAME_{i}__"
                filename_placeholders[placeholder] = match.group(0)
                protected_text = protected_text.replace(match.group(0), placeholder, 1)

            # THEORY 8: Protect already-formatted abbreviations BEFORE URL protection
            # This prevents abbreviations like "i.e." from being mistakenly caught by URL patterns
            abbreviation_placeholders = {}
            # Pattern to match common abbreviations that are already formatted (e.g., i.e., e.g., etc.)
            # Include some context to prevent punctuation model from adding unwanted punctuation around them
            # Note: Don't use word boundaries after periods as periods are not word characters
            # Updated pattern to handle abbreviations at start of text or with spaces
            from ...pattern_modules.common_patterns import ABBREVIATION_SPACING_PATTERN
            abbrev_pattern = ABBREVIATION_SPACING_PATTERN
            for i, match in enumerate(abbrev_pattern.finditer(protected_text)):
                placeholder = f"__ABBREV_{i}__"
                # Store the entire match including surrounding context to preserve positioning
                full_match = match.group(0)
                abbreviation_only = match.group(2)  # Just the abbreviation part without spaces
                abbreviation_placeholders[placeholder] = {
                    'full_match': full_match,
                    'abbreviation_only': abbreviation_only,
                    'prefix': match.group(1),
                    'suffix': match.group(3)
                }
                protected_text = protected_text.replace(full_match, placeholder, 1)
                logger.debug(f"POSITION_TRACKING: Protected abbreviation '{abbreviation_only}' with placeholder {placeholder}")

            # Now protect URLs and technical terms from the punctuation model
            # Using pre-compiled patterns for performance
            url_placeholders = {}

            # Find and replace URLs with placeholders
            for i, match in enumerate(regex_patterns.URL_PROTECTION_PATTERN.finditer(protected_text)):
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

            # Protect decimal numbers from the punctuation model
            decimal_placeholders = {}
            for i, match in enumerate(regex_patterns.DECIMAL_PROTECTION_PATTERN.finditer(protected_text)):
                placeholder = f"__DECIMAL_{i}__"
                decimal_placeholders[placeholder] = match.group(0)
                protected_text = protected_text.replace(match.group(0), placeholder, 1)

            # Apply punctuation to the protected text
            logger.debug(f"POSITION_TRACKING: Sending to punctuation model: '{protected_text}'")
            result = punctuator.restore_punctuation(protected_text)
            logger.debug(f"POSITION_TRACKING: Punctuation model returned: '{result}'")

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

            # Restore decimal numbers
            for placeholder, decimal in decimal_placeholders.items():
                result = re.sub(rf"\b{re.escape(placeholder)}\b", decimal, result)
            
            # THEORY 8: Restore protected abbreviations
            for placeholder, abbrev_data in abbreviation_placeholders.items():
                full_match = abbrev_data['full_match']
                abbreviation_only = abbrev_data['abbreviation_only']
                logger.debug(f"POSITION_TRACKING: Restoring abbreviation placeholder '{placeholder}' -> '{full_match}' in text '{result}'")
                old_result = result
                # Use simple replacement instead of word boundaries since placeholder contains underscores
                result = result.replace(placeholder, full_match)
                if result != old_result:
                    logger.debug(f"POSITION_TRACKING: Successfully restored abbreviation: '{old_result}' -> '{result}'")
                    
                    # POSITION TRACKING: Update entity positions after abbreviation restoration
                    if pipeline_state:
                        # Find the position where the restoration happened
                        restore_pos = old_result.find(placeholder)
                        if restore_pos != -1:
                            # Find all abbreviation entities and update their converted text
                            # since we know we just restored an abbreviation
                            logger.debug(f"POSITION_TRACKING: Looking for ABBREVIATION entities to update with text '{abbreviation_only}'")
                            logger.debug(f"POSITION_TRACKING: Available entities: {[(eid, ei.entity.type.value, ei.original_text, ei.converted_text) for eid, ei in pipeline_state.entity_tracker.entities.items()]}")
                            
                            for entity_id, entity_info in pipeline_state.entity_tracker.entities.items():
                                # Check if this is an abbreviation entity (using EntityType enum comparison)
                                from stt.text_formatting.common import EntityType
                                if entity_info.entity.type == EntityType.ABBREVIATION:
                                    # Update the entity's expected text to match the restored abbreviation
                                    entity_info.converted_text = abbreviation_only
                                    logger.debug(f"POSITION_TRACKING: Updated entity {entity_id} expected text to '{abbreviation_only}'")
                                    break
                else:
                    logger.debug(f"POSITION_TRACKING: Abbreviation placeholder '{placeholder}' not found or not restored")

            # NOTE: Filename restoration moved to end after all post-processing

            # Post-process punctuation using grammatical context
            if nlp:
                try:
                    # Get language-specific resources
                    resources = get_resources(language)
                    
                    # Use shared doc if available and text hasn't changed significantly, otherwise re-run spaCy
                    if doc is not None and result == text:
                        # Can reuse the shared doc since text hasn't changed
                        punc_doc = doc
                    elif ":" not in result:
                        # Skip SpaCy analysis if there are no colons to analyze
                        punc_doc = None
                    else:
                        # Need to re-analyze the punctuated text for grammar context
                        punc_doc = nlp(result)
                    new_result_parts = list(result)

                    # Only do colon analysis if we have a doc and there are colons
                    if punc_doc is not None:
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
                                base_command_words = resources.get("context_words", {}).get(
                                    "command_words", []
                                )
                                command_words = [
                                    *list(base_command_words),
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
                except Exception:
                    # If spaCy processing fails, continue without colon correction
                    pass

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
                resources = get_resources(language)
                preserve_words = resources.get("context_words", {}).get("preserve_colon", [])
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
                # POSITION_TRACKING: Update entity positions after punctuation model changes
                if pipeline_state:
                    logger.debug(f"POSITION_TRACKING: Punctuation model changed text: '{text}' -> '{result}'")
                    
                    # Update pipeline state with the final text after all restorations
                    # This ensures entity tracking uses the text with restored abbreviations
                    pipeline_state.text = result
                    
                    # Validate entity positions after punctuation changes but before restoration
                    position_warnings = pipeline_state.validate_entity_positions(result, "step4_punctuation")
                    for warning in position_warnings:
                        logger.warning(f"POSITION_TRACKING: {warning}")
                
                text = result

        except (AttributeError, ValueError, RuntimeError, OSError):
            # If punctuation model fails, continue with fallback logic
            pass

    # Add final punctuation intelligently when punctuation model is not available
    text = _add_sentence_ending_punctuation(text, is_standalone_technical)

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

    # FINAL: Restore filenames after all post-processing (Theory 7 fix)
    original_text_before_restore = text
    for placeholder, filename in filename_placeholders.items():
        text = re.sub(rf"\b{re.escape(placeholder)}\b", filename, text)
    
    # PHASE 4 FIX: Surgical repair of broken abbreviations that may have been corrupted
    # by the punctuation model or other downstream processing
    text = _repair_broken_abbreviations(text)
    
    # POSITION TRACKING: Update entity positions after filename restoration
    if pipeline_state:
        # Always update the pipeline state with the final text
        pipeline_state.text = text
        
        # Final validation of entity positions after all punctuation processing
        # This includes abbreviation restoration, so entity positions should be correct now
        position_warnings = pipeline_state.validate_entity_positions(text, "step4_punctuation_final")
        for warning in position_warnings:
            logger.warning(f"POSITION_TRACKING: {warning}")

    return text


def _add_sentence_ending_punctuation(text: str, is_standalone_technical: bool = False) -> str:
    """
    Add sentence-ending punctuation when appropriate.
    
    This handles cases where text lacks proper sentence punctuation,
    particularly for mathematical expressions and natural language.
    
    Args:
        text: The text to process
        is_standalone_technical: Whether this is a standalone technical entity
        
    Returns:
        Text with appropriate sentence-ending punctuation
    """
    if not text or not text.strip():
        return text
        
    stripped_text = text.strip()
    
    # Don't add punctuation if text already ends with punctuation
    if stripped_text and stripped_text[-1] in '.!?:;':
        return text
        
    # Don't add punctuation to purely numeric standalone entities
    if is_standalone_technical and stripped_text.replace(' ', '').replace('.', '').replace('-', '').isdigit():
        return text
    
    word_count = len(stripped_text.split())
    
    # Force punctuation for obvious natural language patterns
    natural_patterns = [
        r'\b(?:flatten|sharpen|brighten|darken|soften|harden)\s+the\s+\w+\b',  # "flatten the curve"
        r'\bsolve\s+.*\s+using\s+.*\b',  # "solve x using formula"
        r'\bsave\s+.*\s+with\s+.*\b',  # "save config with encoding"
        r'\blet\s+me\s+\w+\b',  # "let me say", "let me explain"
        r'\b(?:first|second|third)\s+of\s+all\b',  # "first of all", etc.
        r'\b(?:calculate|compute|evaluate)\s+.*\b',  # Mathematical operations
        r'\bmake\s+sure\s+.*\b',  # "make sure to..."
        r'\bneed\s+to\s+\w+\b',  # "need to check", "need to verify"
    ]
    
    is_natural_phrase = any(re.search(pattern, stripped_text, re.IGNORECASE) for pattern in natural_patterns)
    
    # Additional check for mathematical expressions ending with alphanumeric (like "x equals five")
    has_math_context = bool(re.search(r'\b(?:equals?|plus|minus|times|divided by|multiplied by|result)\b', stripped_text, re.IGNORECASE))
    
    # Apply punctuation if:
    # 1. It's not standalone technical OR it matches natural patterns
    # 2. Has 2+ words (avoid single-word technical terms)
    # 3. Last character is alphanumeric (needs punctuation)
    if stripped_text and stripped_text[-1].isalnum():
        should_punctuate = (
            (not is_standalone_technical or is_natural_phrase or has_math_context) 
            and word_count >= 2
        )
        
        if should_punctuate:
            text = stripped_text + "."
    
    return text


def _add_comma_for_introductory_phrases(text: str, language: str = "en", pipeline_state=None) -> str:
    """
    Add commas after common introductory phrases that require them.
    
    This handles phrases like:
    - "first of all" → "first of all,"
    - "second of all" → "second of all,"
    - "by the way" → "by the way,"
    - "in other words" → "in other words,"
    
    THEORY 8 INTEGRATION: Now uses Universal Entity State Coordination to detect
    abbreviation entities and prevent comma insertion that would create
    double punctuation after abbreviation restoration.
    
    Args:
        text: The text to process
        language: Language code ("en", "es", etc.)
        pipeline_state: Pipeline state with universal entity tracking
        
    Returns:
        Text with commas added after introductory phrases
    """
    if not text.strip():
        return text

    # Initialize pipeline state manager for abbreviation detection if not provided
    if pipeline_state is None:
        try:
            from ..pipeline_state import create_pipeline_state_manager
            state_manager = create_pipeline_state_manager(language)
            pipeline_state = state_manager.create_state(text)
        except Exception as e:
            # Fallback to original behavior if pipeline state manager is not available
            pipeline_state = None
            state_manager = None

    # Define comma-requiring introductory phrases with their patterns
    introductory_patterns = [
        r"\bfirst of all\b",
        r"\bsecond of all\b", 
        r"\bthird of all\b",
        r"\bby the way\b",
        r"\bin other words\b",
        r"\bfor example\b",
        r"\bon the other hand\b",
        r"\bas a matter of fact\b",
        r"\bto be honest\b",
        r"\bfrankly speaking\b",
        r"\bin the first place\b",
        r"\bmost importantly\b",
    ]
    
    # Apply comma insertion for each pattern
    for pattern in introductory_patterns:
        # Match the phrase and check if it needs a comma
        def add_comma_if_needed(match):
            matched_phrase = match.group(0)
            start_pos = match.start()
            end_pos = match.end()
            
            # THEORY 8: Use Universal Entity State Coordination for conflict detection
            if pipeline_state:
                # Check if comma insertion would conflict with tracked entities
                if pipeline_state.should_skip_punctuation_modification("step4_punctuation", start_pos, end_pos + 1, "comma"):
                    return matched_phrase  # Skip comma due to entity conflict
            
            # Check what comes after the phrase
            remaining_text = text[end_pos:].lstrip()
            
            # Special case: Don't add comma before Latin abbreviations that already have punctuation
            # This prevents "for example, e.g.," and "that is, i.e.," patterns
            if remaining_text:
                # Check if the remaining text starts with a Latin abbreviation (converted form)
                # This now handles the case where abbreviations have already been converted
                # Pattern matches abbreviations with or without trailing comma/punctuation
                latin_abbrev_pattern = r'^(e\.g\.|i\.e\.|vs\.|etc\.|cf\.)([,.]?)'
                if re.match(latin_abbrev_pattern, remaining_text, re.IGNORECASE):
                    return matched_phrase  # Don't add comma
                
                # ENHANCED CHECK: Also check for spoken forms of abbreviations
                # This catches "e g", "i e", etc. before they are converted
                spoken_abbrev_pattern = r'^(e\s+g|i\s+e|v\s+s|etc)\b'
                if re.match(spoken_abbrev_pattern, remaining_text, re.IGNORECASE):
                    return matched_phrase  # Don't add comma
                    
                # ADDITIONAL CHECK: Handle abbreviations that have periods but no comma yet
                # Pattern like "e.g." without comma - don't add comma before them
                period_abbrev_pattern = r'^(e\.g|i\.e|vs|etc|cf)\.?\b'
                if re.match(period_abbrev_pattern, remaining_text, re.IGNORECASE):
                    return matched_phrase  # Don't add comma
            
            # Only add comma if:
            # 1. There's more text after the phrase
            # 2. The phrase is not already followed by punctuation
            # 3. The phrase is at the beginning or after whitespace/punctuation
            if (remaining_text and 
                not remaining_text[0] in ',.!?;:' and
                (start_pos == 0 or text[start_pos-1] in ' \n\t.!?')):
                return matched_phrase + ','
            
            return matched_phrase
        
        # Apply the pattern with case insensitive matching
        text = re.sub(pattern, add_comma_if_needed, text, flags=re.IGNORECASE)
    
    return text


def clean_standalone_entity_punctuation(text: str, entities: list[Entity]) -> str:
    """
    Remove trailing punctuation from standalone entities.

    If the formatted text is essentially just a single entity with trailing punctuation,
    remove the punctuation. This handles cases like '/compact.' → '/compact'.

    Args:
        text: The text to clean
        entities: List of entities in the text
        
    Returns:
        Cleaned text with standalone entity punctuation removed
    """
    if not text or not entities:
        return text

    # Strip whitespace for analysis
    text_stripped = text.strip()

    # Check if text ends with punctuation
    if not text_stripped or text_stripped[-1] not in ".!?":
        return text

    # Remove trailing punctuation for analysis (handle multiple punctuation marks)
    text_no_punct = re.sub(r"[.!?]+$", "", text_stripped).strip()

    # Define entity types that should be standalone (no punctuation when alone)
    standalone_entity_types = {
        EntityType.SLASH_COMMAND,
        EntityType.CLI_COMMAND,
        EntityType.FILENAME,
        EntityType.URL,
        EntityType.SPOKEN_URL,
        EntityType.SPOKEN_PROTOCOL_URL,
        EntityType.EMAIL,
        EntityType.SPOKEN_EMAIL,
        EntityType.VERSION,
        EntityType.COMMAND_FLAG,
        EntityType.PROGRAMMING_KEYWORD,
    }

    # Only remove punctuation if the text is very short and mostly consists of the entity
    if len(text_no_punct.split()) <= 2:  # 2 words or fewer (more restrictive)
        # Check if we have any standalone entity types that cover most of the text
        for entity in entities:
            if entity.type in standalone_entity_types:
                # Check if this entity covers at least 70% of the text
                try:
                    entity_length = len(entity.text) if hasattr(entity, "text") else (entity.end - entity.start)
                    text_length = len(text_no_punct)
                    coverage = entity_length / text_length if text_length > 0 else 0

                    if coverage >= 0.7:
                        return text_no_punct
                except (AttributeError, ZeroDivisionError):
                    # If we can't calculate coverage, fall back to simpler check
                    if len(text_no_punct.split()) == 1:  # Single word/entity
                        return text_no_punct

    # If we get here, it's likely a sentence containing entities, keep punctuation
    return text


def _repair_broken_abbreviations(text: str) -> str:
    """
    Surgical repair of broken abbreviations that may have been corrupted by the punctuation model.
    
    This fixes cases where abbreviations like "i.e." become "i. e." or "e.g." becomes "e. g."
    due to unwanted space insertion by the punctuation model or other processing steps.
    
    Args:
        text: Text that may contain broken abbreviations
        
    Returns:
        Text with repaired abbreviations
    """
    if not text:
        return text
    
    # Define mapping of broken patterns to correct forms
    abbreviation_repairs = [
        # Fix "i. e." back to "i.e." (preserve original case)
        (re.compile(r'\b(i)\.\s+(e)\.', re.IGNORECASE), r'\1.\2.'),
        
        # Fix "e. g." back to "e.g." (preserve original case)
        (re.compile(r'\b(e)\.\s+(g)\.', re.IGNORECASE), r'\1.\2.'),
        
        # Fix other common abbreviations that may have broken (only if followed by non-space-consuming patterns)
        # These patterns are more conservative to avoid removing legitimate spacing
        (re.compile(r'\b(etc)\.\s+([a-zA-Z])', re.IGNORECASE), r'\1. \2'),
        (re.compile(r'\b(vs)\.\s+([a-zA-Z])', re.IGNORECASE), r'\1. \2'), 
        (re.compile(r'\b(cf)\.\s+([a-zA-Z])', re.IGNORECASE), r'\1. \2'),
    ]
    
    result = text
    for pattern, replacement in abbreviation_repairs:
        result = pattern.sub(replacement, result)
    
    return result