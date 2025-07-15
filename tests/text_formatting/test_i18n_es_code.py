#!/usr/bin/env python3
"""Comprehensive tests for Spanish code-related entities.

This module tests the detection and formatting of:
- SLASH_COMMAND: "/comando" patterns
- COMMAND_FLAG: "-bandera" and "--bandera-larga" patterns
- UNDERSCORE_DELIMITER: "__init__", "__main__" patterns
- SIMPLE_UNDERSCORE_VARIABLE: "mi_variable" patterns
- Spoken operators: "más más" → "++"
"""

import pytest


class TestSpanishSlashCommands:
    """Test Spanish SLASH_COMMAND entity detection and formatting."""

    def test_basic_slash_commands(self, spanish_formatter):
        """Test basic Spanish slash command patterns."""
        test_cases = [
            ("ejecuta barra ayuda", "Ejecuta /ayuda"),
            ("usa barra construir", "Usa /construir"),
            ("comando barra iniciar", "Comando /iniciar"),
            ("prueba barra desplegar", "Prueba /desplegar"),
        ]

        for input_text, expected in test_cases:
            result = spanish_formatter.format_transcription(input_text)
            assert result == expected, f"Input '{input_text}' should format to '{expected}', got '{result}'"

    def test_slash_commands_with_params(self, spanish_formatter):
        """Test Spanish slash commands with parameters."""
        test_cases = [
            ("ejecuta barra crear usuario nuevo", "Ejecuta /crear usuario nuevo"),
            ("usa barra configurar servidor producción", "Usa /configurar servidor producción"),
            ("comando barra eliminar archivo temporal", "Comando /eliminar archivo temporal"),
        ]

        for input_text, expected in test_cases:
            result = spanish_formatter.format_transcription(input_text)
            assert result == expected, f"Input '{input_text}' should format to '{expected}', got '{result}'"

    def test_slash_commands_with_dashes(self, spanish_formatter):
        """Test Spanish slash commands with dashed names."""
        test_cases = [
            ("ejecuta barra construir guión limpio", "Ejecuta /construir-limpio"),
            ("usa barra modo guión desarrollo", "Usa /modo-desarrollo"),
            ("comando barra configurar guión servidor guión web", "Comando /configurar-servidor-web"),
        ]

        for input_text, expected in test_cases:
            result = spanish_formatter.format_transcription(input_text)
            assert result == expected, f"Input '{input_text}' should format to '{expected}', got '{result}'"


class TestSpanishCommandFlags:
    """Test Spanish COMMAND_FLAG entity detection and formatting."""

    def test_short_flags(self, spanish_formatter):
        """Test Spanish short command flag patterns."""
        test_cases = [
            ("ejecuta con guión v", "Ejecuta con -v"),
            ("usa guión h para ayuda", "Usa -h para ayuda"),
            ("comando guión f archivo", "Comando -f archivo"),
            ("prueba guión d para depuración", "Prueba -d para depuración"),
        ]

        for input_text, expected in test_cases:
            result = spanish_formatter.format_transcription(input_text)
            assert result == expected, f"Input '{input_text}' should format to '{expected}', got '{result}'"

    def test_long_flags(self, spanish_formatter):
        """Test Spanish long command flag patterns."""
        test_cases = [
            ("ejecuta con guión guión ayuda", "Ejecuta con --ayuda"),
            ("usa guión guión versión", "Usa --versión"),
            ("comando guión guión modo producción", "Comando --modo producción"),
            ("prueba guión guión salida guión archivo", "Prueba --salida-archivo"),
        ]

        for input_text, expected in test_cases:
            result = spanish_formatter.format_transcription(input_text)
            assert result == expected, f"Input '{input_text}' should format to '{expected}', got '{result}'"


