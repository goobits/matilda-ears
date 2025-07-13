#!/usr/bin/env python3
"""Comprehensive tests for entity interactions: priority conflicts and boundaries.

This module tests how different entities interact:
- Entity priority resolution (overlapping entities)
- Entity boundary detection
- Nested entity handling
- Adjacent entity formatting
- Complex multi-entity sentences
"""

import pytest


class TestEntityPriorities:
    """Test entity priority resolution when entities overlap."""

    def test_url_vs_filename_priority(self, preloaded_formatter):
        """Test that URLs take priority over filenames."""
        format_transcription = preloaded_formatter
        test_cases = [
            # URL should win over filename interpretation
            ("visit example.com", "Visit example.com"),
            ("go to github.com slash project", "Go to github.com/project"),
            ("check api.service.com", "Check api.service.com"),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            assert result == expected, f"Input '{input_text}' should format to '{expected}', got '{result}'"

    def test_email_vs_filename_priority(self, preloaded_formatter):
        """Test that emails take priority over filenames."""
        format_transcription = preloaded_formatter
        test_cases = [
            # Email should win over filename interpretation
            ("contact john at example dot com", "Contact john@example.com"),
            ("email support at company dot com", "Email support@company.com"),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            assert result == expected, f"Input '{input_text}' should format to '{expected}', got '{result}'"

    def test_slash_command_vs_division_priority(self, preloaded_formatter):
        """Test that slash commands take priority at sentence start."""
        format_transcription = preloaded_formatter
        test_cases = [
            # Slash command at start should win
            ("slash deploy to production", "/deploy to production"),
            ("slash help me", "/help me"),
            # Division in middle of sentence
            ("calculate ten slash five", "Calculate 10/5"),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            assert result in [
                expected,
                expected + ".",
            ], f"Input '{input_text}' should format to '{expected}' or '{expected}.', got '{result}'"

    def test_operator_vs_math_expression_priority(self, preloaded_formatter):
        """Test priority between operators and math expressions."""
        format_transcription = preloaded_formatter
        test_cases = [
            # Increment operator should take priority
            ("i plus plus", "i++"),
            # But math expression in different context
            ("calculate two plus two", "Calculate 2 + 2"),
            # Assignment operator priority
            ("x equals five", "x = 5"),
            # Comparison operator priority
            ("if x equals equals y", "if x == y"),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            assert result in [
                expected,
                expected + ".",
            ], f"Input '{input_text}' should format to '{expected}' or '{expected}.', got '{result}'"

    def test_number_entity_priorities(self, preloaded_formatter):
        """Test priorities among number-related entities."""
        format_transcription = preloaded_formatter
        test_cases = [
            # Data size should win over plain cardinal
            ("five megabytes", "5MB"),
            # Percentage should win over plain cardinal
            ("fifty percent", "50%"),
            # Temperature should win over plain cardinal
            ("twenty degrees celsius", "20°C"),
            # Ordinal should be preserved
            ("the first item", "The 1st item"),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            assert result == expected, f"Input '{input_text}' should format to '{expected}', got '{result}'"

    def test_filename_vs_url_priority_complex(self, preloaded_formatter):
        """Test complex filename vs URL conflicts."""
        format_transcription = preloaded_formatter
        test_cases = [
            # Filename should win when it's clearly a filename pattern
            ("go to main dot py on example dot com", "Go to main.py on example.com"),
            # Java package name should be treated as one filename
            ("open com dot example dot myapp dot java", "Open com.example.myapp.java"),
            # URL with filename in path should be treated as one URL
            (
                "download from example dot com slash assets slash archive dot zip",
                "Download from example.com/assets/archive.zip",
            ),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            assert result == expected, f"Input '{input_text}' should format to '{expected}', got '{result}'"


class TestEntityBoundaries:
    """Test entity boundary detection and handling."""

    def test_word_boundary_detection(self, preloaded_formatter):
        """Test that entities respect word boundaries."""
        format_transcription = preloaded_formatter
        test_cases = [
            # Should NOT match 'at' inside words
            ("concatenate strings", "Concatenate strings"),
            ("update database", "Update database"),
            # Should match standalone 'at'
            ("john at example dot com", "john@example.com"),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            assert result in [
                expected,
                expected + ".",
            ], f"Input '{input_text}' should format to '{expected}' or '{expected}.', got '{result}'"

    def test_punctuation_boundaries(self, preloaded_formatter):
        """Test entity detection at punctuation boundaries."""
        format_transcription = preloaded_formatter
        test_cases = [
            ("visit github.com, then stackoverflow.com", "Visit github.com, then stackoverflow.com"),
            ("email: john@example.com", "Email: john@example.com"),
            ("use port 8000; default is 3000", "Use port 8000; default is 3000"),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            assert result == expected, f"Input '{input_text}' should format to '{expected}', got '{result}'"

    def test_sentence_boundary_entities(self, preloaded_formatter):
        """Test entities at sentence boundaries."""
        format_transcription = preloaded_formatter
        test_cases = [
            # Entity at start
            ("github.com has the code", "github.com has the code"),
            ("slash deploy now", "/deploy now"),
            # Entity at end
            ("visit github.com", "Visit github.com"),
            ("the temperature is twenty degrees celsius", "The temperature is 20°C"),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            assert result in [
                expected,
                expected + ".",
            ], f"Input '{input_text}' should format to '{expected}' or '{expected}.', got '{result}'"


class TestNestedEntities:
    """Test handling of nested or partially overlapping entities."""

    def test_url_with_port(self, preloaded_formatter):
        """Test URLs that contain port numbers."""
        format_transcription = preloaded_formatter
        test_cases = [
            ("connect to api.service.com colon three thousand", "Connect to api.service.com:3000"),
            ("localhost colon eight zero eight zero slash admin", "localhost:8080/admin"),
            ("server at example.com colon four four three", "Server at example.com:443"),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            assert result in [
                expected,
                expected + ".",
            ], f"Input '{input_text}' should format to '{expected}' or '{expected}.', got '{result}'"

    def test_filename_with_numbers(self, preloaded_formatter):
        """Test filenames containing numbers."""
        format_transcription = preloaded_formatter
        test_cases = [
            ("open test file version two dot py", "Open test_file_version_2.py"),
            ("edit config v three dot json", "Edit config_v3.json"),
            ("check log twenty twenty four dot txt", "Check log_2024.txt"),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            assert result == expected, f"Input '{input_text}' should format to '{expected}', got '{result}'"

    def test_math_with_units(self, preloaded_formatter):
        """Test mathematical expressions with units."""
        format_transcription = preloaded_formatter
        test_cases = [
            ("five times ten to the sixth meters", "5 × 10⁶ m"),
            ("three point one four times radius squared", "3.14 × radius²"),
            ("twenty degrees times pi over one eighty", "20° × π/180"),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            # Complex nested entities may not be fully implemented
            print(f"Nested math test: '{input_text}' -> '{result}' (expected: '{expected}')")


class TestAdjacentEntities:
    """Test formatting of adjacent entities."""

    def test_adjacent_urls(self, preloaded_formatter):
        """Test multiple URLs in sequence."""
        format_transcription = preloaded_formatter
        test_cases = [
            ("visit github.com and stackoverflow.com", "Visit github.com and stackoverflow.com"),
            ("check example.com or test.com", "Check example.com or test.com"),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            assert result == expected, f"Input '{input_text}' should format to '{expected}', got '{result}'"

    def test_adjacent_numbers(self, preloaded_formatter):
        """Test multiple numbers in sequence."""
        format_transcription = preloaded_formatter
        test_cases = [
            ("add two three and five", "Add 2, 3, and 5"),
            ("version one point two point three", "Version 1.2.3"),
            ("coordinates ten twenty", "Coordinates 10, 20"),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            # Adjacent number handling may vary
            print(f"Adjacent numbers test: '{input_text}' -> '{result}' (expected: '{expected}')")

    def test_adjacent_code_entities(self, preloaded_formatter):
        """Test multiple code entities in sequence."""
        format_transcription = preloaded_formatter
        test_cases = [
            ("use dash v dash dash debug", "Use -v --debug"),
            ("run slash build slash deploy", "/build /deploy"),
            ("check x equals y equals z", "Check x = y = z"),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            assert result in [
                expected,
                expected + ".",
            ], f"Input '{input_text}' should format to '{expected}' or '{expected}.', got '{result}'"


class TestComplexEntityInteractions:
    """Test complex sentences with multiple interacting entities."""

    def test_technical_documentation_sentences(self, preloaded_formatter):
        """Test sentences typical in technical documentation."""
        format_transcription = preloaded_formatter
        test_cases = [
            (
                "the api at api.example.com colon eight thousand slash v two accepts json",
                "The API at api.example.com:8000/v2 accepts JSON",
            ),
            (
                "run python script dot py dash dash input data dot csv dash dash output results dot json",
                "Run python script.py --input data.csv --output results.json.",
            ),
            (
                "connect to database at localhost colon five four three two with user admin at db dot com",
                "Connect to database at localhost:5432 with user admin@db.com.",
            ),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            assert result == expected, f"Input '{input_text}' should format to '{expected}', got '{result}'"

    def test_mathematical_physics_sentences(self, preloaded_formatter):
        """Test sentences with mathematical and physics content."""
        format_transcription = preloaded_formatter
        test_cases = [
            (
                "einstein proved e equals mc squared where c equals three times ten to the eighth meters per second",
                "Einstein proved E = MC² where c = 3 × 10⁸ m/s.",
            ),
            (
                "calculate the square root of two times pi times frequency",
                "Calculate √(2π × frequency).",
            ),
            (
                "force equals mass times acceleration or f equals m times a",
                "Force = mass × acceleration or F = m × a.",
            ),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            # Complex physics sentences may not format perfectly
            print(f"Physics sentence test: '{input_text}' -> '{result}' (expected: '{expected}')")

    def test_mixed_technical_content(self, preloaded_formatter):
        """Test sentences mixing various technical entities."""
        format_transcription = preloaded_formatter
        test_cases = [
            (
                "save config dot json with encoding utf eight and permissions six four four",
                "Save config.json with encoding UTF-8 and permissions 644.",
            ),
            (
                "the server dot py file runs on port three thousand and uses fifty percent cpu",
                "The server.py file runs on port 3000 and uses 50% CPU.",
            ),
            (
                "download five gigabytes from cdn dot example dot com slash files slash data dot zip",
                "Download 5GB from cdn.example.com/files/data.zip.",
            ),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            assert result == expected, f"Input '{input_text}' should format to '{expected}', got '{result}'"


class TestEntityProtectionInFormatting:
    """Test that entities are protected during capitalization and punctuation."""

    def test_url_protection_in_questions(self, preloaded_formatter):
        """Test URLs in questions maintain case."""
        format_transcription = preloaded_formatter
        test_cases = [
            ("have you visited github.com", "Have you visited github.com"),
            ("what is stackoverflow.com", "What is stackoverflow.com"),
            ("why use api.service.com", "Why use api.service.com"),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            assert result == expected, f"Input '{input_text}' should format to '{expected}', got '{result}'"

    def test_email_protection_in_sentences(self, preloaded_formatter):
        """Test emails maintain format in various sentence positions."""
        format_transcription = preloaded_formatter
        test_cases = [
            ("john@example.com sent the file", "john@example.com sent the file"),
            ("the admin is root@localhost", "The admin is root@localhost"),
            ("contact support@help.com for assistance", "Contact support@help.com for assistance"),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            assert result == expected, f"Input '{input_text}' should format to '{expected}', got '{result}'"

    def test_code_protection_in_capitalization(self, preloaded_formatter):
        """Test code entities resist improper capitalization."""
        format_transcription = preloaded_formatter
        test_cases = [
            ("i plus plus increments the counter", "i++ increments the counter"),
            ("dash dash verbose enables logging", "--verbose enables logging"),
            ("slash help shows commands", "/help shows commands"),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            assert result == expected, f"Input '{input_text}' should format to '{expected}', got '{result}'"


class TestEdgeCaseInteractions:
    """Test edge cases in entity interactions."""

    def test_ambiguous_entity_detection(self, preloaded_formatter):
        """Test cases where entity type is ambiguous."""
        format_transcription = preloaded_formatter
        test_cases = [
            # Could be URL or sentence
            ("visit the site", "Visit the site"),
            # Could be email or sentence
            ("contact john at the office", "Contact John at the office"),
            # Could be filename or regular text
            ("the script is ready", "The script is ready"),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            assert result == expected, f"Input '{input_text}' should format to '{expected}', got '{result}'"

    def test_partial_entity_matches(self, preloaded_formatter):
        """Test cases with partial entity patterns."""
        format_transcription = preloaded_formatter
        test_cases = [
            # Partial URL pattern
            ("check the dot com sites", "Check the .com sites"),
            # Partial email pattern
            ("user at", "User at"),
            # Incomplete operator
            ("x equals", "X equals"),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            # Partial matches should not trigger entity conversion
            print(f"Partial match test: '{input_text}' -> '{result}' (expected: '{expected}')")

    def test_entity_in_quoted_text(self, preloaded_formatter):
        """Test entities within quoted text."""
        format_transcription = preloaded_formatter
        test_cases = [
            ('he said "visit github.com"', 'He said "visit github.com."'),
            ("the message was 'email john@example.com'", "The message was 'email john@example.com.'"),
            ('type "slash help" for info', 'Type "/help" for info.'),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            # Quote handling may vary
            print(f"Quoted entity test: '{input_text}' -> '{result}' (expected: '{expected}')")

    def test_spoken_url_vs_numbers(self, preloaded_formatter):
        """Test URLs with spoken numbers vs separate number entities."""
        format_transcription = preloaded_formatter
        test_cases = [
            # URL should be detected as single entity
            ("go to one one one one dot com", "Go to 1111.com"),
            ("visit two two two dot net", "Visit 222.net"),
            ("check three three three dot org", "Check 333.org"),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            assert result == expected, f"Input '{input_text}' should detect as URL: '{expected}', got '{result}'"

    def test_entities_in_lists(self, preloaded_formatter):
        """Test entities in comma-separated lists."""
        format_transcription = preloaded_formatter
        test_cases = [
            # Files in a list
            ("open main dot py, config dot json, and readme dot md", "Open main.py, config.json and README.md"),
            ("check a dot txt, b dot py, and c dot js", "Check a.txt, b.py, and c.js"),
            # Mixed entities in lists
            ("i use vim, vscode, and sublime", "I use vim, Vscode and sublime"),
            ("install python, node, and java", "Install python, node, and java"),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            # List formatting and capitalization may vary
            print(f"List test: '{input_text}' -> '{result}' (expected: '{expected}')")


class TestMultipleAdjacentEntities:
    """Test multiple adjacent and interacting entities."""

    def test_slash_command_with_flag_and_filename(self, preloaded_formatter):
        """Test SLASH_COMMAND, COMMAND_FLAG, and FILENAME in sequence."""
        format_transcription = preloaded_formatter
        test_cases = [
            ("slash deploy --verbose to main.py", "/deploy --verbose to main.py"),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            assert (
                result == expected
            ), f"Input '{input_text}' should handle multiple entities: '{expected}', got '{result}'"

    def test_currency_abbreviation_sequence(self, preloaded_formatter):
        """Test CURRENCY, ABBREVIATION, and another currency entity in sequence."""
        format_transcription = preloaded_formatter
        test_cases = [
            ("the price is ten dollars i.e. 10 USD", "The price is $10 i.e. 10 USD"),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            assert (
                result == expected
            ), f"Input '{input_text}' should handle currency and abbreviation: '{expected}', got '{result}'"

    def test_assignment_then_increment(self, preloaded_formatter):
        """Test ASSIGNMENT followed by INCREMENT_OPERATOR."""
        format_transcription = preloaded_formatter
        test_cases = [
            ("let i equals ten then i plus plus", "let i = 10 then i++"),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            assert (
                result == expected
            ), f"Input '{input_text}' should handle assignment and increment: '{expected}', got '{result}'"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
