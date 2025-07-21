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

# Configure rich-click command groups and sections
click.rich_click.COMMAND_GROUPS = {
    "goobits-stt": [
        {
            "name": "Core Commands",
            "commands": ["listen", "live", "serve"],
        },
        {
            "name": "System & Model Commands", 
            "commands": ["config", "status", "models"],
        },
    ]
}

"""
GOOBITS STT - Pure speech-to-text engine with multiple operation modes
"""

import asyncio
import json
import sys
import argparse
import os
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
    
    @click.group()
    @click.version_option(version="1.0.0", prog_name="GOOBITS STT")
    @click.pass_context
    def main(ctx):
        """🎙️ [bold cyan]STT - Transform speech into text with AI-powered transcription.[/bold cyan]
        
        \b
        From quick voice notes to always-on conversation monitoring,
        stt brings the power of Whisper to your terminal.
        \b
        [bold yellow]💡 Quick Start:[/bold yellow]
        \b
          [green]stt listen[/green]                         [italic]# Capture a single speech utterance[/italic]
          [green]stt live[/green]                           [italic]# Start always-on "live" transcription[/italic] 
          [green]stt listen --hold-to-talk=space[/green]    [italic]# Hold spacebar to record[/italic]
          [green]stt serve --port=8769[/green]              [italic]# Run as a WebSocket server for other apps[/italic]

        \b
        [bold yellow]🔑 First-time Setup:[/bold yellow]
        \b
          1. Check system status:      [green]stt status[/green]
          2. Choose a default model:   [green]stt config set model base[/green]
          3. Test your microphone:     [green]stt listen --debug[/green]
          4. Start transcribing:       [green]stt live[/green]

        \b
        📚 For detailed help on a command, run: [green]stt [COMMAND] --help[/green]
        """
        pass
    
    # Core Commands
    @main.command()
    @click.option("--device", help="🎤 Audio input device name or index")
    @click.option("--language", help="🌍 Language code (e.g., 'en', 'es')")
    @click.option("--model", default="base", help="🤖 Whisper model size (tiny, base, small, medium, large)")
    @click.option("--hold-to-talk", metavar="KEY", help="🔘 Hold KEY to record, release to stop")
    @click.option("--json", is_flag=True, help="📄 Output JSON format (default: simple text)")
    @click.option("--debug", is_flag=True, help="🐛 Enable detailed debug logging")
    @click.option("--config", help="⚙️ Configuration file path")
    @click.option("--no-formatting", is_flag=True, help="🚫 Disable advanced text formatting")
    @click.option("--sample-rate", type=int, default=16000, help="🔊 Audio sample rate in Hz")
    def listen(device, language, model, hold_to_talk, json, debug, config, no_formatting, sample_rate):
        """🎯 Transcribe a single utterance."""
        from types import SimpleNamespace
        args = SimpleNamespace(
            listen_once=True,
            conversation=False,
            wake_word=False,
            tap_to_talk=None,
            hold_to_talk=hold_to_talk,
            server=False,
            port=8769,
            host="0.0.0.0",
            json=json,
            format="json" if json else "text",
            debug=debug,
            no_formatting=no_formatting,
            model=model,
            language=language,
            device=device,
            sample_rate=sample_rate,
            config=config,
            status=False,
            models=False
        )
        asyncio.run(async_main_worker(args))

    @main.command()
    @click.option("--device", help="🎤 Audio input device name or index")
    @click.option("--language", help="🌍 Language code (e.g., 'en', 'es')")
    @click.option("--model", default="base", help="🤖 Whisper model size (tiny, base, small, medium, large)")
    @click.option("--tap-to-talk", metavar="KEY", help="⚡ Tap KEY to start/stop recording")
    @click.option("--json", is_flag=True, help="📄 Output JSON format (default: simple text)")
    @click.option("--debug", is_flag=True, help="🐛 Enable detailed debug logging")
    @click.option("--config", help="⚙️ Configuration file path")
    @click.option("--no-formatting", is_flag=True, help="🚫 Disable advanced text formatting")
    @click.option("--sample-rate", type=int, default=16000, help="🔊 Audio sample rate in Hz")
    def live(device, language, model, tap_to_talk, json, debug, config, no_formatting, sample_rate):
        """💬 Continuous "live" transcription mode."""
        from types import SimpleNamespace
        args = SimpleNamespace(
            listen_once=False,
            conversation=True,
            wake_word=False,
            tap_to_talk=tap_to_talk,
            hold_to_talk=None,
            server=False,
            port=8769,
            host="0.0.0.0",
            json=json,
            format="json" if json else "text",
            debug=debug,
            no_formatting=no_formatting,
            model=model,
            language=language,
            device=device,
            sample_rate=sample_rate,
            config=config,
            status=False,
            models=False
        )
        asyncio.run(async_main_worker(args))

    @main.command()
    @click.option("--port", type=int, default=8769, help="🔌 Server port (default: 8769)")
    @click.option("--host", default="0.0.0.0", help="🏠 Server host (default: 0.0.0.0)")
    @click.option("--debug", is_flag=True, help="🐛 Enable detailed debug logging")
    @click.option("--config", help="⚙️ Configuration file path")
    def serve(port, host, debug, config):
        """🌐 Run as a WebSocket server."""
        from types import SimpleNamespace
        args = SimpleNamespace(
            listen_once=False,
            conversation=False,
            wake_word=False,
            tap_to_talk=None,
            hold_to_talk=None,
            server=True,
            port=port,
            host=host,
            json=False,
            format="text",
            debug=debug,
            no_formatting=False,
            model="base",
            language=None,
            device=None,
            sample_rate=16000,
            config=config,
            status=False,
            models=False
        )
        asyncio.run(async_main_worker(args))

    # System & Model Commands
    @main.group()
    def config():
        """⚙️ Manage default settings."""
        pass

    @config.command()
    @click.argument('key')
    @click.argument('value')
    def set(key, value):
        """Set a configuration value."""
        from src.core.config import get_config
        config_loader = get_config()
        config_loader.set(key, value)
        config_loader.save()
        click.echo(f"Set {key} = {value}")

    @config.command()
    @click.argument('key')
    def get(key):
        """Get a configuration value."""
        from src.core.config import get_config
        config_loader = get_config()
        value = config_loader.get(key)
        if value is not None:
            click.echo(value)
        else:
            click.echo(f"Configuration key '{key}' not found", err=True)

    @config.command()
    def list():
        """List all configuration settings."""
        from src.core.config import get_config
        import json
        config_loader = get_config()
        click.echo(json.dumps(config_loader._config, indent=2))

    @main.command()
    def status():
        """📊 Show system status and capabilities."""
        from types import SimpleNamespace
        args = SimpleNamespace(
            status=True,
            models=False,
            debug=False
        )
        asyncio.run(async_main_worker(args))

    @main.command()
    def models():
        """📋 List available Whisper models."""
        from types import SimpleNamespace
        args = SimpleNamespace(
            status=False,
            models=True,
            debug=False
        )
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
            
            from src.transcription.server import MatildaWebSocketServer
            server = MatildaWebSocketServer()
            await server.start_server()
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