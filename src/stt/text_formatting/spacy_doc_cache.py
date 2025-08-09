"""
Enhanced SpaCy document processing with advanced caching and performance optimization.

This module provides a centralized way to manage SpaCy document creation
and caching to eliminate redundant nlp(text) calls throughout the text
formatting pipeline. Includes content-based caching, thread safety,
document attribute caching, and comprehensive performance monitoring.
"""

import logging
import hashlib
import threading
from typing import Optional, Dict, Any, Tuple, Set
from functools import lru_cache
from weakref import WeakValueDictionary

logger = logging.getLogger(__name__)


class SpacyDocumentProcessor:
    """Enhanced SpaCy document processing with advanced caching, thread safety, and content-based keys"""
    
    def __init__(self, nlp_model: Optional[Any] = None, max_cache_size: int = 50):
        """
        Initialize the document processor.
        
        Args:
            nlp_model: SpaCy NLP model instance
            max_cache_size: Maximum number of documents to cache (increased default)
        """
        self.nlp = nlp_model
        self.max_cache_size = max_cache_size
        
        # Enhanced caching with content-based keys and thread safety
        self._doc_cache: Dict[str, Any] = {}  # Changed to string keys for content-based hashing
        self._cache_order = []  # For LRU eviction
        self._cache_lock = threading.RLock()  # Thread-safe access
        
        # Cache statistics for monitoring
        self._cache_hits = 0
        self._cache_misses = 0
        self._total_requests = 0
        
        # Document attribute cache for faster access to common attributes
        self._token_cache: WeakValueDictionary = WeakValueDictionary()
        self._entity_cache: Dict[str, list] = {}
        
        # Track processed texts for avoiding redundant processing
        self._processed_texts: Set[str] = set()
        
    def get_or_create_doc(self, text: str, force_create: bool = False, cache_attributes: bool = True) -> Optional[Any]:
        """
        Get cached doc or create new one with enhanced content-based caching.
        
        Args:
            text: Text to process
            force_create: If True, always create a new doc (for modified text)
            cache_attributes: If True, cache common document attributes
            
        Returns:
            SpaCy doc object or None if processing fails
        """
        with self._cache_lock:
            self._total_requests += 1
            
            if not text or not self.nlp:
                return None
                
            # For empty or very short text, don't cache but still process
            if len(text.strip()) < 3:
                try:
                    return self.nlp(text)
                except (AttributeError, ValueError, IndexError) as e:
                    logger.warning(f"SpaCy processing failed for short text: {e}")
                    return None
            
            # Generate content-based cache key using secure hash
            cache_key = self._generate_cache_key(text)
            
            # If forcing new creation (e.g., text was modified), skip cache
            if force_create:
                try:
                    doc = self.nlp(text)
                    # Update cache with new doc
                    self._update_cache(cache_key, doc, text)
                    if cache_attributes:
                        self._cache_document_attributes(cache_key, doc)
                    self._cache_misses += 1  # Forced creation counts as miss
                    return doc
                except (AttributeError, ValueError, IndexError) as e:
                    logger.warning(f"SpaCy processing failed: {e}")
                    return None
            
            # Check cache first
            if cache_key in self._doc_cache:
                self._update_access_order(cache_key)
                self._cache_hits += 1
                return self._doc_cache[cache_key]
            
            # Create new document
            try:
                doc = self.nlp(text)
                self._processed_texts.add(text[:100])  # Track processed texts (truncated)
            except (AttributeError, ValueError, IndexError) as e:
                logger.warning(f"SpaCy processing failed: {e}")
                self._cache_misses += 1
                return None
                
            # Cache with LRU eviction
            self._update_cache(cache_key, doc, text)
            if cache_attributes:
                self._cache_document_attributes(cache_key, doc)
            self._cache_misses += 1
            return doc
    
    def _generate_cache_key(self, text: str) -> str:
        """Generate content-based cache key using SHA-256 hash."""
        # Use SHA-256 for better distribution and collision resistance
        return hashlib.sha256(text.encode('utf-8')).hexdigest()[:16]  # Use first 16 chars for efficiency
    
    def _cache_document_attributes(self, cache_key: str, doc: Any) -> None:
        """Cache commonly accessed document attributes for faster access."""
        try:
            # Cache entities list for fast entity access
            entities = [(ent.start, ent.end, ent.label_, ent.text) for ent in doc.ents]
            self._entity_cache[cache_key] = entities
        except Exception as e:
            logger.debug(f"Failed to cache document attributes: {e}")
    
    def get_cached_entities(self, text: str) -> Optional[list]:
        """Get cached entities for a text without processing the full document."""
        cache_key = self._generate_cache_key(text)
        return self._entity_cache.get(cache_key)
    
    def _update_cache(self, cache_key: str, doc: Any, original_text: str) -> None:
        """Update cache with LRU eviction and enhanced memory management."""
        # Remove from cache if already exists (for re-insertion at end)
        if cache_key in self._doc_cache:
            self._cache_order.remove(cache_key)
        
        # Evict oldest if at max capacity
        while len(self._doc_cache) >= self.max_cache_size and self._cache_order:
            oldest_key = self._cache_order.pop(0)
            self._doc_cache.pop(oldest_key, None)
            # Also clean up attribute caches
            self._entity_cache.pop(oldest_key, None)
        
        # Add new entry
        self._doc_cache[cache_key] = doc
        self._cache_order.append(cache_key)
    
    def _update_access_order(self, cache_key: str) -> None:
        """Update access order for LRU."""
        if cache_key in self._cache_order:
            self._cache_order.remove(cache_key)
            self._cache_order.append(cache_key)
    
    def clear_cache(self) -> None:
        """Clear document cache to free memory."""
        with self._cache_lock:
            self._doc_cache.clear()
            self._cache_order.clear()
            self._entity_cache.clear()
            self._processed_texts.clear()
            # Reset statistics
            self._cache_hits = 0
            self._cache_misses = 0
            self._total_requests = 0
        
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get comprehensive cache statistics for monitoring and optimization."""
        with self._cache_lock:
            hit_rate = self._cache_hits / self._total_requests if self._total_requests > 0 else 0
            return {
                'cache_size': len(self._doc_cache),
                'max_cache_size': self.max_cache_size,
                'cache_utilization': len(self._doc_cache) / self.max_cache_size if self.max_cache_size > 0 else 0,
                'hit_rate': hit_rate,
                'cache_hits': self._cache_hits,
                'cache_misses': self._cache_misses,
                'total_requests': self._total_requests,
                'entity_cache_size': len(self._entity_cache),
                'processed_texts_count': len(self._processed_texts)
            }
    
    def warm_cache(self, texts: list) -> None:
        """Pre-warm the cache with commonly used texts."""
        logger.info(f"Warming SpaCy document cache with {len(texts)} texts")
        for text in texts:
            if text and len(text.strip()) >= 3:
                self.get_or_create_doc(text, cache_attributes=True)
    
    def has_processed_similar_text(self, text: str, similarity_threshold: int = 90) -> bool:
        """Check if we've processed similar text before (based on prefix matching)."""
        text_prefix = text[:100]
        return text_prefix in self._processed_texts


