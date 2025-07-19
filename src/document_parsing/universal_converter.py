"""Universal document converter - converts any format to markdown."""

import json
import re
from typing import Optional


class UniversalDocumentConverter:
    """Convert any document format to markdown using simple converters."""
    
    def convert_to_markdown(self, content: str, format_hint: str = "auto") -> str:
        """Convert any format to markdown."""
        
        if format_hint == "auto":
            format_hint = self._detect_format(content)
            
        if format_hint == "html":
            return self._html_to_markdown(content)
        elif format_hint == "json":
            return self._json_to_markdown(content)
        else:
            # Already markdown or plain text
            return content
    
    def _detect_format(self, content: str) -> str:
        """Detect format from content."""
        content_lower = content.lower().strip()
        
        # JSON detection
        if content.strip().startswith(('{', '[')):
            try:
                json.loads(content)
                return "json"
            except:
                pass
                
        # HTML detection  
        if ('<!doctype html' in content_lower or 
            re.search(r'<(html|head|body|div|p|h[1-6])', content_lower)):
            return "html"
            
        # Default to markdown/plain text
        return "markdown"
    
    def _html_to_markdown(self, html: str) -> str:
        """Convert HTML to markdown using simple regex."""
        # Simple HTML → Markdown conversion
        
        # Headers
        html = re.sub(r'<h1[^>]*>(.*?)</h1>', r'# \1', html, flags=re.IGNORECASE|re.DOTALL)
        html = re.sub(r'<h2[^>]*>(.*?)</h2>', r'## \1', html, flags=re.IGNORECASE|re.DOTALL)
        html = re.sub(r'<h3[^>]*>(.*?)</h3>', r'### \1', html, flags=re.IGNORECASE|re.DOTALL)
        html = re.sub(r'<h4[^>]*>(.*?)</h4>', r'#### \1', html, flags=re.IGNORECASE|re.DOTALL)
        html = re.sub(r'<h5[^>]*>(.*?)</h5>', r'##### \1', html, flags=re.IGNORECASE|re.DOTALL)
        html = re.sub(r'<h6[^>]*>(.*?)</h6>', r'###### \1', html, flags=re.IGNORECASE|re.DOTALL)
        
        # Bold/Strong
        html = re.sub(r'<(strong|b)[^>]*>(.*?)</\1>', r'**\2**', html, flags=re.IGNORECASE|re.DOTALL)
        
        # Italic/Em
        html = re.sub(r'<(em|i)[^>]*>(.*?)</\1>', r'*\2*', html, flags=re.IGNORECASE|re.DOTALL)
        
        # Links
        html = re.sub(r'<a[^>]*href=["\']([^"\']*)["\'][^>]*>(.*?)</a>', r'[\2](\1)', html, flags=re.IGNORECASE|re.DOTALL)
        
        # Lists
        html = re.sub(r'<li[^>]*>(.*?)</li>', r'- \1', html, flags=re.IGNORECASE|re.DOTALL)
        
        # Code
        html = re.sub(r'<code[^>]*>(.*?)</code>', r'`\1`', html, flags=re.IGNORECASE|re.DOTALL)
        html = re.sub(r'<pre[^>]*>(.*?)</pre>', r'```\n\1\n```', html, flags=re.IGNORECASE|re.DOTALL)
        
        # Paragraphs (convert to line breaks)
        html = re.sub(r'<p[^>]*>', '\n', html, flags=re.IGNORECASE)
        html = re.sub(r'</p>', '\n', html, flags=re.IGNORECASE)
        
        # Remove remaining HTML tags
        html = re.sub(r'<[^>]+>', ' ', html)
        
        # Clean up whitespace
        html = re.sub(r'\n\s*\n\s*\n', '\n\n', html)
        html = html.strip()
        
        return html
    
    def _json_to_markdown(self, json_str: str) -> str:
        """Convert JSON to readable markdown."""
        try:
            data = json.loads(json_str)
            return self._format_json_data(data)
        except:
            return f"```json\n{json_str}\n```"
    
    def _format_json_data(self, data, level=0) -> str:
        """Recursively format JSON data as markdown."""
        if isinstance(data, dict):
            lines = []
            for key, value in data.items():
                if isinstance(value, (dict, list)):
                    if level == 0:
                        lines.append(f"## {key.title()}")
                    else:
                        lines.append(f"{'  ' * level}- **{key}**:")
                    lines.append(self._format_json_data(value, level + 1))
                else:
                    if level == 0:
                        lines.append(f"**{key.title()}**: {value}")
                    else:
                        lines.append(f"{'  ' * level}- **{key}**: {value}")
            return '\n'.join(lines)
            
        elif isinstance(data, list):
            lines = []
            for item in data:
                if isinstance(item, (dict, list)):
                    lines.append(self._format_json_data(item, level))
                else:
                    lines.append(f"{'  ' * level}- {item}")
            return '\n'.join(lines)
            
        else:
            return str(data)