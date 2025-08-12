"""
Context-based number word detection using research-backed approaches.

This module implements standard techniques for disambiguating when number
words should be converted to digits vs. kept as words.
"""

from typing import List, Set, Optional, Tuple
from enum import Enum
import re

from stt.text_formatting.common import Entity, EntityType


class NumberWordDecision(Enum):
    """Decision for number word conversion."""
    KEEP_WORD = "keep"
    CONVERT_DIGIT = "convert"
    CONTEXT_DEPENDENT = "context"


class NumberWordContextAnalyzer:
    """
    Analyzes context to determine if number words should be converted to digits.
    
    Based on research from:
    - Sproat et al. (2001) "Normalization of non-standard words"
    - Taylor (2009) "Text-to-speech synthesis" 
    - Zhang et al. (2019) "Neural Models of Text Normalization"
    """
    
    def __init__(self, nlp=None):
        """Initialize with optional SpaCy model."""
        self.nlp = nlp
        
        # Load idiom protection resources
        try:
            from stt.text_formatting.constants import get_resources
            self.resources = get_resources("en")
        except ImportError:
            self.resources = {}
        
        # Common patterns where numbers should remain as words
        self.keep_as_word_patterns = [
            # Determiners
            r'\b(the|a|an)\s+one\s+(of|who|that|which)',
            r'\b(the|a|an)\s+one\s+\w+ing\b',  # "the one thing", "a one standing"
            
            # Idiomatic expressions
            r'\bone\s+(of\s+the|of\s+these|of\s+those|of\s+them)\b',
            r'\b(no|any|every|each)\s+one\b',
            r'\bone\s+or\s+the\s+other\b',  # "one or the other"
            r'\btwo\s+can\s+play\s+that\s+game\b',  # "two can play that game"
            r'\bone\s+\w+\s+for\s+each\s+of\s+those\s+(two|three)\b',  # "one test for each of those two issues"
            r'\b(the\s+)?(two|three)\s+(of\s+us|options|issues|things)\b',  # "the two of us", "two options"
            r'\bcatch\s+twenty\s+two\b',  # "catch twenty two" - common idiom
            
            # Pronouns and emphasis
            r'\b(only|just|another|other)\s+one\b',
            r'\byou\'re\s+the\s+one\b',
            r'\bthe\s+one\s+(and\s+only|who|that)\b',
            
            # Common phrases
            r'\bone\s+(day|time|moment|minute)\b(?!\s+ago)',  # But not "one day ago"
            r'\bat\s+one\s+with\b',
            r'\bone\s+by\s+one\b',
            r'\bone\s+on\s+one\b',
            
            # Specific idiomatic patterns that should never convert
            r'\bfirst\s+things\s+first\b',  # "first things first"
            r'\bsecond\s+thoughts\b',  # "second thoughts"
            r'\bthird\s+time\'s\s+the\s+charm\b',  # "third time's the charm"
            
            # Additional comprehensive idiom patterns
            r'\b(the\s+)?whole\s+nine\s+yards\b',  # "the whole nine yards", "whole nine yards"
            r'\bcloud\s+nine\b',  # "cloud nine"
            r'\bon\s+cloud\s+nine\b',  # "on cloud nine"
            r'\bbehind\s+the\s+eight\s+ball\b',  # "behind the eight ball"
            r'\b(in\s+)?one\s+fell\s+swoop\b',  # "one fell swoop", "in one fell swoop"
            r'\b(my\s+)?two\s+cents\b(?!\s+(worth|per|each|coin))',  # "two cents", "my two cents" but not "two cents worth"
            r'\b(the\s+)?seven\s+deadly\s+sins\b',  # "seven deadly sins", "the seven deadly sins"
            r'\bnine\s+to\s+five\b',  # "nine to five"
            r'\bdressed\s+to\s+the\s+nines\b',  # "dressed to the nines"
            r'\bback\s+to\s+square\s+one\b',  # "back to square one"
            r'\btwo\s+peas\s+in\s+a\s+pod\b',  # "two peas in a pod"
            r'\bsix\s+feet\s+under\b',  # "six feet under"
            r'\bkill\s+two\s+birds\s+with\s+one\s+stone\b',  # "kill two birds with one stone"
            r'\bsix\s+of\s+one\s+half\s+a\s+dozen\s+of\s+the\s+other\b',  # "six of one half a dozen of the other"
            r'\b(the\s+)?seven\s+year\s+itch\b',  # "seven year itch", "the seven year itch"
            r'\btwenty\s+twenty\s+(vision|hindsight)\b',  # "twenty twenty vision", "twenty twenty hindsight"
            r'\bzero\s+tolerance\b',  # "zero tolerance"
            r'\bfour\s+score\s+and\s+seven\b',  # "four score and seven"
            r'\b(a\s+)?picture\s+(is\s+)?worth\s+a\s+thousand\s+words\b',  # "a picture is worth a thousand words"
            r'\bone\s+foot\s+in\s+the\s+grave\b',  # "one foot in the grave"
            r'\bone\s+for\s+the\s+road\b',  # "one for the road"
            r'\btwo\s+wrongs\s+don\'t\s+make\s+a\s+right\b',  # "two wrongs don't make a right"
            r'\bthree\s+sheets\s+to\s+the\s+wind\b',  # "three sheets to the wind"
            r'\bat\s+sixes\s+and\s+sevens\b',  # "at sixes and sevens"
        ]
        
        # Patterns where numbers should be converted to digits
        self.convert_to_digit_patterns = [
            # Explicit numbering
            r'\b(page|chapter|section|volume|part|step|line|verse)\s+(\w+)\b',
            r'\b(number|#|no\.?)\s*(\w+)\b',
            
            # Lists and sequences  
            r'\b(\w+)[,;]\s*(\w+)[,;]?\s*(?:and\s+)?(\w+)\b',  # "one, two, three"
            r'\b(step|item|point)\s+(\w+)[:.]',
            
            # Mathematical contexts
            r'\b(\w+)\s*(plus|minus|times|divided\s+by|over)\s*(\w+)\b',
            r'\b(\w+)\s*([\+\-\*/=])\s*(\w+)\b',
            
            # Measurements and quantities
            r'\b(\w+)\s+(feet|inches|meters|miles|pounds|dollars|percent)\b',
            r'\b(\w+)\s+(hundred|thousand|million|billion)\b',
            
            # Time expressions
            r'\b(\w+)\s+o\'clock\b',
            r'\b(\w+)\s+(a\.?m\.?|p\.?m\.?)\b',
            r'\b(\w+)\s+(hours?|minutes?|seconds?)\s+(ago|later|before|after)\b',
            r'\b(\w+)\s+(seconds?|minutes?|hours?|days?|weeks?|months?|years?)\b',  # duration units
            
            # Scores and rankings
            r'\b(\w+)\s+to\s+(\w+)\b(?=\s+(lead|win|victory|score))',
            r'\b(top|first|last)\s+(\w+)\b',
            
            # Technical contexts (Phase 1 additions)
            r'\bport\s+(\w+)\b',  # "port 8000"
            r'\b(\w+)\s+(users?|files?|errors?|requests?|items?|records?|operations?)\b',  # quantities
            r'\bstatus\s+code\s+(\w+)\b',  # "status code 404"
            r'\berror\s+(\w+)\b',  # "error 500"
            
            # Phase 14 additions - quantitative and technical contexts
            r'\bneed\s+(\w+)\s+(?:or\s+(\w+)\s+)?(?:examples?|items?|users?|files?)\b',  # "need one or two examples"
            r'\b(?:we|you|i)\s+(?:need|want|require)\s+(\w+)\s+(?:or\s+(\w+)\s+)?(?:examples?|items?|options?)\b',  # "we need one or two examples"
            r'\bhave\s+(\w+)\s+plus\s+(?:years?|months?)\s+(?:of\s+)?(?:experience|training)\b',  # "have two plus years of experience"
            r'\b(\w+)\s+plus\s+(?:years?|months?|weeks?|days?)\b',  # "two plus years" (mathematical/quantitative)
            r'\b(?:found|process|handle|manage|created?)\s+(\w+)\s+(?:errors?|items?|files?|users?)\b',  # "found three errors"
        ]
        
        # Number words to consider - expanded to include all number words that NumberParser handles
        self.number_words = {
            # Basic ones (0-19)
            'zero', 'one', 'two', 'three', 'four', 'five',
            'six', 'seven', 'eight', 'nine', 'ten',
            'eleven', 'twelve', 'thirteen', 'fourteen', 'fifteen',
            'sixteen', 'seventeen', 'eighteen', 'nineteen',
            # Tens (20-90)
            'twenty', 'thirty', 'forty', 'fifty', 'sixty', 'seventy', 'eighty', 'ninety',
            # Scale words
            'hundred', 'thousand', 'million', 'billion', 'trillion'
        }
    
    def should_convert_number_word(self, text: str, word_start: int, word_end: int) -> NumberWordDecision:
        """
        Determine if a number word at the given position should be converted.
        
        Args:
            text: Full text
            word_start: Start position of number word
            word_end: End position of number word
            
        Returns:
            Decision on whether to convert
        """
        word = text[word_start:word_end].lower()
        
        # Quick check if it's a number word
        if word not in self.number_words:
            return NumberWordDecision.KEEP_WORD
        
        # Get surrounding context
        context_start = max(0, word_start - 50)
        context_end = min(len(text), word_end + 50)
        context = text[context_start:context_end]
        
        # Check keep-as-word patterns
        for pattern in self.keep_as_word_patterns:
            if re.search(pattern, context, re.IGNORECASE):
                return NumberWordDecision.KEEP_WORD
        
        # Check resource-based idiom patterns
        if self._is_in_protected_idiom(text, word_start, word_end):
            return NumberWordDecision.KEEP_WORD
        
        # Check convert-to-digit patterns
        for pattern in self.convert_to_digit_patterns:
            if re.search(pattern, context, re.IGNORECASE):
                return NumberWordDecision.CONVERT_DIGIT
        
        # Use SpaCy if available
        if self.nlp:
            decision = self._analyze_with_spacy(text, word_start, word_end)
            if decision != NumberWordDecision.CONTEXT_DEPENDENT:
                return decision
        
        # Default heuristics
        return self._apply_heuristics(text, word_start, word_end)
    
    def _analyze_with_spacy(self, text: str, word_start: int, word_end: int) -> NumberWordDecision:
        """Use SpaCy for linguistic analysis."""
        try:
            doc = self.nlp(text)
            
            # Find the token
            target_token = None
            for token in doc:
                if token.idx <= word_start and token.idx + len(token.text) >= word_end:
                    target_token = token
                    break
            
            if not target_token:
                return NumberWordDecision.CONTEXT_DEPENDENT
            
            # POS tag analysis
            if target_token.pos_ == "DET":  # Determiner
                return NumberWordDecision.KEEP_WORD
            
            if target_token.pos_ == "NUM":
                # Check dependency
                if target_token.dep_ in ["det", "nsubj", "dobj"]:
                    # Could be either - need more context
                    return NumberWordDecision.CONTEXT_DEPENDENT
                elif target_token.dep_ in ["nummod", "compound"]:
                    # Likely a number modifier
                    return NumberWordDecision.CONVERT_DIGIT
            
            # Entity type analysis
            if target_token.ent_type_ == "CARDINAL":
                # Check if it's modifying something
                if any(child.dep_ in ["compound", "amod"] for child in target_token.children):
                    return NumberWordDecision.CONVERT_DIGIT
            
        except Exception:
            pass
        
        return NumberWordDecision.CONTEXT_DEPENDENT
    
    def _is_technical_context(self, text: str, word_start: int, word_end: int) -> bool:
        """Check if we're in a technical context that favors digit conversion."""
        # Get surrounding context (wider window for technical terms)
        context_start = max(0, word_start - 100)
        context_end = min(len(text), word_end + 100)
        context = text[context_start:context_end].lower()
        
        # Technical indicators
        technical_terms = [
            'port', 'error', 'status', 'code', 'version', 'page', 'line', 
            'step', 'item', 'api', 'http', 'server', 'client', 'request',
            'response', 'url', 'endpoint', 'timeout', 'retry', 'config',
            'setting', 'parameter', 'argument', 'function', 'method',
            'class', 'variable', 'value', 'property', 'field', 'attribute'
        ]
        
        # Check for technical terms in the context
        for term in technical_terms:
            if re.search(r'\b' + term + r'\b', context):
                return True
        
        # Check for patterns that suggest technical content
        technical_patterns = [
            r'\b\d+\.\d+\.\d+',  # version numbers
            r'\bhttps?://',       # URLs
            r'\b\w+\(\)',        # function calls
            r'\b\w+\.\w+',       # dot notation
            r'\b[A-Z_]+\b',      # constants
            r'\bGET|POST|PUT|DELETE\b',  # HTTP methods
        ]
        
        for pattern in technical_patterns:
            if re.search(pattern, context):
                return True
        
        return False
    
    def _is_in_protected_idiom(self, text: str, word_start: int, word_end: int) -> bool:
        """
        Check if the number word is part of a protected idiom using resource patterns.
        """
        # Get context around the word (wider window for idiom detection)
        context_start = max(0, word_start - 100)
        context_end = min(len(text), word_end + 100)
        context = text[context_start:context_end].lower()
        
        # Check idiom patterns from resources
        idiom_patterns = self.resources.get("idiom_protection", {}).get("idiom_context_patterns", [])
        for pattern in idiom_patterns:
            # Remove double backslashes from the pattern (they're for JSON escaping)
            clean_pattern = pattern.replace('\\\\', '\\')
            if re.search(clean_pattern, context, re.IGNORECASE):
                return True
        
        # Check specific exception phrases
        number_unit_exceptions = self.resources.get("idiom_protection", {}).get("number_unit_exceptions", {})
        for exception_phrase in number_unit_exceptions.keys():
            if exception_phrase.lower() in context:
                return True
        
        return False
    
    def _apply_heuristics(self, text: str, word_start: int, word_end: int) -> NumberWordDecision:
        """Apply additional heuristics for edge cases."""
        word = text[word_start:word_end].lower()
        
        # Check if we're in a technical context first
        if self._is_technical_context(text, word_start, word_end):
            # In technical contexts, prefer digit conversion unless very specific patterns
            prev_word_match = re.search(r'(\w+)\s+$', text[:word_start])
            if prev_word_match and prev_word_match.group(1).lower() in ['the', 'a', 'an']:
                # Only keep as word if it's a clear determiner pattern
                next_word_match = re.search(r'^\s+(\w+)', text[word_end:])
                if next_word_match and next_word_match.group(1).lower() in ['thing', 'person', 'way', 'of']:
                    return NumberWordDecision.KEEP_WORD
            return NumberWordDecision.CONVERT_DIGIT
        
        # Check previous word
        prev_word_match = re.search(r'(\w+)\s+$', text[:word_start])
        if prev_word_match:
            prev_word = prev_word_match.group(1).lower()
            
            # Strong indicators to keep as word
            if prev_word in ['the', 'a', 'an', 'only', 'just', 'another']:
                return NumberWordDecision.KEEP_WORD
            
            # Strong indicators to convert (expanded)
            if prev_word in ['page', 'chapter', 'section', 'step', 'number', 'port', 'error', 'status']:
                return NumberWordDecision.CONVERT_DIGIT
        
        # Check next word
        next_word_match = re.search(r'^\s+(\w+)', text[word_end:])
        if next_word_match:
            next_word = next_word_match.group(1).lower()
            
            # Units and quantities suggest conversion (expanded)
            if next_word in ['percent', 'dollars', 'feet', 'meters', 'miles', 'users', 'files', 'errors', 'requests', 'items', 'records', 'operations']:
                return NumberWordDecision.CONVERT_DIGIT
            
            # Scale words indicate numeric context
            if next_word in ['hundred', 'thousand', 'million', 'billion']:
                return NumberWordDecision.CONVERT_DIGIT
            
            # "one thing/person/way" patterns (keep conservative)
            if word == 'one' and next_word in ['thing', 'person', 'way', 'time', 'place']:
                return NumberWordDecision.KEEP_WORD
        
        # Check capitalization (beginning of sentence) - but be less conservative
        if word_start == 0 or (word_start > 0 and text[word_start-1] in '.!?'):
            # Only keep as word for very specific patterns at sentence start
            if word == 'one' and next_word_match and next_word_match.group(1).lower() in ['thing', 'person', 'way', 'time', 'place', 'of']:
                return NumberWordDecision.KEEP_WORD
            # Otherwise, even at sentence start, numbers can be digits
            return NumberWordDecision.CONVERT_DIGIT
        
        # More aggressive conversion - default to converting numbers unless clearly ambiguous
        if word == 'one':
            # Very specific cases where "one" should stay as word
            if prev_word_match and prev_word_match.group(1).lower() in ['the', 'a', 'an']:
                # But even then, check next word - if it suggests enumeration, convert
                if next_word_match:
                    next_word = next_word_match.group(1).lower()
                    if next_word in ['of', 'out', 'from', 'in', 'for', 'hundred', 'thousand', 'million']:
                        return NumberWordDecision.CONVERT_DIGIT
                return NumberWordDecision.KEEP_WORD
            # For all other contexts with "one", convert to digit
            return NumberWordDecision.CONVERT_DIGIT
        
        # All other numbers should convert by default
        return NumberWordDecision.CONVERT_DIGIT


def integrate_with_detector(analyzer: NumberWordContextAnalyzer, 
                           entities: List[Entity]) -> List[Entity]:
    """
    Filter entities based on context analysis.
    
    This would be integrated into the detection pipeline to prevent
    incorrect number word conversions.
    """
    filtered_entities = []
    
    for entity in entities:
        if entity.type == EntityType.CARDINAL:
            # Check if this cardinal should be kept as a word
            decision = analyzer.should_convert_number_word(
                entity.metadata.get('full_text', ''),
                entity.start,
                entity.end
            )
            
            if decision != NumberWordDecision.KEEP_WORD:
                filtered_entities.append(entity)
        else:
            filtered_entities.append(entity)
    
    return filtered_entities