# Global instance for use throughout the text formatting system
_global_doc_processor: Optional[SpacyDocumentProcessor] = None


def initialize_global_doc_processor(nlp_model: Optional[Any] = None, max_cache_size: int = 50) -> None:
    """Initialize the global document processor with enhanced caching."""
    global _global_doc_processor
    _global_doc_processor = SpacyDocumentProcessor(nlp_model, max_cache_size)
    logger.info(f"Initialized enhanced SpaCy document processor with cache size {max_cache_size}")


def get_global_doc_processor() -> Optional[SpacyDocumentProcessor]:
    """Get the global document processor instance."""
    return _global_doc_processor


def get_or_create_shared_doc(text: str, nlp_model: Optional[Any] = None, force_create: bool = False) -> Optional[Any]:
    """
    Primary function for getting or creating shared SpaCy documents.
    
    This is the main entry point for all SpaCy document processing in the pipeline.
    It provides enhanced caching, thread safety, and performance monitoring.
    
    Args:
        text: Text to process
        nlp_model: Optional NLP model (uses global processor if None)
        force_create: If True, always create a new doc
        
    Returns:
        SpaCy doc object or None if processing fails
    """
    processor = get_global_doc_processor()
    if not processor:
        # Fallback: initialize with provided model or return None
        if nlp_model:
            initialize_global_doc_processor(nlp_model)
            processor = get_global_doc_processor()
        else:
            return None
    
    return processor.get_or_create_doc(text, force_create=force_create, cache_attributes=True)

@lru_cache(maxsize=256)  # Increased cache size for better performance
def get_cached_spacy_doc(text: str, nlp_model_id: int) -> Optional[Any]:
    """
    LRU cached function for SpaCy document creation.
    
    This provides an additional caching layer using functools.lru_cache
    for frequently accessed short texts. Now delegates to enhanced processor.
    
    Args:
        text: Text to process
        nlp_model_id: ID of the nlp model (for cache key uniqueness)
        
    Returns:
        SpaCy doc object or None
    """
    return get_or_create_shared_doc(text)

def log_cache_performance() -> None:
    """Log current cache performance statistics."""
    processor = get_global_doc_processor()
    if processor:
        stats = processor.get_cache_stats()
        logger.info(f"SpaCy Cache Stats: {stats['cache_hits']} hits, {stats['cache_misses']} misses, "
                   f"{stats['hit_rate']:.2%} hit rate, {stats['cache_utilization']:.2%} utilization")