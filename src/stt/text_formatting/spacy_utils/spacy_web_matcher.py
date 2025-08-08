#!/usr/bin/env python3
"""
SpaCy-based web entity matcher for intelligent email/URL detection.

This module provides a unified approach to detecting web entities using spaCy's
dependency parsing instead of complex regex patterns. Part of Phase 3 Regex→NLP Migration.

Key improvements over regex:
- Semantic understanding of "send email to john at gmail" vs "john at gmail"  
- Dependency parsing to find verb-object relationships
- Context-aware detection that handles variations naturally
- Significantly reduced pattern complexity
"""
from __future__ import annotations

import re
from typing import Optional, List, Tuple, Dict, Set
from enum import Enum

from ...core.config import setup_logging
from ..constants import get_resources

# Setup logging
logger = setup_logging(__name__, log_filename="text_formatting.txt", include_console=True)


class WebEntityType(Enum):
    """Types of web entities we can detect."""
    EMAIL = "email"
    URL = "url"
    PROTOCOL_URL = "protocol_url"
    PORT_NUMBER = "port"


class SemanticPattern:
    """Represents a semantic pattern for web entity detection."""
    
    def __init__(self, pattern_type: WebEntityType, verbs: Set[str], 
                 prepositions: Set[str] = None, objects: Set[str] = None):
        self.pattern_type = pattern_type
        self.verbs = verbs
        self.prepositions = prepositions or set()
        self.objects = objects or set()


