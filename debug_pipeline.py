#!/usr/bin/env python3
"""Debug script to test pipeline state and conversational flow."""

import logging
from stt.text_formatting.formatter import TextFormatter

# Set up logging to see debug messages
logging.basicConfig(level=logging.DEBUG)

def test_pipeline_debug():
    formatter = TextFormatter(language="es")
    
    test_text = "comprobar si valor mayor que cero"
    print(f"Testing: '{test_text}'")
    
    result = formatter.format_transcription(test_text)
    print(f"Result: '{result}'")

if __name__ == "__main__":
    test_pipeline_debug()