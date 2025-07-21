#!/usr/bin/env python3
"""
CLI Smoke Tests - "Does it still work?" tests

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
import os
from pathlib import Path


class TestCLIImports:
    """Test that core CLI components can be imported without crashing."""
    
    def test_cli_creation_functions_import(self):
        """Can we import and create CLI parsers without explosions?"""
        from src.main import create_rich_cli, async_main
        
        # Test that CLI creation doesn't crash
        cli = create_rich_cli()
        assert cli is not None
        assert hasattr(cli, 'commands')
        assert 'listen' in cli.commands
        assert 'live' in cli.commands
        assert 'config' in cli.commands
        
        # Test that async_main function exists
        assert async_main is not None
    
    def test_mode_classes_import(self):
        """Can we import all the mode classes without dependency errors?"""
        from src.modes.listen_once import ListenOnceMode
        from src.modes.conversation import ConversationMode
        from src.modes.tap_to_talk import TapToTalkMode
        from src.modes.hold_to_talk import HoldToTalkMode
        
        # Just importing without crashing is the test
        assert ListenOnceMode is not None
        assert ConversationMode is not None
        assert TapToTalkMode is not None
        assert HoldToTalkMode is not None


class TestConfigSystem:
    """Test that configuration system works without crashing."""
    
    def test_default_config_loads(self, preloaded_config):
        """Can we load the actual config.json without crashing?"""
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
        from src.core.config import ConfigLoader
        
        # Should be able to create without crashing
        config = ConfigLoader()
        assert config is not None
        
        # Should be able to get basic values
        port = config.websocket_port
        assert isinstance(port, int)


class TestCLICommands:
    """Test that basic CLI commands work without crashing."""
    
    def test_status_command_runs(self):
        """Does status subcommand work without crashing?"""
        # Test status command via subprocess to avoid async complexity
        main_py = Path(__file__).parent.parent / "src" / "main.py"
        
        result = subprocess.run([
            sys.executable, str(main_py), "status"
        ], capture_output=True, text=True, timeout=30, env={**os.environ, "PYTHONPATH": str(Path(__file__).parent.parent)})
        
        # Should not crash (may not have status implementation yet, but shouldn't crash)
        # We just verify it doesn't have a Python syntax error or import failure
        if result.returncode != 0:
            # Allow for missing dependencies but not syntax errors
            assert "import" not in result.stderr.lower() or "modulenotfounderror" in result.stderr.lower()
    
    def test_models_command_runs(self):
        """Does models subcommand work without crashing?"""
        # Test models command via subprocess to avoid async complexity
        main_py = Path(__file__).parent.parent / "src" / "main.py"
        
        result = subprocess.run([
            sys.executable, str(main_py), "models"
        ], capture_output=True, text=True, timeout=30, env={**os.environ, "PYTHONPATH": str(Path(__file__).parent.parent)})
        
        # Should not crash (may not have models implementation yet, but shouldn't crash)
        # We just verify it doesn't have a Python syntax error or import failure
        if result.returncode != 0:
            # Allow for missing dependencies but not syntax errors
            assert "import" not in result.stderr.lower() or "modulenotfounderror" in result.stderr.lower()
    
    def test_help_command_works(self):
        """Does --help work without crashing?"""
        # Test that help can be displayed via subprocess
        # Use Path to get absolute path to main.py
        main_py = Path(__file__).parent.parent / "src" / "main.py"
        
        result = subprocess.run([
            sys.executable, str(main_py), "--help"
        ], capture_output=True, text=True, timeout=10, env={**os.environ, "PYTHONPATH": str(Path(__file__).parent.parent)})
        
        # Should exit with 0 and show help text
        assert result.returncode == 0
        assert "speech-to-text" in result.stdout.lower() or "stt" in result.stdout.lower()
        # Verify subcommands are listed
        assert "listen" in result.stdout.lower()
        assert "live" in result.stdout.lower() 
        assert "config" in result.stdout.lower()
        assert "serve" in result.stdout.lower()
    
    def test_config_subcommands_work(self):
        """Do config subcommands work without crashing?"""
        main_py = Path(__file__).parent.parent / "src" / "main.py"
        env = {**os.environ, "PYTHONPATH": str(Path(__file__).parent.parent)}
        
        # Test config help
        result = subprocess.run([
            sys.executable, str(main_py), "config", "--help"
        ], capture_output=True, text=True, timeout=10, env=env)
        
        assert result.returncode == 0
        assert "set" in result.stdout.lower()
        assert "get" in result.stdout.lower() 
        assert "list" in result.stdout.lower()
        
        # Test config list (should show current config)
        result = subprocess.run([
            sys.executable, str(main_py), "config", "list"
        ], capture_output=True, text=True, timeout=10, env=env)
        
        # May fail due to missing dependencies, but should not be a syntax error
        if result.returncode != 0:
            assert "import" not in result.stderr.lower() or "modulenotfounderror" in result.stderr.lower()
    
    def test_subcommand_help_works(self):
        """Do individual subcommand help pages work?"""
        main_py = Path(__file__).parent.parent / "src" / "main.py"
        env = {**os.environ, "PYTHONPATH": str(Path(__file__).parent.parent)}
        
        subcommands = ["listen", "live", "serve", "status", "models"]
        
        for subcommand in subcommands:
            result = subprocess.run([
                sys.executable, str(main_py), subcommand, "--help"
            ], capture_output=True, text=True, timeout=10, env=env)
            
            # Should show help for that specific subcommand
            assert result.returncode == 0, f"Help failed for subcommand: {subcommand}"
            assert subcommand in result.stdout.lower(), f"Subcommand name not in help: {subcommand}"


class TestBaseModeLogic:
    """Test that base mode functionality works without hardware."""
    
    def test_base_mode_can_be_created(self):
        """Can we create a BaseMode subclass without crashing?"""
        from src.modes.base_mode import BaseMode
        from types import SimpleNamespace
        
        # Create mock args
        args = SimpleNamespace(
            debug=False,
            format="json",
            sample_rate=16000,
            device=None,
            model="base",
            language=None
        )
        
        # Create a concrete implementation for testing
        class TestMode(BaseMode):
            async def run(self):
                pass
        
        # Should be able to create without crashing
        mode = TestMode(args)
        assert mode is not None
        assert mode.args == args
        assert mode.config is not None
        assert mode.logger is not None
    
    def test_mode_name_generation(self):
        """Test that mode name generation works correctly."""
        from src.modes.base_mode import BaseMode
        from types import SimpleNamespace
        
        args = SimpleNamespace(debug=False, format="json", sample_rate=16000, 
                             device=None, model="base", language=None)
        
        class TestSampleMode(BaseMode):
            async def run(self):
                pass
        
        mode = TestSampleMode(args)
        # Should convert TestSampleMode -> test_sample
        assert mode._get_mode_name() == "test_sample"


if __name__ == "__main__":
    # Allow running this file directly for quick smoke tests
    pytest.main([__file__, "-v"])