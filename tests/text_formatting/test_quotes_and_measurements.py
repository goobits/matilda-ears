#!/usr/bin/env python3
"""Test cases for proper quote formatting and measurement conversions."""

import pytest


class TestQuoteFormatting:
    """Test proper smart quote conversion."""

    def test_double_quotes(self, preloaded_formatter):
        """Test double quote conversion to curly quotes."""
        format_transcription = preloaded_formatter
        assert format_transcription('he said "hello"') == 'He said "hello"'
        assert format_transcription('the book "war and peace" is long') == 'The book "war and peace" is long'
        assert format_transcription('she said "I am tired"') == 'She said: "I am tired"'

    def test_single_quotes(self, preloaded_formatter):
        """Test single quote conversion to curly quotes."""
        format_transcription = preloaded_formatter
        assert format_transcription("he said 'hello'") == "He said 'hello'"
        assert format_transcription("the word 'cat' has three letters") == "The word 'cat' has 3 letters"

    def test_apostrophes_preserved(self, preloaded_formatter):
        """Test that apostrophes in contractions remain curly."""
        format_transcription = preloaded_formatter
        assert format_transcription("it's raining") == "It's raining"
        assert format_transcription("the dog's bone") == "The dog's bone"
        assert format_transcription("I can't go") == "I can't go"
        assert format_transcription("they're here") == "They're here"

    def test_nested_quotes(self, preloaded_formatter):
        """Test nested quote handling."""
        format_transcription = preloaded_formatter
        assert format_transcription("he said \"she told me 'hello'\"") == "He said: \"she told me 'hello'\""

    def test_quotes_with_punctuation(self, preloaded_formatter):
        """Test quotes with adjacent punctuation."""
        format_transcription = preloaded_formatter
        assert format_transcription('did he say "hello"?') == 'Did he say "hello"?'


class TestMeasurementConversion:
    """Test measurement to proper symbol conversion."""

    def test_feet_conversion(self, preloaded_formatter):
        """Test feet measurements get prime symbol."""
        format_transcription = preloaded_formatter
        assert format_transcription("six feet") == "6′"
        assert format_transcription("the board is eight feet long") == "The board is 8′ long"
        assert format_transcription("twelve feet") == "12′"

    def test_inches_conversion(self, preloaded_formatter):
        """Test inches measurements get double prime symbol."""
        format_transcription = preloaded_formatter
        assert format_transcription("twelve inches") == "12″"
        assert format_transcription("four inches wide") == "4″ wide"

    def test_height_measurements(self, preloaded_formatter):
        """Test height format like 5'10"."""
        format_transcription = preloaded_formatter
        assert format_transcription("five foot ten") == "5′10″"
        assert format_transcription("six foot two") == "6′2″"
        assert format_transcription("five foot ten inches") == "5′10″"

    def test_fractional_measurements(self, preloaded_formatter):
        """Test measurements with fractions."""
        format_transcription = preloaded_formatter
        assert format_transcription("three and a half feet") == "3.5′"
        assert format_transcription("two and a half inches") == "2.5″"

    def test_measurements_vs_possessives(self, preloaded_formatter):
        """Test that measurements don't interfere with possessives."""
        format_transcription = preloaded_formatter
        assert format_transcription("John's height is six feet") == "John's height is 6′"
        assert format_transcription("the tree's height") == "The tree's height"


