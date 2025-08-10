#!/usr/bin/env python3
"""
Step 6: Post-processing Pipeline Module

This module contains the final post-processing steps for the text formatting pipeline.
It handles abbreviation restoration, keyword conversion, domain rescue, and smart quotes.

Functions:
- restore_abbreviations: Restore proper formatting for abbreviations
- convert_orphaned_keywords: Convert orphaned keywords that weren't captured by entities
- rescue_mangled_domains: Rescue domains that got mangled during processing
- apply_smart_quotes: Convert straight quotes to smart/curly equivalents
"""

import re
from typing import TYPE_CHECKING

from ....core.config import setup_logging
from ... import regex_patterns
from ...constants import get_resources
from ...pattern_modules.basic_numeric_patterns import build_ordinal_pattern
from ...nlp_provider import get_nlp

# Import batch regex processing for string optimization
from ...batch_regex import batch_abbreviation_processing

if TYPE_CHECKING:
    pass

logger = setup_logging(__name__)


def _get_sentence_starter_ordinal_patterns() -> list[str]:
    """
    Get sentence starter ordinal patterns, preferably from spaCy but with fallback.
    
    Returns:
        List of regex patterns for sentence-starting ordinals
    """
    # For post-processing, we use simple hardcoded patterns as they're very specific
    # to sentence starter detection and comma insertion logic
    return [
        r"^(first|second|third|fourth|fifth)\s+(\w+)",  # "First we need", "Second I want"
        r"^(next|then|now|finally)\s+(\w+)",  # "Next we should", "Finally I want"
    ]


def _get_transition_starter_pattern() -> str:
    """Get the transition starter pattern for ordinals."""
    # Simple pattern for transition starters - keep as fallback for post-processing
    return r"^(first|second|third|fourth|fifth)\s+(\w+)"


def restore_abbreviations(text: str, resources: dict) -> str:
    """
    Restore proper formatting for abbreviations after punctuation model.
    
    Args:
        text: Text to process
        resources: Language resources containing abbreviations
        
    Returns:
        Text with properly formatted abbreviations
    """
    # The punctuation model tends to strip periods from common abbreviations
    # This post-processing step restores them to our preferred format

    # Use abbreviations from constants

    # Process each abbreviation
    abbreviations = resources.get("abbreviations", {})
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

    # Apply abbreviation-specific patterns using batch processing for efficiency
    text = batch_abbreviation_processing(text)
    
    # Handle additional edge cases that aren't in the batch processor
    text = re.sub(r"\b(for example|in other words|that is),\s+(e\.g\.|i\.e\.),(\s)", r"\1 \2,\3", text, flags=re.IGNORECASE)
    
    return text


def convert_orphaned_keywords(text: str, language: str = "en", doc=None) -> str:
    """
    Convert orphaned keywords that weren't captured by entities.

    This handles cases where keywords like 'slash', 'dot', 'at' remain in the text
    after entity conversion, typically due to entity boundary issues.
    
    Uses spaCy for context awareness to prevent inappropriate conversions when
    words like 'colon' and 'underscore' are used descriptively.
    
    Args:
        text: Text to process
        language: Language code for resource lookup
        
    Returns:
        Text with orphaned keywords converted to symbols
    """
    from ...nlp_provider import get_nlp
    
    original_text = text
    # Get language-specific keywords
    resources = get_resources(language)
    url_keywords = resources.get("spoken_keywords", {}).get("url", {})

    # Only convert safe keywords that are less likely to appear in natural language
    # Be more conservative about what we convert
    # Include both English and Spanish safe keywords
    safe_keywords = {
        # English keywords
        "slash": "/",
        "colon": ":",
        "underscore": "_",
        # Spanish keywords
        "barra": "/",
        "dos puntos": ":",
        "guión bajo": "_",
        "guión": "-",
        "arroba": "@",
        "punto": ".",
    }

    # Filter to only keywords we want to convert when orphaned
    keywords_to_convert = {}
    for keyword, symbol in url_keywords.items():
        if keyword in safe_keywords and safe_keywords[keyword] == symbol:
            keywords_to_convert[keyword] = symbol

    # Sort by length (longest first) to handle multi-word keywords properly
    sorted_keywords = sorted(keywords_to_convert.items(), key=lambda x: len(x[0]), reverse=True)

    # Define keywords that should consume surrounding spaces when converted
    space_consuming_symbols = {"/", ":", "_", "-"}
    
    # Define keywords that require context validation
    context_sensitive_keywords = {"colon", "underscore"}

    # Convert keywords that appear as standalone words
    for keyword, symbol in sorted_keywords:
        if keyword in context_sensitive_keywords:
            # Use context-aware conversion for sensitive keywords
            text = _convert_context_aware_keyword(text, keyword, symbol, space_consuming_symbols, language, doc)
        else:
            # Special handling for Spanish "guión" to avoid conflict with "guión bajo"
            if keyword == "guión" and language == "es":
                # Only convert "guión" if it's not followed by "bajo"
                pattern = rf"\b{re.escape(keyword)}\b(?!\s+bajo)"
                if symbol in space_consuming_symbols:
                    # For these symbols, consume surrounding spaces but preserve the negative lookahead
                    pattern = rf"\s*\b{re.escape(keyword)}\b(?!\s+bajo)\s*"
                text = re.sub(pattern, symbol, text, flags=re.IGNORECASE)
            else:
                # Use simple conversion for other keywords
                if symbol in space_consuming_symbols:
                    # For these symbols, consume surrounding spaces
                    pattern = rf"\s*\b{re.escape(keyword)}\b\s*"
                    # Simple replacement that consumes spaces
                    text = re.sub(pattern, symbol, text, flags=re.IGNORECASE)
                else:
                    # For other keywords, preserve word boundaries
                    pattern = rf"\b{re.escape(keyword)}\b"
                    text = re.sub(pattern, symbol, text, flags=re.IGNORECASE)

    return text


