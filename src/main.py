#!/usr/bin/env python3

import rich_click as click

# Configure rich-click to enable markup - MUST be first!
click.rich_click.USE_RICH_MARKUP = True

# 🧛‍♂️ Apply Dracula theme colors
click.rich_click.STYLE_OPTION = "#ff79c6"      # Dracula Pink - for option flags
click.rich_click.STYLE_ARGUMENT = "#8be9fd"    # Dracula Cyan - for argument types  
click.rich_click.STYLE_COMMAND = "#50fa7b"     # Dracula Green - for subcommands
click.rich_click.STYLE_USAGE = "#bd93f9"       # Dracula Purple - for "Usage:" line
click.rich_click.STYLE_HELPTEXT = "#b3b8c0"    # Light gray - for help descriptions

"""
GOOBITS STT - Pure speech-to-text engine with multiple operation modes
"""

import asyncio
import json
import sys
import argparse
from pathlib import Path

RICH_AVAILABLE = True

if RICH_AVAILABLE:
    from rich.console import Console
    from rich.panel import Panel
    from rich.text import Text

# Add project root to path for imports
project_root = Path(__file__).parent.parent.absolute()
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Import STT modules


def create_rich_cli():
    """Create Rich-enhanced Click CLI interface"""
    console = Console()
    
    @click.command(context_settings={"allow_extra_args": False})
    @click.version_option(version="1.0.0", prog_name="GOOBITS STT")
    @click.option("--config", help=" ⚙️  Configuration file path")
    @click.option("--conversation", is_flag=True, help=" 💬 Always listening with interruption support")
    @click.option("--debug", is_flag=True, help=" 🐛 Enable detailed debug logging")
    @click.option("--device", help=" 🎤 Audio input device name or index")
    @click.option("--hold-to-talk", metavar="KEY", help=" 🔘 Hold KEY to record, release to stop")
    @click.option("--host", default="0.0.0.0", help=" 🏠 Server host (default: 0.0.0.0)")
    @click.option("--json", is_flag=True, help=" 📄 Output JSON format (default: simple text)")
    @click.option("--language", help=" 🌍 Language code (e.g., 'en', 'es', 'fr')")
    @click.option("--listen-once", is_flag=True, help=" 🎯 Single utterance capture with VAD")
    @click.option("--model", default="base", help=" 🤖 Whisper model size (tiny, base, small, medium, large)")
    @click.option("--models", is_flag=True, help=" 📋 List available Whisper models")
    @click.option("--no-formatting", is_flag=True, help=" 🚫 Disable advanced text formatting")
    @click.option("--port", type=int, default=8769, help=" 🔌 Server port (default: 8769)")
    @click.option("--sample-rate", type=int, default=16000, help=" 🔊 Audio sample rate in Hz")
    @click.option("--server", is_flag=True, help=" 🌐 Run as WebSocket server for remote clients")
    @click.option("--status", is_flag=True, help=" 📊 Show system status and capabilities")
    @click.option("--tap-to-talk", metavar="KEY", help=" ⚡ Tap KEY to start/stop recording")
    @click.option("--wake-word", is_flag=True, help=" 🎤 Wake word detection mode with Porcupine")
    @click.pass_context
    def main(ctx, config, conversation, debug, device, hold_to_talk, host, json, language, listen_once, model, models, no_formatting, port, sample_rate, server, status, tap_to_talk, wake_word):
        """🎙️ [bold cyan]GOOBITS STT v1.0.0[/bold cyan] - Transform speech into text with AI-powered transcription

        \b
        Multiple operation modes for different use cases, from quick voice notes 
        to always-on conversation monitoring with advanced text formatting.

        \b
        [bold yellow]🎯 Quick Start:[/bold yellow]
        \b
          [green]stt --listen-once[/green]                    [italic]# Capture single speech utterance[/italic]
          [green]stt --conversation[/green]                   [italic]# Always listening mode[/italic]
          [green]stt --tap-to-talk=f8[/green]                 [italic]# Toggle recording with F8 key[/italic]
          [green]stt --hold-to-talk=space[/green]             [italic]# Hold spacebar to record[/italic]

        \b
        [bold yellow]🌐 Server & Integration:[/bold yellow]
        \b
          [green]stt --server --port=8769[/green]             [italic]# WebSocket server for remote clients[/italic]
          [green]stt --listen-once | jq -r '.text'[/green]    [italic]# Pipeline JSON output[/italic]
          [green]stt --conversation | llm-chat[/green]        [italic]# Feed transcriptions to AI assistant[/italic]

        \b
        [bold yellow]🎤 Audio Configuration:[/bold yellow]
        \b
          [green]stt --device="USB Microphone"[/green]        [italic]# Specific audio input device[/italic]
          [green]stt --model=small --language=es[/green]      [italic]# Spanish with small Whisper model[/italic]
          [green]stt --sample-rate=44100[/green]              [italic]# High-quality audio sampling[/italic]

        \b
        [bold yellow]✨ Advanced Features:[/bold yellow]
        \b
          [green]stt --wake-word[/green]                      [italic]# Porcupine wake word detection[/italic]
          [green]stt --json --no-formatting[/green]           [italic]# Raw JSON output without formatting[/italic]
          [green]stt --debug[/green]                          [italic]# Detailed logging for troubleshooting[/italic]

        \b
        [bold yellow]🔧 System Commands:[/bold yellow]
        \b
          [green]stt --status[/green]                         [italic]# Check system health and capabilities[/italic]
          [green]stt --models[/green]                         [italic]# List available Whisper models[/italic]

        \b
        [bold yellow]🔑 Setup:[/bold yellow]
        \b
          1. Check system status:  [green]stt --status[/green]
          2. Choose a model:       [green]stt --models[/green]
          3. Test microphone:      [green]stt --listen-once --debug[/green]
          4. Start transcribing:   [green]stt --conversation[/green]

        \b
        📚 For detailed help on options, run: [green]stt --help[/green]
        """
        # Check if any operation mode is selected
        modes_selected = any([
            listen_once,
            conversation,
            wake_word,
            tap_to_talk,
            hold_to_talk,
            server,
            status,
            models
        ])
        
        if not modes_selected:
            # No mode selected, show help
            click.echo(ctx.get_help())
            return
        
        # Create args object from parameters
        from types import SimpleNamespace
        args = SimpleNamespace(
            listen_once=listen_once,
            conversation=conversation,
            wake_word=wake_word,
            tap_to_talk=tap_to_talk,
            hold_to_talk=hold_to_talk,
            server=server,
            port=port,
            host=host,
            json=json,
            format="json" if json else "text",  # Add format attribute based on json flag
            debug=debug,
            no_formatting=no_formatting,
            model=model,
            language=language,
            device=device,
            sample_rate=sample_rate,
            config=config,
            status=status,
            models=models
        )
        
        # Run the async main function
        asyncio.run(async_main_worker(args))
    
    return main