class TestTemperatureConversion:
    """Test temperature entity detection and formatting."""

    def test_celsius_temperatures(self, preloaded_formatter):
        """Test Celsius temperature formatting."""
        format_transcription = preloaded_formatter
        assert format_transcription("twenty degrees celsius") == "20°C"
        assert format_transcription("it is thirty degrees celsius outside") == "It is 30°C outside"
        assert format_transcription("water boils at one hundred degrees celsius") == "Water boils at 100°C"
        assert format_transcription("negative ten degrees celsius") == "-10°C"
        assert format_transcription("minus five degrees celsius") == "-5°C"

    def test_fahrenheit_temperatures(self, preloaded_formatter):
        """Test Fahrenheit temperature formatting."""
        format_transcription = preloaded_formatter
        assert format_transcription("ninety eight point six degrees fahrenheit") == "98.6°F"
        assert format_transcription("set oven to four hundred degrees fahrenheit") == "Set oven to 400°F"
        assert format_transcription("thirty two degrees fahrenheit") == "32°F"
        assert format_transcription("negative forty degrees fahrenheit") == "-40°F"

    def test_generic_degrees(self, preloaded_formatter):
        """Test generic degree formatting without scale."""
        format_transcription = preloaded_formatter
        assert format_transcription("rotate ninety degrees") == "Rotate 90°"
        assert format_transcription("turn it forty five degrees") == "Turn it 45°"
        assert format_transcription("a one eighty degree turn") == "A 180° turn"

    def test_temperature_in_context(self, preloaded_formatter):
        """Test temperature formatting in various contexts."""
        format_transcription = preloaded_formatter
        assert format_transcription("the temperature is twenty five degrees celsius") == "The temperature is 25°C"
        assert format_transcription("it dropped to zero degrees celsius") == "It dropped to 0°C"
        assert format_transcription("bake at three fifty degrees fahrenheit") == "Bake at 350°F"


class TestMetricUnits:
    """Test metric unit detection and formatting."""

    def test_metric_length_units(self, preloaded_formatter):
        """Test metric length measurements."""
        format_transcription = preloaded_formatter
        assert format_transcription("five kilometers") == "5 km"
        assert format_transcription("ten meters") == "10 m"
        assert format_transcription("twenty centimeters") == "20 cm"
        assert format_transcription("fifty millimeters") == "50 mm"
        assert format_transcription("the distance is three point five kilometers") == "The distance is 3.5 km"

    def test_metric_weight_units(self, preloaded_formatter):
        """Test metric weight measurements."""
        format_transcription = preloaded_formatter
        assert format_transcription("two kilograms") == "2 kg"
        assert format_transcription("five hundred grams") == "500 g"
        assert format_transcription("it weighs ten kilograms") == "It weighs 10 kg"
        assert format_transcription("add two hundred fifty grams of flour") == "Add 250 g of flour"

    def test_metric_volume_units(self, preloaded_formatter):
        """Test metric volume measurements."""
        format_transcription = preloaded_formatter
        assert format_transcription("one liter") == "1 L"
        assert format_transcription("five hundred milliliters") == "500 mL"
        assert format_transcription("two liters of water") == "2 L of water"
        assert format_transcription("measure one hundred milliliters") == "Measure 100 mL"

    def test_metric_with_fractions(self, preloaded_formatter):
        """Test metric units with fractional values."""
        format_transcription = preloaded_formatter
        assert format_transcription("one and a half kilometers") == "1.5 km"
        assert format_transcription("two and a quarter kilograms") == "2.25 kg"
        assert format_transcription("three and three quarters liters") == "3.75 L"


class TestImperialUnits:
    """Test imperial unit detection and formatting."""

    def test_imperial_distance_units(self, preloaded_formatter):
        """Test imperial distance measurements."""
        format_transcription = preloaded_formatter
        assert format_transcription("five miles") == "5 mi"
        assert format_transcription("ten yards") == "10 yd"
        assert format_transcription("drive twenty miles") == "Drive 20 mi"
        assert format_transcription("the field is one hundred yards long") == "The field is 100 yd long"

    def test_imperial_weight_units(self, preloaded_formatter):
        """Test imperial weight measurements."""
        format_transcription = preloaded_formatter
        assert format_transcription("fifty pounds") == "50 lbs"
        assert format_transcription("ten ounces") == "10 oz"
        assert format_transcription("it weighs twenty pounds") == "It weighs 20 lbs"
        assert format_transcription("add eight ounces of cheese") == "Add 8 oz of cheese"

    def test_imperial_volume_units(self, preloaded_formatter):
        """Test imperial volume measurements."""
        format_transcription = preloaded_formatter
        assert format_transcription("two gallons") == "2 gal"
        assert format_transcription("four quarts") == "4 qt"
        assert format_transcription("one pint") == "1 pt"
        assert format_transcription("eight fluid ounces") == "8 fl oz"