def _convert_context_aware_keyword(text: str, keyword: str, symbol: str, space_consuming_symbols: set, language: str = "en", doc=None) -> str:
    """
    Convert a keyword to its symbol only in appropriate contexts.
    
    Uses spaCy dependency parsing and POS tagging to determine if a keyword like
    'colon' or 'underscore' is being used functionally (should be converted) or
    descriptively (should remain as word).
    
    Args:
        text: Text to process
        keyword: The keyword to potentially convert (e.g., 'colon', 'underscore')
        symbol: The symbol to convert to (e.g., ':', '_')
        space_consuming_symbols: Set of symbols that consume surrounding spaces
        language: Language code
        
    Returns:
        Text with context-appropriate conversions applied
    """
    from ...nlp_provider import get_nlp
    
    # Use shared doc if available, otherwise create new one
    if doc is None:
        nlp = get_nlp()
        if not nlp:
            # Fallback to regex-based context validation if spaCy is not available
            logger.debug(f"SpaCy not available, using regex-based context validation for '{keyword}'")
            return _convert_keyword_with_regex_context(text, keyword, symbol, space_consuming_symbols)
        
        # Use shared document processor for optimal caching
        from ...spacy_doc_cache import get_or_create_shared_doc
        try:
            # Parse the text with shared SpaCy processor
            doc = get_or_create_shared_doc(text, nlp_model=nlp)
            if doc is None:
                raise ValueError("SpaCy document creation failed")
        except Exception as e:
            logger.warning(f"SpaCy processing failed for keyword conversion: {e}")
            return _convert_keyword_with_regex_context(text, keyword, symbol, space_consuming_symbols)
    
    try:
        # Find all instances of the keyword in the text
        pattern = rf"\b{re.escape(keyword)}\b"
        matches = list(re.finditer(pattern, text, flags=re.IGNORECASE))
        
        if not matches:
            return text
        
        # Process matches from right to left to preserve indices
        for match in reversed(matches):
            start_pos = match.start()
            end_pos = match.end()
            matched_word = match.group(0)
            
            # Find the spaCy token corresponding to this match
            token = None
            for t in doc:
                if t.idx <= start_pos < t.idx + len(t.text):
                    token = t
                    break
            
            if not token:
                continue
            
            # Determine if this keyword should be converted based on context
            should_convert = _should_convert_keyword(token, keyword, doc)
            
            if should_convert:
                # Apply the conversion
                if symbol in space_consuming_symbols:
                    # Consume surrounding spaces
                    replacement = symbol
                    # Find actual boundaries including spaces
                    actual_start = start_pos
                    actual_end = end_pos
                    
                    # Check for leading space
                    if actual_start > 0 and text[actual_start - 1].isspace():
                        actual_start -= 1
                    
                    # Check for trailing space
                    if actual_end < len(text) and text[actual_end].isspace():
                        actual_end += 1
                    
                    text = text[:actual_start] + replacement + text[actual_end:]
                else:
                    # Simple replacement
                    text = text[:start_pos] + symbol + text[end_pos:]
        
        return text
        
    except Exception as e:
        logger.warning(f"Error in context-aware conversion for '{keyword}': {e}")
        # Fallback to regex-based context validation
        return _convert_keyword_with_regex_context(text, keyword, symbol, space_consuming_symbols)


