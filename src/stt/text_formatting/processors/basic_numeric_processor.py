"""
Basic numeric entity processor combining detection and conversion.

This module demonstrates the new EntityProcessor pattern by combining
BasicNumberDetector and BasicNumericConverter functionality.
"""

import re
from typing import Dict, List, Any

from stt.text_formatting.entity_processor import BaseNumericProcessor, ProcessingRule
from stt.text_formatting.common import Entity, EntityType
from stt.text_formatting import regex_patterns

class BasicNumericProcessor(BaseNumericProcessor):
    """Processor for basic numeric entities (cardinals, ordinals, fractions, ranges)."""
    
    def _init_detection_rules(self) -> List[ProcessingRule]:
        """Initialize detection rules for basic numbers."""
        return [
            # Ordinal detection with high priority
            ProcessingRule(
                pattern=regex_patterns.SPOKEN_ORDINAL_PATTERN,
                entity_type=EntityType.ORDINAL,
                metadata_extractor=self._extract_ordinal_metadata,
                context_filters=[self._filter_idiomatic_ordinals],
                priority=10
            ),
            # Fraction detection
            ProcessingRule(
                pattern=regex_patterns.SPOKEN_FRACTION_PATTERN,
                entity_type=EntityType.FRACTION,
                metadata_extractor=self._extract_fraction_metadata,
                priority=8
            ),
            # Compound fraction detection
            ProcessingRule(
                pattern=regex_patterns.SPOKEN_COMPOUND_FRACTION_PATTERN,
                entity_type=EntityType.FRACTION,
                metadata_extractor=self._extract_compound_fraction_metadata,
                priority=9
            ),
            # Numeric range detection
            ProcessingRule(
                pattern=regex_patterns.NUMERIC_RANGE_PATTERN,
                entity_type=EntityType.NUMERIC_RANGE,
                metadata_extractor=self._extract_range_metadata,
                priority=7
            ),
            # Consecutive digits detection
            ProcessingRule(
                pattern=regex_patterns.CONSECUTIVE_DIGITS_PATTERN,
                entity_type=EntityType.CONSECUTIVE_DIGITS,
                metadata_extractor=self._extract_digits_metadata,
                priority=5
            ),
        ]
        
    def _init_conversion_methods(self) -> Dict[EntityType, str]:
        """Initialize conversion methods for basic numeric types."""
        return {
            EntityType.CARDINAL: "convert_cardinal",
            EntityType.ORDINAL: "convert_ordinal",
            EntityType.FRACTION: "convert_fraction",
            EntityType.NUMERIC_RANGE: "convert_numeric_range",
            EntityType.CONSECUTIVE_DIGITS: "convert_consecutive_digits",
        }
    
    # Metadata extractors
    
    def _extract_ordinal_metadata(self, match: re.Match) -> Dict[str, Any]:
        """Extract metadata from ordinal matches."""
        return {
            "ordinal_word": match.group(0).strip().lower()
        }
        
    def _extract_fraction_metadata(self, match: re.Match) -> Dict[str, Any]:
        """Extract metadata from fraction matches."""
        groups = match.groups()
        metadata = {}
        
        if len(groups) >= 2:
            metadata["numerator"] = groups[0] if groups[0] else None
            metadata["denominator"] = groups[1] if groups[1] else None
            
        return metadata
        
    def _extract_compound_fraction_metadata(self, match: re.Match) -> Dict[str, Any]:
        """Extract metadata from compound fraction matches."""
        groups = match.groups()
        metadata = {
            "is_compound": True
        }
        
        if len(groups) >= 3:
            metadata["whole"] = groups[0] if groups[0] else None
            metadata["numerator"] = groups[1] if groups[1] else None
            metadata["denominator"] = groups[2] if groups[2] else None
            
        return metadata
        
    def _extract_range_metadata(self, match: re.Match) -> Dict[str, Any]:
        """Extract metadata from numeric range matches."""
        groups = match.groups()
        metadata = {}
        
        if len(groups) >= 2:
            metadata["start"] = groups[0] if groups[0] else None
            metadata["end"] = groups[1] if groups[1] else None
            
        return metadata
        
    def _extract_digits_metadata(self, match: re.Match) -> Dict[str, Any]:
        """Extract metadata from consecutive digit matches."""
        return {
            "digits": match.group(0).strip()
        }
    
    # Context filters
    
    def _filter_idiomatic_ordinals(self, text: str, start: int, end: int) -> bool:
        """Filter out idiomatic ordinal uses."""
        ordinal_text = text[start:end].lower().strip()
        
        # Check if it's an idiomatic use
        text_after = text[end:end + 20].lower()
        
        # Common idiomatic patterns to skip
        idiomatic_patterns = [
            "first thing",
            "first of all", 
            "second thought",
            "third party",
        ]
        
        for pattern in idiomatic_patterns:
            if pattern.startswith(ordinal_text) and text[start:start + len(pattern)].lower() == pattern:
                return False
                
        return True
    
    # Conversion methods
    
    def convert_cardinal(self, entity: Entity, full_text: str = "") -> str:
        """Convert cardinal numbers with context awareness."""
        text = entity.text
        
        # Handle conversational context
        if self.is_conversational_context(entity, full_text):
            # Keep spelled out in conversational context
            return text
            
        # Parse the number
        parsed = self.parse_number(text)
        if parsed:
            return parsed
            
        return text
        
    def convert_ordinal(self, entity: Entity, full_text: str = "") -> str:
        """Convert ordinal numbers with position detection."""
        ordinal_word = entity.metadata.get("ordinal_word", entity.text).lower()
        
        # Check if it's idiomatic
        if self.is_idiomatic_context(entity, full_text, ordinal_word):
            # Capitalize if at sentence start
            if entity.start == 0 or (entity.start > 0 and full_text[entity.start - 1] in ".!?"):
                return ordinal_word.capitalize()
            return ordinal_word
            
        # Get numeric ordinal
        numeric_ordinal = self.ordinal_word_to_numeric.get(ordinal_word)
        if not numeric_ordinal:
            # Try to parse as number and add suffix
            parsed = self.parse_number(ordinal_word.replace("th", "").replace("st", "").replace("nd", "").replace("rd", ""))
            if parsed:
                numeric_ordinal = self._add_ordinal_suffix(parsed)
            else:
                return entity.text
                
        # Check for positional context
        if self.is_positional_context(entity, full_text):
            return self.convert_ordinal_to_position(numeric_ordinal)
            
        return numeric_ordinal
        
    def convert_fraction(self, entity: Entity) -> str:
        """Convert spoken fractions to numeric format."""
        metadata = entity.metadata
        
        if metadata.get("is_compound"):
            # Handle compound fractions
            whole = metadata.get("whole", "")
            numerator = metadata.get("numerator", "one")
            denominator = metadata.get("denominator", "")
            
            # Parse components
            whole_num = self.parse_number(whole) if whole else ""
            num_num = self.parse_number(numerator) if numerator else "1"
            denom_num = self.denominator_mappings.get(denominator, self.parse_number(denominator))
            
            if whole_num and num_num and denom_num:
                # Check for Unicode fraction
                fraction_key = f"{num_num}/{denom_num}"
                unicode_frac = self.mapping_registry.get_unicode_fraction_mappings().get(fraction_key)
                
                if unicode_frac:
                    return f"{whole_num}{unicode_frac}"
                else:
                    return f"{whole_num} {num_num}/{denom_num}"
        else:
            # Simple fraction
            numerator = metadata.get("numerator", "one")
            denominator = metadata.get("denominator", "")
            
            # Parse components
            num_num = self.parse_number(numerator) if numerator else "1"
            denom_num = self.denominator_mappings.get(denominator, self.parse_number(denominator))
            
            if num_num and denom_num:
                # Check for Unicode fraction
                fraction_key = f"{num_num}/{denom_num}"
                unicode_frac = self.mapping_registry.get_unicode_fraction_mappings().get(fraction_key)
                
                if unicode_frac:
                    return unicode_frac
                else:
                    return f"{num_num}/{denom_num}"
                    
        return entity.text
        
    def convert_numeric_range(self, entity: Entity) -> str:
        """Convert spoken numeric ranges."""
        metadata = entity.metadata
        
        start = metadata.get("start", "")
        end = metadata.get("end", "")
        
        # Parse numbers
        start_num = self.parse_number(start) if start else None
        end_num = self.parse_number(end) if end else None
        
        if start_num and end_num:
            return f"{start_num}-{end_num}"
            
        return entity.text
        
    def convert_consecutive_digits(self, entity: Entity) -> str:
        """Convert consecutive spoken digits."""
        digits = entity.metadata.get("digits", entity.text)
        
        # Parse as individual digits
        parsed = self.parse_as_digits(digits)
        if parsed:
            return parsed
            
        return entity.text
    
    # Helper methods
    
    def _add_ordinal_suffix(self, number: str) -> str:
        """Add appropriate ordinal suffix to a number."""
        try:
            n = int(number)
            if 10 <= n % 100 <= 20:
                suffix = "th"
            else:
                suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
            return f"{number}{suffix}"
        except ValueError:
            return number
    
    # Additional detection methods for SpaCy-based detection
    
    def detect_spacy_cardinals(self, text: str, entities: List[Entity], 
                              all_entities: List[Entity] = None) -> None:
        """Detect cardinal numbers using SpaCy."""
        if not self.nlp:
            return
            
        doc = self.get_spacy_doc(text)
        if not doc:
            return
            
        check_entities = all_entities if all_entities is not None else entities
        
        for token in doc:
            if (token.pos_ == "NUM" and 
                not self._is_ordinal_token(token) and
                not is_inside_entity(token.idx, token.idx + len(token.text), check_entities)):
                
                # Additional validation
                if not self._should_skip_cardinal(token, doc):
                    entities.append(Entity(
                        start=token.idx,
                        end=token.idx + len(token.text),
                        text=token.text,
                        type=EntityType.CARDINAL,
                        metadata={"pos": token.pos_, "tag": token.tag_}
                    ))
    
    def _is_ordinal_token(self, token) -> bool:
        """Check if a token represents an ordinal number."""
        text_lower = token.text.lower()
        return (text_lower in self.ordinal_word_to_numeric or
                text_lower.endswith(("st", "nd", "rd", "th")))
                
    def _should_skip_cardinal(self, token, doc) -> bool:
        """Check if a cardinal number should be skipped."""
        # Skip if it's part of a larger entity
        if token.head != token and token.head.pos_ == "NUM":
            return True
            
        # Skip years in certain contexts
        if token.text.isdigit() and len(token.text) == 4:
            # Simple year detection
            year_val = int(token.text)
            if 1900 <= year_val <= 2100:
                return True
                
        return False