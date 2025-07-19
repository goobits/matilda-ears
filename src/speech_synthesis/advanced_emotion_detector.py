"""Advanced emotion detection with document context awareness."""

import re
from typing import List, Dict, Set
from src.document_parsing.base_parser import SemanticElement, SemanticType
from src.speech_synthesis.emotion_detector import ContentEmotionDetector


class AdvancedEmotionDetector(ContentEmotionDetector):
    """Enhanced emotion detection with document context awareness."""

    def __init__(self):
        super().__init__()
        
        # Document type emotion adjustments
        self.document_type_emotions = {
            "technical": {"base_intensity": 0.4, "emphasis_boost": 0.2, "pace": "steady"},
            "marketing": {"base_intensity": 0.7, "emphasis_boost": 0.3, "pace": "energetic"},
            "narrative": {"base_intensity": 0.6, "emphasis_boost": 0.2, "pace": "flowing"},
            "tutorial": {"base_intensity": 0.5, "emphasis_boost": 0.25, "pace": "measured"}
        }
        
        # Keywords for document type detection
        self.technical_keywords = {
            'api', 'function', 'method', 'class', 'endpoint', 'configuration',
            'implementation', 'algorithm', 'parameter', 'variable', 'debugging',
            'compilation', 'runtime', 'framework', 'library', 'protocol',
            'authentication', 'authorization', 'database', 'query', 'schema'
        }
        
        self.marketing_keywords = {
            'best', 'amazing', 'revolutionary', 'save', 'boost', 'transform',
            'incredible', 'outstanding', 'perfect', 'ultimate', 'premium',
            'exclusive', 'limited', 'offer', 'deal', 'discount', 'free',
            'guarantee', 'proven', 'results', 'benefits', 'advantage'
        }
        
        self.narrative_keywords = {
            'story', 'journey', 'experience', 'adventure', 'chapter',
            'character', 'plot', 'scene', 'dialogue', 'narrative',
            'tale', 'memoir', 'biography', 'personal', 'emotional',
            'feeling', 'thought', 'memory', 'dream', 'hope'
        }
        
        self.tutorial_keywords = {
            'step', 'guide', 'tutorial', 'instructions', 'follow',
            'how to', 'procedure', 'process', 'walkthrough', 'example',
            'demonstration', 'practice', 'exercise', 'lesson', 'learning',
            'first', 'next', 'then', 'finally', 'complete', 'finish'
        }
        
        # Content pattern indicators
        self.content_patterns = {
            'technical': [
                r'`[^`]+`',  # inline code
                r'```[\s\S]*?```',  # code blocks
                r'\b\w+\(\)',  # function calls
                r'\b[A-Z_]{3,}\b',  # constants (3+ chars, word boundaries)
                r'https?://[^\s]+',  # URLs
                r'\b\d+\.\d+\.\d+',  # version numbers
            ],
            'marketing': [
                r'[!]{2,}',  # multiple exclamation marks
                r'\b\d+%\s+off\b',  # percentage discounts
                r'\$\d+',  # prices
                r'\bfree\b',  # free offers
                r'call.{0,10}action',  # call to action
            ],
            'narrative': [
                r'"[^"]*"',  # quoted dialogue
                r'\bi\s+\w+',  # first person narrative
                r'\bwe\s+\w+',  # first person plural
                r'\bonce\s+upon',  # story beginnings
                r'\bsuddenly\b',  # narrative transitions
            ],
            'tutorial': [
                r'\bstep\s+\d+',  # numbered steps
                r'\b\d+\.\s',  # numbered lists
                r'\bnow\s+\w+',  # instruction transitions
                r'\blet\'s\s+\w+',  # tutorial language
                r'\bmake\s+sure',  # verification instructions
            ]
        }

    def detect_document_type(self, elements: List[SemanticElement]) -> str:
        """Detect document type from content patterns."""
        if not elements:
            return "narrative"  # default fallback
        
        # Combine all text content for analysis
        full_text = " ".join(element.content for element in elements).lower()
        
        # Count semantic type indicators
        type_indicators = {
            'technical': 0,
            'marketing': 0, 
            'narrative': 0,
            'tutorial': 0
        }
        
        # Analyze semantic elements
        for element in elements:
            if element.type == SemanticType.CODE_BLOCK or element.type == SemanticType.CODE:
                type_indicators['technical'] += 3
            elif element.type == SemanticType.HEADING:
                content = element.content.lower()
                if any(kw in content for kw in self.tutorial_keywords):
                    type_indicators['tutorial'] += 2
                elif any(kw in content for kw in self.marketing_keywords):
                    type_indicators['marketing'] += 2
                elif any(kw in content for kw in self.technical_keywords):
                    type_indicators['technical'] += 2
        
        # Count keyword matches
        for doc_type, keywords in [
            ('technical', self.technical_keywords),
            ('marketing', self.marketing_keywords),
            ('narrative', self.narrative_keywords),
            ('tutorial', self.tutorial_keywords)
        ]:
            keyword_count = sum(1 for kw in keywords if kw in full_text)
            type_indicators[doc_type] += keyword_count
        
        # Analyze content patterns (use original case for some patterns)
        original_text = " ".join(element.content for element in elements)
        
        for doc_type, patterns in self.content_patterns.items():
            pattern_count = 0
            for pattern in patterns:
                # Use original case for constant detection, lowercase for others
                search_text = original_text if pattern == r'\b[A-Z_]{3,}\b' else full_text
                matches = re.findall(pattern, search_text, re.IGNORECASE if search_text == full_text else 0)
                pattern_count += len(matches)
            type_indicators[doc_type] += pattern_count
        
        # Additional heuristics
        if len([e for e in elements if e.type == SemanticType.LIST_ITEM]) > 3:
            type_indicators['tutorial'] += 2
        
        if any('!' in element.content for element in elements):
            type_indicators['marketing'] += 1
        
        # Return the type with highest score
        max_type = max(type_indicators.items(), key=lambda x: x[1])
        return max_type[0] if max_type[1] > 0 else "narrative"

    def get_contextual_emotions(self, elements: List[SemanticElement]) -> List[Dict]:
        """Get emotions with document context awareness."""
        if not elements:
            return []
        
        doc_type = self.detect_document_type(elements)
        context_settings = self.document_type_emotions[doc_type]
        
        emotions = []
        
        for i, element in enumerate(elements):
            emotion_data = self.detect_emotion(element)
            
            # Apply document-specific adjustments
            emotion_data = self._apply_document_context(emotion_data, doc_type, context_settings)
            
            # Apply positional context
            emotion_data = self._apply_positional_context(emotion_data, i, len(elements))
            
            # Apply flow context
            if i > 0:
                emotion_data = self._apply_flow_context(emotion_data, emotions[i-1], element)
            
            emotions.append(emotion_data)
        
        return emotions

    def _apply_document_context(self, emotion_data: Dict, doc_type: str, settings: Dict) -> Dict:
        """Apply document type-specific emotion adjustments."""
        
        if doc_type == "technical":
            # Technical docs: reduce excitement, emphasize clarity
            if emotion_data["emotion"] == "excited":
                emotion_data["emotion"] = "normal"
                emotion_data["intensity"] = settings["base_intensity"]
            elif emotion_data["emotion"] == "normal":
                emotion_data["intensity"] = settings["base_intensity"]
            
            # Increase pauses for technical content comprehension
            emotion_data["timing"]["pause_after"] *= 1.2
        
        elif doc_type == "marketing":
            # Marketing: boost energy, emphasize benefits
            if emotion_data["emotion"] in ["normal", "soft"]:
                emotion_data["emotion"] = "excited"
            
            emotion_data["intensity"] = min(1.0, 
                emotion_data["intensity"] + settings["emphasis_boost"])
            
            # Faster pace for marketing energy
            emotion_data["timing"]["pause_after"] *= 0.8
        
        elif doc_type == "narrative":
            # Narrative: natural flow, emotional variation
            emotion_data["intensity"] = settings["base_intensity"]
            
            # Maintain natural timing
            pass
        
        elif doc_type == "tutorial":
            # Tutorial: steady pace, emphasize key steps
            emotion_data["intensity"] = settings["base_intensity"]
            
            # Measured timing for instruction clarity
            if "step" in emotion_data.get("content", "").lower():
                emotion_data["timing"]["pause_before"] = 0.3
                emotion_data["timing"]["pause_after"] = 0.6
        
        return emotion_data

    def _apply_positional_context(self, emotion_data: Dict, position: int, total: int) -> Dict:
        """Apply position-based adjustments (intro, body, conclusion)."""
        
        # Introduction (first 10%)
        if position < total * 0.1:
            emotion_data["timing"]["pause_before"] = max(0.5, emotion_data["timing"]["pause_before"])
            if emotion_data["emotion"] == "normal":
                emotion_data["emotion"] = "excited"
                emotion_data["intensity"] = min(1.0, emotion_data["intensity"] + 0.1)
        
        # Conclusion (last 10%)
        elif position > total * 0.9:
            emotion_data["timing"]["pause_after"] = max(0.8, emotion_data["timing"]["pause_after"])
            if emotion_data["emotion"] == "excited":
                emotion_data["intensity"] = min(1.0, emotion_data["intensity"] + 0.1)
        
        return emotion_data

    def _apply_flow_context(self, emotion_data: Dict, prev_emotion: Dict, element: SemanticElement) -> Dict:
        """Apply flow-based adjustments based on previous element."""
        
        # Avoid emotion monotony
        if prev_emotion["emotion"] == emotion_data["emotion"]:
            if emotion_data["emotion"] == "excited":
                # Occasionally reduce excitement to create variation
                if element.type not in [SemanticType.HEADING, SemanticType.BOLD]:
                    emotion_data["intensity"] *= 0.9
            elif emotion_data["emotion"] == "monotone":
                # Break up monotone sequences
                if prev_emotion.get("consecutive_monotone", 0) >= 2:
                    emotion_data["emotion"] = "normal"
                    emotion_data["intensity"] = 0.5
                else:
                    emotion_data["consecutive_monotone"] = prev_emotion.get("consecutive_monotone", 0) + 1
        
        # Transition smoothing
        if prev_emotion["emotion"] == "excited" and emotion_data["emotion"] == "soft":
            emotion_data["timing"]["pause_before"] = max(0.3, emotion_data["timing"]["pause_before"])
        
        return emotion_data

    def get_document_summary(self, elements: List[SemanticElement]) -> Dict:
        """Get comprehensive document analysis summary."""
        doc_type = self.detect_document_type(elements)
        emotions = self.get_contextual_emotions(elements)
        
        # Calculate statistics
        emotion_distribution = {}
        avg_intensity = 0
        total_timing = 0
        
        for emotion_data in emotions:
            emotion = emotion_data["emotion"]
            emotion_distribution[emotion] = emotion_distribution.get(emotion, 0) + 1
            avg_intensity += emotion_data["intensity"]
            total_timing += emotion_data["timing"]["pause_after"]
        
        if emotions:
            avg_intensity /= len(emotions)
        
        return {
            "document_type": doc_type,
            "total_elements": len(elements),
            "emotion_distribution": emotion_distribution,
            "average_intensity": round(avg_intensity, 2),
            "estimated_duration_seconds": round(total_timing, 1),
            "document_characteristics": self.document_type_emotions[doc_type]
        }