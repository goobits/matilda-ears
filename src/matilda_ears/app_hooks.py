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

# i18n support
from matilda_ears.i18n import t, t_common

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


async def run_wake_word(args):
    """Run wake word detection mode."""
    try:
        from matilda_ears.wake_word.mode import WakeWordMode
        mode = WakeWordMode(args)
        await mode.run()
    except ImportError as e:
        error_msg = f"Wake word mode not available: {e}. Install with: pip install goobits-matilda-ears[wake_word]"
        if args.format == "json":
            print(json_module.dumps({"error": error_msg, "mode": "wake_word"}))
        else:
            print(f"Error: {error_msg}", file=sys.stderr)
    except Exception as e:
        error_result = {
            "error": str(e),
            "status": "failed",
            "mode": "wake_word"
        }
        if args.format == "json":
            print(json_module.dumps(error_result))
        else:
            print(f"Error: {e}", file=sys.stderr)
        raise


async def async_worker(args):
    """Async worker for STT operations."""
    try:
        if args.listen_once:
            await run_listen_once(args)
        elif args.conversation:
            await run_conversation(args)
        elif args.wake_word:
            await run_wake_word(args)
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
    wake_word=None,
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
    agents=None,
    threshold=None,
):
    """Main transcription hook - handles all operation modes."""
    # Ensure stdout is unbuffered for piping
    sys.stdout.reconfigure(line_buffering=True)

    # Build args namespace
    args = SimpleNamespace(
        listen_once=listen_once,
        conversation=conversation,
        wake_word=wake_word,
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
        agents=agents,
        threshold=threshold,
    )

    # Check if no mode selected
    modes_selected = sum([
        bool(listen_once),
        bool(conversation),
        bool(wake_word),
        bool(tap_to_talk),
        bool(hold_to_talk),
        bool(file),
        bool(server),
    ])

    if modes_selected == 0:
        print(t("errors.no_mode_selected"), file=sys.stderr)
        sys.exit(0)
    elif modes_selected > 1 and not (tap_to_talk and hold_to_talk):
        print(t("errors.multiple_modes"), file=sys.stderr)
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
            console.print(t("status.title"), style="bold blue")
            console.print("-" * 40, style="blue")
            console.print(f"Python {status['python_version']}")
            for name, stat in status["dependencies"].items():
                icon = f"[green]{t_common('status.available')}[/green]" if stat == "Available" else f"[red]{t_common('status.not_available')}[/red]"
                console.print(f"  {name}: {icon}")
        else:
            print(t("status.title"))
            print(f"Python: {status['python_version']}")
            for name, stat in status["dependencies"].items():
                print(f"  {name}: {stat}")

    except Exception as e:
        if output_format == "json":
            print(json_module.dumps({"error": str(e), "status": "failed"}))
        else:
            print(t_common("errors.generic", message=str(e)), file=sys.stderr)


def on_models(json=False, ctx=None, **kwargs):
    """List available Whisper models."""
    output_format = "json" if json else "text"
    console = get_console()

    # Use translated model info
    models = [
        {"name": t("models.tiny.name"), "size": t("models.tiny.size"), "speed": t("models.tiny.speed"), "accuracy": t("models.tiny.quality")},
        {"name": t("models.base.name"), "size": t("models.base.size"), "speed": t("models.base.speed"), "accuracy": t("models.base.quality")},
        {"name": t("models.small.name"), "size": t("models.small.size"), "speed": t("models.small.speed"), "accuracy": t("models.small.quality")},
        {"name": t("models.medium.name"), "size": t("models.medium.size"), "speed": t("models.medium.speed"), "accuracy": t("models.medium.quality")},
        {"name": t("models.large.name"), "size": t("models.large.size"), "speed": t("models.large.speed"), "accuracy": t("models.large.quality")},
    ]

    if output_format == "json":
        print(json_module.dumps({"available_models": models}, indent=2))
    elif console:
        console.print(t("models.title"), style="bold blue")
        console.print("-" * 50, style="blue")
        console.print(f"{t('models.columns.name'):<10} {t('models.columns.size'):<10} {t('models.columns.speed'):<12} {t('models.columns.quality')}")
        console.print("-" * 50)
        for m in models:
            console.print(f"{m['name']:<10} {m['size']:<10} {m['speed']:<12} {m['accuracy']}")
    else:
        print(f"{t('models.title')}:")
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
    "run_wake_word",
    "run_tap_to_talk",
    "run_hold_to_talk",
    "run_file_transcription",
    "run_server",
    "async_worker",
]
