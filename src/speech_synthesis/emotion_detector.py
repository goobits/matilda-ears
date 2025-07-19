"""Content-based emotion detection for enhanced TTS expression."""

from typing import Dict
from document_parsing.base_parser import SemanticElement, SemanticType


class ContentEmotionDetector:
    """Detects emotion based on content and context."""
    
    def __init__(self):
        # Base emotion rules for different semantic types
        self.base_emotions = {
            SemanticType.HEADING: {"emotion": "excited", "intensity": 0.8},
            SemanticType.BOLD: {"emotion": "excited", "intensity": 0.5},
            SemanticType.ITALIC: {"emotion": "soft", "intensity": 0.4},
            SemanticType.CODE: {"emotion": "monotone", "intensity": 0.3},
            SemanticType.CODE_BLOCK: {"emotion": "monotone", "intensity": 0.3},
            SemanticType.LIST_ITEM: {"emotion": "normal", "intensity": 0.5},
            SemanticType.LINK: {"emotion": "normal", "intensity": 0.5},
            SemanticType.TEXT: {"emotion": "normal", "intensity": 0.5}
        }
        
        # Timing rules based on semantic types
        self.timing_rules = {
            SemanticType.HEADING: {"pause_before": 0.5, "pause_after": 1.0},
            SemanticType.BOLD: {"pause_before": 0.0, "pause_after": 0.2},
            SemanticType.ITALIC: {"pause_before": 0.0, "pause_after": 0.1},
            SemanticType.CODE: {"pause_before": 0.1, "pause_after": 0.1},
            SemanticType.CODE_BLOCK: {"pause_before": 0.5, "pause_after": 1.0},
            SemanticType.LIST_ITEM: {"pause_before": 0.0, "pause_after": 0.5},
            SemanticType.LINK: {"pause_before": 0.0, "pause_after": 0.25},
            SemanticType.TEXT: {"pause_before": 0.0, "pause_after": 0.0}
        }
    
    def detect_emotion(self, element: SemanticElement) -> Dict:
        """Detect emotion based on content and context.
        
        Args:
            element: Semantic element to analyze
            
        Returns:
            Dictionary with emotion, intensity, and timing information
        """
        # Start with base emotion for the element type
        base = self.base_emotions.get(element.type, {"emotion": "normal", "intensity": 0.5})
        timing = self.timing_rules.get(element.type, {"pause_before": 0.0, "pause_after": 0.0})
        
        # Adjust based on element-specific rules
        emotion_data = {
            "emotion": base["emotion"],
            "intensity": base["intensity"],
            "timing": timing.copy()
        }
        
        # Apply content-based adjustments
        emotion_data = self._apply_content_rules(element, emotion_data)
        
        # Apply context-based adjustments
        emotion_data = self._apply_context_rules(element, emotion_data)
        
        return emotion_data
    
    def _apply_content_rules(self, element: SemanticElement, emotion_data: Dict) -> Dict:
        """Apply emotion adjustments based on content analysis."""
        content = element.content.lower()
        
        # Excitement indicators
        if any(word in content for word in ['!', 'amazing', 'awesome', 'great', 'excellent']):
            if emotion_data["emotion"] in ["normal", "soft"]:
                emotion_data["emotion"] = "excited"
                emotion_data["intensity"] = min(1.0, emotion_data["intensity"] + 0.2)
        
        # Emphasis indicators
        if any(word in content for word in ['important', 'note', 'warning', 'critical']):
            emotion_data["intensity"] = min(1.0, emotion_data["intensity"] + 0.3)
        
        # Technical content indicators
        if any(word in content for word in ['api', 'function', 'class', 'method', 'variable']):
            if emotion_data["emotion"] == "normal":
                emotion_data["emotion"] = "monotone"
                emotion_data["intensity"] = 0.4
        
        # Question indicators
        if content.strip().endswith('?'):
            emotion_data["timing"]["pause_after"] = max(0.3, emotion_data["timing"]["pause_after"])
        
        return emotion_data
    
    def _apply_context_rules(self, element: SemanticElement, emotion_data: Dict) -> Dict:
        """Apply emotion adjustments based on context and metadata."""
        
        # Heading level adjustments
        if element.type == SemanticType.HEADING:
            if element.level == 1:
                emotion_data["intensity"] = 0.8
                emotion_data["timing"]["pause_after"] = 1.0
            elif element.level == 2:
                emotion_data["intensity"] = 0.6
                emotion_data["timing"]["pause_after"] = 0.8
            else:
                emotion_data["intensity"] = 0.5
                emotion_data["timing"]["pause_after"] = 0.6
        
        # Code language adjustments
        if element.type == SemanticType.CODE_BLOCK:
            language = element.metadata.get('language', 'unknown')
            if language in ['python', 'javascript', 'rust']:
                # Slightly more engaging for popular languages
                emotion_data["intensity"] = 0.4
            else:
                emotion_data["intensity"] = 0.3
        
        # Link context
        if element.type == SemanticType.LINK:
            url = element.metadata.get('url', '')
            if 'github.com' in url or 'docs.' in url:
                emotion_data["timing"]["pause_after"] = 0.4  # More time for technical links
        
        return emotion_data
    
    def get_emotion_sequence(self, elements: list) -> list:
        """Get emotion sequence for a list of elements with flow adjustments."""
        emotions = []
        
        for i, element in enumerate(elements):
            emotion_data = self.detect_emotion(element)
            
            # Flow adjustments based on previous/next elements
            if i > 0:
                prev_element = elements[i-1]
                if prev_element.type == SemanticType.HEADING:
                    # Reduce pause before if previous was a heading
                    emotion_data["timing"]["pause_before"] = max(0.0, emotion_data["timing"]["pause_before"] - 0.2)
            
            if i < len(elements) - 1:
                next_element = elements[i+1]
                if next_element.type == SemanticType.HEADING:
                    # Add pause after if next is a heading
                    emotion_data["timing"]["pause_after"] = max(0.3, emotion_data["timing"]["pause_after"])
            
            emotions.append(emotion_data)
        
        return emotions