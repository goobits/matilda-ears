#!/usr/bin/env python3
"""
App hooks for STT CLI - provides implementation for all STT commands
This file connects the generated CLI to the actual STT functionality
"""

import asyncio
import sys
from typing import Optional

# Import STT functionality
# Note: Import modes only when needed to avoid side effects


def on_listen(
    device: Optional[str],
    language: Optional[str],
    model: str,
    hold_to_talk: Optional[str],
    json: bool,
    debug: bool,
    config: Optional[str],
    no_formatting: bool,
    sample_rate: int,
    **kwargs,
) -> int:
    """Handle the listen command - record once and transcribe"""
    try:
        # Use hold-to-talk mode if key specified, otherwise listen-once
        if hold_to_talk:
            from goobits_stt.modes.hold_to_talk import HoldToTalkMode
            mode = HoldToTalkMode(
                model_size=model,
                language=language,
                device_name=device,
                hold_key=hold_to_talk,
                sample_rate=sample_rate,
                disable_formatting=no_formatting,
                json_output=json,
                debug=debug,
                config_path=config,
            )
        else:
            from goobits_stt.modes.listen_once import ListenOnceMode
            mode = ListenOnceMode(
                model_size=model,
                language=language,
                device_name=device,
                sample_rate=sample_rate,
                disable_formatting=no_formatting,
                json_output=json,
                debug=debug,
                config_path=config,
            )
        
        # Run the mode
        asyncio.run(mode.run())
        return 0
    except KeyboardInterrupt:
        return 0
    except Exception as e:
        if debug:
            import traceback
            traceback.print_exc()
        else:
            print(f"Error: {e}", file=sys.stderr)
        return 1


def on_live(
    device: Optional[str],
    language: Optional[str],
    model: str,
    tap_to_talk: Optional[str],
    json: bool,
    debug: bool,
    config: Optional[str],
    no_formatting: bool,
    sample_rate: int,
    **kwargs,
) -> int:
    """Handle the live command - continuous conversation mode"""
    try:
        # Use tap-to-talk mode if key specified, otherwise conversation mode
        if tap_to_talk:
            from goobits_stt.modes.tap_to_talk import TapToTalkMode
            mode = TapToTalkMode(
                model_size=model,
                language=language,
                device_name=device,
                tap_key=tap_to_talk,
                sample_rate=sample_rate,
                disable_formatting=no_formatting,
                json_output=json,
                debug=debug,
                config_path=config,
            )
        else:
            from goobits_stt.modes.conversation import ConversationMode
            mode = ConversationMode(
                model_size=model,
                language=language,
                device_name=device,
                sample_rate=sample_rate,
                disable_formatting=no_formatting,
                json_output=json,
                debug=debug,
                config_path=config,
            )
        
        # Run the mode
        asyncio.run(mode.run())
        return 0
    except KeyboardInterrupt:
        return 0
    except Exception as e:
        if debug:
            import traceback
            traceback.print_exc()
        else:
            print(f"Error: {e}", file=sys.stderr)
        return 1


def on_serve(
    port: int,
    host: str,
    debug: bool,
    config: Optional[str],
    **kwargs,
) -> int:
    """Handle the serve command - start transcription server"""
    try:
        # Create and run server
        from goobits_stt.transcription.server import WebSocketServer
        server = WebSocketServer(
            host=host,
            port=port,
            debug=debug,
            config_path=config,
        )
        
        print(f"Starting STT server on {host}:{port}")
        server.run()
        return 0
    except KeyboardInterrupt:
        return 0
    except Exception as e:
        if debug:
            import traceback
            traceback.print_exc()
        else:
            print(f"Error: {e}", file=sys.stderr)
        return 1


def on_status(**kwargs) -> int:
    """Show system status and capabilities"""
    import sys
    import os
    
    try:
        # Add parent directory to path for imports
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        
        print("🎤 STT System Status")
        print("=" * 40)
        
        # Check CUDA availability
        try:
            import torch
            cuda_available = torch.cuda.is_available()
            print(f"CUDA Available: {'✅ Yes' if cuda_available else '❌ No'}")
            if cuda_available:
                print(f"CUDA Device: {torch.cuda.get_device_name(0)}")
        except ImportError:
            print("CUDA Available: ⚠️  PyTorch not installed")
        
        # Check audio devices
        try:
            import pyaudio
            p = pyaudio.PyAudio()
            device_count = p.get_device_count()
            print(f"Audio Devices: {device_count} found")
            p.terminate()
        except Exception as e:
            print(f"Audio Devices: ⚠️  Error checking: {e}")
        
        # Load config to show current settings
        try:
            from goobits_stt.core.config import Config
            config = Config()
        except ImportError:
            # Use simple defaults if config module not available
            config = {'model_size': 'base', 'language': 'en', 'sample_rate': 16000}
        print(f"\nCurrent Configuration:")
        print(f"  Model: {config.get('model_size', 'base')}")
        print(f"  Language: {config.get('language', 'en')}")
        print(f"  Sample Rate: {config.get('sample_rate', 16000)}")
        
        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def on_models(**kwargs) -> int:
    """List available Whisper models"""
    print("📦 Available Whisper Models")
    print("=" * 40)
    
    models = [
        ("tiny", "39M", "~1GB", "Fastest, lowest accuracy"),
        ("base", "74M", "~1GB", "Good balance (default)"),
        ("small", "244M", "~2GB", "Better accuracy"),
        ("medium", "769M", "~5GB", "High accuracy"),
        ("large", "1550M", "~10GB", "Best accuracy, slowest"),
    ]
    
    print(f"{'Model':<10} {'Parameters':<12} {'VRAM':<8} {'Description'}")
    print("-" * 50)
    for model, params, vram, desc in models:
        print(f"{model:<10} {params:<12} {vram:<8} {desc}")
    
    print("\nNote: Larger models require more VRAM and are slower but more accurate.")
    return 0


def on_config_show(json: bool = False, **kwargs) -> int:
    """Show all configuration settings"""
    try:
        from goobits_stt.core.config import Config
        config = Config()
        
        if json:
            import json as j
            # Filter out secrets
            safe_config = {k: v for k, v in config.config.items() if k not in ['jwt_secret']}
            print(j.dumps(safe_config, indent=2))
        else:
            print("🔧 Current Configuration")
            print("=" * 40)
            for k, v in config.config.items():
                if k not in ['jwt_secret']:  # Don't show secrets
                    print(f"  {k}: {v}")
        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def on_config_get(key: str, **kwargs) -> int:
    """Get specific configuration value"""
    try:
        from goobits_stt.core.config import Config
        config = Config()
        value = config.get(key)
        print(f"{key}: {value}")
        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def on_config_set(key: str, value: str, **kwargs) -> int:
    """Set configuration value"""
    try:
        from goobits_stt.core.config import Config
        config = Config()
        config.set(key, value)
        config.save()
        print(f"✅ Set {key} = {value}")
        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1