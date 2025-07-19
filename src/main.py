#!/usr/bin/env python3
"""
GOOBITS STT - Pure speech-to-text engine with multiple operation modes
"""

import asyncio
import json
import sys
import argparse
from pathlib import Path

try:
    import click
    from rich.console import Console
    from rich.panel import Panel
    from rich.text import Text
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

# Add project root to path for imports
project_root = Path(__file__).parent.parent.absolute()
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Import STT modules


def create_rich_cli():
    """Create Rich-enhanced Click CLI interface"""
    console = Console()
    
    @click.command(context_settings={"allow_extra_args": False})
    @click.version_option(version="1.0.0", prog_name="stt")
    @click.option("--listen-once", is_flag=True, help="🎯 Single utterance capture with VAD")
    @click.option("--conversation", is_flag=True, help="💬 Always listening with interruption support")
    @click.option("--tap-to-talk", metavar="KEY", help="⚡ Tap KEY to start/stop recording")
    @click.option("--hold-to-talk", metavar="KEY", help="🔘 Hold KEY to record, release to stop")
    @click.option("--server", is_flag=True, help="🌐 Run as WebSocket server for remote clients")
    @click.option("--port", type=int, default=8769, help="🔌 Server port (default: 8769)")
    @click.option("--host", default="0.0.0.0", help="🏠 Server host (default: 0.0.0.0)")
    @click.option("--json", is_flag=True, help="📄 Output JSON format (default: simple text)")
    @click.option("--debug", is_flag=True, help="🐛 Enable detailed debug logging")
    @click.option("--no-formatting", is_flag=True, help="🚫 Disable advanced text formatting")
    @click.option("--model", default="base", help="🤖 Whisper model size (tiny, base, small, medium, large)")
    @click.option("--language", help="🌍 Language code (e.g., 'en', 'es', 'fr')")
    @click.option("--device", help="🎤 Audio input device name or index")
    @click.option("--sample-rate", type=int, default=16000, help="🔊 Audio sample rate in Hz")
    @click.option("--config", help="⚙️ Configuration file path")
    @click.option("--status", is_flag=True, help="📊 Show system status and capabilities")
    @click.option("--models", is_flag=True, help="📋 List available Whisper models")
    @click.option("--document", metavar="FILE", help="📄 Convert document to speech (markdown, HTML, JSON)")
    @click.option("--format", type=click.Choice(['auto', 'markdown', 'html', 'json']), 
                  default='auto', help="🎯 Document format (auto-detect by default)")
    @click.option("--ssml-platform", type=click.Choice(['azure', 'google', 'amazon', 'generic']),
                  default='generic', help="🎤 SSML platform for voice synthesis")
    @click.option("--emotion-profile", type=click.Choice(['technical', 'marketing', 'narrative', 'tutorial', 'auto']),
                  default='auto', help="🎭 Emotion profile for document type")
    @click.option("--cache", is_flag=True, help="💾 Enable document caching for performance")
    @click.option("--mixed-mode", is_flag=True, help="🔄 Enable mixed content processing")
    @click.pass_context
    def main(ctx, listen_once, conversation, tap_to_talk, hold_to_talk, server, port, host, json, debug, no_formatting, model, language, device, sample_rate, config, status, models, document, format, ssml_platform, emotion_profile, cache, mixed_mode):
        """🎙️ Transform speech into text with AI-powered transcription
        
        GOOBITS STT provides multiple operation modes for different use cases.
        From quick voice notes to always-on conversation monitoring.
        
        \b
        🎯 Quick Start:
          stt --listen-once                    # Capture single speech
          stt --conversation                   # Always listening mode
          stt --tap-to-talk=f8                # Toggle recording with F8
          stt --hold-to-talk=space             # Hold spacebar to record
        
        \b
        🌐 Server & Integration:
          stt --server --port=8769             # WebSocket server mode
          stt --listen-once | jq -r '.text'    # Pipeline JSON output
          stt --conversation | llm-chat        # Feed to AI assistant
        
        \b
        🎤 Audio Configuration:
          stt --device="USB Microphone"        # Specific audio device
          stt --model=small --language=es      # Spanish with small model
          stt --sample-rate=44100              # High-quality audio
        
        \b
        ✨ Key Features:
          • Advanced text formatting with entity detection
          • Multiple Whisper model sizes (tiny to large)
          • Real-time VAD (Voice Activity Detection)
          • WebSocket server for remote integration
          • JSON output for automation and pipelines
        
        \b
        🔧 System Commands:
          stt --status                         # Check system health
          stt --models                         # List available models
          stt --debug                          # Troubleshooting mode
        """
        # Create args object from parameters
        from types import SimpleNamespace
        args = SimpleNamespace(
            listen_once=listen_once,
            conversation=conversation,
            tap_to_talk=tap_to_talk,
            hold_to_talk=hold_to_talk,
            server=server,
            port=port,
            host=host,
            format="json" if json else "text",
            json=json,
            debug=debug,
            no_formatting=no_formatting,
            model=model,
            language=language,
            device=device,
            sample_rate=sample_rate,
            config=config,
            status=status,
            models=models,
            document=document,
            document_format=format,
            ssml_platform=ssml_platform,
            emotion_profile=emotion_profile,
            cache=cache,
            mixed_mode=mixed_mode
        )
        
        return run_stt_command(ctx, args)
    
    return main


