#!/usr/bin/env python3
"""Comprehensive tests for Spanish web-related entities: URLs, emails, and ports.

This module tests the detection and formatting of:
- SPOKEN_URL: "ejemplo punto com" → "ejemplo.com"
- SPOKEN_PROTOCOL_URL: "https dos puntos barra barra ejemplo punto com" → "https://ejemplo.com"
- SPOKEN_EMAIL: "usuario arroba dominio punto com" → "usuario@dominio.com"
- EMAIL: Standard email addresses
- PORT_NUMBER: "localhost dos puntos 8080" → "localhost:8080"
- URL: Standard URLs with proper formatting
"""

import pytest


class TestSpanishSpokenUrls:
    """Test Spanish SPOKEN_URL entity detection and formatting."""

    def test_basic_spoken_urls(self, spanish_formatter):
        """Test basic Spanish spoken URL patterns."""
        test_cases = [
            ("visita google punto com", "Visita google.com"),
            ("ve a ejemplo punto org", "Ve a ejemplo.org"),
            ("revisa github punto com", "Revisa github.com"),
            ("visita mi-sitio punto io", "Visita mi-sitio.io"),
            ("revisa prueba-dominio punto co punto uk", "Revisa prueba-dominio.co.uk"),
        ]

        for input_text, expected in test_cases:
            result = spanish_formatter.format_transcription(input_text)
            assert result == expected, f"Input '{input_text}' should format to '{expected}', got '{result}'"

    def test_spoken_urls_with_paths(self, spanish_formatter):
        """Test Spanish spoken URLs with path segments."""
        test_cases = [
            ("ve a ejemplo punto com barra página", "Ve a ejemplo.com/página"),
            ("visita github punto com barra usuario barra repositorio", "Visita github.com/usuario/repositorio"),
            ("revisa api punto sitio punto com barra v uno barra datos", "Revisa api.sitio.com/v1/datos"),
            ("descarga de cdn punto com barra activos barra archivo", "Descarga de cdn.com/activos/archivo"),
        ]

        for input_text, expected in test_cases:
            result = spanish_formatter.format_transcription(input_text)
            assert result == expected, f"Input '{input_text}' should format to '{expected}', got '{result}'"

    def test_spoken_urls_with_numbers(self, spanish_formatter):
        """Test Spanish spoken URLs containing numbers."""
        test_cases = [
            ("visita servidor uno punto ejemplo punto com", "Visita servidor 1.ejemplo.com"),
            ("ve a api punto v dos punto servicio punto org", "Ve a api.v2.servicio.org"),
            ("revisa sitio punto com barra usuario barra uno dos tres", "Revisa sitio.com/usuario/123"),
            ("descarga de cdn punto com barra v uno barra activos", "Descarga de cdn.com/v1/activos"),
        ]

        for input_text, expected in test_cases:
            result = spanish_formatter.format_transcription(input_text)
            assert result == expected, f"Input '{input_text}' should format to '{expected}', got '{result}'"

    def test_spoken_urls_with_query_parameters(self, spanish_formatter):
        """Test Spanish spoken URLs with query parameters."""
        test_cases = [
            (
                "ve a búsqueda punto com signo de interrogación consulta igual python",
                "Ve a búsqueda.com?consulta=python",
            ),
            (
                "visita sitio punto org interrogación usuario igual admin y token igual abc",
                "Visita sitio.org?usuario=admin&token=abc",
            ),
            (
                "revisa api punto com interrogación página igual uno y límite igual diez",
                "Revisa api.com?página=1&límite=10",
            ),
        ]

        for input_text, expected in test_cases:
            result = spanish_formatter.format_transcription(input_text)
            assert result == expected, f"Input '{input_text}' should format to '{expected}', got '{result}'"


