"""Custom pytest configuration and formatters for beautiful test output."""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

import pytest
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

# CRITICAL: Set environment variable BEFORE any imports that might load models
os.environ["STT_DISABLE_PUNCTUATION"] = "1"

# Add the src directory to the path for all tests to find the stt module
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
# Add the root directory to find tests.tools
sys.path.insert(0, str(Path(__file__).parent.parent))

# Register plugins
pytest_plugins = ["tests.tools.diff_tracker", "tests.tools.summary_plugin", "tests.tools.pattern_coverage_plugin"]

# Disable excessive logging during tests for performance
logging.getLogger("stt.text_formatting").setLevel(logging.CRITICAL)
logging.getLogger("stt.text_formatting.formatter").setLevel(logging.CRITICAL)
logging.getLogger("stt.text_formatting.detectors").setLevel(logging.CRITICAL)
logging.getLogger("stt.text_formatting.nlp_provider").setLevel(logging.WARNING)  # Keep model loading messages
logging.getLogger("stt.core").setLevel(logging.CRITICAL)
logging.getLogger("stt.text_formatting.pattern_converter").setLevel(logging.CRITICAL)

# Also disable the root logger for these modules to catch all sub-loggers
for logger_name in [
    "stt.text_formatting.formatter",
    "stt.text_formatting.detectors",
    "stt.text_formatting.pattern_converter",
]:
    logging.getLogger(logger_name).disabled = True

console = Console()


class FormatterTestReporter:
    """Custom reporter for text formatting tests with beautiful output."""

    def __init__(self):
        self.failures: list[tuple[str, str, str, str]] = []
        self.passes = 0
        self.total = 0

    def record_result(self, test_name: str, input_text: str, expected: str, actual: str, passed: bool):
        """Record a test result."""
        self.total += 1
        if passed:
            self.passes += 1
        else:
            self.failures.append((test_name, input_text, expected, actual))

    def print_summary(self):
        """Print a beautiful summary of test results."""
        if not self.failures:
            console.print(
                Panel.fit(
                    f"[bold green]✨ All {self.total} tests passed! ✨[/bold green]",
                    title="Test Results",
                    border_style="green",
                )
            )
            return

        # Create a table for failures
        table = Table(title="Text Formatting Test Failures", show_header=True, header_style="bold magenta")
        table.add_column("Test", style="cyan", no_wrap=False)
        table.add_column("Input", style="yellow")
        table.add_column("Expected", style="green")
        table.add_column("Actual", style="red")

        for test_name, input_text, expected, actual in self.failures:
            # Highlight differences
            table.add_row(test_name.split("::")[-1], input_text, expected, actual)  # Just the test method name

        console.print(table)

        # Summary panel
        fail_count = len(self.failures)
        console.print(
            Panel.fit(
                f"[bold red]Failed:[/bold red] {fail_count} | [bold green]Passed:[/bold green] {self.passes} | [bold]Total:[/bold] {self.total}",
                title="Summary",
                border_style="red" if fail_count > 0 else "green",
            )
        )


