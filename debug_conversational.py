#!/usr/bin/env python3
"""Debug script to test conversational flow processing."""

from stt.text_formatting.formatter import TextFormatter
from stt.text_formatting.spanish_conversational_flow import SpanishConversationalFlowAnalyzer

def test_conversational_detection():
    # Test conversational analyzer directly
    analyzer = SpanishConversationalFlowAnalyzer("es")
    
    test_texts = [
        "comprobar si valor mayor que cero",
        "resultado igual a más b", 
        "archivo guión bajo configuración guión bajo principal"
    ]
    
    print("=== Direct Analyzer Test ===")
    for text in test_texts:
        is_conversational = analyzer.is_conversational_instruction(text)
        context = analyzer.identify_conversational_context(text)
        entities = analyzer.identify_conversational_entities(text)
        
        print(f"Text: '{text}'")
        print(f"  Conversational: {is_conversational}")
        print(f"  Context: {context}")
        print(f"  Entities found: {len(entities)}")
        for entity in entities:
            print(f"    - {entity.text} ({entity.context.value}) -> {entity.conversational_replacement}")
        print()
    
    print("=== Formatter Test ===")
    formatter = TextFormatter(language="es")
    
    for text in test_texts:
        result = formatter.format_transcription(text)
        print(f"Input: '{text}'")
        print(f"Output: '{result}'")
        print()

if __name__ == "__main__":
    test_conversational_detection()