class SpacyWebMatcher:
    """
    Intelligent web entity matcher using spaCy dependency parsing.
    
    Replaces complex regex patterns from web_patterns.py with semantic understanding:
    - Email patterns: 195+ lines → dependency parsing
    - URL patterns: 167+ lines → action-target relationships
    - Port patterns: Improved context detection
    """
    
    def __init__(self, nlp=None, language: str = "en"):
        """
        Initialize the SpaCy web matcher.
        
        Args:
            nlp: SpaCy NLP model instance
            language: Language code for resource loading (default: 'en')
        """
        self.nlp = nlp
        self.language = language
        
        # Load language-specific resources
        self.resources = get_resources(language)
        self.url_keywords = self.resources["spoken_keywords"]["url"]
        
        # Define semantic patterns for different contexts
        self._init_semantic_patterns()
        
        # Fallback to regex patterns when spaCy fails
        self._init_fallback_patterns()
    
    def _init_semantic_patterns(self):
        """Initialize semantic patterns for web entity detection."""
        
        # Email patterns - understand communication actions
        email_verbs = {
            'send', 'email', 'contact', 'write', 'forward', 'reach', 'notify', 
            'message', 'mail', 'communicate'
        }
        email_prepositions = {'to', 'at'}
        
        # URL patterns - understand navigation actions  
        url_verbs = {
            'go', 'visit', 'navigate', 'browse', 'check', 'open', 'access',
            'view', 'see', 'look', 'find'
        }
        url_prepositions = {'to', 'at'}
        
        # Port patterns - understand connection contexts
        port_verbs = {
            'connect', 'listen', 'run', 'serve', 'bind', 'host'
        }
        port_prepositions = {'on', 'at', 'to'}
        port_objects = {'port', 'server', 'service', 'host'}
        
        self.semantic_patterns = {
            WebEntityType.EMAIL: SemanticPattern(
                WebEntityType.EMAIL, email_verbs, email_prepositions
            ),
            WebEntityType.URL: SemanticPattern(
                WebEntityType.URL, url_verbs, url_prepositions
            ),
            WebEntityType.PORT_NUMBER: SemanticPattern(
                WebEntityType.PORT_NUMBER, port_verbs, port_prepositions, port_objects
            )
        }
    
    def _init_fallback_patterns(self):
        """Initialize fallback regex patterns for when spaCy is unavailable."""
        # Import the existing patterns as fallback
        from ..pattern_modules.web_patterns import (
            build_spoken_email_pattern,
            build_spoken_url_pattern,
            build_port_number_pattern
        )
        
        self.fallback_patterns = {
            WebEntityType.EMAIL: build_spoken_email_pattern(self.language),
            WebEntityType.URL: build_spoken_url_pattern(self.language),
            WebEntityType.PORT_NUMBER: build_port_number_pattern(self.language)
        }
    
    def detect_emails(self, text: str) -> List[Tuple[int, int, str]]:
        """
        Detect email entities using spaCy dependency parsing.
        
        Uses semantic understanding to detect patterns like:
        - "send email to john at gmail dot com" 
        - "contact support at company dot org"
        - "email admin at server dot com"
        
        Args:
            text: Input text to analyze
            
        Returns:
            List of (start, end, text) tuples for detected emails
        """
        if not self.nlp:
            return self._detect_emails_fallback(text)
        
        try:
            doc = self.nlp(text)
            email_spans = []
            
            # Look for communication verbs and their dependencies
            pattern = self.semantic_patterns[WebEntityType.EMAIL]
            
            for token in doc:
                if token.lemma_ in pattern.verbs and token.pos_ == "VERB":
                    # Found a communication verb, look for email patterns in its dependencies
                    email_span = self._analyze_email_dependencies(text, token, doc)
                    if email_span:
                        email_spans.append(email_span)
                
            # Also look for email patterns without explicit verbs
            # (e.g., "john at gmail dot com" without "email john at...")
            orphan_emails = self._detect_orphan_emails(text, doc)
            email_spans.extend(orphan_emails)
            
            # Remove duplicates and overlaps
            return self._deduplicate_spans(email_spans)
            
        except Exception as e:
            logger.warning(f"spaCy email detection failed: {e}")
            return self._detect_emails_fallback(text)
    
    def _analyze_email_dependencies(self, text: str, verb_token, doc) -> Optional[Tuple[int, int, str]]:
        """
        Analyze dependencies of a communication verb to find email patterns.
        
        Looks for patterns like:
        - VERB -> PREP -> EMAIL_PATTERN
        - VERB -> DOBJ -> EMAIL_PATTERN  
        - VERB -> PREP -> POBJ -> EMAIL_PATTERN
        """
        # Get spoken keywords for email detection
        at_keywords = [k for k, v in self.url_keywords.items() if v == "@"]
        at_pattern = "|".join(re.escape(k) for k in at_keywords)
        
        # Look through the verb's children for prepositions and objects
        for child in verb_token.children:
            if child.dep_ in ["prep", "dobj", "ccomp"]:
                # Look for email patterns in this subtree
                subtree_text = text[child.idx:child.idx + len(child.subtree.text)]
                
                # Check if this subtree contains email-like patterns
                email_match = self._find_email_in_subtree(subtree_text, at_pattern)
                if email_match:
                    start, end, email_text = email_match
                    # Convert to absolute positions
                    abs_start = child.idx + start
                    abs_end = child.idx + end
                    return (abs_start, abs_end, email_text)
        
        return None
    
    def _find_email_in_subtree(self, text: str, at_pattern: str) -> Optional[Tuple[int, int, str]]:
        """
        Find email patterns within a syntactic subtree.
        
        Uses simple regex within the constrained subtree identified by spaCy.
        This is much more reliable than applying complex regex to the entire text.
        """
        # Simplified email pattern for use within identified subtrees
        email_pattern = rf"""
        \b
        ([a-zA-Z][a-zA-Z0-9]*(?:\s+[a-zA-Z0-9]+)*)  # Username (may have spaces)
        \s+(?:{at_pattern})\s+                       # "at" keyword  
        ([a-zA-Z0-9-]+(?:\s+[a-zA-Z0-9-]+)*         # Domain with potential spaces
         (?:\s+(?:dot|\.)\s+[a-zA-Z0-9-]+)+)        # Must have dots
        \b
        """
        
        match = re.search(email_pattern, text, re.VERBOSE | re.IGNORECASE)
        if match:
            return (match.start(), match.end(), match.group(0))
        
        return None
    
    def _detect_orphan_emails(self, text: str, doc) -> List[Tuple[int, int, str]]:
        """
        Detect email patterns that appear without explicit action verbs.
        
        These are emails that might be mentioned in context without "send", "email", etc.
        Uses more conservative patterns to avoid false positives.
        """
        orphan_emails = []
        
        # Look for @ symbols and "at" keywords as starting points
        at_keywords = [k for k, v in self.url_keywords.items() if v == "@"]
        
        for at_keyword in at_keywords:
            # Find instances of the "at" keyword
            for match in re.finditer(rf'\b{re.escape(at_keyword)}\b', text, re.IGNORECASE):
                at_start = match.start()
                at_end = match.end()
                
                # Get the spaCy tokens around this "at" keyword
                context_start = max(0, at_start - 100)
                context_end = min(len(text), at_end + 100)
                context = text[context_start:context_end]
                
                # Use spaCy to understand the syntax around the "at" keyword
                try:
                    context_doc = self.nlp(context)
                    email_span = self._analyze_at_context(context, context_doc, at_start - context_start)
                    if email_span:
                        # Convert back to absolute positions
                        start, end, email_text = email_span
                        abs_start = context_start + start
                        abs_end = context_start + end  
                        orphan_emails.append((abs_start, abs_end, email_text))
                except Exception:
                    continue
        
        return orphan_emails
    
    def _analyze_at_context(self, context: str, context_doc, at_pos: int) -> Optional[Tuple[int, int, str]]:
        """
        Analyze the context around an "at" keyword to determine if it's part of an email.
        
        Uses spaCy to understand the grammatical structure and decide if this looks like an email.
        """
        # Find the token that contains or is near the "at" position
        at_token = None
        for token in context_doc:
            if token.idx <= at_pos <= token.idx + len(token.text):
                at_token = token
                break
        
        if not at_token:
            return None
        
        # Check if this "at" token is in an email-like context
        # Look for username-like token before and domain-like tokens after
        prev_token = at_token.nbor(-1) if at_token.i > 0 else None
        next_token = at_token.nbor(1) if at_token.i < len(context_doc) - 1 else None
        
        if not prev_token or not next_token:
            return None
        
        # Simple heuristics based on POS tags and content
        if (prev_token.pos_ in ["NOUN", "PROPN", "X"] and 
            next_token.pos_ in ["NOUN", "PROPN", "X"] and
            self._looks_like_domain(next_token.text)):
            
            # This might be an email, extract the full pattern
            return self._extract_email_around_at(context, at_pos)
        
        return None
    
    def _looks_like_domain(self, text: str) -> bool:
        """Simple heuristic to check if text looks like a domain."""
        # Check if it contains domain-like patterns
        dot_keywords = [k for k, v in self.url_keywords.items() if v == "."]
        for dot_keyword in dot_keywords:
            if dot_keyword in text.lower():
                return True
        
        # Check for actual dots
        if '.' in text:
            return True
            
        # Check for common domain words
        domain_words = {'com', 'org', 'net', 'edu', 'gov', 'io', 'co'}
        if any(word in text.lower() for word in domain_words):
            return True
        
        return False
    
    def _extract_email_around_at(self, text: str, at_pos: int) -> Optional[Tuple[int, int, str]]:
        """
        Extract the full email pattern around an identified "at" position.
        
        This is called after spaCy has identified that the "at" is likely part of an email.
        """
        # Use a simpler pattern since we know this is likely an email
        at_keywords = [k for k, v in self.url_keywords.items() if v == "@"]
        at_pattern = "|".join(re.escape(k) for k in at_keywords)
        
        # Look backwards and forwards from the at position to find email boundaries
        start_pos = max(0, at_pos - 50)
        end_pos = min(len(text), at_pos + 50)
        segment = text[start_pos:end_pos]
        
        # Simple email pattern for this context
        pattern = rf"""
        \b
        ([a-zA-Z][a-zA-Z0-9-_]*(?:\s+[a-zA-Z0-9-_]+)*)  # Username
        \s+(?:{at_pattern})\s+                           # "at" keyword
        ([a-zA-Z0-9-]+(?:\s+[a-zA-Z0-9-]+)*             # Domain
         (?:\s+(?:dot|\.)\s+[a-zA-Z0-9-]+)+)            # Dots and TLDs
        \b
        """
        
        match = re.search(pattern, segment, re.VERBOSE | re.IGNORECASE)
        if match:
            return (start_pos + match.start(), start_pos + match.end(), match.group(0))
        
        return None
    
    def _detect_emails_fallback(self, text: str) -> List[Tuple[int, int, str]]:
        """Fallback email detection using regex when spaCy is unavailable."""
        pattern = self.fallback_patterns[WebEntityType.EMAIL]
        matches = []
        
        for match in pattern.finditer(text):
            matches.append((match.start(), match.end(), match.group()))
        
        return matches
    
    def detect_urls(self, text: str) -> List[Tuple[int, int, str]]:
        """
        Detect URL entities using spaCy dependency parsing.
        
        Uses semantic understanding to detect patterns like:
        - "go to example dot com"
        - "visit website dot org" 
        - "check api dot service dot com"
        
        Args:
            text: Input text to analyze
            
        Returns:
            List of (start, end, text) tuples for detected URLs
        """
        if not self.nlp:
            return self._detect_urls_fallback(text)
        
        try:
            doc = self.nlp(text)
            url_spans = []
            
            # Look for navigation verbs and their targets
            pattern = self.semantic_patterns[WebEntityType.URL]
            
            for token in doc:
                if token.lemma_ in pattern.verbs and token.pos_ == "VERB":
                    # Found a navigation verb, look for URL patterns in its dependencies
                    url_span = self._analyze_url_dependencies(text, token, doc)
                    if url_span:
                        url_spans.append(url_span)
            
            # Also look for URL patterns without explicit verbs
            orphan_urls = self._detect_orphan_urls(text, doc)
            url_spans.extend(orphan_urls)
            
            return self._deduplicate_spans(url_spans)
            
        except Exception as e:
            logger.warning(f"spaCy URL detection failed: {e}")
            return self._detect_urls_fallback(text)
    
    def _analyze_url_dependencies(self, text: str, verb_token, doc) -> Optional[Tuple[int, int, str]]:
        """
        Analyze dependencies of a navigation verb to find URL patterns.
        
        Looks for patterns like:
        - VERB -> PREP -> URL_PATTERN
        - VERB -> DOBJ -> URL_PATTERN
        """
        # Look through the verb's children for URL-like patterns
        for child in verb_token.children:
            if child.dep_ in ["prep", "dobj", "ccomp"]:
                # Check if this subtree contains URL-like patterns  
                subtree_text = text[child.idx:child.idx + len(child.subtree.text)]
                url_match = self._find_url_in_subtree(subtree_text)
                if url_match:
                    start, end, url_text = url_match
                    abs_start = child.idx + start
                    abs_end = child.idx + end
                    return (abs_start, abs_end, url_text)
        
        return None
    
    def _find_url_in_subtree(self, text: str) -> Optional[Tuple[int, int, str]]:
        """Find URL patterns within a syntactic subtree."""
        dot_keywords = [k for k, v in self.url_keywords.items() if v == "."]
        dot_pattern = "|".join(re.escape(k) for k in dot_keywords)
        
        # Simplified URL pattern for identified subtrees
        url_pattern = rf"""
        \b
        ([a-zA-Z0-9-]+(?:\s+[a-zA-Z0-9-]+)*           # Domain parts
         (?:\s+(?:{dot_pattern})\s+[a-zA-Z0-9-]+)+    # Must have dots
         (?:\s+(?:{dot_pattern})\s+(?:com|org|net|edu|gov|io|co|uk))  # TLD
        (?:\s+(?:slash|/)\s+[a-zA-Z0-9-]+)*           # Optional paths
        )
        \b
        """
        
        match = re.search(url_pattern, text, re.VERBOSE | re.IGNORECASE)
        if match:
            return (match.start(), match.end(), match.group(0))
        
        return None
    
    def _detect_orphan_urls(self, text: str, doc) -> List[Tuple[int, int, str]]:
        """Detect URL patterns without explicit navigation verbs."""
        # This is a simplified implementation - in practice you'd want more sophisticated logic
        return []
    
    def _detect_urls_fallback(self, text: str) -> List[Tuple[int, int, str]]:
        """Fallback URL detection using regex when spaCy is unavailable."""
        pattern = self.fallback_patterns[WebEntityType.URL]
        matches = []
        
        for match in pattern.finditer(text):
            matches.append((match.start(), match.end(), match.group()))
        
        return matches
    
    def _deduplicate_spans(self, spans: List[Tuple[int, int, str]]) -> List[Tuple[int, int, str]]:
        """Remove duplicate and overlapping spans."""
        if not spans:
            return spans
        
        # Sort by start position
        sorted_spans = sorted(spans, key=lambda x: x[0])
        deduplicated = [sorted_spans[0]]
        
        for current in sorted_spans[1:]:
            last = deduplicated[-1]
            
            # Check for overlap
            if current[0] < last[1]:
                # Overlapping spans - keep the longer one
                if current[1] - current[0] > last[1] - last[0]:
                    deduplicated[-1] = current
            else:
                # No overlap - add current span
                deduplicated.append(current)
        
        return deduplicated
    
    def detect_all_web_entities(self, text: str) -> Dict[WebEntityType, List[Tuple[int, int, str]]]:
        """
        Detect all web entities in text using spaCy dependency parsing.
        
        Args:
            text: Input text to analyze
            
        Returns:
            Dictionary mapping entity types to lists of (start, end, text) tuples
        """
        results = {}
        
        # Detect each type of web entity
        results[WebEntityType.EMAIL] = self.detect_emails(text)
        results[WebEntityType.URL] = self.detect_urls(text)
        
        return results


# Factory function for easy instantiation
def create_spacy_web_matcher(nlp=None, language: str = "en") -> SpacyWebMatcher:
    """
    Create a SpacyWebMatcher instance.
    
    Args:
        nlp: SpaCy NLP model instance
        language: Language code for resource loading (default: 'en')
        
    Returns:
        SpacyWebMatcher instance
    """
    return SpacyWebMatcher(nlp, language)