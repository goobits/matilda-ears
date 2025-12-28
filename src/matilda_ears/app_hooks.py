#!/usr/bin/env python3
"""App hooks for Matilda Ears CLI - provides implementation for all STT commands.

This module contains the hook functions called by the generated CLI.
Each hook corresponds to a command defined in goobits.yaml.
"""

import asyncio
import json as json_module
import os
import sys
from types import SimpleNamespace

# Check for Rich availability
try:
    from rich.console import Console
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False


def get_console():
    """Get Rich console if available."""
    return Console() if RICH_AVAILABLE else None


# =============================================================================
# Mode Runners
# =============================================================================

async def run_listen_once(args):
    """Run single utterance capture mode."""
    try:
        from matilda_ears.modes.listen_once import ListenOnceMode
        mode = ListenOnceMode(args)
        await mode.run()
    except ImportError as e:
        error_msg = f"Listen-once mode not available: {e}"
        if args.format == "json":
            print(json_module.dumps({"error": error_msg, "mode": "listen_once"}))
        else:
            print(f"Error: {error_msg}", file=sys.stderr)
        raise
    except Exception as e:
        error_result = {
            "error": str(e),
            "status": "failed",
            "mode": "listen_once"
        }
        if args.format == "json":
            print(json_module.dumps(error_result))
        else:
            print(f"Error: {e}", file=sys.stderr)
        raise


async def run_conversation(args):
    """Run continuous conversation mode."""
    try:
        from matilda_ears.modes.conversation import ConversationMode
        mode = ConversationMode(args)
        await mode.run()
    except ImportError as e:
        error_msg = f"Conversation mode not available: {e}"
        if args.format == "json":
            print(json_module.dumps({"error": error_msg, "mode": "conversation"}))
        else:
            print(f"Error: {error_msg}", file=sys.stderr)


async def run_tap_to_talk(args):
    """Run tap-to-talk mode."""
    try:
        from matilda_ears.modes.tap_to_talk import TapToTalkMode
        mode = TapToTalkMode(args)
        await mode.run()
    except ImportError as e:
        error_msg = f"Tap-to-talk mode not available: {e}"
        if args.format == "json":
            print(json_module.dumps({"error": error_msg, "mode": "tap_to_talk", "key": args.tap_to_talk}))
        else:
            print(f"Error: {error_msg}", file=sys.stderr)


async def run_hold_to_talk(args):
    """Run hold-to-talk mode."""
    try:
        from matilda_ears.modes.hold_to_talk import HoldToTalkMode
        mode = HoldToTalkMode(args)
        await mode.run()
    except ImportError as e:
        error_msg = f"Hold-to-talk mode not available: {e}"
        if args.format == "json":
            print(json_module.dumps({"error": error_msg, "mode": "hold_to_talk", "key": args.hold_to_talk}))
        else:
            print(f"Error: {error_msg}", file=sys.stderr)


async def run_file_transcription(args):
    """Run file transcription mode."""
    try:
        from matilda_ears.modes.file_transcribe import FileTranscribeMode
        mode = FileTranscribeMode(args)
        await mode.run()
    except ImportError as e:
        error_msg = f"File transcription mode not available: {e}"
        if args.format == "json":
            print(json_module.dumps({"error": error_msg, "mode": "file", "file": args.file}))
        else:
            print(f"Error: {error_msg}", file=sys.stderr)
    except Exception as e:
        error_msg = f"File transcription failed: {e}"
        if args.format == "json":
            print(json_module.dumps({"error": error_msg, "mode": "file", "file": args.file}))
        else:
            print(f"Error: {error_msg}", file=sys.stderr)


async def run_server(args):
    """Run WebSocket server mode."""
    try:
        # Allow CLI server startup without requiring server.py wrapper.
        os.environ.setdefault("MATILDA_MANAGEMENT_TOKEN", "managed-by-matilda-system")
        from matilda_ears.transcription.server import MatildaWebSocketServer

        # Create and start server
        server = MatildaWebSocketServer()
        await server.start_server(host=args.host, port=args.port)

    except ImportError as e:
        error_msg = f"Server mode not available: {e}"
        if args.format == "json":
            print(json_module.dumps({"error": error_msg, "mode": "server", "host": args.host, "port": args.port}))
        else:
            print(f"Error: {error_msg}", file=sys.stderr)
    except Exception as e:
        error_msg = f"Server failed to start: {e}"
        if args.format == "json":
            print(json_module.dumps({"error": error_msg, "mode": "server", "host": args.host, "port": args.port}))
        else:
            print(f"Error: {error_msg}", file=sys.stderr)


async def async_worker(args):
    """Async worker for STT operations."""
    try:
        if args.listen_once:
            await run_listen_once(args)
        elif args.conversation:
            await run_conversation(args)
        elif args.tap_to_talk and args.hold_to_talk:
            # Combined mode
            print(json_module.dumps({
                "mode": "combined",
                "tap_key": args.tap_to_talk,
                "hold_key": args.hold_to_talk,
                "message": "Combined mode not yet implemented"
            }))
        elif args.tap_to_talk:
            await run_tap_to_talk(args)
        elif args.hold_to_talk:
            await run_hold_to_talk(args)
        elif args.file:
            await run_file_transcription(args)
        elif args.server:
            await run_server(args)
    except KeyboardInterrupt:
        if args.format == "json":
            print(json_module.dumps({"status": "interrupted", "message": "User cancelled"}))
        sys.exit(0)
    except Exception as e:
        if args.format == "json":
            print(json_module.dumps({"error": str(e), "status": "failed"}))
        else:
            print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


