#!/usr/bin/env python3
"""Phase 1 Demo: Document to Speech Pipeline."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from document_parsing.markdown_parser import MarkdownParser
from speech_synthesis.semantic_formatter import SemanticFormatter
from speech_synthesis.tts_engine import SimpleTTSEngine


def demo_document_to_speech(filename: str):
    """Demonstrate end-to-end document to speech conversion."""
    print(f"=== Document to Speech Demo ===")
    print(f"Processing: {filename}")
    
    # Step 1: Read document
    try:
        with open(filename, 'r') as f:
            content = f.read()
    except FileNotFoundError:
        print(f"Error: File {filename} not found")
        return False
        
    print(f"\nDocument content:\n{content}\n")
    
    # Step 2: Parse document
    parser = MarkdownParser()
    if not parser.can_parse(content, filename):
        print("Error: Cannot parse this document format")
        return False
        
    elements = parser.parse(content)
    print(f"Parsed {len(elements)} semantic elements:")
    for i, element in enumerate(elements):
        print(f"  {i+1}. {element}")
    
    # Step 3: Format for speech
    formatter = SemanticFormatter()
    speech_text = formatter.format_for_speech(elements)
    print(f"\nFormatted for speech:\n{speech_text}\n")
    
    # Step 4: Generate speech
    tts_engine = SimpleTTSEngine()
    print(f"Available TTS engines: {tts_engine.available_engines}")
    
    if tts_engine.available_engines:
        print("\nGenerating speech...")
        success = tts_engine.speak_elements(elements)
        if success:
            print("✓ Speech generation completed successfully!")
        else:
            print("⚠ Speech generation had some issues")
    else:
        print("\nNo TTS engines available. Speech output:")
        print(f"[WOULD SPEAK]: {speech_text}")
    
    return True


if __name__ == '__main__':
    # Test with our sample markdown
    if len(sys.argv) > 1:
        filename = sys.argv[1]
    else:
        filename = 'test_markdown.md'
        
    demo_document_to_speech(filename)