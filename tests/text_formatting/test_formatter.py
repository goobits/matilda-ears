#!/usr/bin/env python3
"""Test the new clean formatter architecture with raw transcription data."""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from stt_hotkeys.text_formatting.formatter import format_transcription

# Color codes for output
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"


def test_formatter():
    """Test formatter with various raw transcription scenarios."""
    test_cases = [
        # ACTUAL RAW WHISPER TRANSCRIPTIONS - Edge Cases
        ("www.github.com", "www.github.com"),
        ("Visit Muffin.com for bagels.", "Visit Muffin.com for bagels."),
        ("2 plus 2 equals 4.", "2 + 2 = 4."),
        ("E equals MC squared.", "e = mc²"),
        ("10 minus 3 equals 7.", "10 - 3 = 7."),
        ("Contact me at john at example.com.", "Contact me at john@example.com."),
        ("Call me at 555-123-4567.", "Call me at 555-123-4567."),
        ("localhost colon eight zero eight zero", "localhost:8080"),
        ("version 2.0.1", "version 2.0.1"),
        (
            "Check out github.com slash my dash repo question mark tab equals issues.",
            "Check out github.com/my-repo?tab=issues.",
        ),
        ("The price is $25.99.", "The price is $25.99."),
        # Recent raw transcriptions from logs
        (
            "i.e. this is a test e.g. this is a test ex this is a test and let me say a little list of things and talk about greek gods and people from america",
            "i.e., this is a test, e.g., this is a test, e.g., this is a test. And let me say a little list of things and talk about Greek gods and people from America.",
        ),
        (
            "testing ie this is a test ex this is a test eg this is a test",
            "testing: i.e., this is a test. e.g., this is a test. e.g., this is a test.",
        ),
        # Additional Math expressions
        ("ten minus three equals seven", "10 - 3 = 7"),
        ("five times six", "5 × 6"),
        ("eight divided by two", "8 ÷ 2"),
        # Variable assignments
        ("muffin equals twenty five", "muffin=25"),
        ("cost equals one hundred twenty five", "cost=125"),
        ("x equals y", "x=y"),
        ("a equals b", "a=b"),
        # URLs
        ("visit muffin.com slash architecture", "visit muffin.com/architecture"),
        (
            "muffin.com slash blah slash architecture question mark a equals b and muffin equals three",
            "muffin.com/blah/architecture?a=b&muffin=3",
        ),
        (
            "http colon slash slash google.com slash blah slash blah question mark a equals b",
            "http://google.com/blah/blah?a=b",
        ),
        # Programming
        ("i plus plus", "i++"),
        ("counter minus minus", "counter--"),
        ("if x equals equals y", "if x == y"),
        # Physics
        ("F equals M times A", "F = M × A"),
        # Email
        ("john at example.com", "john@example.com"),
        # Phone numbers
        ("five five five one two three four five six seven", "(555) 123-4567"),
        # Currency
        ("twenty five dollars", "$25"),
        # Time
        ("meet at three thirty PM", "Meet at 3:30 PM."),
        # Should NOT change (except punctuation) - Word-based contextual filtering
        ("I have two plus years of experience", "I have 2 + years of experience."),
        (
            "I have two plus experiences working here",
            "I have 2 + experiences working here.",
        ),  # Test word-based lookahead
        ("The status of the project", "The status of the project."),
        # Test underscore_case preservation in questions
        ("did we install the requirements.txt", "Did we install the requirements.txt?"),
    ]

    passed = 0
    failed = 0

    print(f"\n{BLUE}{'='*60}{RESET}")
    print(f"{BLUE}Testing New Formatter Architecture{RESET}")
    print(f"{BLUE}{'='*60}{RESET}\n")

    for i, (input_text, expected) in enumerate(test_cases, 1):
        # Run formatter
        output = format_transcription(input_text)

        # Remove trailing spaces for comparison
        output = output.rstrip()

        # Check if it matches expected
        if output == expected:
            print(f"{GREEN}✓ Test {i:2d} PASSED{RESET}")
            print(f"   Input:    '{input_text}'")
            print(f"   Output:   '{output}'")
            passed += 1
        else:
            print(f"{RED}✗ Test {i:2d} FAILED{RESET}")
            print(f"   Input:    '{input_text}'")
            print(f"   Expected: '{expected}'")
            print(f"   Got:      '{output}'")
            failed += 1
        print()

    print(f"\n{BLUE}{'='*60}{RESET}")
    print(f"Results: {GREEN}{passed} passed{RESET}, {RED}{failed} failed{RESET}")
    print(f"{BLUE}{'='*60}{RESET}\n")

    return failed == 0


if __name__ == "__main__":
    success = test_formatter()
    sys.exit(0 if success else 1)