# =============================================================================
# CLI Hooks
# =============================================================================

def on_transcribe(
    listen_once=False,
    conversation=False,
    tap_to_talk=None,
    hold_to_talk=None,
    file=None,
    server=False,
    port=8769,
    host="0.0.0.0",
    json_output=False,
    debug=False,
    no_formatting=False,
    model="base",
    language=None,
    device=None,
    sample_rate=16000,
    config=None,
):
    """Main transcription hook - handles all operation modes."""
    # Ensure stdout is unbuffered for piping
    sys.stdout.reconfigure(line_buffering=True)

    # Build args namespace
    args = SimpleNamespace(
        listen_once=listen_once,
        conversation=conversation,
        tap_to_talk=tap_to_talk,
        hold_to_talk=hold_to_talk,
        file=file,
        server=server,
        port=port,
        host=host,
        format="json" if json_output else "text",
        json=json_output,
        debug=debug,
        no_formatting=no_formatting,
        model=model,
        language=language,
        device=device,
        sample_rate=sample_rate,
        config=config,
    )

    # Check if no mode selected
    modes_selected = sum([
        bool(listen_once),
        bool(conversation),
        bool(tap_to_talk),
        bool(hold_to_talk),
        bool(file),
        bool(server),
    ])

    if modes_selected == 0:
        print("No operation mode selected. Use --help for options.", file=sys.stderr)
        sys.exit(0)
    elif modes_selected > 1 and not (tap_to_talk and hold_to_talk):
        print("Error: Multiple operation modes selected. Choose one mode.", file=sys.stderr)
        sys.exit(1)

    # Run the async worker
    asyncio.run(async_worker(args))


def on_status(json=False, ctx=None, **kwargs):
    """Show system status and capabilities."""
    console = get_console()
    output_format = "json" if json else "text"

    try:
        # Check dependencies
        status = {
            "system": "ready",
            "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            "dependencies": {},
            "audio": {},
            "models": []
        }

        # Check core dependencies
        deps_to_check = [
            ("faster_whisper", "FastWhisper"),
            ("mlx.core", "Apple MLX"),
            ("parakeet_mlx", "Parakeet (MLX)"),
            ("torch", "PyTorch"),
            ("websockets", "WebSockets"),
            ("opuslib", "Opus Audio"),
            ("silero_vad", "Voice Activity Detection")
        ]

        for module, name in deps_to_check:
            try:
                __import__(module)
                status["dependencies"][name] = "Available"
            except ImportError:
                status["dependencies"][name] = "Missing"

        if output_format == "json":
            print(json_module.dumps(status, indent=2))
        elif console:
            console.print("Ears System Status", style="bold blue")
            console.print("-" * 40, style="blue")
            console.print(f"Python {status['python_version']}")
            for name, stat in status["dependencies"].items():
                icon = "[green]OK[/green]" if stat == "Available" else "[red]Missing[/red]"
                console.print(f"  {name}: {icon}")
        else:
            print("Ears System Status")
            print(f"Python: {status['python_version']}")
            for name, stat in status["dependencies"].items():
                print(f"  {name}: {stat}")

    except Exception as e:
        if output_format == "json":
            print(json_module.dumps({"error": str(e), "status": "failed"}))
        else:
            print(f"Status check failed: {e}", file=sys.stderr)


def on_models(json=False, ctx=None, **kwargs):
    """List available Whisper models."""
    output_format = "json" if json else "text"
    console = get_console()

    models = [
        {"name": "tiny", "size": "37 MB", "speed": "Very Fast", "accuracy": "Basic"},
        {"name": "base", "size": "142 MB", "speed": "Fast", "accuracy": "Good"},
        {"name": "small", "size": "463 MB", "speed": "Medium", "accuracy": "Better"},
        {"name": "medium", "size": "1.4 GB", "speed": "Slow", "accuracy": "High"},
        {"name": "large", "size": "2.9 GB", "speed": "Very Slow", "accuracy": "Highest"}
    ]

    if output_format == "json":
        print(json_module.dumps({"available_models": models}, indent=2))
    elif console:
        console.print("Available Whisper Models", style="bold blue")
        console.print("-" * 50, style="blue")
        console.print(f"{'Name':<10} {'Size':<10} {'Speed':<12} {'Accuracy'}")
        console.print("-" * 50)
        for m in models:
            console.print(f"{m['name']:<10} {m['size']:<10} {m['speed']:<12} {m['accuracy']}")
    else:
        print("Available Whisper Models:")
        for m in models:
            print(f"  {m['name']}: {m['size']} - {m['speed']} - {m['accuracy']}")


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    "on_transcribe",
    "on_status",
    "on_models",
    # Mode runners (for testing)
    "run_listen_once",
    "run_conversation",
    "run_tap_to_talk",
    "run_hold_to_talk",
    "run_file_transcription",
    "run_server",
    "async_worker",
]