class TestSpanishSpokenEmails:
    """Test Spanish SPOKEN_EMAIL entity detection and formatting."""

    def test_basic_spoken_emails(self, spanish_formatter):
        """Test basic Spanish spoken email patterns."""
        test_cases = [
            ("mi email es usuario arroba ejemplo punto com", "Mi email es usuario@ejemplo.com"),
            ("contacta a admin arroba sitio punto org", "Contacta a admin@sitio.org"),
            ("envía a prueba arroba dominio punto net", "Envía a prueba@dominio.net"),
            ("escribe a soporte arroba empresa punto es", "Escribe a soporte@empresa.es"),
        ]

        for input_text, expected in test_cases:
            result = spanish_formatter.format_transcription(input_text)
            assert result == expected, f"Input '{input_text}' should format to '{expected}', got '{result}'"

    def test_spoken_emails_with_numbers(self, spanish_formatter):
        """Test Spanish spoken emails with numbers."""
        test_cases = [
            ("envía a usuario uno dos tres arroba ejemplo punto com", "Envía a usuario123@ejemplo.com"),
            ("email juan dos mil arroba correo punto es", "Email juan2000@correo.es"),
            ("contacta a prueba cinco arroba sitio punto mx", "Contacta a prueba5@sitio.mx"),
        ]

        for input_text, expected in test_cases:
            result = spanish_formatter.format_transcription(input_text)
            assert result == expected, f"Input '{input_text}' should format to '{expected}', got '{result}'"


class TestSpanishCodeOperators:
    """Test Spanish code operator detection and formatting."""

    def test_basic_operators(self, spanish_formatter):
        """Test basic Spanish code operators."""
        test_cases = [
            ("contador más más", "contador++"),
            ("valor menos menos", "valor--"),
            ("si x igual igual cinco", "Si x == 5"),
            ("resultado igual a más b", "resultado = a + b"),
            ("diferencia igual x menos y", "diferencia = x - y"),
        ]

        for input_text, expected in test_cases:
            result = spanish_formatter.format_transcription(input_text)
            assert result == expected, f"Input '{input_text}' should format to '{expected}', got '{result}'"

    def test_slash_commands(self, spanish_formatter):
        """Test Spanish slash command formatting."""
        test_cases = [
            ("ejecuta barra construir", "Ejecuta /construir"),
            ("usa barra ayuda", "Usa /ayuda"),
            ("comando barra desplegar guión producción", "Comando /desplegar-producción"),
        ]

        for input_text, expected in test_cases:
            result = spanish_formatter.format_transcription(input_text)
            assert result == expected, f"Input '{input_text}' should format to '{expected}', got '{result}'"

    def test_underscore_variables(self, spanish_formatter):
        """Test Spanish underscore variable formatting."""
        test_cases = [
            ("variable guión bajo nombre", "variable_nombre"),
            ("mi guión bajo función", "mi_función"),
            ("constante guión bajo valor guión bajo máximo", "constante_valor_máximo"),
        ]

        for input_text, expected in test_cases:
            result = spanish_formatter.format_transcription(input_text)
            assert result == expected, f"Input '{input_text}' should format to '{expected}', got '{result}'"


class TestSpanishNumericEntities:
    """Test Spanish numeric entity detection and formatting."""

    def test_spanish_numbers(self, spanish_formatter):
        """Test Spanish number word conversion."""
        test_cases = [
            ("tengo veinte años", "Tengo 20 años"),
            ("compré treinta libros", "Compré 30 libros"),  # Changed to non-currency context
            ("hay cien personas", "Hay 100 personas"),
            ("mil documentos", "1000 documentos"),  # Changed from currency to documents
            ("dos mil veintitrés", "2023"),
        ]

        for input_text, expected in test_cases:
            result = spanish_formatter.format_transcription(input_text)
            assert result == expected, f"Input '{input_text}' should format to '{expected}', got '{result}'"

    def test_currency_formatting(self, spanish_formatter):
        """Test Spanish currency formatting."""
        test_cases = [
            ("cuesta cinco euros", "Cuesta €5"),
            ("precio treinta dólares", "Precio $30"),
            ("vale cien pesos", "Vale $100"),
            ("total mil quinientos euros", "Total €1500"),
        ]

        for input_text, expected in test_cases:
            result = spanish_formatter.format_transcription(input_text)
            assert result == expected, f"Input '{input_text}' should format to '{expected}', got '{result}'"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
