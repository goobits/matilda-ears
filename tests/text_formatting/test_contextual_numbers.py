"""Test contextual number handling to prevent unwanted conversions."""


class TestContextualNumbers:
    """Test that number words in certain contexts are not converted to digits."""

    def test_number_words_in_natural_speech(self, preloaded_formatter):
        """Test that number words in natural speech contexts remain as words."""
        format_transcription = preloaded_formatter
        test_cases = [
            # "one" in non-numeric contexts
            ("the one thing I need", "The one thing I need"),
            ("one of us should go", "One of us should go"),
            ("which one do you prefer", "Which one do you prefer"),
            ("one or the other", "One or the other"),
            # "two" in non-numeric contexts
            ("the two of us", "The two of us"),
            ("two can play that game", "Two can play that game"),
            ("between the two options", "Between the two options"),
            # Mixed contexts
            ("one test for each of those two issues", "One test for each of those two issues"),
            ("create one or two examples", "Create one or two examples"),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            # Allow for optional punctuation at the end
            assert result in [
                expected,
                expected + ".",
            ], f"Input '{input_text}' should format to '{expected}', got '{result}'"

    def test_number_words_that_should_convert(self, preloaded_formatter):
        """Test that number words in numeric contexts ARE converted to digits."""
        format_transcription = preloaded_formatter
        test_cases = [
            # Clear numeric contexts
            ("add one plus one", "Add 1 + 1"),
            ("multiply two times three", "Multiply 2 × 3"),
            ("version one point two", "Version 1.2"),
            ("page one of ten", "Page 1 of 10"),
            # With units
            ("wait one second", "Wait 1s"),  # Time duration gets abbreviated
            ("two minutes remaining", "2min remaining"),  # Time duration gets abbreviated
            ("one dollar fifty", "$1 50"),  # Currency gets $ symbol
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            # Allow for optional punctuation at the end
            assert result in [
                expected,
                expected + ".",
            ], f"Input '{input_text}' should format to '{expected}', got '{result}'"


class TestContextualOrdinals:
    """Test that ordinal numbers are formatted appropriately based on context."""

    def test_ordinals_that_should_be_numeric(self, preloaded_formatter):
        """Test that ordinals in technical/formal contexts become numeric (1st, 2nd, 3rd)."""
        format_transcription = preloaded_formatter
        test_cases = [
            # Technical/Formal contexts
            ("first quarter earnings report", "1st quarter earnings report"),
            ("second generation iPhone", "2nd generation iPhone"),
            ("third party software", "3rd party software"),
            ("twenty first century technology", "21st century technology"),
            # Rankings/Competition
            ("first place winner", "1st place winner"),
            ("second best performance", "2nd best performance"),
            ("third fastest time", "3rd fastest time"),
            # Lists/Procedures
            ("first item on the agenda", "1st item on the agenda"),
            ("second step in the process", "2nd step in the process"),
            ("third option available", "3rd option available"),
            # Dates
            ("January first meeting", "January 1st meeting"),
            ("March twenty third deadline", "March 23rd deadline"),
            ("May second conference", "May 2nd conference"),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            # Allow for optional punctuation at the end
            assert result in [
                expected,
                expected + ".",
            ], f"Input '{input_text}' should format to '{expected}', got '{result}'"

    def test_ordinals_that_should_be_spelled_out(self, preloaded_formatter):
        """Test that ordinals in natural speech/idiomatic contexts remain spelled out."""
        format_transcription = preloaded_formatter
        test_cases = [
            # Natural speech/Idiomatic
            ("first thing I need to do", "First thing I need to do"),
            ("second nature to me", "Second nature to me"),
            ("third time's the charm", "Third time's the charm"),
            ("first of all let me say", "First of all, let me say"),
            ("second thoughts about this", "Second thoughts about this"),
            # Common expressions
            ("first things first", "First things first"),
            ("second to none", "Second to none"),
            ("third wheel in the group", "Third wheel in the group"),
            ("first come first served", "First come, first served"),
            # Sentence beginnings (emphasis)
            ("first we need to discuss", "First, we need to discuss"),
            ("second the budget concerns", "Second, the budget concerns"),
            ("third implementation timeline", "Third, implementation timeline"),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            # Allow for optional punctuation at the end
            assert result in [
                expected,
                expected + ".",
            ], f"Input '{input_text}' should format to '{expected}', got '{result}'"


class TestStandaloneEntityPunctuation:
    """Test that standalone entities don't get unnecessary punctuation."""

    def test_standalone_entities_no_punctuation(self, preloaded_formatter):
        """Test that standalone entities have trailing punctuation removed."""
        format_transcription = preloaded_formatter
        test_cases = [
            # Slash commands
            ("slash compact.", "/compact"),
            ("slash help.", "/help"),
            ("slash status.", "/status"),
            # Filenames
            ("config dot json.", "config.json"),
            ("readme dot md.", "README.md"),
            ("app dot py.", "app.py"),
            # URLs (if detected as single entity)
            ("github dot com.", "github.com"),
            ("example dot org.", "example.org"),
            # CLI commands
            ("git status.", "git status"),
            ("npm install.", "npm install"),
            ("docker run.", "docker run"),
            # Version numbers
            ("version two point one.", "Version 2.1"),
            ("v one point zero.", "v1.0"),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            assert result == expected, f"Input '{input_text}' should format to '{expected}' (no period), got '{result}'"

    def test_sentences_with_entities_keep_punctuation(self, preloaded_formatter):
        """Test that real sentences containing entities are formatted correctly (punctuation disabled in test env)."""
        format_transcription = preloaded_formatter
        test_cases = [
            # Sentences - no periods expected since punctuation is disabled in test environment
            ("please run slash compact", "Please run /compact"),
            ("the file is config dot json", "The file is config.json"),
            ("visit github dot com for more info", "Visit github.com for more info"),
            ("run git status to check", "Run git status to check"),
            ("we're using version two point one", "We're using version 2.1"),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            assert result == expected, f"Input '{input_text}' should format to '{expected}', got '{result}'"


class TestFillerWordPreservation:
    """Test that certain filler words are preserved when contextually important."""

    def test_filler_words_in_quotes_or_examples(self, preloaded_formatter):
        """Test that filler words are preserved when they're part of quoted speech or examples."""
        format_transcription = preloaded_formatter
        test_cases = [
            # When discussing the words themselves
            ("words like actually should be preserved", "Words like actually should be preserved"),
            ("I say things like actually or like", "I say things like actually or like"),
            ("he literally said literally", "He literally said literally"),
            # In quoted contexts (once quote detection is implemented)
            # ("she said like three times", "She said like three times"),
            # When they're meaningful
            ("I actually finished it", "I actually finished it"),
            ("basically correct", "Basically correct"),
            ("literally true", "Literally true"),
            # Test comma cleanup after filler word removal
            ("actually, that's freaking awesome", "That's freaking awesome"),
            ("like, this is really cool", "This is really cool"),
            ("basically, we need this", "We need this"),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            # Allow for optional punctuation at the end
            assert result in [
                expected,
                expected + ".",
            ], f"Input '{input_text}' should format to '{expected}', got '{result}'"

    def test_filler_words_that_should_be_removed(self, preloaded_formatter):
        """Test that filler words ARE removed in appropriate contexts."""
        format_transcription = preloaded_formatter
        test_cases = [
            # Clear filler usage
            ("like I was saying", "I was saying"),
            ("it was like really hot", "It was really hot"),
            ("you know what I mean", "What I mean"),
            ("basically we need to go", "We need to go"),
            # Multiple fillers
            ("so like basically I think", "So I think"),
            ("actually like you know", ""),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            # Allow for optional punctuation at the end
            if expected:  # Non-empty expected output
                assert result in [
                    expected,
                    expected + ".",
                ], f"Input '{input_text}' should format to '{expected}', got '{result}'"
            else:  # Empty expected output
                assert result == expected, f"Input '{input_text}' should format to empty string, got '{result}'"
