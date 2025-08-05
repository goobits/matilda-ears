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

import os
import re

from ... import regex_patterns
from ...common import Entity, EntityType
from ...constants import get_resources
from ...nlp_provider import get_punctuator


def add_punctuation(
    text: str,
    original_had_punctuation: bool = False,
    is_standalone_technical: bool = False,
    filtered_entities: list[Entity] | None = None,
    nlp=None,
    language: str = "en"
) -> str:
    """Add punctuation - treat all text as sentences unless single standalone technical entity"""
    if filtered_entities is None:
        filtered_entities = []

    # Add this at the beginning to handle empty inputs
    if not text.strip():
        return ""

    # Check if punctuation is disabled for testing
    if os.environ.get("STT_DISABLE_PUNCTUATION") == "1":
        return text

    # Check if text is a standalone technical entity that should bypass punctuation
    if is_standalone_technical:
        return text

    # If original text already had punctuation, don't add more
    if original_had_punctuation:
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
            result = punctuator.restore_punctuation(protected_text)

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
            if nlp:
                try:
                    # Get language-specific resources
                    resources = get_resources(language)
                    
                    # Re-run spaCy on the punctuated text to analyze grammar
                    punc_doc = nlp(result)
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
                text = result

        except (AttributeError, ValueError, RuntimeError, OSError):
            # If punctuation model fails, continue with fallback logic
            pass

    # Add final punctuation intelligently when punctuation model is not available
    if text and text.strip() and text.strip()[-1].isalnum():
        word_count = len(text.split())
        
        # Force punctuation for obvious natural language patterns
        natural_patterns = [
            r'\b(?:flatten|sharpen|brighten|darken|soften|harden)\s+the\s+\w+\b',  # "flatten the curve"
            r'\bsolve\s+.*\s+using\s+.*\b',  # "solve x using formula"
            r'\bsave\s+.*\s+with\s+.*\b',  # "save config with encoding"
        ]
        
        is_natural_phrase = any(re.search(pattern, text, re.IGNORECASE) for pattern in natural_patterns)
        
        # Apply punctuation if it's not standalone technical OR if it matches natural patterns
        if (not is_standalone_technical or is_natural_phrase) and word_count >= 2:
            text += "."

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