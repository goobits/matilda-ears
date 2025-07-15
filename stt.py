#!/usr/bin/env python3
"""
GOOBITS STT - Pure speech-to-text engine with multiple operation modes

Usage:
    stt --listen-once           # Single utterance with VAD
    stt --conversation          # Always listening, interruption support
    stt --tap-to-talk=f8        # Tap to start/stop recording
    stt --hold-to-talk=space    # Hold to record, release to stop
    stt --server --port=8769    # WebSocket server for remote clients
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

# Add project root to path for imports
current_dir = Path(__file__).parent.absolute()
if str(current_dir) not in sys.path:
    sys.path.insert(0, str(current_dir))

# Import STT modules


def create_parser():
    parser = argparse.ArgumentParser(
        description="GOOBITS STT - Pure speech-to-text engine",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Operation Modes:
  --listen-once         Single utterance capture with VAD
  --conversation        Always listening with interruption support
  --tap-to-talk KEY     Tap KEY to start/stop recording
  --hold-to-talk KEY    Hold KEY to record, release to stop
  --server              Run as WebSocket server

Examples:
  stt --listen-once | jq -r '.text'
  stt --conversation | llm-process | tts-speak
  stt --tap-to-talk=f8
  stt --server --port=8769
        """,
    )

    # Operation modes
    modes = parser.add_argument_group("Operation Modes")
    modes.add_argument("--listen-once", action="store_true", help="Single utterance with VAD")
    modes.add_argument("--conversation", action="store_true", help="Always listening mode")
    modes.add_argument("--tap-to-talk", metavar="KEY", help="Tap to start/stop recording")
    modes.add_argument("--hold-to-talk", metavar="KEY", help="Hold to record")

    # Server mode
    server = parser.add_argument_group("Server Mode")
    server.add_argument("--server", action="store_true", help="Run as WebSocket server")
    server.add_argument("--port", type=int, default=8769, help="Server port (default: 8769)")
    server.add_argument("--host", default="0.0.0.0", help="Server host (default: 0.0.0.0)")

    # Output options
    output = parser.add_argument_group("Output Options")
    output.add_argument("--format", choices=["json", "text"], default="json", help="Output format")
    output.add_argument("--no-formatting", action="store_true", help="Disable text formatting")

    # Model options
    model = parser.add_argument_group("Model Options")
    model.add_argument("--model", default="base", help="Whisper model size (default: base)")
    model.add_argument("--language", help="Language code (e.g., 'en', 'es')")

    # Audio options
    audio = parser.add_argument_group("Audio Options")
    audio.add_argument("--device", help="Audio input device")
    audio.add_argument("--sample-rate", type=int, default=16000, help="Sample rate")

    # Other options
    parser.add_argument("--config", help="Configuration file path")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    parser.add_argument("--version", action="version", version="%(prog)s 1.0.0")

    return parser


async def run_listen_once(args):
    """Run single utterance capture mode"""
    try:
        from src.modes.listen_once import ListenOnceMode
        mode = ListenOnceMode(args)
        await mode.run()
    except ImportError as e:
        error_msg = f"Listen-once mode not available: {e}"
        if args.format == "json":
            print(json.dumps({"error": error_msg, "mode": "listen_once"}))
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
            print(json.dumps(error_result))
        else:
            print(f"Error: {e}", file=sys.stderr)
        raise


async def run_conversation(args):
    """Run continuous conversation mode"""
    try:
        from src.modes.conversation import ConversationMode
        mode = ConversationMode(args)
        await mode.run()
    except ImportError as e:
        error_msg = f"Conversation mode not available: {e}"
        if args.format == "json":
            print(json.dumps({"error": error_msg, "mode": "conversation"}))
        else:
            print(f"Error: {error_msg}", file=sys.stderr)


async def run_tap_to_talk(args):
    """Run tap-to-talk mode"""
    try:
        from src.modes.tap_to_talk import TapToTalkMode
        mode = TapToTalkMode(args)
        await mode.run()
    except ImportError as e:
        error_msg = f"Tap-to-talk mode not available: {e}"
        if args.format == "json":
            print(json.dumps({"error": error_msg, "mode": "tap_to_talk", "key": args.tap_to_talk}))
        else:
            print(f"Error: {error_msg}", file=sys.stderr)


async def run_hold_to_talk(args):
    """Run hold-to-talk mode"""
    try:
        from src.modes.hold_to_talk import HoldToTalkMode
        mode = HoldToTalkMode(args)
        await mode.run()
    except ImportError as e:
        error_msg = f"Hold-to-talk mode not available: {e}"
        if args.format == "json":
            print(json.dumps({"error": error_msg, "mode": "hold_to_talk", "key": args.hold_to_talk}))
        else:
            print(f"Error: {error_msg}", file=sys.stderr)


async def run_server(args):
    """Run WebSocket server mode"""
    try:
        from src.transcription.server import MatildaWebSocketServer

        # Create and start server
        server = MatildaWebSocketServer()
        await server.start_server(host=args.host, port=args.port)

    except ImportError as e:
        error_msg = f"Server mode not available: {e}"
        if args.format == "json":
            print(json.dumps({"error": error_msg, "mode": "server", "host": args.host, "port": args.port}))
        else:
            print(f"Error: {error_msg}", file=sys.stderr)
    except Exception as e:
        error_msg = f"Server failed to start: {e}"
        if args.format == "json":
            print(json.dumps({"error": error_msg, "mode": "server", "host": args.host, "port": args.port}))
        else:
            print(f"Error: {error_msg}", file=sys.stderr)


async def async_main():
    parser = create_parser()
    args = parser.parse_args()

    # Validate that at least one mode is selected
    modes_selected = sum([
        bool(args.listen_once),
        bool(args.conversation),
        bool(args.tap_to_talk),
        bool(args.hold_to_talk),
        bool(args.server),
    ])

    if modes_selected == 0:
        parser.error("No operation mode selected. Use --help for options.")
    elif modes_selected > 1 and not (args.tap_to_talk and args.hold_to_talk):
        # Allow combining tap-to-talk and hold-to-talk
        parser.error("Multiple operation modes selected. Choose one mode or combine --tap-to-talk with --hold-to-talk.")

    # Route to appropriate mode
    try:
        if args.listen_once:
            await run_listen_once(args)
        elif args.conversation:
            await run_conversation(args)
        elif args.tap_to_talk and args.hold_to_talk:
            # Combined mode
            print(json.dumps({
                "mode": "combined",
                "tap_key": args.tap_to_talk,
                "hold_key": args.hold_to_talk,
                "message": "Combined mode not yet implemented"
            }))
        elif args.tap_to_talk:
            await run_tap_to_talk(args)
        elif args.hold_to_talk:
            await run_hold_to_talk(args)
        elif args.server:
            await run_server(args)
    except KeyboardInterrupt:
        if args.format == "json":
            print(json.dumps({"status": "interrupted", "message": "User cancelled"}))
        sys.exit(0)
    except Exception as e:
        if args.format == "json":
            print(json.dumps({"error": str(e), "status": "failed"}))
        else:
            print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def main():
    """Entry point for the STT CLI"""
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
