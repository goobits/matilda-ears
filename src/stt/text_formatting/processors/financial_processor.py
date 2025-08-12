"""
Financial entity processor combining detection and conversion.

This module migrates FinancialDetector and FinancialConverter to the new
EntityProcessor pattern, eliminating code duplication and providing a
cleaner abstraction.
"""

import re
from typing import Dict, List, Any, Optional, Pattern

from stt.text_formatting.entity_processor import BaseNumericProcessor, ProcessingRule
from stt.text_formatting.common import Entity, EntityType
from stt.text_formatting.utils import is_inside_entity
from stt.text_formatting.modern_pattern_cache import cached_pattern


class FinancialProcessor(BaseNumericProcessor):
    """Processor for financial entities (currency, dollar-cents, cents)."""
    
    def _init_detection_rules(self) -> List[ProcessingRule]:
        """Initialize detection rules for financial entities."""
        # Build patterns
        number_pattern = self._build_number_pattern()
        currency_units = self.resources.get("currency", {}).get("units", [])
        unit_pattern = r"(?:" + "|".join(sorted(currency_units, key=len, reverse=True)) + r")"
        
        return [
            # Dollar-cents pattern (highest priority)
            ProcessingRule(
                pattern=self._build_dollar_cents_pattern(),
                entity_type=EntityType.DOLLAR_CENTS,
                metadata_extractor=self._extract_dollar_cents_metadata,
                priority=60
            ),
            # Euro-cents pattern (same priority as dollar-cents)
            ProcessingRule(
                pattern=self._build_euro_cents_pattern(),
                entity_type=EntityType.EURO_CENTS,
                metadata_extractor=self._extract_euro_cents_metadata,
                priority=60
            ),
            # Pound-pence pattern (same priority as dollar-cents)
            ProcessingRule(
                pattern=self._build_pound_pence_pattern(),
                entity_type=EntityType.POUND_PENCE,
                metadata_extractor=self._extract_pound_pence_metadata,
                priority=60
            ),
            # Cents only pattern
            ProcessingRule(
                pattern=self._build_cents_pattern(),
                entity_type=EntityType.CENTS,
                metadata_extractor=self._extract_cents_metadata,
                priority=50
            ),
            # General currency pattern (with context filtering)
            ProcessingRule(
                pattern=re.compile(
                    number_pattern + r"(?:\s+" + number_pattern + r")*\s+" + unit_pattern + r"\b", 
                    re.IGNORECASE
                ),
                entity_type=EntityType.CURRENCY,
                metadata_extractor=self._extract_currency_metadata,
                context_filters=[self._filter_pound_context],
                priority=40
            ),
        ]
    
    def _init_conversion_methods(self) -> Dict[EntityType, str]:
        """Initialize conversion methods for financial types."""
        return {
            EntityType.CURRENCY: "convert_currency",
            EntityType.MONEY: "convert_currency",  # SpaCy detected money entity
            EntityType.DOLLAR_CENTS: "convert_dollar_cents",
            EntityType.EURO_CENTS: "convert_euro_cents",
            EntityType.POUND_PENCE: "convert_pound_pence",
            EntityType.CENTS: "convert_cents",
        }
    
    def detect_entities(self, text: str, entities: List[Entity], 
                       all_entities: Optional[List[Entity]] = None) -> None:
        """
        Detect financial entities with additional SpaCy-based detection.
        
        This overrides the base method to add SpaCy currency detection.
        """
        # First apply regex-based rules
        super().detect_entities(text, entities, all_entities)
        
        # Then apply SpaCy-based detection if available
        if self.nlp:
            doc = self.get_spacy_doc(text)
            if doc:
                self._detect_currency_with_spacy(doc, text, entities, all_entities)
    
    # Pattern builders
    
    def _build_number_pattern(self) -> str:
        """Build pattern for number words."""
        return r"\b(?:" + "|".join(sorted(self.number_parser.all_number_words, key=len, reverse=True)) + r")"
    
    @cached_pattern(category='financial', language_aware=True)
    def _build_dollar_cents_pattern(self) -> Pattern[str]:
        """Build pattern for 'X dollars and Y cents'."""
        number_words = "|".join(re.escape(word) for word in self.number_parser.all_number_words)
        number_pattern = rf"(?:\d+|(?:{number_words})(?:\s+(?:{number_words}))*)"
        
        return re.compile(
            rf"\b({number_pattern})\s+dollars?\s+and\s+({number_pattern})\s+cents?\b",
            re.IGNORECASE
        )
    
    @cached_pattern(category='financial', language_aware=True)
    def _build_cents_pattern(self) -> Pattern[str]:
        """Build pattern for 'X cents'."""
        number_words = "|".join(re.escape(word) for word in self.number_parser.all_number_words)
        number_pattern = rf"(?:\d+|(?:{number_words})(?:\s+(?:{number_words}))*)"
        
        return re.compile(
            rf"\b({number_pattern})\s+cents?\b",
            re.IGNORECASE
        )
    
    @cached_pattern(category='financial', language_aware=True)
    def _build_euro_cents_pattern(self) -> Pattern[str]:
        """Build pattern for 'X euros and Y cents'."""
        number_words = "|".join(re.escape(word) for word in self.number_parser.all_number_words)
        number_pattern = rf"(?:\d+|(?:{number_words})(?:\s+(?:{number_words}))*)"
        
        return re.compile(
            rf"\b({number_pattern})\s+euros?\s+and\s+({number_pattern})\s+cents?\b",
            re.IGNORECASE
        )
    
    @cached_pattern(category='financial', language_aware=True)
    def _build_pound_pence_pattern(self) -> Pattern[str]:
        """Build pattern for 'X pounds and Y pence'."""
        number_words = "|".join(re.escape(word) for word in self.number_parser.all_number_words)
        number_pattern = rf"(?:\d+|(?:{number_words})(?:\s+(?:{number_words}))*)"
        
        return re.compile(
            rf"\b({number_pattern})\s+pounds?\s+and\s+({number_pattern})\s+pence\b",
            re.IGNORECASE
        )
    
    # Metadata extractors
    
    def _extract_currency_metadata(self, match: re.Match) -> Dict[str, Any]:
        """Extract metadata from currency matches."""
        match_text = match.group().lower()
        currency_units = self.resources.get("currency", {}).get("units", [])
        
        # Find which unit was matched
        unit = None
        for test_unit in currency_units:
            if match_text.endswith(" " + test_unit.lower()):
                unit = test_unit
                break
        
        if unit:
            # Extract number part
            number_text = match_text[: -(len(unit) + 1)]  # Remove unit and space
            return {
                "number": number_text.strip(),
                "unit": unit
            }
        
        return {}
    
    def _extract_dollar_cents_metadata(self, match: re.Match) -> Dict[str, Any]:
        """Extract metadata from dollar-cents matches."""
        dollars_text = match.group(1).strip()
        cents_text = match.group(2).strip()
        
        # Parse the amounts
        dollars_value = self.number_parser.parse(dollars_text)
        cents_value = self.number_parser.parse(cents_text)
        
        return {
            "dollars": dollars_value,
            "cents": cents_value
        }
    
    def _extract_cents_metadata(self, match: re.Match) -> Dict[str, Any]:
        """Extract metadata from cents matches."""
        cents_text = match.group(1).strip()
        cents_value = self.number_parser.parse(cents_text)
        
        return {
            "cents": cents_value
        }
    
    def _extract_euro_cents_metadata(self, match: re.Match) -> Dict[str, Any]:
        """Extract metadata from euro-cents matches."""
        euros_text = match.group(1).strip()
        cents_text = match.group(2).strip()
        
        # Parse the amounts
        euros_value = self.number_parser.parse(euros_text)
        cents_value = self.number_parser.parse(cents_text)
        
        return {
            "euros": euros_value,
            "cents": cents_value
        }
    
    def _extract_pound_pence_metadata(self, match: re.Match) -> Dict[str, Any]:
        """Extract metadata from pound-pence matches."""
        pounds_text = match.group(1).strip()
        pence_text = match.group(2).strip()
        
        # Parse the amounts
        pounds_value = self.number_parser.parse(pounds_text)
        pence_value = self.number_parser.parse(pence_text)
        
        return {
            "pounds": pounds_value,
            "pence": pence_value
        }
    
    # Context filters
    
    def _filter_pound_context(self, text: str, start: int, end: int) -> bool:
        """Filter pounds based on currency vs weight context."""
        match_text = text[start:end].lower()
        
        # Only filter if the match contains "pound"
        if "pound" not in match_text:
            return True
        
        prefix_context = text[:start].lower()
        currency_contexts = self.resources.get("context_words", {}).get("currency_contexts", [])
        weight_contexts = self.resources.get("context_words", {}).get("weight_contexts", [])
        
        # If it has clear weight context, filter out. Default to currency for ambiguous cases.
        if any(ctx in prefix_context for ctx in weight_contexts):
            return False
        
        return True
    
    # SpaCy-based detection
    
    def _detect_currency_with_spacy(self, doc, text: str, entities: List[Entity], 
                                   all_entities: Optional[List[Entity]] = None) -> None:
        """Detect currency entities using SpaCy's grammar analysis."""
        # Define currency units
        currency_units = set(self.resources.get("currency", {}).get("units", []))
        
        i = 0
        while i < len(doc):
            token = doc[i]
            
            # Find a number-like token
            is_a_number = (
                (token.like_num and token.lower_ not in self.resources.get("technical", {}).get("ordinal_words", []))
                or (token.ent_type_ == "CARDINAL")
                or (token.lower_ in self.number_parser.all_number_words)
            )
            
            if is_a_number:
                number_tokens = [token]
                j = i + 1
                # Greedily consume all consecutive number-related words
                while j < len(doc) and (
                    doc[j].like_num
                    or doc[j].lower_ in self.number_parser.all_number_words
                    or doc[j].lower_ in {"and", "point", "dot"}
                ):
                    if doc[j].lower_ != "and":
                        number_tokens.append(doc[j])
                    j += 1
                
                # Check if next token is a currency unit
                if j < len(doc):
                    unit_token = doc[j]
                    unit_lemma = unit_token.lemma_.lower()
                    
                    if unit_lemma in currency_units:
                        # Apply pound context filtering
                        if unit_token.text.lower() in ["pound", "pounds"]:
                            if not self._filter_pound_context(text, number_tokens[0].idx, 
                                                            unit_token.idx + len(unit_token.text)):
                                i += 1
                                continue
                        
                        start_pos = number_tokens[0].idx
                        end_pos = unit_token.idx + len(unit_token.text)
                        
                        # Check overlap
                        if not is_inside_entity(start_pos, end_pos, all_entities or []):
                            number_text = " ".join([t.text for t in number_tokens])
                            entities.append(
                                Entity(
                                    start=start_pos,
                                    end=end_pos,
                                    text=text[start_pos:end_pos],
                                    type=EntityType.CURRENCY,
                                    metadata={"number": number_text, "unit": unit_token.text},
                                )
                            )
                        i = j  # Move past the consumed unit
                        continue
            i += 1
    
    # Conversion methods
    
    def convert_currency(self, entity: Entity, full_text: str = "") -> str:
        """Convert currency like 'twenty five dollars' -> '$25'."""
        text = entity.text
        
        # If it's already in currency format (e.g., "25.99" from SpaCy MONEY)
        if re.match(r"^\d+\.?\d*$", text.strip()):
            # Check if dollar sign precedes this entity in the full text
            if full_text and entity.start > 0 and full_text[entity.start - 1] == "$":
                # Dollar sign already present, just return the number
                return text.strip()
            # No dollar sign, add it
            return f"${text.strip()}"
        
        # Handle spoken currency
        text, trailing_punct = self.extract_trailing_punctuation(text)
        
        # Extract currency unit
        unit = None
        if entity.metadata and "unit" in entity.metadata:
            unit = entity.metadata["unit"].lower()
        else:
            # Try to extract unit from text
            text_lower = text.lower()
            currency_map = self.mapping_registry.get_currency_map()
            for currency_word in currency_map:
                if currency_word in text_lower:
                    unit = currency_word
                    break
        
        # Get the currency symbol
        currency_map = self.mapping_registry.get_currency_map()
        symbol = currency_map.get(unit, "$")  # Default to $ if not found
        
        # Extract and parse the number
        number_text = None
        if entity.metadata and "number" in entity.metadata:
            number_text = entity.metadata["number"]
        else:
            # Remove currency word and parse
            text_lower = text.lower()
            if unit:
                pattern = r"\b" + re.escape(unit) + r"s?\b"
                number_text = re.sub(pattern, "", text_lower).strip()
            else:
                # Try removing any known currency words
                for currency_word in currency_map:
                    if currency_word in text_lower:
                        pattern = r"\b" + re.escape(currency_word) + r"s?\b"
                        number_text = re.sub(pattern, "", text_lower).strip()
                        unit = currency_word
                        break
        
        if number_text:
            amount = self.number_parser.parse(number_text)
            if amount:
                # Format based on currency position
                return self.format_with_currency_position(amount, symbol, unit, trailing_punct)
        
        return entity.text  # Fallback
    
    def convert_dollar_cents(self, entity: Entity) -> str:
        """Convert 'X dollars and Y cents' to '$X.Y'."""
        if entity.metadata:
            dollars = entity.metadata.get("dollars", "0")
            cents = entity.metadata.get("cents", "0")
            if dollars and cents:
                try:
                    dollars_int = int(dollars) if isinstance(dollars, str) else dollars
                    cents_int = int(cents) if isinstance(cents, str) else cents
                    # Ensure cents is zero-padded to 2 digits
                    cents_str = str(cents_int).zfill(2)
                    return f"${dollars_int}.{cents_str}"
                except (ValueError, TypeError):
                    pass
        return entity.text
    
    def convert_cents(self, entity: Entity) -> str:
        """Convert 'X cents' to '¢X' or '$0.XX'."""
        if entity.metadata:
            cents = entity.metadata.get("cents", "0")
            if cents:
                try:
                    cents_int = int(cents) if isinstance(cents, str) else cents
                    # Format as cents symbol (preferred)
                    return f"{cents_int}¢"
                except (ValueError, TypeError):
                    pass
        return entity.text

    def convert_euro_cents(self, entity: Entity) -> str:
        """Convert 'X euros and Y cents' to '€X.Y'."""
        if entity.metadata:
            euros = entity.metadata.get("euros", "0")
            cents = entity.metadata.get("cents", "0")
            if euros and cents:
                try:
                    euros_int = int(euros) if isinstance(euros, str) else euros
                    cents_int = int(cents) if isinstance(cents, str) else cents
                    # Ensure cents is zero-padded to 2 digits
                    cents_str = str(cents_int).zfill(2)
                    return f"€{euros_int}.{cents_str}"
                except (ValueError, TypeError):
                    pass
        return entity.text

    def convert_pound_pence(self, entity: Entity) -> str:
        """Convert 'X pounds and Y pence' to '£X.Y'."""
        if entity.metadata:
            pounds = entity.metadata.get("pounds", "0")
            pence = entity.metadata.get("pence", "0")
            if pounds and pence:
                try:
                    pounds_int = int(pounds) if isinstance(pounds, str) else pounds
                    pence_int = int(pence) if isinstance(pence, str) else pence
                    # Ensure pence is zero-padded to 2 digits
                    pence_str = str(pence_int).zfill(2)
                    return f"£{pounds_int}.{pence_str}"
                except (ValueError, TypeError):
                    pass
        return entity.text