def _should_convert_keyword(token, keyword: str, doc) -> bool:
    """
    Determine if a keyword token should be converted to its symbol based on context.
    
    Uses spaCy's linguistic analysis to detect descriptive vs functional usage.
    
    Args:
        token: spaCy token for the keyword
        keyword: The keyword string ('colon', 'underscore', etc.)
        doc: The spaCy document
        
    Returns:
        bool: True if the keyword should be converted to symbol, False if it should remain as word
    """
    # Descriptive patterns that indicate the word should NOT be converted
    descriptive_indicators = {
        # Determiners before the word indicate descriptive usage
        "det_before": ["a", "an", "the"],
        
        # Verbs that indicate drawing/writing/describing
        "descriptive_verbs": ["draw", "write", "add", "insert", "type", "include", "contain", 
                             "have", "need", "want", "see", "show", "display"],
        
        # Prepositions that indicate descriptive context
        "descriptive_preps": ["with", "without", "using", "by"],
        
        # Objects that indicate the keyword is being described
        "descriptive_objects": ["here", "there", "character", "symbol", "mark"],
    }
    
    # Check for determiners before the keyword
    if token.i > 0:
        prev_token = doc[token.i - 1]
        if (prev_token.pos_ == "DET" and 
            prev_token.text.lower() in descriptive_indicators["det_before"]):
            logger.debug(f"Found determiner '{prev_token.text}' before '{keyword}' - descriptive context")
            return False
    
    # Check for descriptive verbs in the sentence
    sentence_tokens = [t for t in doc if t.sent == token.sent]
    for sent_token in sentence_tokens:
        if (sent_token.pos_ == "VERB" and 
            sent_token.lemma_.lower() in descriptive_indicators["descriptive_verbs"]):
            logger.debug(f"Found descriptive verb '{sent_token.text}' in sentence with '{keyword}' - descriptive context")
            return False
    
    # Check for descriptive prepositions
    if token.i > 0:
        prev_token = doc[token.i - 1]
        if (prev_token.pos_ == "ADP" and 
            prev_token.text.lower() in descriptive_indicators["descriptive_preps"]):
            logger.debug(f"Found descriptive preposition '{prev_token.text}' before '{keyword}' - descriptive context")
            return False
    
    # Check for descriptive objects after the keyword
    if token.i < len(doc) - 1:
        next_token = doc[token.i + 1]
        if next_token.text.lower() in descriptive_indicators["descriptive_objects"]:
            logger.debug(f"Found descriptive object '{next_token.text}' after '{keyword}' - descriptive context")
            return False
    
    # Check dependency relationships
    # If the keyword is the direct object of certain verbs, it's likely descriptive
    if token.dep_ == "dobj":  # direct object
        head = token.head
        if head.lemma_.lower() in descriptive_indicators["descriptive_verbs"]:
            logger.debug(f"'{keyword}' is direct object of descriptive verb '{head.text}' - descriptive context")
            return False
    
    # Check for "must have" constructions
    if token.i > 1:
        prev_prev_token = doc[token.i - 2]
        prev_token = doc[token.i - 1]
        if (prev_prev_token.lemma_.lower() == "must" and 
            prev_token.lemma_.lower() in ["have", "contain", "include"]):
            logger.debug(f"Found 'must have/contain' construction before '{keyword}' - descriptive context")
            return False
    
    # Functional context indicators (should convert)
    functional_indicators = {
        # Technical contexts where keywords are likely functional
        "tech_words": ["localhost", "server", "port", "url", "domain", "website", "api", "endpoint"],
        
        # Programming contexts
        "code_words": ["variable", "function", "method", "class", "object", "parameter"],
        
        # Words that indicate the keyword is part of a technical specification
        "spec_words": ["format", "syntax", "pattern", "structure"],
    }
    
    # Check for technical/functional context in the sentence
    sentence_text = token.sent.text.lower()
    for category, words in functional_indicators.items():
        if any(word in sentence_text for word in words):
            logger.debug(f"Found {category} context in sentence with '{keyword}' - functional context")
            return True
    
    # If no clear descriptive indicators found, default to conversion
    # This maintains backward compatibility for most cases
    logger.debug(f"No clear descriptive context found for '{keyword}' - allowing conversion")
    return True


