"""Convert semantic elements to speech-ready text with basic emotion."""

from typing import List
from document_parsing.base_parser import SemanticElement, SemanticType


class SemanticFormatter:
    """Converts semantic elements to text formatted for TTS with emotion cues."""
    
    def __init__(self):
        # Simple emotion mapping for Phase 1
        self.emotion_map = {
            SemanticType.HEADING: "excited",
            SemanticType.BOLD: "emphasis", 
            SemanticType.ITALIC: "soft",
            SemanticType.CODE: "monotone",
            SemanticType.TEXT: "normal"
        }
    
    def format_for_speech(self, elements: List[SemanticElement]) -> str:
        """Convert semantic elements to speech-ready text.
        
        For Phase 1, this creates simple text with emotion hints that
        can be processed by TTS engines.
        """
        speech_parts = []
        
        for element in elements:
            formatted_text = self._format_element(element)
            if formatted_text:
                speech_parts.append(formatted_text)
        
        return ' '.join(speech_parts)
    
    def _format_element(self, element: SemanticElement) -> str:
        """Format a single semantic element for speech."""
        content = element.content.strip()
        if not content:
            return ""
            
        if element.type == SemanticType.HEADING:
            # Headers get excitement and pauses
            level_emphasis = "!" * min(element.level or 1, 3)  # More ! for higher level headers
            return f"HEADING: {content}{level_emphasis}"
            
        elif element.type == SemanticType.BOLD:
            # Bold text gets emphasis
            return f"IMPORTANT: {content}"
            
        elif element.type == SemanticType.ITALIC:
            # Italic text is softer
            return f"gently, {content}"
            
        elif element.type == SemanticType.CODE:
            # Code is monotone
            return f"code: {content}"
            
        else:
            # Regular text
            return content
    
    def to_speech_markdown(self, elements: List[SemanticElement]) -> str:
        """Convert to Speech Markdown format (for future phases).
        
        This is a placeholder for Phase 2 when we implement Speech Markdown.
        """
        # For now, just return basic formatting
        return self.format_for_speech(elements)