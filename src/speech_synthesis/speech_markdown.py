"""Speech Markdown converter for enhanced TTS with timing and emotion."""

from typing import List
from document_parsing.base_parser import SemanticElement, SemanticType


class SpeechMarkdownConverter:
    """Converts semantic elements to Speech Markdown syntax."""
    
    def __init__(self):
        self.timing_map = {
            SemanticType.HEADING: {"after": "[1s]"},
            SemanticType.LIST_ITEM: {"after": "[500ms]"},
            SemanticType.CODE_BLOCK: {"after": "[1s]"},
            SemanticType.LINK: {"after": "[250ms]"},
            SemanticType.BOLD: {"after": ""},
            SemanticType.ITALIC: {"after": ""},
            SemanticType.TEXT: {"after": ""}
        }
        
        self.emotion_map = {
            SemanticType.HEADING: "excited",
            SemanticType.BOLD: "excited",
            SemanticType.ITALIC: "soft",
            SemanticType.CODE: "monotone",
            SemanticType.CODE_BLOCK: "monotone",
            SemanticType.LIST_ITEM: "normal",
            SemanticType.LINK: "normal",
            SemanticType.TEXT: "normal"
        }
    
    def convert_elements(self, elements: List[SemanticElement]) -> str:
        """Convert semantic elements to Speech Markdown syntax."""
        speech_parts = []
        
        for element in elements:
            speech_part = self._convert_element(element)
            if speech_part:
                speech_parts.append(speech_part)
        
        return " ".join(speech_parts)
    
    def _convert_element(self, element: SemanticElement) -> str:
        """Convert a single semantic element to Speech Markdown."""
        emotion = self.emotion_map.get(element.type, "normal")
        timing = self.timing_map.get(element.type, {})
        
        # Base content
        content = element.content
        
        # Apply emotion and timing based on element type
        if element.type == SemanticType.HEADING:
            # Headers get excited emotion with timing
            level_timing = "[1s]" if element.level == 1 else "[800ms]"
            return f"({emotion})[{content}] {level_timing}"
        
        elif element.type == SemanticType.BOLD:
            # Bold text gets emphasis markers
            return f"**{content}**"
        
        elif element.type == SemanticType.ITALIC:
            # Italic text gets soft emotion
            return f"({emotion})[{content}]"
        
        elif element.type == SemanticType.CODE_BLOCK:
            # Code blocks get monotone emotion with pause
            return f"({emotion})[{content}] [1s]"
        
        elif element.type == SemanticType.LIST_ITEM:
            # List items get pauses between them
            return f"{content} [500ms]"
        
        elif element.type == SemanticType.LINK:
            # Links get normal emotion with slight pause
            url = element.metadata.get('url', '')
            return f"({emotion})[{content}] [250ms]"
        
        elif element.type == SemanticType.CODE:
            # Inline code gets monotone
            return f"({emotion})[{content}]"
        
        else:
            # Regular text
            return content
    
    def convert_to_ssml(self, elements: List[SemanticElement]) -> str:
        """Convert elements to SSML format (future enhancement)."""
        # This would convert Speech Markdown to platform-specific SSML
        # For now, return the Speech Markdown
        return self.convert_elements(elements)
    
    def convert_with_timing_precision(self, elements: List[SemanticElement], precision: str = "standard") -> str:
        """Convert with different timing precision levels."""
        if precision == "detailed":
            # More detailed timing
            for timing in self.timing_map.values():
                if "500ms" in timing.get("after", ""):
                    timing["after"] = "[750ms]"
                elif "250ms" in timing.get("after", ""):
                    timing["after"] = "[400ms]"
        elif precision == "minimal":
            # Reduced timing
            for timing in self.timing_map.values():
                if timing.get("after"):
                    timing["after"] = "[200ms]"
        
        return self.convert_elements(elements)