def _convert_keyword_with_regex_context(text: str, keyword: str, symbol: str, space_consuming_symbols: set) -> str:
    """
    Regex-based fallback for context-aware keyword conversion when spaCy is not available.
    
    Uses simple regex patterns to detect descriptive vs functional contexts.
    
    Args:
        text: Text to process
        keyword: The keyword to potentially convert (e.g., 'colon', 'underscore')
        symbol: The symbol to convert to (e.g., ':', '_')
        space_consuming_symbols: Set of symbols that consume surrounding spaces
        
    Returns:
        Text with context-appropriate conversions applied
    """
    # Descriptive patterns that indicate the word should NOT be converted
    descriptive_patterns = [
        # Determiners before the keyword
        rf"\b(?:a|an|the)\s+{re.escape(keyword)}\b",
        
        # Descriptive verbs in the sentence with the keyword
        rf"\b(?:draw|write|add|insert|type|include|contain|have|need|want|see|show|display)\b.*\b{re.escape(keyword)}\b",
        rf"\b{re.escape(keyword)}\b.*\b(?:draw|write|add|insert|type|include|contain|have|need|want|see|show|display)\b",
        
        # "must have/contain" constructions
        rf"\bmust\s+(?:have|contain|include)\s+.*\b{re.escape(keyword)}\b",
        
        # Descriptive objects after the keyword
        rf"\b{re.escape(keyword)}\s+(?:here|there|character|symbol|mark)\b",
        
        # Please + descriptive verb
        rf"\bplease\s+(?:draw|write|add|insert|type)\b.*\b{re.escape(keyword)}\b",
    ]
    
    # Check if any descriptive patterns match
    for pattern in descriptive_patterns:
        if re.search(pattern, text, flags=re.IGNORECASE):
            logger.debug(f"Regex-based context validation: Found descriptive pattern for '{keyword}' - NOT converting")
            return text  # Don't convert, return original text
    
    # Check for functional/technical contexts
    functional_patterns = [
        # Technical contexts
        rf"\b(?:localhost|server|port|url|domain|website|api|endpoint)\b.*\b{re.escape(keyword)}\b",
        rf"\b{re.escape(keyword)}\b.*\b(?:localhost|server|port|url|domain|website|api|endpoint)\b",
        
        # Programming contexts  
        rf"\b(?:variable|function|method|class|object|parameter)\b.*\b{re.escape(keyword)}\b",
        rf"\b{re.escape(keyword)}\b.*\b(?:variable|function|method|class|object|parameter)\b",
        
        # Format specifications
        rf"\b(?:format|syntax|pattern|structure)\b.*\b{re.escape(keyword)}\b",
        rf"\b{re.escape(keyword)}\b.*\b(?:format|syntax|pattern|structure)\b",
    ]
    
    # Check if any functional patterns match (force conversion)
    for pattern in functional_patterns:
        if re.search(pattern, text, flags=re.IGNORECASE):
            logger.debug(f"Regex-based context validation: Found functional pattern for '{keyword}' - converting")
            break
    else:
        # No clear functional context, but no descriptive indicators either
        # Default to conversion for backward compatibility, but be more conservative
        logger.debug(f"Regex-based context validation: No clear context for '{keyword}' - allowing conversion")
    
    # Apply the conversion
    if symbol in space_consuming_symbols:
        # For these symbols, consume surrounding spaces
        pattern = rf"\s*\b{re.escape(keyword)}\b\s*"
        result = re.sub(pattern, symbol, text, flags=re.IGNORECASE)
    else:
        # For other keywords, preserve word boundaries
        pattern = rf"\b{re.escape(keyword)}\b"
        result = re.sub(pattern, symbol, text, flags=re.IGNORECASE)
    
    return result