async def async_main_worker(args):
    """Main worker function that handles all modes"""
    try:
        # Handle status command
        if args.status:
            from src.utils.system_status import show_system_status
            await show_system_status()
            return
        
        # Handle models listing
        if args.models:
            from src.utils.model_utils import list_available_models
            await list_available_models()
            return
        
        # Initialize configuration and logging
        from src.core.config import setup_logging
        logger = setup_logging("main", log_level="DEBUG" if args.debug else "INFO")
        
        # Server mode
        if args.server:
            # Set environment variables for server configuration
            if args.host:
                os.environ["WEBSOCKET_SERVER_HOST"] = args.host
            if args.port:
                os.environ["WEBSOCKET_SERVER_PORT"] = str(args.port)
            os.environ["MATILDA_MANAGEMENT_TOKEN"] = "managed-by-matilda-system"
            
            from src.transcription.server import main as server_main
            server_main()
            return
        
        # Select appropriate mode
        mode = None
        
        if args.listen_once:
            from src.modes.listen_once import ListenOnceMode
            mode = ListenOnceMode(args)
        elif args.conversation:
            from src.modes.conversation import ConversationMode
            mode = ConversationMode(args)
        elif args.wake_word:
            from src.modes.wake_word import WakeWordMode
            mode = WakeWordMode(args)
        elif args.tap_to_talk:
            from src.modes.tap_to_talk import TapToTalkMode
            mode = TapToTalkMode(args)
        elif args.hold_to_talk:
            from src.modes.hold_to_talk import HoldToTalkMode
            mode = HoldToTalkMode(args)
        
        # Run the selected mode
        await mode.run()
        
    except KeyboardInterrupt:
        if RICH_AVAILABLE:
            console = Console()
            console.print("\n[yellow]Interrupted by user[/yellow]")
        else:
            print("\nInterrupted by user", file=sys.stderr)
    except Exception as e:
        if RICH_AVAILABLE:
            console = Console()
            console.print(f"\n[red]Error: {str(e)}[/red]")
        else:
            print(f"\nError: {str(e)}", file=sys.stderr)
        if args.debug:
            import traceback
            traceback.print_exc()
        sys.exit(1)