class TestSpanishUnderscorePatterns:
    """Test Spanish underscore pattern detection and formatting."""

    def test_simple_underscore_variables(self, spanish_formatter):
        """Test Spanish simple underscore variable patterns."""
        test_cases = [
            ("variable mi guión bajo nombre", "Variable mi_nombre"),
            ("función obtener guión bajo datos", "Función obtener_datos"),
            ("constante valor guión bajo máximo", "Constante valor_máximo"),
            ("método calcular guión bajo resultado", "Método calcular_resultado"),
        ]

        for input_text, expected in test_cases:
            result = spanish_formatter.format_transcription(input_text)
            assert result == expected, f"Input '{input_text}' should format to '{expected}', got '{result}'"

    def test_multiple_underscores(self, spanish_formatter):
        """Test Spanish patterns with multiple underscores."""
        test_cases = [
            ("archivo guión bajo configuración guión bajo principal", "Archivo _configuración_principal"),
            ("función guión bajo guión bajo init guión bajo guión bajo", "Función __init__"),
            ("variable guión bajo privada guión bajo valor", "Variable _privada_valor"),
        ]

        for input_text, expected in test_cases:
            result = spanish_formatter.format_transcription(input_text)
            assert result == expected, f"Input '{input_text}' should format to '{expected}', got '{result}'"


class TestSpanishCodeOperators:
    """Test Spanish code operator detection and formatting."""

    def test_increment_decrement(self, spanish_formatter):
        """Test Spanish increment and decrement operators."""
        test_cases = [
            ("contador más más", "contador++"),
            ("índice menos menos", "índice--"),
            ("variable x más más", "Variable x++"),
            ("valor y menos menos", "Valor y--"),
        ]

        for input_text, expected in test_cases:
            result = spanish_formatter.format_transcription(input_text)
            assert result == expected, f"Input '{input_text}' should format to '{expected}', got '{result}'"

    def test_comparison_operators(self, spanish_formatter):
        """Test Spanish comparison operators."""
        test_cases = [
            ("si x igual igual cinco", "Si x == 5"),
            ("mientras a menor que b", "Mientras a menor que b"),
            ("comprobar si valor mayor que cero", "Comprobar si valor mayor que 0"),
        ]

        for input_text, expected in test_cases:
            result = spanish_formatter.format_transcription(input_text)
            assert result == expected, f"Input '{input_text}' should format to '{expected}', got '{result}'"

    def test_assignment_operators(self, spanish_formatter):
        """Test Spanish assignment operators."""
        test_cases = [
            ("x igual cinco", "x = 5"),
            ("resultado igual a más b", "resultado = a + b"),
            ("total igual precio por cantidad", "total = precio × cantidad"),
            ("promedio igual suma dividido entre n", "promedio = suma ÷ n"),
        ]

        for input_text, expected in test_cases:
            result = spanish_formatter.format_transcription(input_text)
            assert result == expected, f"Input '{input_text}' should format to '{expected}', got '{result}'"


class TestSpanishMixedPatterns:
    """Test Spanish mixed code patterns."""

    def test_code_with_urls(self, spanish_formatter):
        """Test Spanish code patterns mixed with URLs."""
        test_cases = [
            ("visita api punto ejemplo punto com barra v uno", "Visita api.ejemplo.com/v1"),
            ("conecta a servidor punto local dos puntos ocho cero ocho cero", "Conecta a servidor.local:8080"),
            ("descarga de github punto com barra usuario barra repo", "Descarga de github.com/usuario/repo"),
        ]

        for input_text, expected in test_cases:
            result = spanish_formatter.format_transcription(input_text)
            assert result == expected, f"Input '{input_text}' should format to '{expected}', got '{result}'"

    def test_code_with_numbers(self, spanish_formatter):
        """Test Spanish code patterns with numbers."""
        test_cases = [
            ("array de tamaño diez", "Array de tamaño 10"),
            ("puerto tres mil", "Puerto 3000"),
            ("versión dos punto cinco", "Versión 2.5"),
            ("índice cero", "Índice 0"),
        ]

        for input_text, expected in test_cases:
            result = spanish_formatter.format_transcription(input_text)
            assert result == expected, f"Input '{input_text}' should format to '{expected}', got '{result}'"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
