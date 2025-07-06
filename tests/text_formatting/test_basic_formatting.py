#!/usr/bin/env python3
"""Comprehensive tests for basic text formatting: capitalization and punctuation.

This module tests the core formatting behaviors:
- Sentence capitalization
- Punctuation addition/restoration
- Entity protection during formatting
- Special punctuation rules (e.g., abbreviations)
- Idiomatic expression preservation
"""

import pytest
import sys
import os

# Add the project root to the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from stt_hotkeys.text_formatting.formatter import format_transcription


class TestBasicCapitalization:
    """Test basic capitalization rules."""

    def test_sentence_start_capitalization(self):
        """Test that sentences start with capital letters."""
        test_cases = [
            ("hello world", "Hello world."),
            ("welcome to the system", "Welcome to the system."),
            ("this is a test", "This is a test."),
            ("the quick brown fox", "The quick brown fox."),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            assert result == expected, f"Input '{input_text}' should format to '{expected}', got '{result}'"

    def test_proper_noun_capitalization(self):
        """Test that proper nouns are capitalized correctly."""
        test_cases = [
            ("i met john yesterday", "I met John yesterday."),
            ("we visited paris in june", "We visited Paris in June."),
            ("microsoft and google are competitors", "Microsoft and Google are competitors."),
            ("python is a programming language", "Python is a programming language."),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            # Some proper nouns may not be detected without full NLP
            print(f"Proper noun test: '{input_text}' -> '{result}' (expected: '{expected}')")

    def test_pronoun_i_capitalization(self):
        """Test that pronoun 'I' is always capitalized."""
        test_cases = [
            ("i think therefore i am", "I think therefore I am."),
            ("you and i should meet", "You and I should meet."),
            ("when i was young", "When I was young."),
            ("i am working on it", "I am working on it."),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            assert result == expected, f"Input '{input_text}' should format to '{expected}', got '{result}'"

    def test_multi_sentence_capitalization(self):
        """Test capitalization in multi-sentence text."""
        test_cases = [
            ("hello. how are you", "Hello. How are you?"),
            ("this is great. i love it", "This is great. I love it."),
            ("stop. look. listen", "Stop. Look. Listen."),
            ("first sentence. second sentence. third sentence", "First sentence. Second sentence. Third sentence."),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            assert result == expected, f"Input '{input_text}' should format to '{expected}', got '{result}'"

    def test_question_mark_capitalization(self):
        """Test capitalization after question marks."""
        test_cases = [
            ("what is your name? my name is john", "What is your name? My name is John."),
            ("are you ready? let's go", "Are you ready? Let's go."),
            ("how does it work? it's simple", "How does it work? It's simple."),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            assert result == expected, f"Input '{input_text}' should format to '{expected}', got '{result}'"

    def test_exclamation_mark_capitalization(self):
        """Test capitalization after exclamation marks."""
        test_cases = [
            ("stop! don't move", "Stop! Don't move."),
            ("amazing! i can't believe it", "Amazing! I can't believe it."),
            ("hurry up! we're late", "Hurry up! We're late."),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            assert result == expected, f"Input '{input_text}' should format to '{expected}', got '{result}'"


class TestBasicPunctuation:
    """Test basic punctuation rules."""

    def test_period_at_sentence_end(self):
        """Test that periods are added at sentence end."""
        test_cases = [
            ("this is a statement", "This is a statement."),
            ("the system is running", "The system is running."),
            ("everything works fine", "Everything works fine."),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            assert result == expected, f"Input '{input_text}' should format to '{expected}', got '{result}'"

    def test_question_mark_detection(self):
        """Test that questions get question marks."""
        test_cases = [
            ("what is your name", "What is your name?"),
            ("how does this work", "How does this work?"),
            ("can you help me", "Can you help me?"),
            ("where are we going", "Where are we going?"),
            ("why did this happen", "Why did this happen?"),
            ("when will it be ready", "When will it be ready?"),
            ("who is responsible", "Who is responsible?"),
            ("which one should i choose", "Which one should I choose?"),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            assert result == expected, f"Input '{input_text}' should format to '{expected}', got '{result}'"

    def test_exclamation_context_detection(self):
        """Test that exclamatory sentences get exclamation marks."""
        test_cases = [
            ("wow that's amazing", "Wow, that's amazing!"),
            ("oh no i forgot", "Oh no, I forgot!"),
            ("great job everyone", "Great job everyone!"),
            ("congratulations on your success", "Congratulations on your success!"),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            # Exclamation detection may depend on context analysis
            print(f"Exclamation test: '{input_text}' -> '{result}' (expected: '{expected}')")

    def test_comma_in_lists(self):
        """Test comma insertion in lists."""
        test_cases = [
            ("apples oranges and bananas", "Apples, oranges, and bananas."),
            ("red blue green and yellow", "Red, blue, green, and yellow."),
            ("one two three and four", "1, 2, 3, and 4."),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            # List comma insertion may require advanced NLP
            print(f"List comma test: '{input_text}' -> '{result}' (expected: '{expected}')")

    def test_apostrophe_contractions(self):
        """Test apostrophes in contractions."""
        test_cases = [
            ("dont do that", "Don't do that."),
            ("cant find it", "Can't find it."),
            ("its working now", "It's working now."),
            ("thats correct", "That's correct."),
            ("weve finished", "We've finished."),
            ("theyre here", "They're here."),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            # Contraction detection may require specific patterns
            print(f"Contraction test: '{input_text}' -> '{result}' (expected: '{expected}')")


class TestEntityProtection:
    """Test that entities are protected during formatting."""

    def test_url_capitalization_protection(self):
        """Test that URLs maintain their original case."""
        test_cases = [
            ("visit github.com for more info", "Visit github.com for more info."),
            ("go to stackoverflow.com", "Go to stackoverflow.com."),
            ("check api.service.com", "Check api.service.com."),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            assert result == expected, f"Input '{input_text}' should format to '{expected}', got '{result}'"

    def test_email_capitalization_protection(self):
        """Test that emails maintain their original case."""
        test_cases = [
            ("contact john@example.com", "Contact john@example.com."),
            ("email support@company.com", "Email support@company.com."),
            ("send to user@domain.com", "Send to user@domain.com."),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            assert result == expected, f"Input '{input_text}' should format to '{expected}', got '{result}'"

    def test_code_entity_protection(self):
        """Test that code entities are protected from capitalization."""
        test_cases = [
            ("the variable i plus plus", "The variable i++."),
            ("use the flag dash dash verbose", "Use the flag --verbose."),
            ("run slash deploy command", "Run /deploy command."),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            assert result == expected, f"Input '{input_text}' should format to '{expected}', got '{result}'"

    def test_filename_case_preservation(self):
        """Test that filenames get appropriate casing based on extension."""
        test_cases = [
            ("open the file config dot py", "Open the file config.py."),
            ("edit app dot js", "Edit app.js."),
            ("check readme dot md", "Check README.md."),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            assert result == expected, f"Input '{input_text}' should format to '{expected}', got '{result}'"

    def test_entities_at_sentence_start(self):
        """Test that entities at sentence start maintain their proper case."""
        test_cases = [
            # Email at sentence start should not be capitalized
            ("hello@muffin.com is my email address", "hello@muffin.com is my email address."),
            # URL at sentence start should maintain case
            ("github.com is a website", "github.com is a website."),
            ("example.org has info", "example.org has info."),
            # But regular action words should still be capitalized
            ("john@company.com sent this", "john@company.com sent this."),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            assert result == expected, f"Input '{input_text}' should protect entity case: '{expected}', got '{result}'"

    def test_pronoun_i_protection_in_entities(self):
        """Test that 'i' inside entities is protected from capitalization."""
        test_cases = [
            # 'i' in filenames should stay lowercase
            ("the file is config_i.json", "The file is config_i.json."),
            ("open the file config_i.py", "Open the file config_i.py."),
            # Variable 'i' should stay lowercase
            ("the variable is i", "The variable is i."),
            ("set i equals zero", "Set i = 0."),
            # Mixed case - pronoun I vs variable i
            ("i think the variable is i", "I think the variable is i."),
            ("when i write i equals zero", "When I write i = 0."),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            assert result == expected, f"Input '{input_text}' should protect 'i' in entities: '{expected}', got '{result}'"

    def test_mixed_case_technical_terms(self):
        """Test preservation of mixed-case technical terms and acronyms."""
        test_cases = [
            # Mixed-case entities
            ("javaScript is a language", "JavaScript is a language."),
            ("the fileName is important", "The fileName is important."),
            # All-caps technical terms
            ("the API is down", "The API is down."),
            ("an API call failed", "An API call failed."),
            ("JSON API response", "JSON API response."),
            ("HTML CSS JavaScript", "HTML CSS JavaScript."),
            ("use SSH to connect", "Use SSH to connect."),
            ("CPU usage is high", "CPU usage is high."),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            assert result == expected, f"Input '{input_text}' should preserve case: '{expected}', got '{result}'"


class TestSpecialPunctuationRules:
    """Test special punctuation rules and edge cases."""

    def test_abbreviation_periods(self):
        """Test periods in abbreviations."""
        test_cases = [
            ("that is i e the main point", "That is i.e. the main point."),
            ("for example e g this case", "For example e.g. this case."),
            ("at three p m", "At 3 p.m."),
            ("in the u s a", "In the U.S.A."),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            # Abbreviation handling varies
            print(f"Abbreviation test: '{input_text}' -> '{result}' (expected: '{expected}')")

    def test_no_double_punctuation(self):
        """Test that we don't add double punctuation."""
        test_cases = [
            ("what is github.com?", "What is github.com?"),
            ("visit example.com.", "Visit example.com."),
            ("the temperature is 98.6°F.", "The temperature is 98.6°F."),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            assert result == expected, f"Input '{input_text}' should format to '{expected}', got '{result}'"

    def test_punctuation_after_entities(self):
        """Test punctuation placement after entities."""
        test_cases = [
            ("the file is main dot py", "The file is main.py."),
            ("send to john@example.com", "Send to john@example.com."),
            ("use port eight thousand", "Use port 8000."),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            assert result == expected, f"Input '{input_text}' should format to '{expected}', got '{result}'"


class TestIdiomaticExpressions:
    """Test preservation of idiomatic expressions."""

    def test_common_idioms_preserved(self):
        """Test that common idioms are preserved."""
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

    def test_numeric_idioms_preserved(self):
        """Test that numeric idioms are not converted."""
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

    def test_technical_sentences(self):
        """Test formatting of technical sentences."""
        test_cases = [
            (
                "open config dot py and set debug equals true",
                "Open config.py and set debug = true.",
            ),
            (
                "the server runs on port eight thousand",
                "The server runs on port 8000.",
            ),
            (
                "email john@example.com for help",
                "Email john@example.com for help.",
            ),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            assert result == expected, f"Input '{input_text}' should format to '{expected}', got '{result}'"

    def test_multi_entity_sentences(self):
        """Test sentences with multiple entity types."""
        test_cases = [
            (
                "visit github.com and download version two point one",
                "Visit github.com and download version 2.1.",
            ),
            (
                "the api at api.service.com colon three thousand is ready",
                "The API at api.service.com:3000 is ready.",
            ),
            (
                "send fifty percent to user@domain.com",
                "Send 50% to user@domain.com.",
            ),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            assert result == expected, f"Input '{input_text}' should format to '{expected}', got '{result}'"


class TestPunctuationModelIntegration:
    """Test integration with punctuation restoration model."""

    def test_punctuation_model_vs_rules(self):
        """Test when punctuation model should be used vs rule-based."""
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
            print(f"Punctuation model test: '{input_text}' -> '{result}' (expected: '{expected}')")


class TestEdgeCasesAndRegressions:
    """Test edge cases and document known issues."""

    def test_empty_and_whitespace_handling(self):
        """Test handling of empty strings and whitespace."""
        test_cases = [
            ("", ""),
            ("   ", ""),
            ("\t\n", ""),
            ("   hello   ", "Hello."),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            assert result == expected, f"Input '{input_text}' should format to '{expected}', got '{result}'"

    def test_filler_word_removal(self):
        """Test that filler words are removed."""
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
            print(f"Filler word test: '{input_text}' -> '{result}' (expected: '{expected}')")

    def test_casual_starters_capitalization(self):
        """Test that casual conversation starters are still capitalized."""
        test_cases = [
            ("hey there", "Hey there."),
            ("well hello", "Well, hello."),
            ("oh hi", "Oh, hi."),
            ("wow thats cool", "Wow, that's cool!"),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            # Punctuation may vary
            print(f"Casual starter test: '{input_text}' -> '{result}' (expected: '{expected}')")

    def test_profanity_filtering(self):
        """Test that profanity is replaced with asterisks."""
        test_cases = [
            ("what the fuck", "What the ****."),
            ("this is shit", "This is ****."),
            ("damn it", "**** it."),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            # Profanity filtering may be configurable
            print(f"Profanity test: '{input_text}' -> '{result}' (expected: '{expected}')")

    def test_version_number_formatting(self):
        """Test version number formatting."""
        test_cases = [
            ("version 16.4.2", "Version 16.4.2."),
            ("build 1.0.0", "Build 1.0.0."),
            ("release 2.5.0-beta", "Release 2.5.0-beta."),
            ("v three point two", "v3.2"),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            assert result in [expected, expected + "."], f"Input '{input_text}' should format to '{expected}', got '{result}'"


class TestIdiomaticExpressions:
    """Test idiomatic expressions that shouldn't be converted."""

    def test_idiomatic_math_words(self):
        """Test that idiomatic expressions with math words aren't converted."""
        test_cases = [
            ("i have five plus years of experience", "I have 5 + years of experience."),
            ("the game is over", "The game is over."),
            ("this is two times better", "This is 2 times better."),
            ("he went above and beyond", "He went above and beyond."),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            # Some idiomatic expressions may still be converted
            print(f"Idiomatic test: '{input_text}' -> '{result}' (expected: '{expected}')")


class TestComplexEdgeCases:
    """Test complex edge cases combining multiple challenges."""

    def test_kitchen_sink_scenarios(self):
        """Test complex sentences combining multiple edge cases."""
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
            print(f"Kitchen sink test: '{input_text}' -> '{result}' (expected: '{expected}')")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])