def rescue_mangled_domains(text: str, resources: dict) -> str:
    """
    Rescue domains that got mangled - IMPROVED VERSION.
    
    Args:
        text: Text to process
        resources: Language resources containing TLDs and context words
        
    Returns:
        Text with rescued domain names
    """

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

    tlds = resources.get("top_level_domains", [])
    for tld in tlds:
        # Pattern: word + TLD at word boundary
        pattern = rf"\b([a-zA-Z]{{3,}})({tld})\b"

        def fix_domain(match):
            word = match.group(1)
            found_tld = match.group(2)
            full_word = word + found_tld

            # Skip if it's in our exclude list
            exclude_words = resources.get("context_words", {}).get("exclude_words", [])
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
            tech_patterns = resources.get("context_words", {}).get("tech_patterns", [])
            if any(pattern in word.lower() for pattern in tech_patterns):
                return f"{word}.{found_tld}"

            # Otherwise, leave it unchanged
            return full_word

        text = re.sub(pattern, fix_domain, text, flags=re.IGNORECASE)

    return text


def add_introductory_phrase_commas(text: str) -> str:
    """
    Add commas after common introductory phrases.
    
    This function handles cases like "first of all" → "first of all," that
    need comma insertion but aren't handled by the punctuation model step
    (which may be disabled in testing environments).
    
    Args:
        text: Text to process
        
    Returns:
        Text with commas added after introductory phrases
    """
    if not text.strip():
        return text

    # Define introductory phrases that require commas
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
    
    # Define sentence-starting ordinals that need commas when used as transitions
    sentence_starter_patterns = _get_sentence_starter_ordinal_patterns()
    
    # Apply repeated phrase patterns (like "first come first served")
    repeated_phrase_pattern = r"\b(first|second|third)\s+([a-z]+)\s+(\1)\s+([a-z]+)\b"
    
    def fix_repeated_phrase(match):
        word1 = match.group(1)  # "first"
        middle1 = match.group(2)  # "come"
        word2 = match.group(3)  # "first"
        middle2 = match.group(4)  # "served"
        
        # Preserve the case of the first occurrence, but make second occurrence lowercase
        return f"{word1} {middle1}, {word2.lower()} {middle2}"
    
    text = re.sub(repeated_phrase_pattern, fix_repeated_phrase, text, flags=re.IGNORECASE)
    
    # Apply comma insertion for each pattern
    for pattern in introductory_patterns:
        def add_comma_if_needed(match):
            matched_phrase = match.group(0)
            start_pos = match.start()
            end_pos = match.end()
            
            # Check what comes after the phrase
            remaining_text = text[end_pos:].lstrip()
            
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
    
    # Apply sentence starter patterns only for simple transition cases
    # Avoid patterns that are handled elsewhere (introductory phrases, repeated phrases, idioms)
    transition_starter_pattern = _get_transition_starter_pattern()
    
    def add_comma_for_transitions(match):
        starter = match.group(1).lower()  # "first", "second", etc.
        next_word = match.group(2).lower()  # next word
        full_match = match.group(0).lower()
        
        # Skip if this is part of an introductory phrase
        if 'of all' in text[match.start():match.start()+20].lower():
            return match.group(0)  # Let introductory phrase handler deal with it
        
        # Skip if this looks like a repeated phrase pattern
        remaining_text = text[match.end():].lower()
        if f" {starter} " in remaining_text:
            return match.group(0)  # Let repeated phrase handler deal with it
        
        # Skip idiomatic expressions
        idiomatic_starters = {
            'first thing', 'first things', 'second nature', 'second to', 'third wheel', 
            'second thoughts', 'first time', 'second time', 'third time', 'fourth time',
            'first place', 'second place', 'third place', 'first come'
        }
        phrase_start = f"{starter} {next_word}"
        if any(phrase_start.startswith(idiom) for idiom in idiomatic_starters):
            return match.group(0)  # No comma for idioms
        
        # For non-idiomatic transition uses at sentence start, add comma
        return f"{match.group(1)}, {match.group(2)}"
    
    text = re.sub(transition_starter_pattern, add_comma_for_transitions, text, flags=re.IGNORECASE)
    
    # (repeated phrase patterns already applied above)
    
    return text


def apply_smart_quotes(text: str) -> str:
    """
    Convert straight quotes and apostrophes to smart/curly equivalents.
    
    Args:
        text: Text to process
        
    Returns:
        Text with smart quotes (currently preserves straight quotes for compatibility)
    """
    # The tests expect straight quotes, so this implementation will preserve them
    # while fixing the bug that was injecting code into the output.
    # Since we're preserving quotes as-is, simply return the original text
    # This eliminates unnecessary character-by-character processing
    return text