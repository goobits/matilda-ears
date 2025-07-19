"""Basic markdown parser for Phase 1 - headers, bold, italic only."""

import re
from typing import List, Optional
from .base_parser import BaseDocumentParser, SemanticElement, SemanticType


class MarkdownParser(BaseDocumentParser):
    """Basic markdown parser supporting headers, bold, and italic text."""
    
    def __init__(self):
        # Compile regex patterns for better performance
        self.header_pattern = re.compile(r'^(#{1,6})\s+(.+)$', re.MULTILINE)
        self.bold_pattern = re.compile(r'\*\*([^*]+)\*\*')
        self.italic_pattern = re.compile(r'\*([^*]+)\*')
        self.code_block_pattern = re.compile(r'```([^`]+)```', re.DOTALL)
        self.list_item_pattern = re.compile(r'^\s*[-*+]\s+(.+)', re.MULTILINE)
        self.link_pattern = re.compile(r'\[([^\]]+)\]\(([^)]+)\)')
        
    def can_parse(self, content: str, filename: Optional[str] = None) -> bool:
        """Check if content looks like markdown."""
        if filename and filename.endswith(('.md', '.markdown')):
            return True
            
        # Simple heuristic: contains markdown headers, formatting, code blocks, lists, or links
        has_headers = bool(self.header_pattern.search(content))
        has_formatting = bool(self.bold_pattern.search(content) or self.italic_pattern.search(content))
        has_code_blocks = bool(self.code_block_pattern.search(content))
        has_lists = bool(self.list_item_pattern.search(content))
        has_links = bool(self.link_pattern.search(content))
        
        return has_headers or has_formatting or has_code_blocks or has_lists or has_links
    
    def parse(self, content: str) -> List[SemanticElement]:
        """Parse markdown content into semantic elements."""
        elements = []
        
        # First, extract code blocks (they can span multiple lines)
        remaining_content = content
        code_blocks = []
        
        for match in self.code_block_pattern.finditer(content):
            code_blocks.append((match.start(), match.end(), match.group(1).strip()))
            
        # Process content in segments, avoiding code blocks
        current_pos = 0
        
        for start, end, code_content in code_blocks:
            # Process content before this code block
            if current_pos < start:
                segment = content[current_pos:start]
                elements.extend(self._parse_text_content(segment))
                
            # Add the code block
            elements.append(SemanticElement(
                type=SemanticType.CODE_BLOCK,
                content=code_content,
                metadata={'language': self._detect_code_language(code_content)}
            ))
            
            current_pos = end
            
        # Process any remaining content after the last code block
        if current_pos < len(content):
            segment = content[current_pos:]
            elements.extend(self._parse_text_content(segment))
        elif not code_blocks:
            # If no code blocks found, parse the entire content
            elements.extend(self._parse_text_content(content))
            
        return elements
    
    def _parse_text_content(self, content: str) -> List[SemanticElement]:
        """Parse text content that doesn't contain code blocks."""
        elements = []
        
        # Split content into lines for processing
        lines = content.split('\n')
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # Check for list items first
            list_match = self.list_item_pattern.match(line)
            if list_match:
                list_content = list_match.group(1)
                # Parse inline formatting in list content
                inline_elements = self._parse_inline_formatting(list_content)
                elements.append(SemanticElement(
                    type=SemanticType.LIST_ITEM,
                    content=self._extract_text_content(inline_elements),
                    metadata={'inline_elements': inline_elements}
                ))
                continue
                
            # Parse regular line
            line_elements = self._parse_line(line)
            elements.extend(line_elements)
            
        return elements
    
    def _detect_code_language(self, code_content: str) -> str:
        """Detect programming language from code content."""
        # Simple heuristics for common languages
        if 'def ' in code_content or 'import ' in code_content or 'print(' in code_content:
            return 'python'
        elif 'function ' in code_content or 'const ' in code_content or 'console.log' in code_content:
            return 'javascript'
        elif '#include' in code_content or 'int main' in code_content:
            return 'c'
        elif 'fn ' in code_content or 'let mut' in code_content:
            return 'rust'
        else:
            return 'unknown'
    
    def _parse_line(self, line: str) -> List[SemanticElement]:
        """Parse a single line of markdown."""
        if not line:
            return []
            
        elements = []
        
        # Check for headers first
        header_match = self.header_pattern.match(line)
        if header_match:
            level = len(header_match.group(1))  # Count # symbols
            content = header_match.group(2)
            
            # Parse inline formatting in header content
            header_elements = self._parse_inline_formatting(content)
            
            # Wrap header content in a heading element
            elements.append(SemanticElement(
                type=SemanticType.HEADING,
                content=self._extract_text_content(header_elements),
                level=level,
                metadata={'inline_elements': header_elements}
            ))
        else:
            # Parse inline formatting for regular text
            inline_elements = self._parse_inline_formatting(line)
            elements.extend(inline_elements)
            
        return elements
    
    def _parse_inline_formatting(self, text: str) -> List[SemanticElement]:
        """Parse bold, italic, and link formatting within text."""
        elements = []
        current_pos = 0
        
        # Find all formatting markers and their positions
        markers = []
        
        # Find bold markers
        for match in self.bold_pattern.finditer(text):
            markers.append(('bold', match.start(), match.end(), match.group(1)))
            
        # Find italic markers (but not inside bold)
        for match in self.italic_pattern.finditer(text):
            # Check if this italic is inside a bold section
            inside_bold = any(
                marker[0] == 'bold' and marker[1] <= match.start() and match.end() <= marker[2]
                for marker in markers
            )
            if not inside_bold:
                markers.append(('italic', match.start(), match.end(), match.group(1)))
                
        # Find link markers
        for match in self.link_pattern.finditer(text):
            # Check if this link is inside formatting
            inside_formatting = any(
                marker[1] <= match.start() and match.end() <= marker[2]
                for marker in markers
            )
            if not inside_formatting:
                markers.append(('link', match.start(), match.end(), match.group(1), match.group(2)))
        
        # Sort markers by position
        markers.sort(key=lambda x: x[1])
        
        # Extract text segments
        for marker in markers:
            marker_type = marker[0]
            start = marker[1]
            end = marker[2]
            content = marker[3]
            
            # Add plain text before this marker
            if current_pos < start:
                plain_text = text[current_pos:start]
                if plain_text.strip():
                    elements.append(SemanticElement(
                        type=SemanticType.TEXT,
                        content=plain_text.strip()
                    ))
            
            # Add the formatted element
            if marker_type == 'bold':
                elements.append(SemanticElement(
                    type=SemanticType.BOLD,
                    content=content
                ))
            elif marker_type == 'italic':
                elements.append(SemanticElement(
                    type=SemanticType.ITALIC,
                    content=content
                ))
            elif marker_type == 'link':
                url = marker[4]  # Fifth element for links
                elements.append(SemanticElement(
                    type=SemanticType.LINK,
                    content=content,
                    metadata={'url': url}
                ))
                
            current_pos = end
        
        # Add any remaining plain text
        if current_pos < len(text):
            plain_text = text[current_pos:]
            if plain_text.strip():
                elements.append(SemanticElement(
                    type=SemanticType.TEXT,
                    content=plain_text.strip()
                ))
        
        # If no formatting found, treat entire line as text
        if not elements and text.strip():
            elements.append(SemanticElement(
                type=SemanticType.TEXT,
                content=text.strip()
            ))
        
        return elements
    
    def _clean_markdown_syntax(self, text: str) -> str:
        """Remove markdown syntax from plain text."""
        # Remove bold markers
        text = self.bold_pattern.sub(r'\1', text)
        # Remove italic markers
        text = self.italic_pattern.sub(r'\1', text)
        return text
    
    def _extract_text_content(self, elements: List[SemanticElement]) -> str:
        """Extract plain text content from a list of semantic elements."""
        return ' '.join(element.content for element in elements)