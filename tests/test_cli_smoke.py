#!/usr/bin/env python3
"""CLI Smoke Tests - "Does it still work?" tests

These tests detect when the app is fundamentally broken:
- Import errors
- Config file corruption
- Basic CLI functionality
- Startup crashes

NOT testing edge cases or complex logic - just "can the app start?"
"""

import pytest
import json
import io
import sys
import subprocess


class TestCLIImports:
    """Test that core CLI components can be imported without crashing."""

    def test_app_hooks_import(self):
        """Can we import app hooks without explosions?"""
        from matilda_ears.app_hooks import on_status, on_models, on_download

        # Test that hooks are callable
        assert callable(on_status)
        assert callable(on_models)
        assert callable(on_download)

    def test_mode_classes_import(self):
        """Can we import all the mode classes without dependency errors?"""
        from matilda_ears.modes.listen_once import ListenOnceMode
        from matilda_ears.modes.conversation import ConversationMode

        # Just importing without crashing is the test
        assert ListenOnceMode is not None
        assert ConversationMode is not None


class TestConfigSystem:
    """Test that configuration system works without crashing."""

    def test_default_config_loads(self, preloaded_config):
        """Can we load the actual config.toml without crashing?"""
        if preloaded_config is None:
            pytest.skip("Config not available")

        config = preloaded_config

        # Basic smoke test - these should not crash and return sensible values
        assert config.websocket_port > 0
        assert config.websocket_port < 65536
        assert len(config.whisper_model) > 0
        assert len(config.get_audio_tool()) > 0

    def test_config_loader_direct(self):
        """Test creating ConfigLoader directly doesn't crash."""
        from matilda_ears.core.config import ConfigLoader

        # Should be able to create without crashing
        config = ConfigLoader()
        assert config is not None

        # Should be able to get basic values
        port = config.websocket_port
        assert isinstance(port, int)

    def test_matilda_locale_overrides_tuner_locale(self, monkeypatch):
        """MATILDA_LOCALE should override Ears Tuner formatting locale."""
        from matilda_ears.core.config import ConfigLoader

        monkeypatch.setenv("MATILDA_LOCALE", "en-GB")
        config = ConfigLoader()
        assert config.get("ears_tuner.locale") == "en-GB"
        assert config.get("ears_tuner.formatting.locale") == "en-GB"


class TestCLICommands:
    """Test that basic CLI commands work without crashing."""

    def test_status_command_runs(self):
        """Does status command work without crashing?"""
        from matilda_ears.app_hooks import on_status

        # Capture output
        old_stdout = sys.stdout
        sys.stdout = captured_output = io.StringIO()

        try:
            on_status(json=True)
            output = captured_output.getvalue()

            # Basic smoke test - did it produce valid JSON?
            result = json.loads(output)
            assert "backend" in result
            assert "model" in result

        finally:
            sys.stdout = old_stdout

    def test_models_command_runs(self):
        """Does models command work without crashing?"""
        from matilda_ears.app_hooks import on_models

        # Capture output
        old_stdout = sys.stdout
        sys.stdout = captured_output = io.StringIO()

        try:
            on_models(json=True)
            output = captured_output.getvalue()

            # Basic smoke test - did it produce valid JSON?
            result = json.loads(output)
            assert len(result) > 0

        finally:
            sys.stdout = old_stdout

    def test_help_command_works(self):
        """Does --help work without crashing?"""
        # Test via the ears command entry point
        result = subprocess.run(
            [sys.executable, "-m", "matilda_ears.cli", "--help"],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )

        # Should exit with 0 and show help text
        assert result.returncode == 0
        assert "speech" in result.stdout.lower() or "transcri" in result.stdout.lower()


class TestBaseModeLogic:
    """Test that base mode functionality works without hardware."""

    def test_base_mode_can_be_created(self):
        """Can we create a BaseMode subclass without crashing?"""
        from matilda_ears.modes.base_mode import BaseMode
        from matilda_ears.core.mode_config import ModeConfig

        mode_config = ModeConfig(
            debug=False,
            format="json",
            sample_rate=16000,
            device=None,
            model="base",
            language="en",
        )

        # Create a concrete implementation for testing
        class TestMode(BaseMode):
            async def run(self):
                pass

        # Should be able to create without crashing
        mode = TestMode(mode_config)
        assert mode is not None
        assert mode.mode_config == mode_config
        assert mode.config is not None
        assert mode.logger is not None

    def test_mode_name_generation(self):
        """Test that mode name generation works correctly."""
        from matilda_ears.modes.base_mode import BaseMode
        from matilda_ears.core.mode_config import ModeConfig

        mode_config = ModeConfig(
            debug=False,
            format="json",
            sample_rate=16000,
            device=None,
            model="base",
            language="en",
        )

        class TestSampleMode(BaseMode):
            async def run(self):
                pass

        mode = TestSampleMode(mode_config)
        # Should convert TestSampleMode -> test_sample
        assert mode._get_mode_name() == "test_sample"


if __name__ == "__main__":
    # Allow running this file directly for quick smoke tests
    pytest.main([__file__, "-v"])