# Global reporter instance
reporter = FormatterTestReporter()


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Hook to capture test results for our custom reporter."""
    outcome = yield
    report = outcome.get_result()

    if report.when == "call" and "text_formatting" in str(item.fspath):
        # First check for structured data from user_properties
        for prop_name, prop_value in item.user_properties:
            if prop_name == "formatting_test":
                reporter.record_result(
                    item.nodeid,
                    prop_value["input"],
                    prop_value["expected"],
                    prop_value["actual"],
                    report.outcome == "passed",
                )
                return  # Found structured data, we're done

        # Fallback to improved assertion message parsing for existing tests
        if hasattr(report, "longrepr") and report.longrepr:
            try:
                repr_str = str(report.longrepr)
                if "AssertionError" in repr_str and "should format to" in repr_str:
                    # Use regex to extract the formatted assertion message more reliably
                    import re

                    # Pattern to match: "Input 'X' should format to 'Y', got 'Z'"
                    pattern = r"Input '([^']*)' should format to '([^']*)', got '([^']*)'"
                    match = re.search(pattern, repr_str)
                    if match:
                        input_text = match.group(1)
                        expected = match.group(2)
                        actual = match.group(3)
                        reporter.record_result(item.nodeid, input_text, expected, actual, report.outcome == "passed")
            except Exception:
                # If regex parsing fails, skip this test for reporter
                pass


def pytest_sessionfinish(session, exitstatus):
    """Print our custom summary at the end of the test session."""
    if reporter.failures or reporter.total > 0:
        console.print("\n")
        reporter.print_summary()


# Custom assertion helper for text formatting tests
def assert_format(input_text: str, expected: str, actual: str, test_name: str = "", item=None):
    """Enhanced assertion with beautiful failure output."""
    if expected != actual:
        # Attach structured data to the test item for the reporter
        if item is not None:
            item.user_properties.append(
                ("formatting_test", {"input": input_text, "expected": expected, "actual": actual})
            )

        # Create a rich diff view (keep existing rich output for immediate feedback)
        console.print(
            Panel.fit(
                f"[bold]Input:[/bold] '{input_text}'\n"
                f"[bold green]Expected:[/bold green] '{expected}'\n"
                f"[bold red]Actual:[/bold red] '{actual}'",
                title=f"Assertion Failed: {test_name}",
                border_style="red",
            )
        )

        # Show character-by-character diff if needed
        if len(expected) < 50 and len(actual) < 50:
            diff_text = ""
            for _i, (e, a) in enumerate(zip(expected, actual)):
                if e != a:
                    diff_text += f"[red]{a}[/red]"
                else:
                    diff_text += a
            if len(actual) > len(expected):
                diff_text += f"[red]{actual[len(expected):]}[/red]"

            console.print(f"[bold]Diff:[/bold] {diff_text}")
    # Also attach data for passed tests (optional for logging)
    elif item is not None:
        item.user_properties.append(("formatting_test", {"input": input_text, "expected": expected, "actual": actual}))

    assert expected == actual, f"Input '{input_text}' should format to '{expected}' but got '{actual}'"


# Session-scoped fixtures for preloading heavy libraries
@pytest.fixture(scope="session")
def preloaded_nlp_models():
    """Preload NLP models once per test session to avoid repeated loading."""
    # Enable no-punctuation mode for testing FIRST
    import os

    os.environ["STT_DISABLE_PUNCTUATION"] = "1"

    try:
        from stt.text_formatting.nlp_provider import get_nlp, get_punctuator

        # Warm up both models
        nlp = get_nlp()
        punctuator = get_punctuator()

        return {"nlp": nlp, "punctuator": punctuator}
    except ImportError as e:
        return None


@pytest.fixture(scope="session")
def preloaded_formatter(preloaded_nlp_models):
    """Preload the formatter function with warmed-up NLP models and result caching."""
    # Enable no-punctuation mode for testing
    os.environ["STT_DISABLE_PUNCTUATION"] = "1"

    # Reset any cached models to ensure the environment variable takes effect
    from stt.text_formatting.nlp_provider import reset_models

    reset_models()

    try:
        from stt.text_formatting.formatter import format_transcription

        # Cache for formatter results during testing
        cache = {}

        def cached_format_transcription(text, key_name="", enter_pressed=False):
            """Cached version of format_transcription for test performance."""
            cache_key = (text, key_name, enter_pressed)
            if cache_key not in cache:
                cache[cache_key] = format_transcription(text, key_name, enter_pressed)
            return cache[cache_key]

        # Warm up the formatter with a test call to ensure models are loaded
        test_result = cached_format_transcription("test warmup")

        yield cached_format_transcription

        # Clean up environment variable after tests
        if "STT_DISABLE_PUNCTUATION" in os.environ:
            del os.environ["STT_DISABLE_PUNCTUATION"]

    except ImportError as e:
        yield None


@pytest.fixture
def raw_formatter():
    """
    Provides a TextFormatter instance with AI punctuation and smart
    capitalization disabled for predictable unit testing of entity conversion.
    """
    import os

    from stt.text_formatting.formatter import TextFormatter

    # Set environment variable to disable punctuation
    old_env = os.environ.get("STT_DISABLE_PUNCTUATION")
    os.environ["STT_DISABLE_PUNCTUATION"] = "1"

    try:
        # 1. Create a formatter instance (it can be any language, we'll override it in tests)
        formatter = TextFormatter(language="en")

        # 2. Define a mock capitalizer that does nothing.
        class NoopCapitalizer:
            def capitalize(self, text: str, entities: list | None = None, doc=None) -> str:
                return text

        # 3. Replace the smart capitalizer on our test instance
        formatter.smart_capitalizer = NoopCapitalizer()

        # 4. Yield the formatter's main method for tests to use.
        yield formatter.format_transcription
    finally:
        # Clean up environment variable
        if old_env is None:
            if "STT_DISABLE_PUNCTUATION" in os.environ:
                del os.environ["STT_DISABLE_PUNCTUATION"]
        else:
            os.environ["STT_DISABLE_PUNCTUATION"] = old_env


@pytest.fixture(scope="session")
def preloaded_config():
    """Preload config once per test session."""
    try:
        from stt.core.config import get_config

        config = get_config()
        return config
    except ImportError as e:
        return None


@pytest.fixture(scope="session")
def preloaded_test_audio():
    """Preload common audio test data once per test session."""
    try:
        import numpy as np

        # Common test audio patterns
        sample_rate = 16000
        duration = 1.0

        # 440Hz sine wave (A4 note - common test frequency)
        t = np.linspace(0, duration, int(sample_rate * duration))
        sine_440 = np.sin(2 * np.pi * 440.0 * t)
        sine_440_int16 = (sine_440 * 32767).astype(np.int16)

        # Speech-like varying frequency (200-300Hz)
        speech_like = np.sin(2 * np.pi * (200 + 100 * np.sin(2 * np.pi * 0.5 * t)) * t)
        speech_like_int16 = (speech_like * 16384).astype(np.int16)

        # Silence
        silence = np.zeros(int(sample_rate * duration), dtype=np.int16)

        audio_data = {
            "sample_rate": sample_rate,
            "duration": duration,
            "sine_440": sine_440_int16,
            "speech_like": speech_like_int16,
            "silence": silence,
            "time_array": t,
        }

        return audio_data
    except ImportError as e:
        return None


@pytest.fixture(scope="session")
def preloaded_opus_codecs():
    """Preload Opus codecs once per test session."""
    try:
        from stt.audio.decoder import OpusDecoder, OpusStreamDecoder
        from stt.transcription.client import OpusEncoder

        sample_rate = 16000
        channels = 1

        # Create encoder and decoder instances
        encoder = OpusEncoder(sample_rate, channels)
        decoder = OpusDecoder(sample_rate, channels)
        stream_decoder = OpusStreamDecoder()

        codecs = {
            "encoder": encoder,
            "decoder": decoder,
            "stream_decoder": stream_decoder,
            "sample_rate": sample_rate,
            "channels": channels,
        }

        return codecs
    except ImportError as e:
        return None


@pytest.fixture
def spanish_formatter():
    """
    Provides a TextFormatter instance configured for Spanish language
    with punctuation disabled for predictable testing.
    """
    import os

    from stt.text_formatting.formatter import TextFormatter

    # Save the current value of the environment variable
    old_env = os.environ.get("STT_DISABLE_PUNCTUATION")

    # Set environment variable to disable punctuation
    os.environ["STT_DISABLE_PUNCTUATION"] = "1"

    try:
        # Create a formatter instance for Spanish
        formatter = TextFormatter(language="es")
        yield formatter
    finally:
        # Clean up environment variable
        if old_env is None:
            if "STT_DISABLE_PUNCTUATION" in os.environ:
                del os.environ["STT_DISABLE_PUNCTUATION"]
        else:
            os.environ["STT_DISABLE_PUNCTUATION"] = old_env


@pytest.fixture
def preloaded_formatter():
    """Provide preloaded text formatter for tests."""
    from stt.text_formatting.formatter import format_transcription

    return format_transcription


@pytest.fixture
def aec_processor():
    """Provide WebRTC AEC processor with dependency checking."""
    try:
        from examples.smart_voice_demo import WebRTCAECProcessor
        return WebRTCAECProcessor()
    except ImportError:
        pytest.skip("WebRTC AEC processor not available - missing demo dependencies")


@pytest.fixture
def tts_engine():
    """Provide TTS engine with graceful dependency checking."""
    try:
        from examples.smart_voice_demo import TTSCLIEngine
        
        # Create a mock class that bypasses TTS CLI verification for testing
        class MockTTSCLIEngine(TTSCLIEngine):
            def _verify_tts_available(self):
                """Override TTS CLI verification for testing."""
                import subprocess
                try:
                    result = subprocess.run(["tts", "status"], capture_output=True, text=True, timeout=5)
                    if result.returncode == 0:
                        self.logger.info("TTS CLI verified successfully")
                        return
                except (subprocess.TimeoutExpired, FileNotFoundError) as e:
                    # Instead of logging error, skip the test gracefully
                    pytest.skip(f"TTS CLI not available: {e}. Install TTS CLI or ensure it's in your PATH")
        
        return MockTTSCLIEngine()
        
    except ImportError:
        pytest.skip("TTS CLI engine not available - missing demo dependencies")


@pytest.fixture
def ttt_processor():
    """Provide TTT CLI processor with graceful dependency checking."""
    try:
        from examples.smart_voice_demo import TTTCLIProcessor
        
        # Create a mock class that bypasses TTT CLI verification for testing
        class MockTTTCLIProcessor(TTTCLIProcessor):
            def _verify_ttt_available(self):
                """Override TTT CLI verification for testing."""
                import subprocess
                try:
                    result = subprocess.run(["ttt", "status"], capture_output=True, text=True, timeout=5)
                    if result.returncode == 0:
                        self.logger.info("TTT CLI verified successfully")
                        return
                except (subprocess.TimeoutExpired, FileNotFoundError) as e:
                    # Instead of logging error, skip the test gracefully
                    pytest.skip(f"TTT CLI not available: {e}. Install TTT CLI or ensure it's in your PATH")
        
        return MockTTTCLIProcessor()
        
    except ImportError:
        pytest.skip("TTT CLI processor not available - missing demo dependencies")
