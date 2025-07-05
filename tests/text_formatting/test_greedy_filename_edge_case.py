#!/usr/bin/env python3
"""Test the greedy filename detection issue."""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from stt_hotkeys.text_formatting.formatter import format_transcription

# Test cases showing the greedy detection issue
test_cases = [
    # The exact problematic case
    "This is a test to see if this entire phrase gets consumed by the filename readme dot md",
    # Variations
    "Hello world this is a long sentence readme dot md",
    "I want to check if everything before this becomes part of the filename test dot py",
    "Does this entire thing become a filename when I say config dot json",
    # With punctuation
    "This is a sentence. And this is another sentence readme dot md",
    "First part, second part, third part readme dot md",
]

print("Testing greedy filename detection:")
print("=" * 60)

for input_text in test_cases:
    result = format_transcription(input_text)
    print(f"\nInput:  '{input_text}'")
    print(f"Output: '{result}'")