async def async_main():
    """Async entry point for argparse fallback"""
    parser = argparse.ArgumentParser(
        description='GOOBITS STT - Transform speech into text with AI-powered transcription',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --listen-once                    # Capture single speech
  %(prog)s --conversation                   # Always listening mode
  %(prog)s --tap-to-talk=f8                # Toggle recording with F8
  %(prog)s --hold-to-talk=space             # Hold spacebar to record
  %(prog)s --server --port=8769             # WebSocket server mode
  %(prog)s --listen-once | jq -r '.text'    # Pipeline JSON output
  %(prog)s --conversation | llm-chat        # Feed to AI assistant
        """
    )
    
    # Operation modes
    mode_group = parser.add_argument_group('operation modes')
    mode_group.add_argument('--listen-once', action='store_true', help='Single utterance capture with VAD')
    mode_group.add_argument('--conversation', action='store_true', help='Always listening with interruption support')
    mode_group.add_argument('--wake-word', action='store_true', help='Wake word detection mode with Porcupine')
    mode_group.add_argument('--tap-to-talk', metavar='KEY', help='Tap KEY to start/stop recording')
    mode_group.add_argument('--hold-to-talk', metavar='KEY', help='Hold KEY to record, release to stop')
    mode_group.add_argument('--server', action='store_true', help='Run as WebSocket server for remote clients')
    
    # Server options
    server_group = parser.add_argument_group('server options')
    server_group.add_argument('--port', type=int, default=8769, help='Server port (default: 8769)')
    server_group.add_argument('--host', default='0.0.0.0', help='Server host (default: 0.0.0.0)')
    
    # Output options
    output_group = parser.add_argument_group('output options')
    output_group.add_argument('--json', action='store_true', help='Output JSON format (default: simple text)')
    output_group.add_argument('--debug', action='store_true', help='Enable detailed debug logging')
    output_group.add_argument('--no-formatting', action='store_true', help='Disable advanced text formatting')
    
    # Model options
    model_group = parser.add_argument_group('model options')
    model_group.add_argument('--model', default='base', help='Whisper model size (tiny, base, small, medium, large)')
    model_group.add_argument('--language', help='Language code (e.g., "en", "es", "fr")')
    
    # Audio options
    audio_group = parser.add_argument_group('audio options')
    audio_group.add_argument('--device', help='Audio input device name or index')
    audio_group.add_argument('--sample-rate', type=int, default=16000, help='Audio sample rate in Hz')
    
    # System options
    system_group = parser.add_argument_group('system options')
    system_group.add_argument('--config', help='Configuration file path')
    system_group.add_argument('--status', action='store_true', help='Show system status and capabilities')
    system_group.add_argument('--models', action='store_true', help='List available Whisper models')
    system_group.add_argument('--version', action='version', version='%(prog)s 1.0.0')
    
    args = parser.parse_args()
    
    # Validate mode selection
    modes_selected = sum([
        bool(args.listen_once),
        bool(args.conversation),
        bool(args.wake_word),
        bool(args.tap_to_talk),
        bool(args.hold_to_talk),
        bool(args.server)
    ])

    if modes_selected == 0:
        parser.error("No operation mode selected. Use --help for options.")
    elif modes_selected > 1 and not (args.tap_to_talk and args.hold_to_talk):
        # Allow combining tap-to-talk and hold-to-talk
        parser.error("Multiple operation modes selected. Choose one mode or combine --tap-to-talk with --hold-to-talk.")

    await async_main_worker(args)


def main():
    """Entry point for the STT CLI"""
    # Ensure stdout is unbuffered for piping
    import sys
    sys.stdout.reconfigure(line_buffering=True)
    
    if RICH_AVAILABLE:
        # Use Rich-enhanced Click interface
        cli = create_rich_cli()
        cli()
    else:
        # Fallback to basic argparse
        asyncio.run(async_main())


if __name__ == "__main__":
    main()