"""Parser factory with markdown-first architecture - preserves Phase 4 compatibility."""

from typing import Optional, List
from .base_parser import BaseDocumentParser, SemanticElement
from .markdown_parser import MarkdownParser
from .universal_converter import UniversalDocumentConverter


class DocumentParserFactory:
    """Factory using markdown-first architecture for universal document support."""
    
    def __init__(self):
        """Initialize factory with universal converter and markdown parser."""
        self.converter = UniversalDocumentConverter()
        self.markdown_parser = MarkdownParser()
        
        # Supported formats (for API compatibility)
        self._supported_formats = ['auto', 'markdown', 'html', 'json']
    
    def get_parser(self, content: str, filename: Optional[str] = None) -> BaseDocumentParser:
        """Returns markdown parser (all formats converted to markdown first).
        
        Args:
            content: Document content to analyze
            filename: Optional filename for extension-based hints
            
        Returns:
            Parser instance that can handle the content
        """
        # Always return markdown parser since we convert everything to markdown
        return self.markdown_parser
    
    def get_specific_parser(self, format_name: str) -> BaseDocumentParser:
        """Get parser for specific format.
        
        Args:
            format_name: Format name ('json', 'html', 'markdown')
            
        Returns:
            Parser instance for the specified format
            
        Raises:
            ValueError: If format is not supported
        """
        if format_name.lower() not in self._supported_formats:
            available = ', '.join(self._supported_formats)
            raise ValueError(f"Unsupported format '{format_name}'. Available: {available}")
        # Always return markdown parser since we convert everything to markdown
        return self.markdown_parser
    
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
        # Step 1: Convert any format to markdown
        format_hint = format_override if format_override and format_override != 'auto' else 'auto'
        markdown_content = self.converter.convert_to_markdown(content, format_hint)
        
        # Step 2: Parse with our proven markdown parser
        return self.markdown_parser.parse(markdown_content)
    
    def detect_format(self, content: str, filename: Optional[str] = None) -> str:
        """Detect document format without parsing.
        
        Args:
            content: Document content to analyze
            filename: Optional filename for extension hints
            
        Returns:
            Detected format name ('json', 'html', 'markdown')
        """
        # Use converter's detection logic
        detected = self.converter._detect_format(content)
        
        # Also check filename extension for better detection
        if filename:
            filename_lower = filename.lower()
            if filename_lower.endswith('.html') or filename_lower.endswith('.htm'):
                return 'html'
            elif filename_lower.endswith('.json'):
                return 'json'
            elif filename_lower.endswith(('.md', '.markdown')):
                return 'markdown'
        
        return detected
    
    def get_supported_formats(self) -> List[str]:
        """Get list of supported format names.
        
        Returns:
            List of supported format names
        """
        return self._supported_formats.copy()