class TestMeasurementEdgeCases:
    """Test edge cases for measurement formatting."""

    def test_measurements_with_spoken_numbers(self, preloaded_formatter):
        """Test measurements with various spoken number formats."""
        format_transcription = preloaded_formatter
        assert format_transcription("twenty five point five degrees celsius") == "25.5°C"
        assert format_transcription("one thousand meters") == "1000 m"
        assert format_transcription("two thousand five hundred kilometers") == "2500 km"
        assert format_transcription("one hundred twenty degrees fahrenheit") == "120°F"

    def test_measurements_in_lists(self, preloaded_formatter):
        """Test multiple measurements in lists."""
        format_transcription = preloaded_formatter
        result = format_transcription("add five grams ten grams and fifteen grams")
        # Should handle measurements in a list context
        assert "5 g" in result and "10 g" in result and "15 g" in result

    def test_measurements_vs_regular_numbers(self, preloaded_formatter):
        """Test that measurements take priority over plain numbers."""
        format_transcription = preloaded_formatter
        assert format_transcription("the temperature is twenty degrees") == "The temperature is 20°"
        assert format_transcription("it weighs fifty kilograms") == "It weighs 50 kg"
        assert format_transcription("drive ten miles") == "Drive 10 mi"

    def test_fraction_formatting_in_context(self, preloaded_formatter):
        """Test fraction formatting in descriptive text."""
        format_transcription = preloaded_formatter
        assert format_transcription("set delay from half a second to one tenth of a second") == "Set delay from ½ a second to ⅒ of a second"


class TestEdgeCases:
    """Test edge cases combining quotes and measurements."""

    def test_quotes_with_measurements(self, preloaded_formatter):
        """Test quotes containing measurements."""
        format_transcription = preloaded_formatter
        assert format_transcription('he said "I am six feet tall"') == 'He said: "I am 6′ tall"'
        assert (
            format_transcription('the sign reads "maximum height twelve feet"')
            == 'The sign reads: "maximum height: 12′"'
        )

    def test_technical_content_with_quotes(self, preloaded_formatter):
        """Test technical content doesn't get wrong quotes."""
        format_transcription = preloaded_formatter
        # URLs should remain standalone
        assert format_transcription("example dot com") == "example.com"
        # But URLs in sentences get quotes
        assert format_transcription('visit "example dot com" today') == 'Visit "example.com" today'

    def test_measurements_as_standalone(self, preloaded_formatter):
        """Test standalone measurements."""
        format_transcription = preloaded_formatter
        # Standalone measurements should not get extra punctuation
        assert format_transcription("six feet") == "6′"
        # But measurements in sentences should work normally
        assert format_transcription("the height is six feet exactly") == "The height is 6′ exactly"

    def test_mixed_quote_types(self, preloaded_formatter):
        """Test mixing straight and curly quotes doesn't break."""
        format_transcription = preloaded_formatter
        # Even if input has mixed quotes, output should be consistent
        text = "he said \"hello\" and she said 'goodbye'"
        result = format_transcription(text)
        assert '"' in result  # Should have left double quote
        assert '"' in result  # Should have right double quote
        # Note: The punctuation model already handles apostrophes/single quotes
        assert "goodbye" in result  # Content should be preserved

    def test_temperature_with_quotes(self, preloaded_formatter):
        """Test temperatures in quoted text."""
        format_transcription = preloaded_formatter
        assert format_transcription('the forecast says "twenty degrees celsius"') == 'The forecast says: "20°C"'
        assert format_transcription('"it is minus ten degrees fahrenheit" he said') == '"It is -10°F," he said'

    def test_metric_units_with_quotes(self, preloaded_formatter):
        """Test metric units in quoted text."""
        format_transcription = preloaded_formatter
        assert (
            format_transcription('the sign says "maximum load fifty kilograms"')
            == 'The sign says: "maximum load: 50 kg"'
        )
        assert format_transcription('"add two hundred milliliters" the recipe says') == '"Add 200 mL," the recipe says'


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
