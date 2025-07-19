"""Parser factory with intelligent format detection and parser selection."""

from typing import Optional, List
from .base_parser import BaseDocumentParser, SemanticElement
from .html_parser import HTMLParser
from .json_parser import JSONParser
from .markdown_parser import MarkdownParser


class DocumentParserFactory:
    """Factory for automatically detecting document format and selecting appropriate parser."""
    
    def __init__(self):
        """Initialize factory with available parsers in order of specificity."""
        # Order matters: most specific formats first, flexible fallback last
        self.parsers = [
            JSONParser(),    # Most strict format
            HTMLParser(),    # HTML has clear indicators
            MarkdownParser() # Flexible fallback - can handle plain text
        ]
        
        # Parser mapping for explicit format selection
        self._parser_map = {
            'json': JSONParser(),
            'html': HTMLParser(),
            'markdown': MarkdownParser()
        }
    
    def get_parser(self, content: str, filename: Optional[str] = None) -> BaseDocumentParser:
        """Auto-detect format and return appropriate parser.
        
        Args:
            content: Document content to analyze
            filename: Optional filename for extension-based hints
            
        Returns:
            Parser instance that can handle the content
        """
        # Try parsers in order of specificity
        for parser in self.parsers:
            if parser.can_parse(content, filename):
                return parser
        
        # Fallback to markdown parser (handles plain text)
        return self.parsers[-1]
    
    def get_specific_parser(self, format_name: str) -> BaseDocumentParser:
        """Get parser for specific format.
        
        Args:
            format_name: Format name ('json', 'html', 'markdown')
            
        Returns:
            Parser instance for the specified format
            
        Raises:
            ValueError: If format is not supported
        """
        parser = self._parser_map.get(format_name.lower())
        if not parser:
            available = ', '.join(self._parser_map.keys())
            raise ValueError(f"Unsupported format '{format_name}'. Available: {available}")
        return parser
    
    def parse_document(self, content: str, filename: Optional[str] = None, 
                      format_override: Optional[str] = None) -> List[SemanticElement]:
        """One-stop parsing with auto-detection or format override.
        
        Args:
            content: Document content to parse
            filename: Optional filename for format hints
            format_override: Optional format override ('json', 'html', 'markdown')
            
        Returns:
            List of semantic elements extracted from the document
        """
        if format_override:
            parser = self.get_specific_parser(format_override)
        else:
            parser = self.get_parser(content, filename)
        
        return parser.parse(content)
    
    def detect_format(self, content: str, filename: Optional[str] = None) -> str:
        """Detect document format without parsing.
        
        Args:
            content: Document content to analyze
            filename: Optional filename for extension hints
            
        Returns:
            Detected format name ('json', 'html', 'markdown')
        """
        parser = self.get_parser(content, filename)
        
        # Map parser class to format name
        parser_class = type(parser).__name__
        if parser_class == 'JSONParser':
            return 'json'
        elif parser_class == 'HTMLParser':
            return 'html'
        elif parser_class == 'MarkdownParser':
            return 'markdown'
        else:
            return 'unknown'
    
    def get_supported_formats(self) -> List[str]:
        """Get list of supported format names.
        
        Returns:
            List of supported format names
        """
        return list(self._parser_map.keys())