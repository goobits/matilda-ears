#!/usr/bin/env python3
"""Comprehensive tests for web-related entities: URLs, emails, and ports.

This module tests the detection and formatting of:
- SPOKEN_URL: "example dot com" → "example.com"
- SPOKEN_PROTOCOL_URL: "https colon slash slash example dot com" → "https://example.com"
- SPOKEN_EMAIL: "user at domain dot com" → "user@domain.com"
- EMAIL: Standard email addresses
- PORT_NUMBER: "localhost colon 8080" → "localhost:8080"
- URL: Standard URLs with proper formatting
"""

import pytest


class TestSpokenUrls:
    """Test SPOKEN_URL entity detection and formatting."""

    def test_basic_spoken_urls(self, preloaded_formatter):
        """Test basic spoken URL patterns."""
        format_transcription = preloaded_formatter
        test_cases = [
            ("visit google dot com", "Visit google.com"),
            ("go to example dot org", "Go to example.org"),
            ("check github dot com", "Check github.com"),
            ("visit my-site dot io", "Visit my-site.io"),
            ("check test-domain dot co dot uk", "Check test-domain.co.uk"),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            assert result == expected, f"Input '{input_text}' should format to '{expected}', got '{result}'"

    def test_spoken_urls_with_paths(self, preloaded_formatter):
        """Test spoken URLs with path segments."""
        format_transcription = preloaded_formatter
        test_cases = [
            ("go to example dot com slash page", "Go to example.com/page"),
            ("visit github dot com slash user slash repo", "Visit github.com/user/repo"),
            ("check api dot site dot com slash v one slash data", "Check api.site.com/v1/data"),
            ("download from cdn dot com slash assets slash file", "Download from cdn.com/assets/file"),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            assert result == expected, f"Input '{input_text}' should format to '{expected}', got '{result}'"

    def test_spoken_urls_with_numbers(self, preloaded_formatter):
        """Test spoken URLs containing numbers."""
        format_transcription = preloaded_formatter
        test_cases = [
            ("visit server one dot example dot com", "Visit server1.example.com"),
            ("go to api dot v two dot service dot org", "Go to api.v2.service.org"),
            ("check site dot com slash user slash one two three", "Check site.com/user/123"),
            ("download from cdn dot com slash v one slash assets", "Download from cdn.com/v1/assets"),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            assert result == expected, f"Input '{input_text}' should format to '{expected}', got '{result}'"

    def test_spoken_urls_with_query_parameters(self, preloaded_formatter):
        """Test spoken URLs with query parameters."""
        format_transcription = preloaded_formatter
        test_cases = [
            (
                "go to search dot com question mark query equals python",
                "Go to search.com?query=python",
            ),
            (
                "visit site dot org question mark user equals admin and token equals abc",
                "Visit site.org?user=admin&token=abc",
            ),
            (
                "check api dot com question mark page equals one and limit equals ten",
                "Check api.com?page=1&limit=10",
            ),
            (
                "search on google dot com question mark q equals voice recognition",
                "Search on google.com?q=voicerecognition",
            ),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            assert result == expected, f"Input '{input_text}' should format to '{expected}', got '{result}'"

    def test_spoken_urls_with_subdomains(self, preloaded_formatter):
        """Test spoken URLs with subdomains."""
        format_transcription = preloaded_formatter
        test_cases = [
            ("visit mail dot google dot com", "Visit mail.google.com"),
            ("go to api dot my-service dot example dot org", "Go to api.my-service.example.org"),
            ("check www dot github dot com", "Check www.github.com"),
            ("visit docs dot python dot org", "Visit docs.python.org"),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            assert result == expected, f"Input '{input_text}' should format to '{expected}', got '{result}'"

    def test_domain_rescue_mangled_urls(self, preloaded_formatter):
        """Test rescue of mangled domain names."""
        format_transcription = preloaded_formatter
        test_cases = [
            ("visit googlecom", "Visit google.com"),
            ("go to githubcom", "Go to github.com"),
            ("check stackoverflowcom", "Check stackoverflow.com"),
            ("visit wwwgooglecom", "Visit www.google.com"),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            assert result == expected, f"Input '{input_text}' should format to '{expected}', got '{result}'"

    def test_spoken_urls_in_sentences(self, preloaded_formatter):
        """Test spoken URLs embedded in natural sentences."""
        format_transcription = preloaded_formatter
        test_cases = [
            ("you can find the docs at python dot org", "You can find the docs at python.org"),
            ("the source code is hosted on github dot com", "The source code is hosted on github.com"),
            ("for more info visit our website at company dot com", "For more info visit our website at company.com"),
            ("the API endpoint is api dot service dot com slash v one", "The API endpoint is api.service.com/v1"),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            assert result == expected, f"Input '{input_text}' should format to '{expected}', got '{result}'"


class TestSpokenProtocolUrls:
    """Test SPOKEN_PROTOCOL_URL entity detection and formatting."""

    def test_basic_protocol_urls(self, preloaded_formatter):
        """Test basic protocol URL patterns."""
        format_transcription = preloaded_formatter
        test_cases = [
            ("http colon slash slash example dot com", "http://example.com"),
            ("https colon slash slash secure dot site dot org", "https://secure.site.org"),
            ("ftp colon slash slash files dot server dot com", "ftp://files.server.com"),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            # Protocol URLs are technical content so might not get punctuation
            assert result in [
                expected,
                expected + ".",
            ], f"Input '{input_text}' should format to '{expected}' or '{expected}.', got '{result}'"

    def test_protocol_urls_with_paths(self, preloaded_formatter):
        """Test protocol URLs with path segments."""
        format_transcription = preloaded_formatter
        test_cases = [
            ("https colon slash slash my app dot com slash login", "https://myapp.com/login"),
            ("http colon slash slash api dot service dot com slash v one", "http://api.service.com/v1"),
            ("https colon slash slash cdn dot example dot org slash assets", "https://cdn.example.org/assets"),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            assert result in [
                expected,
                expected + ".",
            ], f"Input '{input_text}' should format to '{expected}' or '{expected}.', got '{result}'"

    def test_protocol_urls_with_ports(self, preloaded_formatter):
        """Test protocol URLs with port numbers."""
        format_transcription = preloaded_formatter
        test_cases = [
            ("http colon slash slash test dot local colon eight zero eight zero", "http://test.local:8080"),
            (
                "https colon slash slash secure dot example dot com colon four four three",
                "https://secure.example.com:443",
            ),
            ("http colon slash slash localhost colon three thousand", "http://localhost:3000"),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            assert result in [
                expected,
                expected + ".",
            ], f"Input '{input_text}' should format to '{expected}' or '{expected}.', got '{result}'"

    def test_protocol_urls_with_query_parameters(self, preloaded_formatter):
        """Test protocol URLs with query parameters."""
        format_transcription = preloaded_formatter
        test_cases = [
            (
                "https colon slash slash api dot service dot com slash v one question mark key equals value",
                "https://api.service.com/v1?key=value",
            ),
            (
                "http colon slash slash search dot com question mark q equals test and page equals one",
                "http://search.com?q=test&page=1",
            ),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            assert result in [
                expected,
                expected + ".",
            ], f"Input '{input_text}' should format to '{expected}' or '{expected}.', got '{result}'"

    def test_protocol_urls_with_authentication(self, preloaded_formatter):
        """Test protocol URLs with authentication."""
        format_transcription = preloaded_formatter
        test_cases = [
            ("https colon slash slash user at secure dot site dot org", "https://user@secure.site.org"),
            ("ftp colon slash slash admin at files dot server dot com", "ftp://admin@files.server.com"),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            assert result in [
                expected,
                expected + ".",
            ], f"Input '{input_text}' should format to '{expected}' or '{expected}.', got '{result}'"


class TestSpokenEmails:
    """Test SPOKEN_EMAIL entity detection and formatting."""


    def test_spoken_emails_with_numbers(self, preloaded_formatter):
        """Test spoken emails containing numbers."""
        format_transcription = preloaded_formatter
        test_cases = [
            ("contact user one two three at test-domain dot co dot uk", "Contact user123@test-domain.co.uk"),
            ("send to admin at server two dot example dot com", "Send to admin@server2.example.com"),
            ("email support at help one dot service dot org", "Email support@help1.service.org"),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            assert result == expected, f"Input '{input_text}' should format to '{expected}', got '{result}'"

    def test_spoken_emails_with_special_characters(self, preloaded_formatter):
        """Test spoken emails with underscores and hyphens."""
        format_transcription = preloaded_formatter
        test_cases = [
            ("email first underscore last at my-company dot org", "Email first_last@my-company.org"),
            ("contact support dash team at help dot io", "Contact support-team@help.io"),
            ("send to user underscore admin at test dot com", "Send to user_admin@test.com"),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            assert result == expected, f"Input '{input_text}' should format to '{expected}', got '{result}'"

    def test_spoken_emails_with_subdomains(self, preloaded_formatter):
        """Test spoken emails with subdomains."""
        format_transcription = preloaded_formatter
        test_cases = [
            ("reach out to sales at mail dot big-corp dot com", "Reach out to sales@mail.big-corp.com"),
            ("notify admin at db dot prod dot company dot net", "Notify admin@db.prod.company.net"),
            ("email support at help dot customer-service dot org", "Email support@help.customer-service.org"),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            assert result == expected, f"Input '{input_text}' should format to '{expected}', got '{result}'"

    def test_spoken_emails_with_action_verbs(self, preloaded_formatter):
        """Test spoken emails with action verbs."""
        format_transcription = preloaded_formatter
        test_cases = [
            ("email john doe at example dot com about the meeting", "Email johndoe@example.com about the meeting"),
            (
                "send the report to data at analytics dot company dot com",
                "Send the report to data@analytics.company.com.",
            ),
            ("forward this to admin at server dot example dot org", "Forward this to admin@server.example.org"),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            assert result == expected, f"Input '{input_text}' should format to '{expected}', got '{result}'"

    def test_spoken_emails_entity_protection(self, preloaded_formatter):
        """Test that email entities are protected from capitalization."""
        format_transcription = preloaded_formatter
        test_cases = [
            # Email at start of sentence - should not be capitalized
            ("hello at muffin dot com is my email address", "hello@muffin.com is my email address"),
            ("john at company dot com sent this", "john@company.com sent this"),
            ("support at help dot org will respond", "support@help.org will respond"),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            assert result == expected, f"Input '{input_text}' should protect email text: '{expected}', got '{result}'"


class TestStandardEmails:
    """Test standard EMAIL entity detection and formatting."""

    def test_standard_email_addresses(self, preloaded_formatter):
        """Test standard email addresses that are already formatted."""
        format_transcription = preloaded_formatter
        test_cases = [
            ("My email is user@example.com", "My email is user@example.com"),
            ("Contact support@company.org for help", "Contact support@company.org for help"),
            ("Send to admin@server.net", "Send to admin@server.net"),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            assert result == expected, f"Input '{input_text}' should format to '{expected}', got '{result}'"

    def test_standard_emails_with_punctuation(self, preloaded_formatter):
        """Test standard emails with existing punctuation."""
        format_transcription = preloaded_formatter
        test_cases = [
            ("Email me at user@example.com!", "Email me at user@example.com!"),
            ("Is admin@server.org working?", "Is admin@server.org working?"),
            ("Contact support@help.io.", "Contact support@help.io"),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            assert result == expected, f"Input '{input_text}' should format to '{expected}', got '{result}'"


class TestPortNumbers:
    """Test PORT_NUMBER entity detection and formatting."""

    def test_basic_port_numbers(self, preloaded_formatter):
        """Test basic port number patterns."""
        format_transcription = preloaded_formatter
        test_cases = [
            ("connect to localhost colon eight zero eight zero", "Connect to localhost:8080"),
            ("the server runs on port nine thousand", "The server runs on port 9000"),
            ("database server colon five four three two", "Database server:5432"),
            ("redis colon six three seven nine", "Redis:6379"),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            # Port numbers are technical content so might not get punctuation
            assert result in [
                expected,
                expected + ".",
            ], f"Input '{input_text}' should format to '{expected}' or '{expected}.', got '{result}'"

    def test_port_numbers_with_ips(self, preloaded_formatter):
        """Test port numbers with IP addresses."""
        format_transcription = preloaded_formatter
        test_cases = [
            ("connect to one two seven dot zero dot zero dot one colon two two", "Connect to 127.0.0.1:22"),
            (
                "the API is at one nine two dot one six eight dot one dot one colon three thousand",
                "The API is at 192.168.1.1:3000",
            ),
            ("ssh to ten dot zero dot zero dot one colon two two two two", "SSH to 10.0.0.1:2222"),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            assert result in [
                expected,
                expected + ".",
            ], f"Input '{input_text}' should format to '{expected}' or '{expected}.', got '{result}'"

    def test_port_numbers_with_domains(self, preloaded_formatter):
        """Test port numbers with domain names."""
        format_transcription = preloaded_formatter
        test_cases = [
            ("the API is at api dot service dot com colon three thousand", "The API is at api.service.com:3000"),
            ("database at db dot example dot org colon five four three two", "Database at db.example.org:5432"),
            ("web server at www dot site dot com colon eight zero eight zero", "Web server at www.site.com:8080"),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            assert result in [
                expected,
                expected + ".",
            ], f"Input '{input_text}' should format to '{expected}' or '{expected}.', got '{result}'"

    def test_common_service_ports(self, preloaded_formatter):
        """Test common service port numbers."""
        format_transcription = preloaded_formatter
        test_cases = [
            ("HTTP server colon eight zero", "HTTP server:80"),
            ("HTTPS server colon four four three", "HTTPS server:443"),
            ("FTP server colon twenty one", "FTP server:21"),
            ("SSH server colon twenty two", "SSH server:22"),
            ("MySQL server colon three three zero six", "MySQL server:3306"),
            ("PostgreSQL server colon five four three two", "PostgreSQL server:5432"),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            assert result in [
                expected,
                expected + ".",
            ], f"Input '{input_text}' should format to '{expected}' or '{expected}.', got '{result}'"


class TestStandardUrls:
    """Test standard URL entity detection and formatting."""

    def test_standard_urls(self, preloaded_formatter):
        """Test standard URLs that are already formatted."""
        format_transcription = preloaded_formatter
        test_cases = [
            ("Visit https://example.com", "Visit https://example.com"),
            (
                "Check the documentation at https://docs.python.org",
                "Check the documentation at https://docs.python.org",
            ),
            ("The API endpoint is http://api.service.com/v1", "The API endpoint is http://api.service.com/v1"),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            assert result == expected, f"Input '{input_text}' should format to '{expected}', got '{result}'"

    def test_standard_urls_with_punctuation(self, preloaded_formatter):
        """Test standard URLs with existing punctuation."""
        format_transcription = preloaded_formatter
        test_cases = [
            ("Go to https://example.com!", "Go to https://example.com!"),
            ("Is https://api.service.com working?", "Is https://api.service.com working?"),
            ("Visit https://docs.site.org.", "Visit https://docs.site.org"),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            assert result == expected, f"Input '{input_text}' should format to '{expected}', got '{result}'"


class TestWebEntityInteractions:
    """Test interactions between different web entities."""

    def test_url_vs_email_priority(self, preloaded_formatter):
        """Test that URLs and emails are detected correctly when both patterns could match."""
        format_transcription = preloaded_formatter
        test_cases = [
            # Should be detected as URL, not email
            ("visit user at example dot com", "Visit user@example.com"),  # This is actually an email pattern
            ("go to example dot com slash user", "Go to example.com/user"),  # This is clearly a URL
            # Should be detected as email, not URL
            ("email admin at server dot com", "Email admin@server.com"),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            assert result == expected, f"Input '{input_text}' should format to '{expected}', got '{result}'"

    def test_url_with_email_in_path(self, preloaded_formatter):
        """Test URLs that contain email-like patterns in their paths."""
        format_transcription = preloaded_formatter
        test_cases = [
            ("visit site dot com slash user at admin", "Visit site.com/user@admin"),
            ("go to example dot org slash contact at info", "Go to example.org/contact@info"),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            assert result == expected, f"Input '{input_text}' should format to '{expected}', got '{result}'"

    def test_complex_web_entities_in_sentences(self, preloaded_formatter):
        """Test complex sentences with multiple web entities."""
        format_transcription = preloaded_formatter
        test_cases = [
            (
                "email admin at server dot com or visit the site at example dot org",
                "Email admin@server.com or visit the site at example.org",
            ),
            (
                "the API at api dot service dot com colon three thousand returns JSON",
                "The API at api.service.com:3000 returns JSON",
            ),
            (
                "contact support at help dot company dot org or check https colon slash slash docs dot company dot org",
                "Contact: support@help.company.org or check https://docs.company.org",
            ),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            assert result == expected, f"Input '{input_text}' should format to '{expected}', got '{result}'"



class TestNestedWebEntityPatterns:
    """Test nested and compound web entity patterns."""

    def test_url_with_multiple_numbers(self, preloaded_formatter):
        """Test SPOKEN_URL containing multiple CARDINAL number words."""
        format_transcription = preloaded_formatter
        test_cases = [
            ("go to one one one one dot com slash users slash two", "Go to 1111.com/users/2"),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            assert result == expected, f"Input '{input_text}' should handle URL with numbers: '{expected}', got '{result}'"

    def test_email_with_underscore_and_number(self, preloaded_formatter):
        """Test SPOKEN_EMAIL containing SIMPLE_UNDERSCORE_VARIABLE and CARDINAL."""
        format_transcription = preloaded_formatter
        test_cases = [
            ("email user underscore one at example dot com", "Email user_1@example.com"),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            assert result == expected, f"Input '{input_text}' should handle complex email: '{expected}', got '{result}'"


class TestAmbiguousWebContexts:
    """Test ambiguous contexts where keywords shouldn't be converted."""

    def test_at_in_non_email_context(self, preloaded_formatter):
        """Test that 'at' is not converted to @ in non-email context."""
        format_transcription = preloaded_formatter
        test_cases = [
            ("I am at the office not at home", "I am at the office not at home"),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            assert result == expected, f"Input '{input_text}' should not convert 'at' in non-email context: '{expected}', got '{result}'"

    def test_false_email_patterns_in_conversation(self, preloaded_formatter):
        """Test that conversational patterns with 'at' are not misinterpreted as emails."""
        format_transcription = preloaded_formatter
        test_cases = [
            ("Please compare this branch to the main branch and tell me all the differences. I think that if you look at the proposal.md", "Please compare this branch to the main branch and tell me all the differences. I think that if you look at the proposal.md"),
            ("you look at the file and tell me", "You look at the file and tell me"),
            ("when you go at the store", "When you go at the store"),
            ("if you think at the problem differently", "If you think at the problem differently"),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            assert result == expected, f"Input '{input_text}' should not be interpreted as email: '{expected}', got '{result}'"


class TestWebEntityProtection:
    """Test protection of technical web entities from capitalization."""

    def test_url_at_sentence_start(self, preloaded_formatter):
        """Test that URLs at sentence start are NOT capitalized."""
        format_transcription = preloaded_formatter
        test_cases = [
            ("http://example.com is a url", "http://example.com is a url"),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            assert result == expected, f"Input '{input_text}' should protect URL from capitalization: '{expected}', got '{result}'"

    def test_email_and_phone_sequence(self, preloaded_formatter):
        """Test SPOKEN_EMAIL followed by PHONE_LONG number."""
        format_transcription = preloaded_formatter
        test_cases = [
            ("contact support at example dot com or call 555-123-4567", "Contact support@example.com or call 555-123-4567"),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            assert result == expected, f"Input '{input_text}' should handle email and phone: '{expected}', got '{result}'"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
