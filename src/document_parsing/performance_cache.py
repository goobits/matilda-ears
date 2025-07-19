"""Document caching and performance optimization for large documents."""

import hashlib
import pickle
import time
import os
from typing import Optional, List, Dict, Any
from pathlib import Path
from src.document_parsing.base_parser import SemanticElement
from src.document_parsing.parser_factory import DocumentParserFactory


class DocumentCache:
    """Cache parsed documents for performance."""

    def __init__(self, cache_dir: str = ".cache/documents", max_cache_size_mb: int = 100):
        """Initialize document cache.
        
        Args:
            cache_dir: Directory to store cache files
            max_cache_size_mb: Maximum cache size in megabytes
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.max_cache_size = max_cache_size_mb * 1024 * 1024  # Convert to bytes
        
        # Cache metadata file
        self.metadata_file = self.cache_dir / "cache_metadata.json"
        self.metadata = self._load_metadata()

    def get_cache_key(self, content: str, format_hint: str = "") -> str:
        """Generate cache key from content hash and format hint."""
        content_hash = hashlib.sha256(content.encode()).hexdigest()[:16]
        if format_hint:
            return f"{format_hint}_{content_hash}.pkl"
        else:
            return f"auto_{content_hash}.pkl"

    def get_cached_elements(
        self, 
        content: str, 
        format_hint: str = ""
    ) -> Optional[List[SemanticElement]]:
        """Retrieve cached parsed elements if available and valid."""
        cache_key = self.get_cache_key(content, format_hint)
        cache_file = self.cache_dir / cache_key
        
        if not cache_file.exists():
            return None
        
        try:
            # Check cache age (expire after 24 hours by default)
            file_age = time.time() - cache_file.stat().st_mtime
            if file_age > 86400:  # 24 hours in seconds
                cache_file.unlink()
                self._remove_from_metadata(cache_key)
                return None
            
            # Load cached elements
            with open(cache_file, 'rb') as f:
                cached_data = pickle.load(f)
            
            # Update access time in metadata
            self._update_access_time(cache_key)
            
            return cached_data['elements']
            
        except (pickle.PickleError, KeyError, FileNotFoundError):
            # Remove corrupted cache file
            if cache_file.exists():
                cache_file.unlink()
            self._remove_from_metadata(cache_key)
            return None

    def cache_elements(
        self, 
        content: str, 
        elements: List[SemanticElement], 
        format_hint: str = "",
        processing_time: float = 0.0
    ) -> None:
        """Cache parsed elements for future use."""
        cache_key = self.get_cache_key(content, format_hint)
        cache_file = self.cache_dir / cache_key
        
        try:
            # Prepare cache data
            cache_data = {
                'elements': elements,
                'content_length': len(content),
                'format_hint': format_hint,
                'processing_time': processing_time,
                'cached_at': time.time()
            }
            
            # Write to cache file
            with open(cache_file, 'wb') as f:
                pickle.dump(cache_data, f)
            
            # Update metadata
            self._add_to_metadata(cache_key, cache_data)
            
            # Clean up cache if too large
            self._cleanup_cache_if_needed()
            
        except Exception as e:
            # If caching fails, continue without caching
            if cache_file.exists():
                cache_file.unlink()

    def _load_metadata(self) -> Dict:
        """Load cache metadata from file."""
        if self.metadata_file.exists():
            try:
                import json
                with open(self.metadata_file, 'r') as f:
                    return json.load(f)
            except:
                pass
        return {"files": {}, "total_size": 0, "last_cleanup": time.time()}

    def _save_metadata(self) -> None:
        """Save cache metadata to file."""
        try:
            import json
            with open(self.metadata_file, 'w') as f:
                json.dump(self.metadata, f, indent=2)
        except:
            pass

    def _add_to_metadata(self, cache_key: str, cache_data: Dict) -> None:
        """Add file to metadata tracking."""
        cache_file = self.cache_dir / cache_key
        file_size = cache_file.stat().st_size if cache_file.exists() else 0
        
        self.metadata["files"][cache_key] = {
            "size": file_size,
            "content_length": cache_data['content_length'],
            "format_hint": cache_data['format_hint'],
            "processing_time": cache_data['processing_time'],
            "cached_at": cache_data['cached_at'],
            "last_accessed": time.time()
        }
        
        self.metadata["total_size"] = sum(f["size"] for f in self.metadata["files"].values())
        self._save_metadata()

    def _remove_from_metadata(self, cache_key: str) -> None:
        """Remove file from metadata tracking."""
        if cache_key in self.metadata["files"]:
            del self.metadata["files"][cache_key]
            self.metadata["total_size"] = sum(f["size"] for f in self.metadata["files"].values())
            self._save_metadata()

    def _update_access_time(self, cache_key: str) -> None:
        """Update last access time for a cache file."""
        if cache_key in self.metadata["files"]:
            self.metadata["files"][cache_key]["last_accessed"] = time.time()
            self._save_metadata()

    def _cleanup_cache_if_needed(self) -> None:
        """Clean up cache if it exceeds size limit."""
        if self.metadata["total_size"] <= self.max_cache_size:
            return
        
        # Sort files by last access time (least recently used first)
        files_by_access = sorted(
            self.metadata["files"].items(),
            key=lambda x: x[1]["last_accessed"]
        )
        
        # Remove oldest files until under size limit
        for cache_key, file_info in files_by_access:
            cache_file = self.cache_dir / cache_key
            if cache_file.exists():
                cache_file.unlink()
            
            self._remove_from_metadata(cache_key)
            
            if self.metadata["total_size"] <= self.max_cache_size * 0.8:  # Leave some buffer
                break

    def get_cache_stats(self) -> Dict:
        """Get cache statistics."""
        total_files = len(self.metadata["files"])
        total_size_mb = self.metadata["total_size"] / (1024 * 1024)
        
        if total_files > 0:
            avg_file_size = self.metadata["total_size"] / total_files
            avg_processing_time = sum(f["processing_time"] for f in self.metadata["files"].values()) / total_files
            
            # Calculate hit rate (approximate based on access patterns)
            recent_accesses = sum(1 for f in self.metadata["files"].values() 
                                if time.time() - f["last_accessed"] < 3600)  # Last hour
        else:
            avg_file_size = 0
            avg_processing_time = 0
            recent_accesses = 0
        
        return {
            "total_files": total_files,
            "total_size_mb": round(total_size_mb, 2),
            "max_size_mb": self.max_cache_size / (1024 * 1024),
            "utilization": round(total_size_mb / (self.max_cache_size / (1024 * 1024)) * 100, 1),
            "avg_file_size_bytes": int(avg_file_size),
            "avg_processing_time_seconds": round(avg_processing_time, 3),
            "recent_accesses": recent_accesses
        }

    def clear_cache(self) -> None:
        """Clear all cached files."""
        for cache_file in self.cache_dir.glob("*.pkl"):
            cache_file.unlink()
        
        self.metadata = {"files": {}, "total_size": 0, "last_cleanup": time.time()}
        self._save_metadata()


class PerformanceOptimizer:
    """Optimize document processing performance."""

    def __init__(self, cache_dir: str = ".cache/documents", enable_caching: bool = True):
        """Initialize performance optimizer.
        
        Args:
            cache_dir: Directory for caching
            enable_caching: Whether to enable caching
        """
        self.enable_caching = enable_caching
        self.cache = DocumentCache(cache_dir) if enable_caching else None
        self.parser_factory = DocumentParserFactory()
        
        # Performance tracking
        self.processing_stats = {
            "total_processed": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "total_processing_time": 0.0,
            "total_content_length": 0
        }

    def process_document(
        self, 
        content: str, 
        format_hint: str = "auto",
        max_chunk_size: int = 5000
    ) -> List[SemanticElement]:
        """Process document with caching and chunking optimization.
        
        Args:
            content: Document content to process
            format_hint: Format hint for parsing
            max_chunk_size: Maximum size for document chunks
            
        Returns:
            List of semantic elements
        """
        start_time = time.time()
        
        # Try cache first
        if self.enable_caching and self.cache:
            cached_elements = self.cache.get_cached_elements(content, format_hint)
            if cached_elements is not None:
                self.processing_stats["cache_hits"] += 1
                self.processing_stats["total_processed"] += 1
                return cached_elements
        
        # Cache miss - process document
        self.processing_stats["cache_misses"] += 1
        
        # Choose processing strategy based on content size
        if len(content) <= max_chunk_size:
            elements = self._parse_single_document(content, format_hint)
        else:
            elements = self._parse_large_document(content, format_hint, max_chunk_size)
        
        processing_time = time.time() - start_time
        
        # Update stats
        self.processing_stats["total_processed"] += 1
        self.processing_stats["total_processing_time"] += processing_time
        self.processing_stats["total_content_length"] += len(content)
        
        # Cache results
        if self.enable_caching and self.cache:
            self.cache.cache_elements(content, elements, format_hint, processing_time)
        
        return elements

    def _parse_single_document(self, content: str, format_hint: str) -> List[SemanticElement]:
        """Parse a single document."""
        return self.parser_factory.parse_document(content, format_hint)

    def _parse_large_document(
        self, 
        content: str, 
        format_hint: str, 
        max_chunk_size: int
    ) -> List[SemanticElement]:
        """Parse large documents in intelligent chunks."""
        
        # Try to split by logical boundaries first
        chunks = self._split_document_intelligently(content, max_chunk_size)
        
        all_elements = []
        current_offset = 0
        
        for chunk in chunks:
            # Process each chunk
            chunk_elements = self._parse_single_document(chunk, format_hint)
            
            # Adjust element positions to account for chunk offset
            for element in chunk_elements:
                element.start += current_offset
                element.end += current_offset
            
            all_elements.extend(chunk_elements)
            current_offset += len(chunk)
        
        return all_elements

    def _split_document_intelligently(self, content: str, max_chunk_size: int) -> List[str]:
        """Split document into logical chunks preserving structure."""
        
        if len(content) <= max_chunk_size:
            return [content]
        
        chunks = []
        
        # Try splitting by major sections first (headers, etc.)
        section_boundaries = self._find_section_boundaries(content)
        
        if section_boundaries:
            current_start = 0
            current_chunk = ""
            
            for boundary in section_boundaries + [len(content)]:
                section = content[current_start:boundary]
                
                if len(current_chunk) + len(section) <= max_chunk_size:
                    current_chunk += section
                else:
                    if current_chunk:
                        chunks.append(current_chunk)
                    current_chunk = section
                
                current_start = boundary
            
            if current_chunk:
                chunks.append(current_chunk)
        
        else:
            # Fallback: split by paragraphs, then by sentences
            chunks = self._split_by_paragraphs(content, max_chunk_size)
        
        return chunks

    def _find_section_boundaries(self, content: str) -> List[int]:
        """Find natural section boundaries in the document."""
        import re
        
        boundaries = []
        
        # Look for headers
        for match in re.finditer(r'\n\s*#{1,6}\s+.+', content):
            boundaries.append(match.start())
        
        # Look for HTML headers
        for match in re.finditer(r'<h[1-6][^>]*>', content, re.IGNORECASE):
            boundaries.append(match.start())
        
        # Look for major paragraph breaks
        for match in re.finditer(r'\n\s*\n\s*\n', content):
            boundaries.append(match.start())
        
        return sorted(set(boundaries))

    def _split_by_paragraphs(self, content: str, max_chunk_size: int) -> List[str]:
        """Split content by paragraphs, then sentences if needed."""
        import re
        
        paragraphs = re.split(r'\n\s*\n', content)
        chunks = []
        current_chunk = ""
        
        for paragraph in paragraphs:
            if len(current_chunk) + len(paragraph) <= max_chunk_size:
                current_chunk += paragraph + "\n\n"
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                
                # If single paragraph is too large, split by sentences
                if len(paragraph) > max_chunk_size:
                    sentence_chunks = self._split_by_sentences(paragraph, max_chunk_size)
                    chunks.extend(sentence_chunks)
                    current_chunk = ""
                else:
                    current_chunk = paragraph + "\n\n"
        
        if current_chunk:
            chunks.append(current_chunk.strip())
        
        return chunks

    def _split_by_sentences(self, text: str, max_chunk_size: int) -> List[str]:
        """Split text by sentences as a last resort."""
        import re
        
        sentences = re.split(r'[.!?]+', text)
        chunks = []
        current_chunk = ""
        
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
                
            if len(current_chunk) + len(sentence) <= max_chunk_size:
                current_chunk += sentence + ". "
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                
                # If single sentence is still too large, just truncate
                if len(sentence) > max_chunk_size:
                    chunks.append(sentence[:max_chunk_size])
                else:
                    current_chunk = sentence + ". "
        
        if current_chunk:
            chunks.append(current_chunk.strip())
        
        return chunks

    def get_performance_stats(self) -> Dict:
        """Get comprehensive performance statistics."""
        stats = self.processing_stats.copy()
        
        # Calculate derived metrics
        if stats["total_processed"] > 0:
            stats["cache_hit_rate"] = stats["cache_hits"] / stats["total_processed"]
            stats["avg_processing_time"] = stats["total_processing_time"] / stats["total_processed"]
            stats["avg_content_length"] = stats["total_content_length"] / stats["total_processed"]
            
            # Estimate time saved by caching
            if stats["cache_hits"] > 0:
                stats["estimated_time_saved"] = stats["cache_hits"] * stats["avg_processing_time"]
        else:
            stats["cache_hit_rate"] = 0.0
            stats["avg_processing_time"] = 0.0
            stats["avg_content_length"] = 0.0
            stats["estimated_time_saved"] = 0.0
        
        # Add cache stats if available
        if self.cache:
            stats["cache_stats"] = self.cache.get_cache_stats()
        
        return stats

    def clear_performance_stats(self) -> None:
        """Reset performance statistics."""
        self.processing_stats = {
            "total_processed": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "total_processing_time": 0.0,
            "total_content_length": 0
        }

    def optimize_cache_size(self, target_hit_rate: float = 0.8) -> Dict:
        """Analyze cache usage and recommend optimal cache size."""
        if not self.cache:
            return {"error": "Caching not enabled"}
        
        stats = self.get_performance_stats()
        current_hit_rate = stats.get("cache_hit_rate", 0.0)
        
        recommendations = {
            "current_hit_rate": current_hit_rate,
            "target_hit_rate": target_hit_rate,
            "current_cache_size_mb": stats.get("cache_stats", {}).get("total_size_mb", 0),
            "recommendations": []
        }
        
        if current_hit_rate < target_hit_rate:
            # Recommend increasing cache size
            suggested_increase = min(50, int((target_hit_rate - current_hit_rate) * 100))
            recommendations["recommendations"].append(
                f"Consider increasing cache size by {suggested_increase}MB to improve hit rate"
            )
        elif current_hit_rate > target_hit_rate + 0.1:
            # Cache might be oversized
            recommendations["recommendations"].append(
                "Cache hit rate is very high - consider reducing cache size to save disk space"
            )
        else:
            recommendations["recommendations"].append("Cache size appears to be well-tuned")
        
        return recommendations