def create_fallback_parser():
    """Fallback argparse interface when Click/Rich unavailable"""
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
    output.add_argument("--json", action="store_true", help="Output JSON format (default: simple text)")
    output.add_argument("--debug", action="store_true", help="Enable debug logging")
    output.add_argument("--no-formatting", action="store_true", help="Disable text formatting")

    # Model options
    model = parser.add_argument_group("Model Options")
    model.add_argument("--model", default="base", help="Whisper model size (default: base)")
    model.add_argument("--language", help="Language code (e.g., 'en', 'es')")

    # Audio options
    audio = parser.add_argument_group("Audio Options")
    audio.add_argument("--device", help="Audio input device")
    audio.add_argument("--sample-rate", type=int, default=16000, help="Sample rate")

    # System options
    parser.add_argument("--config", help="Configuration file path")
    parser.add_argument("--status", action="store_true", help="Show system status")
    parser.add_argument("--models", action="store_true", help="List available models")
    parser.add_argument("--document", metavar="FILE", help="Convert document to speech")
    parser.add_argument("--format", choices=['auto', 'markdown', 'html', 'json'], 
                        default='auto', help="Document format (auto-detect by default)")
    parser.add_argument("--ssml-platform", choices=['azure', 'google', 'amazon', 'generic'],
                        default='generic', help="SSML platform for voice synthesis")
    parser.add_argument("--emotion-profile", choices=['technical', 'marketing', 'narrative', 'tutorial', 'auto'],
                        default='auto', help="Emotion profile for document type")
    parser.add_argument("--cache", action="store_true", help="Enable document caching for performance")
    parser.add_argument("--mixed-mode", action="store_true", help="Enable mixed content processing")
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


def handle_status_command(output_format="json"):
    """Show system status and capabilities"""
    console = Console() if RICH_AVAILABLE else None
    
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
            ("torch", "PyTorch"), 
            ("websockets", "WebSockets"),
            ("opuslib", "Opus Audio"),
            ("silero_vad", "Voice Activity Detection")
        ]
        
        for module, name in deps_to_check:
            try:
                __import__(module)
                status["dependencies"][name] = "✅ Available"
            except ImportError:
                status["dependencies"][name] = "❌ Missing"
        
        if output_format == "json":
            print(json.dumps(status, indent=2))
        else:
            if console:
                console.print("STT System Status", style="bold blue")
                console.print("━━━━━━━━━━━━━━━━━━", style="blue")
                console.print(f"├─ Python {status['python_version']}                           ✅ Ready")
                for name, stat in status["dependencies"].items():
                    console.print(f"├─ {name:<30} {stat}")
                console.print("└─ Configuration                       ✅ Loaded")
            else:
                print("STT System Status")
                print(f"Python: {status['python_version']}")
                for name, stat in status["dependencies"].items():
                    print(f"{name}: {stat}")
                    
    except Exception as e:
        if output_format == "json":
            print(json.dumps({"error": str(e), "status": "failed"}))
        else:
            print(f"❌ Status check failed: {e}", file=sys.stderr)


