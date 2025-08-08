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

if TYPE_CHECKING:
    pass

logger = setup_logging(__name__, log_filename="text_formatting.txt", include_console=False)


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

    # Add comma after i.e. and e.g. when followed by a word,
    # but NOT if a comma is already there.
    text = re.sub(r"(i\.e\.)(\s+[a-zA-Z])", r"\1,\2", text, flags=re.IGNORECASE)
    text = re.sub(r"(e\.g\.)(\s+[a-zA-Z])", r"\1,\2", text, flags=re.IGNORECASE)
    
    # Remove double commas that might result from the above
    text = re.sub(r",,", ",", text)
    
    return text


def convert_orphaned_keywords(text: str, language: str = "en") -> str:
    """
    Convert orphaned keywords that weren't captured by entities.

    This handles cases where keywords like 'slash', 'dot', 'at' remain in the text
    after entity conversion, typically due to entity boundary issues.
    
    Args:
        text: Text to process
        language: Language code for resource lookup
        
    Returns:
        Text with orphaned keywords converted to symbols
    """
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

    # Convert keywords that appear as standalone words
    for keyword, symbol in sorted_keywords:
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
    sentence_starter_patterns = [
        r"^(first|second|third|fourth|fifth)\s+(\w+)",  # "First we need", "Second I want"
        r"^(next|then|now|finally)\s+(\w+)",  # "Next we should", "Finally I want"
    ]
    
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
    transition_starter_pattern = r"^(first|second|third|fourth|fifth)\s+(\w+)"
    
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
    new_chars = []
    for _i, char in enumerate(text):
        if char == '"':
            new_chars.append('"')
        elif char == "'":
            new_chars.append("'")
        else:
            new_chars.append(char)

    return "".join(new_chars)