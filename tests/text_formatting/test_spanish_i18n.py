#!/usr/bin/env python3
"""Tests for Spanish language support in text formatting."""

import pytest
from src.text_formatting.formatter import TextFormatter
from src.text_formatting.constants import get_resources


class TestSpanishI18n:
    """Test comprehensive Spanish language support."""

    def test_spanish_resources_loading(self):
        """Test that Spanish resources load correctly."""
        resources = get_resources("es")

        # Test that key sections exist
        assert "spoken_keywords" in resources
        assert "abbreviations" in resources
        assert "top_level_domains" in resources

        # Test specific Spanish keywords
        assert resources["spoken_keywords"]["url"]["punto"] == "."
        assert resources["spoken_keywords"]["url"]["arroba"] == "@"
        assert resources["spoken_keywords"]["code"]["barra"] == "/"
        assert resources["spoken_keywords"]["operators"]["más más"] == "++"

    def test_spanish_email_formatting(self):
        """Test Spanish email address formatting."""
        formatter = TextFormatter(language="es")

        # Test basic email
        result = formatter.format_transcription("mi email es usuario arroba ejemplo punto com")
        assert "usuario@ejemplo.com" in result

        # Test with subdomain
        result = formatter.format_transcription("contacta admin arroba correo punto ejemplo punto org")
        assert "admin@correo.ejemplo.org" in result

    def test_spanish_url_formatting(self):
        """Test Spanish URL formatting."""
        formatter = TextFormatter(language="es")

        # Test basic URL
        result = formatter.format_transcription("visita ejemplo punto com")
        assert "ejemplo.com" in result

        # Test URL with protocol
        result = formatter.format_transcription("ve a http dos puntos barra barra ejemplo punto es")
        assert "http://ejemplo.es" in result

    def test_spanish_slash_commands(self):
        """Test Spanish slash command formatting."""
        formatter = TextFormatter(language="es")

        # Test slash command
        result = formatter.format_transcription("ejecuta barra desplegar")
        assert "/desplegar" in result

        # Test slash command with dashes
        result = formatter.format_transcription("corre barra construir guión todo")
        assert "/construir-todo" in result

    def test_spanish_code_operators(self):
        """Test Spanish code operator formatting."""
        formatter = TextFormatter(language="es")

        # Test increment operator
        result = formatter.format_transcription("contador más más")
        assert "contador++" in result

        # Test decrement operator
        result = formatter.format_transcription("valor menos menos")
        assert "valor--" in result

        # Test comparison
        result = formatter.format_transcription("si x igual igual cinco")
        assert "x == 5" in result

    def test_spanish_file_operations(self):
        """Test Spanish file-related formatting."""
        formatter = TextFormatter(language="es")

        # Test underscore variables
        result = formatter.format_transcription("variable guión bajo nombre")
        assert "variable_nombre" in result

        # Test assignment
        result = formatter.format_transcription("valor igual diez")
        assert "valor = 10" in result

    def test_spanish_fallback_to_english(self):
        """Test that non-existent language falls back to English."""
        # This should fall back to English and not crash
        formatter = TextFormatter(language="nonexistent")
        result = formatter.format_transcription("email user at example dot com")
        assert "user@example.com" in result

    def test_spanish_mixed_with_english_keywords(self):
        """Test that Spanish formatter only responds to Spanish keywords."""
        formatter = TextFormatter(language="es")

        # English keywords should not be converted when using Spanish formatter
        result = formatter.format_transcription("email user at example dot com")
        # Should not convert English keywords
        assert "@" not in result
        assert "user at example dot com" in result

    def test_spanish_context_preservation(self):
        """Test that Spanish formatter preserves context and capitalization."""
        formatter = TextFormatter(language="es")

        # Test proper capitalization
        result = formatter.format_transcription("envía un email a juan arroba empresa punto com")
        assert "Juan@empresa.com" in result

        # Test sentence structure preservation
        result = formatter.format_transcription("la página web es ejemplo punto org")
        assert "La página web es ejemplo.org" in result

    def test_language_switching_within_formatter(self):
        """Test that language can be overridden per call."""
        formatter = TextFormatter(language="en")  # Default English

        # Use English (default)
        result_en = formatter.format_transcription("email user at example dot com")
        assert "user@example.com" in result_en

        # Override to Spanish for one call
        result_es = formatter.format_transcription("usuario arroba ejemplo punto com", language="es")
        assert "usuario@ejemplo.com" in result_es

        # Back to English (default)
        result_en2 = formatter.format_transcription("contact admin at site dot org")
        assert "admin@site.org" in result_en2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
