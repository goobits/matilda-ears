#!/usr/bin/env python3
"""Debug script to test specific comparison case."""

from stt.text_formatting.formatter import TextFormatter

def test_comparison():
    formatter = TextFormatter(language="es")
    
    text = "comprobar si valor mayor que cero"
    print(f"Testing: '{text}'")
    
    result = formatter.format_transcription(text)
    print(f"Result: '{result}'")
    
    expected = "Comprobar si valor mayor que 0"
    print(f"Expected: '{expected}'")
    print(f"Match: {result == expected}")

if __name__ == "__main__":
    test_comparison()