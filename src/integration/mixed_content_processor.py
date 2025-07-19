"""Mixed content processor integrating document parsing with text formatting."""

import re
from typing import List, Dict, Optional, Union
from src.document_parsing.base_parser import SemanticElement
from src.document_parsing.parser_factory import DocumentParserFactory
from src.text_formatting.formatter import TextFormatter


class MixedContentProcessor:
    """Process mixed content: documents + transcribed text."""

    def __init__(self, language: str = "en"):
        """Initialize with text formatting and document parsing components."""
        self.language = language
        
        # Import existing text formatting
        self.text_formatter = TextFormatter(language=language)
        
        # Import document parsing
        self.document_factory = DocumentParserFactory()
        
        # Content type detection patterns
        self.document_indicators = [
            r'<[^>]+>',  # HTML tags
            r'#+\s',  # Markdown headers
            r'```[\s\S]*?```',  # Code blocks
            r'\[.*?\]\(.*?\)',  # Markdown links
            r'^\s*[\-\*\+]\s',  # List items
            r'^\s*\d+\.\s',  # Numbered lists
            r'"[^"]*":\s*[{\[]',  # JSON structure
            r'{\s*"[^"]*"',  # JSON object start
        ]
        
        self.transcription_indicators = [
            r'\b(?:um|uh|ah|er|mm)\b',  # Filler words
            r'\b(?:like|you know|I mean)\b',  # Speech patterns
            r'\b(?:gonna|wanna|gotta)\b',  # Contractions
            r'\.{2,}',  # Pause indicators
            r'\?\s*\?',  # Uncertainty markers
        ]

    def process_mixed_content(
        self, 
        content: str, 
        content_type: str = "auto",
        format_hint: str = ""
    ) -> str:
        """Process content that might be document OR transcribed speech.
        
        Args:
            content: Text content to process
            content_type: "auto", "transcription", or "document"
            format_hint: Optional format hint (html, markdown, json)
        
        Returns:
            Processed text ready for speech synthesis
        """
        if not content or not content.strip():
            return ""
        
        # Auto-detect content type if not specified
        if content_type == "auto":
            content_type = self._detect_content_type(content, format_hint)
        
        if content_type == "transcription":
            # Use existing text formatting pipeline
            return self._process_transcription(content)
        
        elif content_type == "document":
            # Use document parsing pipeline
            return self._process_document(content, format_hint)
        
        else:
            # Fallback: try document first, then transcription
            try:
                elements = self.document_factory.parse_document(content, format_hint)
                if elements and len(elements) > 0:
                    return self._format_for_speech(elements)
            except:
                pass
            
            # Fallback to transcription processing
            return self._process_transcription(content)

    def _detect_content_type(self, content: str, format_hint: str = "") -> str:
        """Heuristics to distinguish documents from transcriptions."""
        
        # If we have a format hint, prefer document processing
        if format_hint and format_hint in ["html", "markdown", "json"]:
            return "document"
        
        content_lower = content.lower()
        
        # Count document indicators
        doc_score = 0
        for pattern in self.document_indicators:
            matches = len(re.findall(pattern, content, re.MULTILINE | re.IGNORECASE))
            doc_score += matches
        
        # Count transcription indicators
        trans_score = 0
        for pattern in self.transcription_indicators:
            matches = len(re.findall(pattern, content, re.MULTILINE | re.IGNORECASE))
            trans_score += matches
        
        # Additional document heuristics
        
        # Structured headers (#, ##, <h1>)
        if re.search(r'(^|\n)#{1,6}\s+\w+', content, re.MULTILINE):
            doc_score += 3
        
        # HTML structure
        if re.search(r'<(html|head|body|div|p|h[1-6])', content, re.IGNORECASE):
            doc_score += 5
        
        # JSON structure
        if content.strip().startswith('{') and content.strip().endswith('}'):
            doc_score += 4
        
        # Formatted lists (-, *, <li>)
        list_items = len(re.findall(r'^\s*[\-\*\+]\s+\w+', content, re.MULTILINE))
        if list_items >= 2:
            doc_score += list_items
        
        # Code blocks (```, <pre>)
        code_blocks = len(re.findall(r'```[\s\S]*?```|<pre>[\s\S]*?</pre>', content))
        if code_blocks > 0:
            doc_score += code_blocks * 2
        
        # Additional transcription heuristics
        
        # Conversational language
        conversation_patterns = [
            r'\bi\s+(?:think|believe|feel|want|need)\b',
            r'\byou\s+(?:know|see|think)\b',
            r'\blet\'s\s+\w+',
            r'\bwhat\s+do\s+you\b',
        ]
        for pattern in conversation_patterns:
            if re.search(pattern, content_lower):
                trans_score += 1
        
        # Incomplete sentences (common in speech)
        sentences = re.split(r'[.!?]+', content)
        short_sentences = sum(1 for s in sentences if len(s.split()) <= 3 and len(s.strip()) > 0)
        if short_sentences >= 2:
            trans_score += short_sentences
        
        # Spoken numbers/entities
        spoken_numbers = len(re.findall(r'\b(?:one|two|three|four|five|six|seven|eight|nine|ten)\b', content_lower))
        trans_score += spoken_numbers
        
        # Decision logic
        if doc_score > trans_score * 1.5:  # Bias slightly toward document detection
            return "document"
        elif trans_score > doc_score:
            return "transcription"
        else:
            # When in doubt, try document parsing first (it's more structured)
            return "document"

    def _process_transcription(self, content: str) -> str:
        """Process content as transcribed speech using existing formatter."""
        return self.text_formatter.format_transcription(content, language=self.language)

    def _process_document(self, content: str, format_hint: str = "") -> str:
        """Process content as a document using document parsers."""
        try:
            elements = self.document_factory.parse_document(content, format_hint)
            return self._format_for_speech(elements)
        except Exception as e:
            # If document parsing fails, fall back to transcription processing
            return self._process_transcription(content)

    def _format_for_speech(self, elements: List[SemanticElement]) -> str:
        """Format semantic elements for natural speech output."""
        if not elements:
            return ""
        
        # Import speech synthesis components
        from src.speech_synthesis.semantic_formatter import SemanticFormatter
        from src.speech_synthesis.speech_markdown import SpeechMarkdownConverter
        
        # Format elements semantically
        formatter = SemanticFormatter()
        formatted_text = formatter.format_for_speech(elements)
        
        # Convert to speech markdown
        converter = SpeechMarkdownConverter()
        speech_markdown = converter.convert_elements(elements)
        
        return speech_markdown

    def get_content_analysis(self, content: str, format_hint: str = "") -> Dict:
        """Analyze content and return detailed classification information."""
        content_type = self._detect_content_type(content, format_hint)
        
        # Count various indicators
        doc_indicators = sum(len(re.findall(pattern, content, re.MULTILINE | re.IGNORECASE)) 
                           for pattern in self.document_indicators)
        
        trans_indicators = sum(len(re.findall(pattern, content, re.MULTILINE | re.IGNORECASE)) 
                             for pattern in self.transcription_indicators)
        
        # Word and sentence statistics
        words = len(content.split())
        sentences = len(re.split(r'[.!?]+', content))
        avg_sentence_length = words / max(sentences, 1)
        
        # Structure analysis
        has_headers = bool(re.search(r'(^|\n)#{1,6}\s+\w+|<h[1-6]', content, re.MULTILINE | re.IGNORECASE))
        has_lists = bool(re.search(r'^\s*[\-\*\+]\s+\w+|<li>', content, re.MULTILINE | re.IGNORECASE))
        has_code = bool(re.search(r'```[\s\S]*?```|<pre>|<code>', content))
        has_links = bool(re.search(r'\[.*?\]\(.*?\)|<a\s+href', content))
        
        return {
            "detected_type": content_type,
            "confidence": self._calculate_confidence(doc_indicators, trans_indicators),
            "statistics": {
                "word_count": words,
                "sentence_count": sentences,
                "avg_sentence_length": round(avg_sentence_length, 1),
                "document_indicators": doc_indicators,
                "transcription_indicators": trans_indicators
            },
            "structure": {
                "has_headers": has_headers,
                "has_lists": has_lists,
                "has_code_blocks": has_code,
                "has_links": has_links
            },
            "recommended_processing": self._get_processing_recommendation(content_type, content)
        }

    def _calculate_confidence(self, doc_indicators: int, trans_indicators: int) -> float:
        """Calculate confidence score for content type detection."""
        total_indicators = doc_indicators + trans_indicators
        if total_indicators == 0:
            return 0.5  # Neutral confidence
        
        stronger = max(doc_indicators, trans_indicators)
        confidence = stronger / total_indicators
        
        # Scale to 0.5-1.0 range (0.5 = low confidence, 1.0 = high confidence)
        return 0.5 + (confidence * 0.5)

    def _get_processing_recommendation(self, content_type: str, content: str) -> Dict:
        """Get processing recommendations based on content analysis."""
        recommendations = {
            "primary_processor": content_type,
            "fallback_processor": "transcription" if content_type == "document" else "document",
            "suggested_options": []
        }
        
        # Add specific recommendations
        if content_type == "document":
            if re.search(r'<[^>]+>', content):
                recommendations["suggested_options"].append("Use HTML parser for best results")
            elif re.search(r'#{1,6}\s+', content):
                recommendations["suggested_options"].append("Use Markdown parser for best results")
            elif content.strip().startswith('{'):
                recommendations["suggested_options"].append("Use JSON parser for best results")
        
        elif content_type == "transcription":
            if len(content.split()) > 50:
                recommendations["suggested_options"].append("Consider breaking into smaller chunks")
            if re.search(r'\b(?:um|uh|ah|er)\b', content.lower()):
                recommendations["suggested_options"].append("Speech artifacts detected - will be cleaned")
        
        return recommendations

    def process_batch_content(
        self, 
        content_items: List[Dict[str, str]], 
        preserve_order: bool = True
    ) -> List[str]:
        """Process multiple content items in batch.
        
        Args:
            content_items: List of dicts with keys 'content', 'type', 'format_hint'
            preserve_order: Whether to maintain input order in output
        
        Returns:
            List of processed content strings
        """
        results = []
        
        for item in content_items:
            content = item.get('content', '')
            content_type = item.get('type', 'auto')
            format_hint = item.get('format_hint', '')
            
            processed = self.process_mixed_content(content, content_type, format_hint)
            results.append(processed)
        
        return results

    def create_processing_report(self, content: str, format_hint: str = "") -> str:
        """Create a detailed processing report for debugging and analysis."""
        analysis = self.get_content_analysis(content, format_hint)
        processed = self.process_mixed_content(content, "auto", format_hint)
        
        report_lines = [
            "=== Mixed Content Processing Report ===",
            f"Content Length: {len(content)} characters",
            f"Detected Type: {analysis['detected_type']}",
            f"Confidence: {analysis['confidence']:.2f}",
            "",
            "=== Statistics ===",
            f"Words: {analysis['statistics']['word_count']}",
            f"Sentences: {analysis['statistics']['sentence_count']}",
            f"Avg Sentence Length: {analysis['statistics']['avg_sentence_length']}",
            f"Document Indicators: {analysis['statistics']['document_indicators']}",
            f"Transcription Indicators: {analysis['statistics']['transcription_indicators']}",
            "",
            "=== Structure ===",
            f"Has Headers: {analysis['structure']['has_headers']}",
            f"Has Lists: {analysis['structure']['has_lists']}",
            f"Has Code: {analysis['structure']['has_code_blocks']}",
            f"Has Links: {analysis['structure']['has_links']}",
            "",
            "=== Processing Recommendation ===",
            f"Primary: {analysis['recommended_processing']['primary_processor']}",
            f"Fallback: {analysis['recommended_processing']['fallback_processor']}",
        ]
        
        if analysis['recommended_processing']['suggested_options']:
            report_lines.append("Suggestions:")
            for suggestion in analysis['recommended_processing']['suggested_options']:
                report_lines.append(f"  - {suggestion}")
        
        report_lines.extend([
            "",
            "=== Processed Output ===",
            f"Length: {len(processed)} characters",
            f"Preview: {processed[:100]}{'...' if len(processed) > 100 else ''}",
        ])
        
        return "\n".join(report_lines)