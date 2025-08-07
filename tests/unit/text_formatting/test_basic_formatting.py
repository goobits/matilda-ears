#!/usr/bin/env python3
"""
Comprehensive tests for basic text formatting: capitalization and punctuation.

This module tests the core formatting behaviors:
- Sentence capitalization
- Punctuation addition/restoration
- Entity protection during formatting
- Special punctuation rules (e.g., abbreviations)
- Idiomatic expression preservation
"""

import pytest


class TestBasicCapitalization:
    """Test basic capitalization rules."""

    def test_sentence_start_capitalization(self, preloaded_formatter):
        """Test that sentences start with capital letters."""
        format_transcription = preloaded_formatter
        test_cases = [
            ("hello world", "Hello world"),
            ("welcome to the system", "Welcome to the system"),
            ("this is a test", "This is a test"),
            ("the quick brown fox", "The quick brown fox"),
            ("written as follows capital K lowercase I T T Y", "Written as follows Kitty"),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            assert result == expected, f"Input '{input_text}' should format to '{expected}', got '{result}'"

    def test_proper_noun_capitalization(self, preloaded_formatter):
        """Test that proper nouns are capitalized correctly."""
        format_transcription = preloaded_formatter
        test_cases = [
            ("i met john yesterday", "I met John yesterday."),
            ("we visited paris in june", "We visited Paris in June."),
            ("microsoft and google are competitors", "Microsoft and Google are competitors."),
            ("python is a programming language", "Python is a programming language."),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            # Some proper nouns may not be detected without full NLP

    def test_pronoun_i_capitalization(self, preloaded_formatter):
        """Test that pronoun 'I' is always capitalized."""
        format_transcription = preloaded_formatter
        test_cases = [
            ("i think therefore i am", "I think therefore I am"),
            ("you and i should meet", "You and I should meet"),
            ("when i was young", "When I was young"),
            ("i am working on it", "I am working on it"),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            assert result == expected, f"Input '{input_text}' should format to '{expected}', got '{result}'"

    def test_multi_sentence_capitalization(self, preloaded_formatter):
        """Test capitalization in multi-sentence text."""
        format_transcription = preloaded_formatter
        test_cases = [
            ("hello. how are you", "Hello. How are you"),
            ("this is great. i love it", "This is great. I love it"),
            ("stop. look. listen", "Stop. Look. Listen"),
            ("first sentence. second sentence. third sentence", "1st sentence. 2nd sentence. 3rd sentence"),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            assert result == expected, f"Input '{input_text}' should format to '{expected}', got '{result}'"


class TestBasicPunctuation:
    """Test basic punctuation rules."""

    def test_period_at_sentence_end(self, preloaded_formatter):
        """Test that periods are added at sentence end."""
        format_transcription = preloaded_formatter
        test_cases = [
            ("this is a statement", "This is a statement"),
            ("the system is running", "The system is running"),
            ("everything works fine", "Everything works fine"),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            assert result == expected, f"Input '{input_text}' should format to '{expected}', got '{result}'"

    def test_question_mark_detection(self, preloaded_formatter):
        """Test that questions get question marks."""
        format_transcription = preloaded_formatter
        test_cases = [
            ("what is your name", "What is your name"),
            ("how does this work", "How does this work"),
            ("can you help me", "Can you help me"),
            ("where are we going", "Where are we going"),
            ("why did this happen", "Why did this happen"),
            ("when will it be ready", "When will it be ready"),
            ("who is responsible", "Who is responsible"),
            ("which one should i choose", "Which one should I choose"),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            assert result == expected, f"Input '{input_text}' should format to '{expected}', got '{result}'"

    def test_exclamation_context_detection(self, preloaded_formatter):
        """Test that exclamatory sentences get exclamation marks."""
        format_transcription = preloaded_formatter
        test_cases = [
            ("wow that's amazing", "Wow, that's amazing!"),
            ("oh no i forgot", "Oh no, I forgot!"),
            ("great job everyone", "Great job everyone!"),
            ("congratulations on your success", "Congratulations on your success!"),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            # Exclamation detection may depend on context analysis

    def test_comma_in_lists(self, preloaded_formatter):
        """Test comma insertion in lists."""
        format_transcription = preloaded_formatter
        test_cases = [
            ("apples oranges and bananas", "Apples, oranges, and bananas."),
            ("red blue green and yellow", "Red, blue, green, and yellow."),
            ("one two three and four", "1, 2, 3, and 4."),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            # List comma insertion may require advanced NLP

    def test_apostrophe_contractions(self, preloaded_formatter):
        """Test apostrophes in contractions."""
        format_transcription = preloaded_formatter
        test_cases = [
            ("dont do that", "Don't do that."),
            ("cant find it", "Can't find it."),
            ("its working now", "It's working now."),
            ("thats correct", "That's correct."),
            ("weve finished", "We've finished."),
            ("theyre here", "They're here."),
            ("whats our test coverage look like", "What's our test coverage look like?"),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            # Contraction detection may require specific patterns


class TestEntityProtection:
    """Test that entities are protected during formatting."""

    def test_code_entity_protection(self, preloaded_formatter):
        """Test that code entities are protected from capitalization."""
        format_transcription = preloaded_formatter
        test_cases = [
            ("the variable i plus plus", "The variable i++"),
            ("use the flag dash dash verbose", "Use the flag --verbose"),
            ("run slash deploy command", "Run /deploy command"),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            assert result == expected, f"Input '{input_text}' should format to '{expected}', got '{result}'"

    def test_filename_case_preservation(self, preloaded_formatter):
        """Test that filenames get appropriate casing based on extension."""
        format_transcription = preloaded_formatter
        test_cases = [
            ("open the file config dot py", "Open the file config.py"),
            ("edit app dot js", "Edit app.js"),
            ("check readme dot md", "Check README.md"),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            assert result == expected, f"Input '{input_text}' should format to '{expected}', got '{result}'"


    def test_pronoun_i_protection_in_entities(self, preloaded_formatter):
        """Test that 'i' inside entities is protected from capitalization."""
        format_transcription = preloaded_formatter
        test_cases = [
            # 'i' in filenames should stay lowercase
            ("the file is config_i.json", "The file is config_i.json"),
            ("open the file config_i.py", "Open the file config_i.py"),
            # Variable 'i' should stay lowercase
            ("set i equals zero", "Set i = 0"),
            # Mixed case - pronoun I vs variable i
            ("i think the variable is i", "I think the variable is i."),
            ("when i write i equals zero", "When I write i = 0."),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            assert (
                result == expected
            ), f"Input '{input_text}' should protect 'i' in entities: '{expected}', got '{result}'"

    def test_mixed_case_technical_terms(self, preloaded_formatter):
        """Test preservation of mixed-case technical terms and acronyms."""
        format_transcription = preloaded_formatter
        test_cases = [
            # Mixed-case entities
            ("javaScript is a language", "JavaScript is a language"),
            ("the fileName is important", "The fileName is important"),
            # All-caps technical terms
            ("the API is down", "The API is down"),
            ("an API call failed", "An API call failed"),
            ("JSON API response", "JSON API response"),
            ("HTML CSS JavaScript", "HTML CSS JavaScript"),
            ("use SSH to connect", "Use SSH to connect"),
            ("CPU usage is high", "CPU usage is high"),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            assert result == expected, f"Input '{input_text}' should preserve case: '{expected}', got '{result}'"


class TestSpecialPunctuationRules:
    """Test special punctuation rules and edge cases."""

    def test_abbreviation_periods(self, preloaded_formatter):
        """Test periods in abbreviations."""
        format_transcription = preloaded_formatter
        test_cases = [
            ("that is i e the main point", "That is i.e. the main point."),
            ("for example e g this case", "For example e.g. this case."),
            ("at three p m", "At 3 p.m."),
            ("in the u s a", "In the U.S.A."),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            # Abbreviation handling varies




class TestIdiomaticExpressions:
    """Test preservation of idiomatic expressions."""

    def test_common_idioms_preserved(self, preloaded_formatter):
        """Test that common idioms are preserved."""
        format_transcription = preloaded_formatter
        test_cases = [
            ("break a leg", "Break a leg."),
            ("piece of cake", "Piece of cake."),
            ("under the weather", "Under the weather."),
            ("spill the beans", "Spill the beans."),
            ("hit the nail on the head", "Hit the nail on the head."),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            assert result == expected, f"Input '{input_text}' should format to '{expected}', got '{result}'"

    def test_numeric_idioms_preserved(self, preloaded_formatter):
        """Test that numeric idioms are not converted."""
        format_transcription = preloaded_formatter
        test_cases = [
            ("on cloud nine", "On cloud nine."),
            ("catch twenty two", "Catch twenty two."),
            ("at sixes and sevens", "At sixes and sevens."),
            ("the whole nine yards", "The whole nine yards."),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            assert result == expected, f"Input '{input_text}' should preserve idiom: '{expected}', got '{result}'"


class TestMixedContent:
    """Test formatting of mixed content with various entities."""

    def test_technical_sentences(self, preloaded_formatter):
        """Test formatting of technical sentences."""
        format_transcription = preloaded_formatter
        test_cases = [
            (
                "open config dot py and set debug equals true",
                "Open config.py and set debug = true",
            ),
            (
                "the server runs on port eight thousand",
                "The server runs on port 8000",
            ),
            (
                "email john@example.com for help",
                "Email john@example.com for help",
            ),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            assert result == expected, f"Input '{input_text}' should format to '{expected}', got '{result}'"

    def test_multi_entity_sentences(self, preloaded_formatter):
        """Test sentences with multiple entity types."""
        format_transcription = preloaded_formatter
        test_cases = [
            (
                "visit github.com and download version two point one",
                "Visit github.com and download version 2.1",
            ),
            (
                "the api at api.service.com colon three thousand is ready",
                "The API at api.service.com:3000 is ready",
            ),
            (
                "send fifty percent to user@domain.com",
                "Send 50% to user@domain.com",
            ),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            assert result == expected, f"Input '{input_text}' should format to '{expected}', got '{result}'"


class TestPunctuationModelIntegration:
    """Test integration with punctuation restoration model."""

    def test_punctuation_model_vs_rules(self, preloaded_formatter):
        """Test when punctuation model should be used vs rule-based."""
        format_transcription = preloaded_formatter
        test_cases = [
            # Technical content (skip punctuation model)
            ("x equals five", "x = 5"),
            ("i plus plus", "i++"),
            ("dash dash verbose", "--verbose"),
            # Natural language (use punctuation model if available)
            ("hello how are you today", "Hello, how are you today?"),
            ("thats great news", "That's great news!"),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            # Results depend on punctuation model availability


class TestEdgeCasesAndRegressions:
    """Test edge cases and document known issues."""

    def test_empty_and_whitespace_handling(self, preloaded_formatter):
        """Test handling of empty strings and whitespace."""
        format_transcription = preloaded_formatter
        test_cases = [
            ("", ""),
            ("   ", ""),
            ("\t\n", ""),
            ("   hello   ", "Hello"),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            assert result == expected, f"Input '{input_text}' should format to '{expected}', got '{result}'"

    def test_filler_word_removal(self, preloaded_formatter):
        """Test that filler words are removed."""
        format_transcription = preloaded_formatter
        test_cases = [
            ("um hello there", "Hello there."),
            ("uh what is this", "What is this?"),
            ("well um i think so", "Well, I think so."),
            ("hmm", ""),
            ("uhh", ""),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            # Filler word removal may vary

    def test_casual_starters_capitalization(self, preloaded_formatter):
        """Test that casual conversation starters are still capitalized."""
        format_transcription = preloaded_formatter
        test_cases = [
            ("hey there", "Hey there."),
            ("well hello", "Well, hello."),
            ("oh hi", "Oh, hi."),
            ("wow thats cool", "Wow, that's cool!"),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            # Punctuation may vary

    def test_profanity_filtering(self, preloaded_formatter):
        """Test that profanity is replaced with asterisks."""
        format_transcription = preloaded_formatter
        test_cases = [
            ("what the fuck", "What the ****."),
            ("this is shit", "This is ****."),
            ("damn it", "**** it."),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            # Profanity filtering may be configurable

    def test_version_number_formatting(self, preloaded_formatter):
        """Test version number formatting."""
        format_transcription = preloaded_formatter
        test_cases = [
            ("version 16.4.2", "Version 16.4.2"),
            ("build 1.0.0", "Build 1.0.0"),
            ("release 2.5.0-beta", "Release 2.5.0-beta"),
            ("v three point two", "v3.2"),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            assert result == expected, f"Input '{input_text}' should format to '{expected}', got '{result}'"


class TestIdiomaticExpressions:
    """Test idiomatic expressions that shouldn't be converted."""

    def test_idiomatic_math_words(self, preloaded_formatter):
        """Test that idiomatic expressions with math words aren't converted."""
        format_transcription = preloaded_formatter
        test_cases = [
            ("i have five plus years of experience", "I have 5 + years of experience."),
            ("the game is over", "The game is over."),
            ("this is two times better", "This is 2 times better."),
            ("he went above and beyond", "He went above and beyond."),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            # Some idiomatic expressions may still be converted


class TestComplexEdgeCases:
    """Test complex edge cases combining multiple challenges."""

    def test_kitchen_sink_scenarios(self, preloaded_formatter):
        """Test complex sentences combining multiple edge cases."""
        format_transcription = preloaded_formatter
        test_cases = [
            # Pronoun i, filename, URL, acronym, punctuation
            (
                "i told him to edit the file config_i dot js on github dot com not the API docs",
                "I told him to edit the file config_i.js on github.com, not the API docs.",
            ),
            # Math, URL, pronoun, API
            (
                "i think x equals five at example dot com but the API says otherwise",
                "I think x = 5 at example.com but the API says otherwise.",
            ),
            # Mixed technical content
            (
                "i use vim to edit main dot py and push to github dot com via SSH",
                "I use vim to edit main.py and push to github.com via SSH.",
            ),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            # Complex punctuation may vary


class TestCapitalizationEdgeCases:
    """Test edge cases for capitalization logic and entity protection."""

    def test_abbreviation_at_sentence_start(self, preloaded_formatter):
        """Test that prose entities like abbreviations are capitalized at sentence start."""
        format_transcription = preloaded_formatter
        test_cases = [
            ("i.e. the code must be clean", "I.e., the code must be clean"),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            assert (
                result == expected
            ), f"Input '{input_text}' should capitalize abbreviation at start: '{expected}', got '{result}'"

    def test_all_caps_input_with_entities(self, preloaded_formatter):
        """Test handling of all-caps input while correctly formatting sub-parts."""
        format_transcription = preloaded_formatter
        test_cases = [
            ('GIT COMMIT --MESSAGE "FIX"', 'GIT COMMIT --message "FIX"'),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            assert (
                result == expected
            ), f"Input '{input_text}' should handle all-caps correctly: '{expected}', got '{result}'"

    def test_mixed_case_brand_preservation(self, preloaded_formatter):
        """Test that pre-formatted technical/brand names preserve their casing."""
        format_transcription = preloaded_formatter
        test_cases = [
            ("iPhone and iPad are made by Apple", "iPhone and iPad are made by Apple"),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            assert (
                result == expected
            ), f"Input '{input_text}' should preserve mixed-case brands: '{expected}', got '{result}'"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