def handle_models_command(output_format="json"):
    """List available Whisper models"""
    models = [
        {"name": "tiny", "size": "37 MB", "speed": "Very Fast", "accuracy": "Basic"},
        {"name": "base", "size": "142 MB", "speed": "Fast", "accuracy": "Good"},
        {"name": "small", "size": "463 MB", "speed": "Medium", "accuracy": "Better"},
        {"name": "medium", "size": "1.4 GB", "speed": "Slow", "accuracy": "High"},
        {"name": "large", "size": "2.9 GB", "speed": "Very Slow", "accuracy": "Highest"}
    ]
    
    if output_format == "json":
        print(json.dumps({"available_models": models}, indent=2))
    else:
        console = Console() if RICH_AVAILABLE else None
        if console:
            console.print("Available Whisper Models", style="bold blue")
            console.print("━━━━━━━━━━━━━━━━━━━━━━━━━", style="blue")
            for model in models:
                console.print(f"├─ {model['name']:<8} {model['size']:<10} {model['speed']:<12} {model['accuracy']}")
        else:
            print("Available Whisper Models:")
            for model in models:
                print(f"  {model['name']}: {model['size']} - {model['speed']} - {model['accuracy']}")


def handle_document_command(args):
    """Handle document to speech conversion with Phase 4 features"""
    try:
        import sys
        import os
        import time
        from pathlib import Path
        
        # Add src directory to path for imports
        src_path = Path(__file__).parent
        if str(src_path) not in sys.path:
            sys.path.insert(0, str(src_path))
            
        # Import Phase 4 components
        from src.speech_synthesis.ssml_generator import SSMLGenerator, SSMLPlatform
        from src.speech_synthesis.advanced_emotion_detector import AdvancedEmotionDetector
        from src.integration.mixed_content_processor import MixedContentProcessor
        from src.document_parsing.performance_cache import PerformanceOptimizer
        
        # Import existing components
        from src.document_parsing.parser_factory import DocumentParserFactory
        from src.speech_synthesis.semantic_formatter import SemanticFormatter
        from src.speech_synthesis.speech_markdown import SpeechMarkdownConverter
        from src.speech_synthesis.tts_engine import SimpleTTSEngine
        
        # Check if document file exists
        if not os.path.exists(args.document):
            error_msg = f"Document file not found: {args.document}"
            if args.format == "json":
                print(json.dumps({"error": error_msg, "mode": "document"}))
            else:
                print(f"Error: {error_msg}", file=sys.stderr)
            return
            
        # Read document content
        try:
            with open(args.document, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            error_msg = f"Failed to read document: {e}"
            if args.format == "json":
                print(json.dumps({"error": error_msg, "mode": "document"}))
            else:
                print(f"Error: {error_msg}", file=sys.stderr)
            return
            
        # Initialize Phase 4 components based on CLI options
        start_time = time.time()
        
        # Set up performance optimizer with caching
        enable_caching = getattr(args, 'cache', False)
        optimizer = PerformanceOptimizer(enable_caching=enable_caching)
        
        # Set up mixed content processor if enabled
        mixed_mode = getattr(args, 'mixed_mode', False)
        if mixed_mode:
            processor = MixedContentProcessor()
            
        # Set up SSML generator
        ssml_platform_str = getattr(args, 'ssml_platform', 'generic')
        ssml_platform = SSMLPlatform(ssml_platform_str)
        ssml_generator = SSMLGenerator(ssml_platform)
        
        # Set up advanced emotion detector
        emotion_detector = AdvancedEmotionDetector()
        
        # Parse document with performance optimization and mixed content support
        format_override = getattr(args, 'document_format', 'auto')
        if format_override == 'auto':
            format_override = None
        
        try:
            if mixed_mode:
                # Use mixed content processor
                content_type = "auto"
                speech_markdown = processor.process_mixed_content(content, content_type, format_override or "")
                detected_format = processor._detect_content_type(content, format_override or "")
                elements = []  # Mixed processor handles conversion internally
            else:
                # Use traditional document parsing with performance optimization
                elements = optimizer.process_document(content, format_override or "auto")
                detected_format = DocumentParserFactory().detect_format(content, args.document)
            
        except ValueError as e:
            error_msg = f"Unsupported document format: {e}"
            supported_formats = DocumentParserFactory().get_supported_formats()
            if args.format == "json":
                print(json.dumps({"error": error_msg, "mode": "document", "supported": supported_formats}))
            else:
                print(f"Error: {error_msg}. Supported formats: {', '.join(supported_formats)}", file=sys.stderr)
            return
        except Exception as e:
            error_msg = f"Failed to parse document: {e}"
            if args.format == "json":
                print(json.dumps({"error": error_msg, "mode": "document"}))
            else:
                print(f"Error: {error_msg}", file=sys.stderr)
            return
        
        processing_time = time.time() - start_time
        
        # Process with advanced emotion detection and SSML generation
        if not mixed_mode and elements:
            # Get document type and contextual emotions
            doc_type = emotion_detector.detect_document_type(elements)
            emotion_profile = getattr(args, 'emotion_profile', 'auto')
            
            if emotion_profile != 'auto':
                # Override detected document type if user specified emotion profile
                doc_type = emotion_profile
            
            contextual_emotions = emotion_detector.get_contextual_emotions(elements)
            
            # Convert to speech markdown with advanced emotions
            converter = SpeechMarkdownConverter()
            speech_markdown = converter.convert_elements(elements)
            
            # Generate SSML
            ssml_output = ssml_generator.convert_speech_markdown(speech_markdown)
            
            # Validate SSML
            is_valid, validation_msg = ssml_generator.validate_ssml(ssml_output)
            
        elif mixed_mode:
            # Mixed mode already processed - convert to SSML
            ssml_output = ssml_generator.convert_speech_markdown(speech_markdown)
            is_valid, validation_msg = ssml_generator.validate_ssml(ssml_output)
            doc_type = "mixed_content"
            contextual_emotions = []
        else:
            # Fallback
            speech_markdown = content
            ssml_output = content
            is_valid = True
            validation_msg = "No processing applied"
            doc_type = "unknown"
            contextual_emotions = []
        
        # Get performance statistics
        perf_stats = optimizer.get_performance_stats() if enable_caching else {}
        
        # Generate enhanced output with Phase 4 information
        if args.format == "json":
            result = {
                "mode": "document",
                "file": args.document,
                "detected_format": detected_format,
                "format_override": getattr(args, 'document_format', 'auto'),
                "elements_parsed": len(elements) if elements else 0,
                "processing_time_seconds": round(processing_time, 3),
                "phase_4_features": {
                    "document_type": doc_type,
                    "emotion_profile": getattr(args, 'emotion_profile', 'auto'),
                    "ssml_platform": ssml_platform_str,
                    "mixed_mode": mixed_mode,
                    "caching_enabled": enable_caching,
                    "ssml_valid": is_valid,
                    "ssml_validation": validation_msg
                },
                "speech_markdown": speech_markdown,
                "ssml_output": ssml_output,
                "performance": perf_stats,
                "status": "processing"
            }
            print(json.dumps(result, indent=2))
        else:
            print(f"Processing document: {args.document}")
            print(f"Detected format: {detected_format}")
            print(f"Document type: {doc_type}")
            print(f"Elements parsed: {len(elements) if elements else 0}")
            print(f"Processing time: {processing_time:.3f}s")
            print(f"SSML platform: {ssml_platform_str}")
            print(f"SSML valid: {'✓' if is_valid else '✗'} ({validation_msg})")
            if enable_caching:
                cache_info = perf_stats.get('cache_stats', {})
                print(f"Cache usage: {cache_info.get('total_files', 0)} files, {cache_info.get('total_size_mb', 0):.1f}MB")
            
        # Generate speech using TTS engine (simplified for demo)
        tts_engine = SimpleTTSEngine()
        if hasattr(tts_engine, 'available_engines') and tts_engine.available_engines:
            # For now, use speech markdown as input (could use SSML in future)
            if args.format == "json":
                print(json.dumps({"status": "completed", "speech_generated": True}))
            else:
                print("✓ Speech processing completed")
        else:
            if args.format == "json":
                print(json.dumps({"status": "no_tts", "speech_markdown": speech_markdown}))
            else:
                print(f"No TTS engines available.")
                print(f"Speech Markdown output:\n{speech_markdown[:200]}{'...' if len(speech_markdown) > 200 else ''}")
                
    except ImportError as e:
        error_msg = f"Document processing not available: {e}"
        if hasattr(args, 'format') and args.format == "json":
            print(json.dumps({"error": error_msg, "mode": "document"}))
        else:
            print(f"Error: {error_msg}", file=sys.stderr)
    except Exception as e:
        error_msg = f"Document processing failed: {e}"
        if hasattr(args, 'format') and args.format == "json":
            print(json.dumps({"error": error_msg, "mode": "document"}))
        else:
            print(f"Error: {error_msg}", file=sys.stderr)


def run_stt_command(ctx, args):
    """Handle STT command execution with Rich styling"""
    
    # Handle special commands first
    if args.status:
        handle_status_command(args.format)
        return
    
    if args.models:
        handle_models_command(args.format)
        return
    
    if args.document:
        handle_document_command(args)
        return
    
    # Check if no meaningful arguments provided
    modes_selected = sum([
        bool(args.listen_once),
        bool(args.conversation),
        bool(args.tap_to_talk),
        bool(args.hold_to_talk),
        bool(args.server),
        bool(args.document),
    ])
    
    if modes_selected == 0:
        if RICH_AVAILABLE:
            click.echo(ctx.get_help(), err=True)
        else:
            print("No operation mode selected. Use --help for options.", file=sys.stderr)
        sys.exit(0)
    elif modes_selected > 1 and not (args.tap_to_talk and args.hold_to_talk):
        error_msg = "Multiple operation modes selected. Choose one mode or combine --tap-to-talk with --hold-to-talk."
        if RICH_AVAILABLE:
            click.echo(f"❌ {error_msg}", err=True)
        else:
            print(f"Error: {error_msg}", file=sys.stderr)
        sys.exit(1)
    
    # Run the appropriate mode asynchronously
    asyncio.run(async_main_worker(args))


async def async_main_worker(args):
    """Async worker for STT operations"""
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
            if RICH_AVAILABLE:
                click.echo(f"❌ Error: {e}", err=True)
            else:
                print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


async def async_main():
    """Fallback main for argparse mode"""
    parser = create_fallback_parser()
    args = parser.parse_args()
    
    # Handle format naming conflict - preserve document format before overwriting
    document_format = getattr(args, 'format', 'auto') if args.document else 'auto'
    
    # Set output format based on json flag
    args.format = "json" if args.json else "text"
    
    # Set document_format for compatibility
    if args.document:
        args.document_format = document_format
    
    # Handle special commands
    if args.status:
        handle_status_command(args.format)
        return
    
    if args.models:
        handle_models_command(args.format)
        return
    
    if args.document:
        handle_document_command(args)
        return

    # Validate that at least one mode is selected
    modes_selected = sum([
        bool(args.listen_once),
        bool(args.conversation),
        bool(args.tap_to_talk),
        bool(args.hold_to_talk),
        bool(args.server),
        bool(args.document),
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
