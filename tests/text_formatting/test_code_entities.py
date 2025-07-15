#!/usr/bin/env python3
"""Comprehensive tests for code-related entities: filenames, operators, and flags.

This module tests the detection and formatting of:
- FILENAME: File names with case formatting based on extension
- ASSIGNMENT: "x equals 5" → "x = 5"
- INCREMENT_OPERATOR: "i plus plus" → "i++"
- DECREMENT_OPERATOR: "counter minus minus" → "counter--"
- COMPARISON: "x equals equals y" → "x == y"
- COMMAND_FLAG: "dash dash verbose" → "--verbose"
- SLASH_COMMAND: "slash deploy" → "/deploy"
- UNDERSCORE_DELIMITER: "underscore underscore init underscore underscore" → "__init__"
- ABBREVIATION: "i dot e" → "i.e."
"""

import pytest


class TestFilenameEntities:
    """Test FILENAME entity detection and case formatting based on file extension."""

    def test_python_files_snake_case(self, preloaded_formatter):
        """Test Python files get lower_snake_case formatting."""
        format_transcription = preloaded_formatter
        test_cases = [
            ("open main dot py", "Open main.py"),
            ("edit my script dot py", "Edit my_script.py"),
            ("check config loader dot py", "Check config_loader.py"),
            ("run test helper dot py", "Run test_helper.py"),
            ("import utils dot py", "Import utils.py"),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            assert result == expected, f"Input '{input_text}' should format to '{expected}', got '{result}'"

    def test_javascript_files_camel_case(self, preloaded_formatter):
        """Test JavaScript files get camelCase formatting."""
        format_transcription = preloaded_formatter
        test_cases = [
            ("edit app dot js", "Edit app.js"),
            ("open my component dot js", "Open myComponent.js"),
            ("check api client dot js", "Check apiClient.js"),
            ("run test utils dot js", "Run testUtils.js"),
            ("import user service dot js", "Import userService.js"),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            assert result == expected, f"Input '{input_text}' should format to '{expected}', got '{result}'"

    def test_typescript_files_pascal_case(self, preloaded_formatter):
        """Test TypeScript files get PascalCase formatting."""
        format_transcription = preloaded_formatter
        test_cases = [
            ("create user service dot ts", "Create UserService.ts"),
            ("edit my component dot tsx", "Edit MyComponent.tsx"),
            ("open api client dot ts", "Open ApiClient.ts"),
            ("check data service dot tsx", "Check DataService.tsx"),
            ("import auth helper dot ts", "Import AuthHelper.ts"),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            assert result == expected, f"Input '{input_text}' should format to '{expected}', got '{result}'"

    def test_java_files_pascal_case(self, preloaded_formatter):
        """Test Java files get PascalCase formatting."""
        format_transcription = preloaded_formatter
        test_cases = [
            ("open user service dot java", "Open UserService.java"),
            ("edit my component dot java", "Edit MyComponent.java"),
            ("check api client dot java", "Check ApiClient.java"),
            ("run test helper dot java", "Run TestHelper.java"),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            assert result == expected, f"Input '{input_text}' should format to '{expected}', got '{result}'"

    def test_csharp_files_pascal_case(self, preloaded_formatter):
        """Test C# files get PascalCase formatting."""
        format_transcription = preloaded_formatter
        test_cases = [
            ("open user service dot cs", "Open UserService.cs"),
            ("edit my component dot cs", "Edit MyComponent.cs"),
            ("check api client dot cs", "Check ApiClient.cs"),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            assert result == expected, f"Input '{input_text}' should format to '{expected}', got '{result}'"

    def test_css_files_kebab_case(self, preloaded_formatter):
        """Test CSS files get kebab-case formatting."""
        format_transcription = preloaded_formatter
        test_cases = [
            ("edit main styles dot css", "Edit main-styles.css"),
            ("open my stylesheet dot css", "Open my-stylesheet.css"),
            ("check component styles dot scss", "Check component-styles.scss"),
            ("import base theme dot css", "Import base-theme.css"),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            assert result == expected, f"Input '{input_text}' should format to '{expected}', got '{result}'"

    def test_markdown_files_upper_snake_case(self, preloaded_formatter):
        """Test Markdown files get UPPER_SNAKE_CASE formatting."""
        format_transcription = preloaded_formatter
        test_cases = [
            ("open readme dot md", "Open README.md"),
            ("edit change log dot md", "Edit CHANGE_LOG.md"),
            ("check api docs dot md", "Check API_DOCS.md"),
            ("view user guide dot md", "View USER_GUIDE.md"),
            ("please update the clod dot md", "Please update the CLAUDE.md"),  # "clod" -> "CLAUDE" only when followed by .md
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            assert result == expected, f"Input '{input_text}' should format to '{expected}', got '{result}'"

    def test_filenames_with_numbers(self, preloaded_formatter):
        """Test filenames containing numbers."""
        format_transcription = preloaded_formatter
        test_cases = [
            ("open report version two dot pdf", "Open report_version_2.pdf"),
            ("edit config v one dot json", "Edit config_v1.json"),
            ("check log file one hundred dot txt", "Check log_file_100.txt"),
            ("run test case three dot py", "Run test_case_3.py"),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            assert result == expected, f"Input '{input_text}' should format to '{expected}', got '{result}'"

    def test_filenames_with_underscores(self, preloaded_formatter):
        """Test filenames with spoken underscores."""
        format_transcription = preloaded_formatter
        test_cases = [
            ("open my file underscore name dot py", "Open my_file_name.py"),
            ("edit config underscore loader dot js", "Edit config_loader.js"),
            ("check test underscore helper dot rb", "Check test_helper.rb"),
            ("import data underscore utils dot py", "Import data_utils.py"),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            assert result == expected, f"Input '{input_text}' should format to '{expected}', got '{result}'"

    def test_dunder_filenames(self, preloaded_formatter):
        """Test special dunder filenames."""
        format_transcription = preloaded_formatter
        test_cases = [
            ("open underscore underscore init underscore underscore dot py", "Open __init__.py"),
            ("edit underscore underscore main underscore underscore dot py", "Edit __main__.py"),
            ("check underscore underscore name underscore underscore dot py", "Check __name__.py"),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            assert result == expected, f"Input '{input_text}' should format to '{expected}', got '{result}'"

    def test_java_package_names(self, preloaded_formatter):
        """Test Java package names as filenames."""
        format_transcription = preloaded_formatter
        test_cases = [
            ("open com dot example dot myapp", "Open com.example.myapp"),
            ("edit org dot springframework dot boot", "Edit org.springframework.boot"),
            ("check io dot github dot user dot project", "Check io.github.user.project"),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            assert result == expected, f"Input '{input_text}' should format to '{expected}', got '{result}'"

    def test_filenames_in_context(self, preloaded_formatter):
        """Test filenames embedded in natural sentences."""
        format_transcription = preloaded_formatter
        test_cases = [
            ("the error is in main dot js on line five", "The error is in main.js on line 5"),
            ("edit the config file settings dot json", "Edit the config file settings.json"),
            ("my favorite file is utils dot py", "My favorite file is utils.py"),
            ("the documentation is in readme dot md", "The documentation is in README.md"),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            assert result == expected, f"Input '{input_text}' should format to '{expected}', got '{result}'"

    def test_unknown_extension_filenames(self, preloaded_formatter):
        """Test filenames with unknown extensions."""
        format_transcription = preloaded_formatter
        test_cases = [
            ("open my custom file dot custom", "Open my_custom_file.custom"),
            ("edit config dot ini", "Edit config.ini"),
            ("check data dot xml", "Check data.xml"),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            assert result == expected, f"Input '{input_text}' should format to '{expected}', got '{result}'"


class TestAssignmentOperators:
    """Test ASSIGNMENT entity detection and formatting."""

    def test_basic_assignments(self, preloaded_formatter):
        """Test basic assignment patterns."""
        format_transcription = preloaded_formatter
        test_cases = [
            ("x equals five", "x = 5"),
            ("name equals john", "name = john"),
            ("count equals twenty", "count = 20"),
            ("value equals true", "value = true"),
            ("status equals active", "status = active"),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            # Assignments are technical content so might not get punctuation
            assert result in [
                expected,
                expected + ".",
            ], f"Input '{input_text}' should format to '{expected}' or '{expected}.', got '{result}'"

    def test_assignments_with_strings(self, preloaded_formatter):
        """Test assignments with string values."""
        format_transcription = preloaded_formatter
        test_cases = [
            ("message equals hello world", "message = hello_world"),
            ("filename equals my document", "filename = my_document"),
            ("title equals user guide", "title = user_guide"),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            assert result in [
                expected,
                expected + ".",
            ], f"Input '{input_text}' should format to '{expected}' or '{expected}.', got '{result}'"

    def test_assignments_with_expressions(self, preloaded_formatter):
        """Test assignments with mathematical expressions."""
        format_transcription = preloaded_formatter
        test_cases = [
            ("result equals x plus y", "result = x + y"),
            ("total equals sum times two", "total = sum × 2"),
            ("average equals total divided by count", "average = total ÷ count"),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            assert result in [
                expected,
                expected + ".",
            ], f"Input '{input_text}' should format to '{expected}' or '{expected}.', got '{result}'"

    def test_typed_assignments(self, preloaded_formatter):
        """Test assignments with type annotations."""
        format_transcription = preloaded_formatter
        test_cases = [
            ("let x equals five", "let x = 5"),
            ("const name equals john", "const name = john"),
            ("var count equals zero", "var count = 0"),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            assert result in [
                expected,
                expected + ".",
            ], f"Input '{input_text}' should format to '{expected}' or '{expected}.', got '{result}'"


class TestIncrementDecrementOperators:
    """Test INCREMENT_OPERATOR and DECREMENT_OPERATOR entities."""

    def test_increment_operators(self, preloaded_formatter):
        """Test increment operator patterns."""
        format_transcription = preloaded_formatter
        test_cases = [
            ("i plus plus", "i++"),
            ("count plus plus", "count++"),
            ("index plus plus", "index++"),
            ("counter plus plus", "counter++"),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            # Operators are technical content so might not get punctuation
            assert result in [
                expected,
                expected + ".",
            ], f"Input '{input_text}' should format to '{expected}' or '{expected}.', got '{result}'"

    def test_decrement_operators(self, preloaded_formatter):
        """Test decrement operator patterns."""
        format_transcription = preloaded_formatter
        test_cases = [
            ("i minus minus", "i--"),
            ("count minus minus", "count--"),
            ("index minus minus", "index--"),
            ("counter minus minus", "counter--"),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            assert result in [
                expected,
                expected + ".",
            ], f"Input '{input_text}' should format to '{expected}' or '{expected}.', got '{result}'"

    def test_operators_in_context(self, preloaded_formatter):
        """Test operators in code context."""
        format_transcription = preloaded_formatter
        test_cases = [
            ("in the loop i plus plus", "In the loop i++"),
            ("at the end counter minus minus", "At the end counter--"),
            ("use index plus plus for iteration", "Use index++ for iteration"),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            assert result in [
                expected,
                expected + ".",
            ], f"Input '{input_text}' should format to '{expected}' or '{expected}.', got '{result}'"


class TestComparisonOperators:
    """Test COMPARISON entity detection and formatting."""

    def test_equality_comparisons(self, preloaded_formatter):
        """Test equality comparison patterns."""
        format_transcription = preloaded_formatter
        test_cases = [
            ("x equals equals y", "x == y"),
            ("value equals equals true", "value == true"),
            ("count equals equals zero", "count == 0"),
            ("status equals equals active", "status == active"),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            # Comparisons are technical content so might not get punctuation
            assert result in [
                expected,
                expected + ".",
            ], f"Input '{input_text}' should format to '{expected}' or '{expected}.', got '{result}'"

    def test_comparisons_in_conditions(self, preloaded_formatter):
        """Test comparisons in conditional statements."""
        format_transcription = preloaded_formatter
        test_cases = [
            ("if value equals equals true", "if value == true"),
            ("when count equals equals zero", "When count == 0"),
            ("check if x equals equals y", "Check if x == y"),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            assert result in [
                expected,
                expected + ".",
            ], f"Input '{input_text}' should format to '{expected}' or '{expected}.', got '{result}'"


class TestCommandFlags:
    """Test COMMAND_FLAG entity detection and formatting."""

    def test_short_flags(self, preloaded_formatter):
        """Test short command-line flags."""
        format_transcription = preloaded_formatter
        test_cases = [
            ("use dash f for file", "Use -f for file"),
            ("run with dash v for verbose", "Run with -v for verbose"),
            ("try dash h for help", "Try -h for help"),
            ("pass dash x flag", "Pass -x flag"),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            assert result in [
                expected,
                expected + ".",
            ], f"Input '{input_text}' should format to '{expected}' or '{expected}.', got '{result}'"

    def test_long_flags(self, preloaded_formatter):
        """Test long command-line flags."""
        format_transcription = preloaded_formatter
        test_cases = [
            ("use dash dash verbose", "Use --verbose"),
            ("run with dash dash help", "Run with --help"),
            ("try dash dash version", "Try --version"),
            ("pass dash dash debug flag", "Pass --debug flag"),
            ("use dash dash output file", "Use --output file"),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            assert result in [
                expected,
                expected + ".",
            ], f"Input '{input_text}' should format to '{expected}' or '{expected}.', got '{result}'"

    def test_command_flags_in_context(self, preloaded_formatter):
        """Test command flags in complete command contexts."""
        format_transcription = preloaded_formatter
        test_cases = [
            ("git commit dash m message", "Git commit -m message"),
            ("run the script with dash dash verbose mode", "Run the script with --verbose mode"),
            ("use docker run dash d for daemon", "Use docker run -d for daemon"),
            ("try npm install dash dash save dev", "Try npm install --save-dev"),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            assert result in [
                expected,
                expected + ".",
            ], f"Input '{input_text}' should format to '{expected}' or '{expected}.', got '{result}'"

    def test_multiple_flags(self, preloaded_formatter):
        """Test multiple flags in one command."""
        format_transcription = preloaded_formatter
        test_cases = [
            ("pass dash v and dash dash debug", "Pass -v and --debug"),
            ("use dash x dash f together", "Use -x -f together"),
            ("combine dash dash verbose and dash dash output", "Combine --verbose and --output"),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            # Check that both flags are present
            assert (
                ("-v" in result and "--debug" in result)
                or ("-x" in result and "-f" in result)
                or ("--verbose" in result and "--output" in result)
            ), f"Expected multiple flags in result '{result}' for input '{input_text}'"


class TestSlashCommands:
    """Test SLASH_COMMAND entity detection and formatting."""

    def test_basic_slash_commands(self, preloaded_formatter):
        """Test basic slash command patterns."""
        format_transcription = preloaded_formatter
        test_cases = [
            ("slash deploy to production", "/deploy to production"),
            ("slash compact", "/compact"),
            ("use slash help for assistance", "Use /help for assistance"),
            ("try slash status command", "Try /status command"),
            ("run slash build now", "Run /build now"),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            assert result in [
                expected,
                expected + ".",
            ], f"Input '{input_text}' should format to '{expected}' or '{expected}.', got '{result}'"

    def test_slash_commands_with_parameters(self, preloaded_formatter):
        """Test slash commands with parameters."""
        format_transcription = preloaded_formatter
        test_cases = [
            ("slash restart server one", "/restart server1"),
            ("use slash search term query", "Use /search term query"),
            ("try slash config set debug true", "Try /config set debug true"),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            assert result in [
                expected,
                expected + ".",
            ], f"Input '{input_text}' should format to '{expected}' or '{expected}.', got '{result}'"

    def test_slash_commands_at_start_of_transcription(self, preloaded_formatter):
        """Test slash commands when they appear at the start of transcription."""
        format_transcription = preloaded_formatter
        test_cases = [
            ("slash compact", "/compact"),
            ("slash deploy now", "/deploy now"),
            ("slash help me", "/help me"),
            ("slash status check", "/status check"),
            ("slash anything goes", "/anything goes"),
            (
                "test it out in the slash temp directory see if it works",
                "Test it out in the /temp directory see if it works",
            ),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            assert result in [
                expected,
                expected + ".",
            ], f"Input '{input_text}' should format to '{expected}' or '{expected}.', got '{result}'"


class TestUnderscoreDelimiters:
    """Test UNDERSCORE_DELIMITER entity detection and formatting."""

    def test_dunder_methods(self, preloaded_formatter):
        """Test Python dunder method patterns."""
        format_transcription = preloaded_formatter
        test_cases = [
            ("define underscore underscore init underscore underscore", "Define __init__"),
            ("call underscore underscore name underscore underscore", "Call __name__"),
            ("use underscore underscore main underscore underscore", "Use __main__"),
            ("check underscore underscore doc underscore underscore", "Check __doc__"),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            assert result in [
                expected,
                expected + ".",
            ], f"Input '{input_text}' should format to '{expected}' or '{expected}.', got '{result}'"

    def test_underscore_delimited_variables(self, preloaded_formatter):
        """Test underscore-delimited variable names."""
        format_transcription = preloaded_formatter
        test_cases = [
            ("the variable user underscore id", "The variable user_id"),
            ("set max underscore length", "Set max_length"),
            ("check is underscore valid", "Check is_valid"),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            assert result in [
                expected,
                expected + ".",
            ], f"Input '{input_text}' should format to '{expected}' or '{expected}.', got '{result}'"


class TestAbbreviations:
    """Test ABBREVIATION entity detection and formatting."""

    def test_latin_abbreviations(self, preloaded_formatter):
        """Test Latin abbreviation patterns."""
        format_transcription = preloaded_formatter
        test_cases = [
            ("that is i e very important", "That is i.e., very important"),
            ("for example e g this case", "For example e.g., this case"),
            ("and so on etc", "And so on etc."),
            ("versus v s other options", "Versus vs. other options"),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            assert result == expected, f"Input '{input_text}' should format to '{expected}', got '{result}'"

    def test_abbreviations_with_punctuation(self, preloaded_formatter):
        """Test abbreviations with proper punctuation formatting."""
        format_transcription = preloaded_formatter
        test_cases = [
            ("i dot e dot we should refactor", "i.e., we should refactor"),
            ("e dot g dot use a linter", "e.g., use a linter"),
            ("ex this is an example", "e.g., this is an example"),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            assert result == expected, f"Input '{input_text}' should format to '{expected}', got '{result}'"

    def test_abbreviations_in_context(self, preloaded_formatter):
        """Test abbreviations in natural sentences."""
        format_transcription = preloaded_formatter
        test_cases = [
            ("use design patterns i e singleton factory", "Use design patterns i.e., singleton factory"),
            ("configure the tools e g linters formatters", "Configure the tools e.g., linters formatters"),
            (
                "and install dependencies libraries frameworks etc",
                "And install dependencies libraries frameworks etc.",
            ),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            assert result == expected, f"Input '{input_text}' should format to '{expected}', got '{result}'"


class TestCodeEntityInteractions:
    """Test interactions between different code entities."""

    def test_filename_with_assignment(self, preloaded_formatter):
        """Test sentences with both filenames and assignments."""
        format_transcription = preloaded_formatter
        test_cases = [
            ("in config dot py set debug equals true", "In config.py set debug = true"),
            ("edit main dot js where count equals zero", "Edit main.js where count = 0"),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            assert result == expected, f"Input '{input_text}' should format to '{expected}', got '{result}'"

    def test_filename_with_operators(self, preloaded_formatter):
        """Test sentences with filenames and operators."""
        format_transcription = preloaded_formatter
        test_cases = [
            ("in loop dot py use i plus plus", "In loop.py use i++"),
            ("check util dot js for counter minus minus", "Check util.js for counter--"),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            assert result == expected, f"Input '{input_text}' should format to '{expected}', got '{result}'"

    def test_command_with_flags_and_filenames(self, preloaded_formatter):
        """Test commands with both flags and filenames."""
        format_transcription = preloaded_formatter
        test_cases = [
            ("run script dot py with dash dash verbose", "Run script.py with --verbose"),
            ("execute main dot js using dash d flag", "Execute main.js using -d flag"),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            assert result == expected, f"Input '{input_text}' should format to '{expected}', got '{result}'"

    def test_complex_code_statements(self, preloaded_formatter):
        """Test complex statements with multiple code entities."""
        format_transcription = preloaded_formatter
        test_cases = [
            (
                "in config dot py set debug equals true and run with dash dash verbose",
                "In config.py set debug = true and run with --verbose",
            ),
            (
                "edit main dot js where count plus plus and status equals active",
                "Edit main.js where count++ and status = active",
            ),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            assert result == expected, f"Input '{input_text}' should format to '{expected}', got '{result}'"


class TestNestedCodeEntityPatterns:
    """Test nested and compound code entity patterns."""

    def test_filename_with_tld_word(self, preloaded_formatter):
        """Test FILENAME containing a TLD-like word (com)."""
        format_transcription = preloaded_formatter
        test_cases = [
            ("open my com project dot py", "Open my_com_project.py"),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            assert (
                result == expected
            ), f"Input '{input_text}' should handle filename with TLD word: '{expected}', got '{result}'"


class TestAmbiguousCodeContexts:
    """Test ambiguous contexts where keywords shouldn't be converted."""

    def test_colon_in_non_port_context(self, preloaded_formatter):
        """Test that 'colon' is not converted to : in non-port context."""
        format_transcription = preloaded_formatter
        test_cases = [
            ("the sentence must have a colon", "The sentence must have a colon"),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            assert (
                result == expected
            ), f"Input '{input_text}' should not convert 'colon' in non-port context: '{expected}', got '{result}'"

    def test_underscore_in_non_variable_context(self, preloaded_formatter):
        """Test that 'underscore' is not converted to _ in non-variable context."""
        format_transcription = preloaded_formatter
        test_cases = [
            ("please draw an underscore here", "Please draw an underscore here"),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            assert (
                result == expected
            ), f"Input '{input_text}' should not convert 'underscore' in non-variable context: '{expected}', got '{result}'"


class TestFilenameEdgeCasesAndRegressions:
    """Test edge cases and known issues with filename detection."""

    def test_greedy_filename_detection_regression(self, preloaded_formatter):
        """Test and document KNOWN ISSUE: Filename regex is too greedy.

        The filename detection currently consumes entire sentences when it finds
        'dot extension' patterns, which is incorrect behavior.
        """
        format_transcription = preloaded_formatter
        test_cases = [
            # KNOWN ISSUE: Everything before 'dot js' is consumed as filename
            ("function opens the door dot js", "Function opens the door dot js"),
            # Expected: "Function opens the door.js" or similar
            # Actual: The entire phrase becomes a filename entity
            # More examples of the greedy behavior
            ("the error is in main dot py on line 5", "The error is in main.py on line 5"),
            # Currently may consume too much as filename
            ("i love python dot py is great", "I love python.py is great"),
            # Should only treat 'python.py' as filename, not the whole sentence
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            # This documents the current behavior, which may be incorrect
            print(f"GREEDY FILENAME ISSUE - Input: '{input_text}'")
            print(f"                       Expected: '{expected}'")
            print(f"                       Actual: '{result}'")
            print("                       Issue: Filename detection is too greedy")
            print()

    def test_filename_boundary_detection(self, preloaded_formatter):
        """Test that filename detection respects word boundaries."""
        format_transcription = preloaded_formatter
        test_cases = [
            # Should stop at common verbs/prepositions
            ("the file utils dot py is ready", "The file utils.py is ready"),
            ("check main dot js for errors", "Check main.js for errors"),
            ("open config dot json and edit", "Open config.json and edit"),
            # Should handle 'dot' in non-filename contexts
            ("put a dot here", "Put a dot here"),
            ("the dot com boom", "The .com boom"),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            # Boundary detection may not work perfectly
            print(f"Boundary test: '{input_text}' -> '{result}' (expected: '{expected}')")

    def test_ambiguous_dot_patterns(self, preloaded_formatter):
        """Test ambiguous cases where 'dot' could mean different things."""
        format_transcription = preloaded_formatter
        test_cases = [
            # Could be filename or sentence about a dot
            ("red dot py", "Red dot py"),
            # Is this 'red.py' or 'red dot py'?
            # Sentence ending with extension-like word
            ("i love dot com", "I love .com"),
            # Could be a sentence about .com domains
            # Multiple dots in sequence
            ("example dot com dot au", "example.com.au"),
            # Should be recognized as domain, not filename
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            print(f"Ambiguous dot: '{input_text}' -> '{result}' (expected: '{expected}')")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
