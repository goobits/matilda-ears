"""Base parser interface and semantic data structures."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Dict, Any


class SemanticType(Enum):
    """Types of semantic elements that can be extracted from documents."""
    TEXT = "text"
    HEADING = "heading"
    BOLD = "bold"
    ITALIC = "italic"
    CODE = "code"
    CODE_BLOCK = "code_block"
    LIST_ITEM = "list_item"
    LINK = "link"
    QUOTE = "quote"
    PARAGRAPH = "paragraph"


@dataclass
class SemanticElement:
    """Represents a semantic element extracted from a document."""
    type: SemanticType
    content: str
    level: Optional[int] = None  # For headings (1-6), list nesting, etc.
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __str__(self) -> str:
        level_str = f" (level {self.level})" if self.level is not None else ""
        return f"{self.type.value}{level_str}: {self.content[:50]}..."


class BaseDocumentParser(ABC):
    """Abstract base class for document parsers."""
    
    @abstractmethod
    def parse(self, content: str) -> List[SemanticElement]:
        """Parse document content and return semantic elements.
        
        Args:
            content: Raw document content as string
            
        Returns:
            List of semantic elements in document order
        """
        pass
    
    @abstractmethod
    def can_parse(self, content: str, filename: Optional[str] = None) -> bool:
        """Check if this parser can handle the given content.
        
        Args:
            content: Raw document content
            filename: Optional filename for extension-based detection
            
        Returns:
            True if this parser can handle the content
        """
        pass