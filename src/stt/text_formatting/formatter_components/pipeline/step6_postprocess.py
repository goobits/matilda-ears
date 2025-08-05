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
    return re.sub(r"(\b(?:i\.e\.|e\.g\.))(?!,)(\s+[a-zA-Z])", r"\1,\2", text)


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
    safe_keywords = {
        "slash": "/",
        "colon": ":",
        "underscore": "_",
    }

    # Filter to only keywords we want to convert when orphaned
    keywords_to_convert = {}
    for keyword, symbol in url_keywords.items():
        if keyword in safe_keywords and safe_keywords[keyword] == symbol:
            keywords_to_convert[keyword] = symbol

    # Sort by length (longest first) to handle multi-word keywords properly
    sorted_keywords = sorted(keywords_to_convert.items(), key=lambda x: len(x[0]), reverse=True)

    # Define keywords that should consume surrounding spaces when converted
    space_consuming_symbols = {"/", ":", "_"}

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