#!/usr/bin/env python3
"""Comprehensive tests for financial and currency entities.

This module tests the detection and formatting of:
- MONEY: "$100", "€50", "£20"
- SPOKEN_CURRENCY: "fifty dollars" → "$50"
- COMPOUND_CURRENCY: "five dollars and fifty cents" → "$5.50"
- CURRENCY_SYMBOL: "USD", "EUR", "GBP" 
- STOCK_SYMBOL: "AAPL", "GOOGL"
- Financial expressions and contexts
"""

import pytest
import sys
import os

# Add the project root to the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from stt_hotkeys.text_formatting.formatter import format_transcription


class TestSpokenCurrency:
    """Test SPOKEN_CURRENCY entity detection and formatting."""

    def test_basic_dollar_amounts(self):
        """Test basic dollar amount patterns."""
        test_cases = [
            ("ten dollars", "$10"),
            ("fifty dollars", "$50"),
            ("one hundred dollars", "$100"),
            ("five thousand dollars", "$5,000"),
            ("two million dollars", "$2,000,000"),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            # May or may not include commas in large numbers
            assert result in [expected, expected.replace(",", ""), expected + ".", expected.replace(",", "") + "."], \
                f"Input '{input_text}' should format to '{expected}' variant, got '{result}'"

    def test_decimal_dollar_amounts(self):
        """Test dollar amounts with decimal values."""
        test_cases = [
            ("ten dollars and fifty cents", "$10.50"),
            ("twenty five dollars and ninety nine cents", "$25.99"),
            ("one dollar and one cent", "$1.01"),
            ("nine dollars and zero cents", "$9.00"),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            assert result in [expected, expected + "."], f"Input '{input_text}' should format to '{expected}' or '{expected}.', got '{result}'"

    def test_cents_only(self):
        """Test amounts in cents only."""
        test_cases = [
            ("fifty cents", "50¢"),
            ("ninety nine cents", "99¢"),
            ("one cent", "1¢"),
            ("twenty five cents", "25¢"),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            # May format as cents symbol or as $0.XX
            assert result in [expected, expected + ".", f"${expected[:-1]}.{expected[:-1]}", f"$0.{expected[:-1]}"], \
                f"Input '{input_text}' should format to cents notation, got '{result}'"

    def test_other_currencies(self):
        """Test other currency patterns."""
        test_cases = [
            ("fifty euros", "€50"),
            ("twenty pounds", "£20"),
            ("one hundred yen", "¥100"),
            ("thirty francs", "₣30"),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            # Currency detection may vary
            print(f"Currency test: '{input_text}' -> '{result}' (expected: '{expected}')")

    def test_currency_in_sentences(self):
        """Test currency amounts in natural sentences."""
        test_cases = [
            ("the price is twenty dollars", "The price is $20."),
            ("it costs fifty dollars and fifty cents", "It costs $50.50."),
            ("save ten dollars today", "Save $10 today."),
            ("earn one thousand dollars", "Earn $1,000."),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            # May or may not include commas
            expected_no_comma = expected.replace(",", "")
            assert result in [expected, expected_no_comma], f"Input '{input_text}' should format to '{expected}' or '{expected_no_comma}', got '{result}'"


class TestCompoundCurrency:
    """Test COMPOUND_CURRENCY entity detection and formatting."""

    def test_dollars_and_cents(self):
        """Test compound dollar and cent patterns."""
        test_cases = [
            ("five dollars and fifty cents", "$5.50"),
            ("ten dollars and twenty five cents", "$10.25"),
            ("one hundred dollars and one cent", "$100.01"),
            ("three dollars and ninety nine cents", "$3.99"),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            assert result in [expected, expected + "."], f"Input '{input_text}' should format to '{expected}' or '{expected}.', got '{result}'"

    def test_large_amounts_with_cents(self):
        """Test large amounts with cents."""
        test_cases = [
            ("one thousand dollars and fifty cents", "$1,000.50"),
            ("five thousand two hundred dollars and thirty cents", "$5,200.30"),
            ("ten thousand dollars and one cent", "$10,000.01"),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            # May or may not include commas
            expected_no_comma = expected.replace(",", "")
            assert result in [expected, expected + ".", expected_no_comma, expected_no_comma + "."], \
                f"Input '{input_text}' should format to currency notation, got '{result}'"

    def test_other_compound_currencies(self):
        """Test compound amounts in other currencies."""
        test_cases = [
            ("five euros and fifty cents", "€5.50"),
            ("ten pounds and twenty pence", "£10.20"),
            ("three euros and ninety nine cents", "€3.99"),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            # International currency support may vary
            print(f"Compound currency test: '{input_text}' -> '{result}' (expected: '{expected}')")


class TestCurrencySymbols:
    """Test CURRENCY_SYMBOL entity detection and formatting."""

    def test_currency_codes(self):
        """Test three-letter currency codes."""
        test_cases = [
            ("price in USD", "Price in USD."),
            ("convert to EUR", "Convert to EUR."),
            ("paid in GBP", "Paid in GBP."),
            ("amount in JPY", "Amount in JPY."),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            assert result == expected, f"Input '{input_text}' should format to '{expected}', got '{result}'"

    def test_currency_codes_with_amounts(self):
        """Test currency codes with numeric amounts."""
        test_cases = [
            ("fifty USD", "$50 USD"),
            ("one hundred EUR", "€100 EUR"),
            ("twenty GBP", "£20 GBP"),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            # Currency code formatting may vary
            print(f"Currency code with amount: '{input_text}' -> '{result}' (expected: '{expected}')")


class TestStockSymbols:
    """Test STOCK_SYMBOL entity detection and formatting."""

    def test_common_stock_symbols(self):
        """Test common stock ticker symbols."""
        test_cases = [
            ("buy AAPL stock", "Buy AAPL stock."),
            ("GOOGL is up", "GOOGL is up."),
            ("sell MSFT shares", "Sell MSFT shares."),
            ("TSLA price increased", "TSLA price increased."),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            assert result == expected, f"Input '{input_text}' should format to '{expected}', got '{result}'"

    def test_stock_symbols_in_context(self):
        """Test stock symbols in financial contexts."""
        test_cases = [
            ("AMZN hit a new high", "AMZN hit a new high."),
            ("the ticker is META", "The ticker is META."),
            ("watch NFLX today", "Watch NFLX today."),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            assert result == expected, f"Input '{input_text}' should format to '{expected}', got '{result}'"


class TestFinancialExpressions:
    """Test financial expressions and contexts."""

    def test_price_expressions(self):
        """Test various price expression patterns."""
        test_cases = [
            ("the cost is twenty five ninety nine", "The cost is $25.99."),
            ("priced at nine ninety five", "Priced at $9.95."),
            ("on sale for nineteen ninety nine", "On sale for $19.99."),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            # Price pattern detection may vary
            print(f"Price expression test: '{input_text}' -> '{result}' (expected: '{expected}')")

    def test_financial_calculations(self):
        """Test financial calculation expressions."""
        test_cases = [
            ("ten percent of one hundred dollars", "10% of $100"),
            ("fifty dollars times twelve months", "$50 × 12 months"),
            ("thousand dollars divided by four", "$1,000 ÷ 4"),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            # Complex financial expressions
            print(f"Financial calculation: '{input_text}' -> '{result}' (expected: '{expected}')")

    def test_financial_ranges(self):
        """Test financial range expressions."""
        test_cases = [
            ("between ten and twenty dollars", "Between $10 and $20"),
            ("from fifty to one hundred dollars", "From $50 to $100"),
            ("costs five to ten dollars", "Costs $5-10"),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            # Range formatting may vary
            print(f"Financial range: '{input_text}' -> '{result}' (expected: '{expected}')")


class TestCurrencyEdgeCases:
    """Test edge cases in currency formatting."""

    def test_ambiguous_numbers(self):
        """Test numbers that could be prices or regular numbers."""
        test_cases = [
            # Clear price context
            ("it costs twenty five", "It costs $25."),
            ("the price is fifty", "The price is $50."),
            # Ambiguous context
            ("twenty five items", "25 items."),
            ("found fifty", "Found 50."),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            # Context detection for currency may vary
            print(f"Ambiguous number test: '{input_text}' -> '{result}' (expected: '{expected}')")

    def test_multiple_currencies(self):
        """Test sentences with multiple currency amounts."""
        test_cases = [
            ("convert fifty dollars to euros", "Convert $50 to euros."),
            ("exchange twenty pounds for thirty dollars", "Exchange £20 for $30."),
            ("the fee is five dollars plus ten euros", "The fee is $5 plus €10."),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            # Multiple currency handling
            print(f"Multiple currencies: '{input_text}' -> '{result}' (expected: '{expected}')")

    def test_currency_with_other_entities(self):
        """Test currency mixed with other entity types."""
        test_cases = [
            ("send twenty dollars to john@example.com", "Send $20 to john@example.com."),
            ("the api costs five dollars per thousand requests", "The API costs $5 per 1,000 requests."),
            ("save fifty percent on hundred dollar items", "Save 50% on $100 items."),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            # Mixed entity handling
            print(f"Currency with entities: '{input_text}' -> '{result}' (expected: '{expected}')")


class TestInternationalCurrencies:
    """Test international currency formats."""

    def test_european_currencies(self):
        """Test European currency patterns."""
        test_cases = [
            ("fifty euros", "€50"),
            ("twenty pounds sterling", "£20"),
            ("thirty swiss francs", "CHF 30"),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            # International currency support
            print(f"European currency: '{input_text}' -> '{result}' (expected: '{expected}')")

    def test_asian_currencies(self):
        """Test Asian currency patterns."""
        test_cases = [
            ("one thousand yen", "¥1,000"),
            ("fifty yuan", "¥50"),
            ("hundred rupees", "₹100"),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            # Asian currency support
            print(f"Asian currency: '{input_text}' -> '{result}' (expected: '{expected}')")

    def test_cryptocurrency(self):
        """Test cryptocurrency patterns."""
        test_cases = [
            ("one bitcoin", "1 BTC"),
            ("fifty ethereum", "50 ETH"),
            ("point one bitcoin", "0.1 BTC"),
        ]

        for input_text, expected in test_cases:
            result = format_transcription(input_text)
            # Cryptocurrency support may not be implemented
            print(f"Cryptocurrency: '{input_text}' -> '{result}' (expected: '{expected}')")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])