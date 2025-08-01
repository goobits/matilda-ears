#!/usr/bin/env python3
"""Auto-generated from goobits.yaml"""
import os
import sys
import importlib.util
from pathlib import Path
import rich_click as click
from rich_click import RichGroup, RichCommand

# Set up rich-click configuration globally
click.rich_click.USE_RICH_MARKUP = True  
click.rich_click.USE_MARKDOWN = False  # Disable markdown to avoid conflicts
click.rich_click.MARKUP_MODE = "rich"

# Environment variables for additional control
os.environ["RICH_CLICK_USE_RICH_MARKUP"] = "1"
os.environ["RICH_CLICK_FORCE_TERMINAL"] = "1"
click.rich_click.SHOW_ARGUMENTS = True
click.rich_click.GROUP_ARGUMENTS_OPTIONS = True
click.rich_click.SHOW_METAVARS_COLUMN = False
click.rich_click.APPEND_METAVARS_HELP = True
click.rich_click.STYLE_ERRORS_SUGGESTION = "#ff5555"
click.rich_click.ERRORS_SUGGESTION = "Try running the '--help' flag for more information."
click.rich_click.ERRORS_EPILOGUE = "To find out more, visit https://github.com/anthropics/claude-code"
click.rich_click.MAX_WIDTH = 120  # Set reasonable width
click.rich_click.WIDTH = 120  # Set consistent width
click.rich_click.COLOR_SYSTEM = "auto"
click.rich_click.SHOW_SUBCOMMAND_ALIASES = True
click.rich_click.ALIGN_OPTIONS_SWITCHES = True
click.rich_click.STYLE_OPTION = "#ff79c6"      # Dracula Pink - for option flags
click.rich_click.STYLE_SWITCH = "#50fa7b"      # Dracula Green - for switches
click.rich_click.STYLE_METAVAR = "#8BE9FD not bold"   # Light cyan - for argument types (OPTIONS, COMMAND)  
click.rich_click.STYLE_METAVAR_SEPARATOR = "#6272a4"  # Dracula Comment
click.rich_click.STYLE_HEADER_TEXT = "bold yellow"    # Bold yellow - for section headers
click.rich_click.STYLE_EPILOGUE_TEXT = "#6272a4"      # Dracula Comment
click.rich_click.STYLE_FOOTER_TEXT = "#6272a4"        # Dracula Comment
click.rich_click.STYLE_USAGE = "#BD93F9"              # Purple - for "Usage:" line
click.rich_click.STYLE_USAGE_COMMAND = "bold"         # Bold for main command name
click.rich_click.STYLE_DEPRECATED = "#ff5555"         # Dracula Red
click.rich_click.STYLE_HELPTEXT_FIRST_LINE = "#f8f8f2" # Dracula Foreground
click.rich_click.STYLE_HELPTEXT = "#B3B8C0"           # Light gray - for help descriptions
click.rich_click.STYLE_OPTION_DEFAULT = "#ffb86c"     # Dracula Orange
click.rich_click.STYLE_REQUIRED_SHORT = "#ff5555"     # Dracula Red
click.rich_click.STYLE_REQUIRED_LONG = "#ff5555"      # Dracula Red
click.rich_click.STYLE_OPTIONS_PANEL_BORDER = "dim"   # Dim for subtle borders
click.rich_click.STYLE_COMMANDS_PANEL_BORDER = "dim"  # Dim for subtle borders
click.rich_click.STYLE_COMMAND = "#50fa7b"            # Dracula Green - for command names in list
click.rich_click.STYLE_COMMANDS_TABLE_COLUMN_WIDTH_RATIO = (1, 3)  # Command:Description ratio (1/4 : 3/4)


# Command groups will be set after main function is defined


# Hooks system - try to import app_hooks module
app_hooks = None

# Using configured hooks path: src/stt/app_hooks.py
try:
    # First try as a module import (e.g., "ttt.app_hooks")
    module_path = "src/stt/app_hooks.py".replace(".py", "").replace("/", ".")
    if module_path.startswith("src."):
        module_path = module_path[4:]  # Remove 'src.' prefix
    
    try:
        app_hooks = importlib.import_module(module_path)
    except ImportError:
        # If module import fails, try relative import
        try:
            from . import app_hooks
        except ImportError:
            # If relative import fails, try file-based import as last resort
            script_dir = Path(__file__).parent.parent.parent
            hooks_file = script_dir / "src/stt/app_hooks.py"
            
            if hooks_file.exists():
                spec = importlib.util.spec_from_file_location("app_hooks", hooks_file)
                app_hooks = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(app_hooks)
except Exception:
    # No hooks module found, use default behavior
    pass


# Built-in commands

def builtin_upgrade_command(check_only=False, pre=False, version=None, dry_run=False):
    """Built-in upgrade function for STT - Speech to Text - uses enhanced setup.sh script."""
    import subprocess
    import sys
    from pathlib import Path

    if check_only:
        print(f"Checking for updates to STT - Speech to Text...")
        print("Update check not yet implemented. Run without --check to upgrade.")
        return

    if dry_run:
        print("Dry run - would execute: pipx upgrade goobits-stt")
        return

    # Find the setup.sh script - look in common locations
    setup_script = None
    search_paths = [
        Path(__file__).parent / "setup.sh",  # Package directory (installed packages)
        Path(__file__).parent.parent / "setup.sh",  # Development mode 
        Path.home() / ".local" / "share" / "goobits-stt" / "setup.sh",  # User data
        # Remove Path.cwd() to prevent cross-contamination
    ]
    
    for path in search_paths:
        if path.exists():
            setup_script = path
            break
    
    if setup_script is None:
        # Fallback to basic upgrade if setup.sh not found
        print(f"Enhanced setup script not found. Using basic upgrade for STT - Speech to Text...")
        import shutil
        
        package_name = "goobits-stt"
        pypi_name = "goobits-stt"
        
        if shutil.which("pipx"):
            result = subprocess.run(["pipx", "list"], capture_output=True, text=True)
            if package_name in result.stdout or pypi_name in result.stdout:
                cmd = ["pipx", "upgrade", pypi_name]
            else:
                cmd = [sys.executable, "-m", "pip", "install", "--upgrade", pypi_name]
        else:
            cmd = [sys.executable, "-m", "pip", "install", "--upgrade", pypi_name]
        
        result = subprocess.run(cmd)
        if result.returncode == 0:
            print(f"✅ STT - Speech to Text upgraded successfully!")
            print(f"Run 'stt --version' to verify the new version.")
        else:
            print(f"❌ Upgrade failed with exit code {result.returncode}")
            sys.exit(1)
        return

    # Use the enhanced setup.sh script
    result = subprocess.run([str(setup_script), "upgrade"])
    sys.exit(result.returncode)


def load_plugins(cli_group):
    """Load plugins from the conventional plugin directory."""
    # Define plugin directories to search
    plugin_dirs = [
        # User-specific plugin directory
        Path.home() / ".config" / "goobits" / "GOOBITS STT CLI" / "plugins",
        # Local plugin directory (same as script)
        Path(__file__).parent / "plugins",
    ]
    
    for plugin_dir in plugin_dirs:
        if not plugin_dir.exists():
            continue
            
        # Add plugin directory to Python path
        sys.path.insert(0, str(plugin_dir))
        
        # Scan for plugin files
        for plugin_file in plugin_dir.glob("*.py"):
            if plugin_file.name.startswith("_"):
                continue
                
            # Skip core system files that aren't plugins
            if plugin_file.name in ["loader.py", "__init__.py"]:
                continue
                
            plugin_name = plugin_file.stem
            
            try:
                # Import the plugin module
                spec = importlib.util.spec_from_file_location(plugin_name, plugin_file)
                plugin_module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(plugin_module)
                
                # Call register_plugin if it exists
                if hasattr(plugin_module, "register_plugin"):
                    plugin_module.register_plugin(cli_group)
                    click.echo(f"Loaded plugin: {plugin_name}", err=True)
            except Exception as e:
                click.echo(f"Failed to load plugin {plugin_name}: {e}", err=True)







def get_version():
    """Get version from pyproject.toml or __init__.py"""
    import re
    
    try:
        # Try to get version from pyproject.toml FIRST (most authoritative)
        # Look in multiple possible locations
        possible_paths = [
            Path(__file__).parent.parent / "pyproject.toml",  # For flat structure
            Path(__file__).parent.parent.parent / "pyproject.toml",  # For src/ structure
        ]
        toml_path = None
        for path in possible_paths:
            if path.exists():
                toml_path = path
                break
        if toml_path:
            content = toml_path.read_text()
            match = re.search(r'version\s*=\s*["\']([^"\']+)["\']', content)
            if match:
                return match.group(1)
    except Exception:
        pass
    
    try:
        # Fallback to __init__.py
        init_path = Path(__file__).parent / "__init__.py"
        if init_path.exists():
            content = init_path.read_text()
            match = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', content)
            if match:
                return match.group(1)
    except Exception:
        pass
        
    # Final fallback
    return "1.0.2"


def show_help_json(ctx, param, value):
    """Callback for --help-json option."""
    if not value or ctx.resilient_parsing:
        return
    # The triple quotes are important to correctly handle the multi-line JSON string
    click.echo('''{
  "name": "GOOBITS STT CLI",
  "version": "1.0.2",
  "display_version": true,
  "tagline": "Real-time speech-to-text with AI-powered Whisper models",
  "description": "Convert speech into accurate text with multiple operation modes and advanced formatting.",
  "icon": "🎤",
  "header_sections": [
    {
      "title": "🎯 Most Common Use Cases",
      "icon": null,
      "items": [
        {
          "item": "stt listen",
          "desc": "Quick voice note: Record and transcribe once",
          "style": "example"
        },
        {
          "item": "stt transcribe audio.wav --json",
          "desc": "File transcription: Process audio files with JSON output",
          "style": "example"
        },
        {
          "item": "stt live",
          "desc": "Always listening: Hands-free conversation mode",
          "style": "example"
        },
        {
          "item": "stt live --tap-to-talk=F8",
          "desc": "Press F8 to talk: Controlled conversation mode",
          "style": "example"
        },
        {
          "item": "stt listen --hold-to-talk=space",
          "desc": "Hold spacebar: Push-to-talk recording",
          "style": "example"
        },
        {
          "item": "stt serve --port=8080",
          "desc": "Remote transcription: WebSocket server for clients",
          "style": "example"
        }
      ]
    },
    {
      "title": "🚀 Quick Start (First Time)",
      "icon": null,
      "items": [
        {
          "item": "1. Check system",
          "desc": "stt status",
          "style": "setup"
        },
        {
          "item": "2. Test recording",
          "desc": "stt listen",
          "style": "setup"
        },
        {
          "item": "3. Try conversation",
          "desc": "stt live",
          "style": "setup"
        }
      ]
    },
    {
      "title": "💭 Popular Workflows",
      "icon": null,
      "items": [
        {
          "item": "Voice Notes",
          "desc": "stt listen > notes.txt  # Save transcription to file",
          "style": "example"
        },
        {
          "item": "Batch Processing",
          "desc": "stt transcribe *.wav --json  # Process multiple audio files",
          "style": "example"
        },
        {
          "item": "Meeting Notes",
          "desc": "stt live --json > meeting.json  # Structured output",
          "style": "example"
        },
        {
          "item": "Remote Dictation",
          "desc": "stt serve  # Server + client apps on other devices",
          "style": "example"
        },
        {
          "item": "Gaming/Streaming",
          "desc": "stt live --tap-to-talk=F8  # Hotkey control",
          "style": "example"
        }
      ]
    },
    {
      "title": "💡 Core Commands",
      "icon": null,
      "items": [
        {
          "item": "listen",
          "desc": "🎙️  Record once and transcribe (default command)",
          "style": "command"
        },
        {
          "item": "live",
          "desc": "🗣️  Real-time conversation mode with VAD",
          "style": "command"
        },
        {
          "item": "transcribe",
          "desc": "🎯 Transcribe audio files to text",
          "style": "command"
        },
        {
          "item": "serve",
          "desc": "🌐 Launch WebSocket transcription server",
          "style": "command"
        }
      ]
    }
  ],
  "footer_note": "📚 For detailed help on a command, run: [color(2)]stt [COMMAND][/color(2)] [#ff79c6]--help[/#ff79c6]",
  "options": [],
  "commands": {
    "listen": {
      "desc": "🎙️ Record once and transcribe",
      "icon": "🎙️",
      "is_default": false,
      "lifecycle": "standard",
      "args": [],
      "options": [
        {
          "name": "model",
          "short": "m",
          "type": "str",
          "desc": "🧠 Whisper model size (tiny=fastest, large=most accurate)",
          "default": "base",
          "choices": [
            "tiny",
            "base",
            "small",
            "medium",
            "large"
          ],
          "multiple": false
        },
        {
          "name": "language",
          "short": "l",
          "type": "str",
          "desc": "🌍 Language code for transcription (e.g., en, es, fr, auto-detect)",
          "default": null,
          "choices": null,
          "multiple": false
        },
        {
          "name": "device",
          "short": "d",
          "type": "str",
          "desc": "🎤 Audio input device (microphone name or index)",
          "default": null,
          "choices": null,
          "multiple": false
        },
        {
          "name": "hold-to-talk",
          "short": null,
          "type": "str",
          "desc": "⌨️  Hold-to-talk key (e.g., space, F8, ctrl)",
          "default": null,
          "choices": null,
          "multiple": false
        },
        {
          "name": "no-formatting",
          "short": null,
          "type": "bool",
          "desc": "📝 Output unformatted raw text",
          "default": false,
          "choices": null,
          "multiple": false
        },
        {
          "name": "sample-rate",
          "short": null,
          "type": "int",
          "desc": "🔊 Audio sampling rate (Hz)",
          "default": 16000,
          "choices": null,
          "multiple": false
        },
        {
          "name": "json",
          "short": null,
          "type": "flag",
          "desc": "📋 Output transcription results as JSON",
          "default": null,
          "choices": null,
          "multiple": false
        },
        {
          "name": "debug",
          "short": null,
          "type": "flag",
          "desc": "🐞 Enable detailed debug logging",
          "default": null,
          "choices": null,
          "multiple": false
        },
        {
          "name": "config",
          "short": null,
          "type": "str",
          "desc": "⚙️ Path to custom config file",
          "default": null,
          "choices": null,
          "multiple": false
        }
      ],
      "subcommands": null
    },
    "live": {
      "desc": "🗣️ Real-time interactive transcription",
      "icon": "🗣️",
      "is_default": false,
      "lifecycle": "standard",
      "args": [],
      "options": [
        {
          "name": "model",
          "short": "m",
          "type": "str",
          "desc": "🧠 Whisper model size (tiny=fastest, large=most accurate)",
          "default": "base",
          "choices": [
            "tiny",
            "base",
            "small",
            "medium",
            "large"
          ],
          "multiple": false
        },
        {
          "name": "language",
          "short": "l",
          "type": "str",
          "desc": "🌍 Language code for transcription (e.g., en, es, fr, auto-detect)",
          "default": null,
          "choices": null,
          "multiple": false
        },
        {
          "name": "device",
          "short": "d",
          "type": "str",
          "desc": "🎤 Audio input device (microphone name or index)",
          "default": null,
          "choices": null,
          "multiple": false
        },
        {
          "name": "tap-to-talk",
          "short": null,
          "type": "str",
          "desc": "👆 Tap-to-talk key (e.g., F8)",
          "default": null,
          "choices": null,
          "multiple": false
        },
        {
          "name": "no-formatting",
          "short": null,
          "type": "bool",
          "desc": "📝 Output unformatted raw text",
          "default": false,
          "choices": null,
          "multiple": false
        },
        {
          "name": "sample-rate",
          "short": null,
          "type": "int",
          "desc": "🔊 Audio sampling rate (Hz)",
          "default": 16000,
          "choices": null,
          "multiple": false
        },
        {
          "name": "json",
          "short": null,
          "type": "flag",
          "desc": "📋 Output transcription results as JSON",
          "default": null,
          "choices": null,
          "multiple": false
        },
        {
          "name": "debug",
          "short": null,
          "type": "flag",
          "desc": "🐞 Enable detailed debug logging",
          "default": null,
          "choices": null,
          "multiple": false
        },
        {
          "name": "config",
          "short": null,
          "type": "str",
          "desc": "⚙️ Path to custom config file",
          "default": null,
          "choices": null,
          "multiple": false
        }
      ],
      "subcommands": null
    },
    "serve": {
      "desc": "🌐 Launch transcription server",
      "icon": "🌐",
      "is_default": false,
      "lifecycle": "standard",
      "args": [],
      "options": [
        {
          "name": "port",
          "short": "p",
          "type": "int",
          "desc": "🌐 Server port (default 8769)",
          "default": 8769,
          "choices": null,
          "multiple": false
        },
        {
          "name": "host",
          "short": "h",
          "type": "str",
          "desc": "🏠 Server host address (default 0.0.0.0)",
          "default": "0.0.0.0",
          "choices": null,
          "multiple": false
        },
        {
          "name": "debug",
          "short": null,
          "type": "flag",
          "desc": "🐞 Enable detailed debug logging",
          "default": null,
          "choices": null,
          "multiple": false
        },
        {
          "name": "config",
          "short": null,
          "type": "str",
          "desc": "⚙️ Path to custom config file",
          "default": null,
          "choices": null,
          "multiple": false
        }
      ],
      "subcommands": null
    },
    "transcribe": {
      "desc": "🎯 Transcribe audio files to text",
      "icon": "🎯",
      "is_default": false,
      "lifecycle": "standard",
      "args": [
        {
          "name": "audio_files",
          "desc": "🎵 Audio file(s) to transcribe (WAV, MP3, Opus supported)",
          "nargs": "+",
          "choices": null,
          "required": true
        }
      ],
      "options": [
        {
          "name": "model",
          "short": "m",
          "type": "str",
          "desc": "🧠 Whisper model size (tiny=fastest, large=most accurate)",
          "default": "base",
          "choices": [
            "tiny",
            "base",
            "small",
            "medium",
            "large"
          ],
          "multiple": false
        },
        {
          "name": "language",
          "short": "l",
          "type": "str",
          "desc": "🌍 Language code for transcription (e.g., en, es, fr, auto-detect)",
          "default": null,
          "choices": null,
          "multiple": false
        },
        {
          "name": "json",
          "short": null,
          "type": "flag",
          "desc": "📋 Output transcription results as JSON",
          "default": null,
          "choices": null,
          "multiple": false
        },
        {
          "name": "prefer-server",
          "short": null,
          "type": "flag",
          "desc": "🌐 Try WebSocket server first, fallback to direct",
          "default": null,
          "choices": null,
          "multiple": false
        },
        {
          "name": "server-only",
          "short": null,
          "type": "flag",
          "desc": "🔒 Require WebSocket server connection",
          "default": null,
          "choices": null,
          "multiple": false
        },
        {
          "name": "direct-only",
          "short": null,
          "type": "flag",
          "desc": "🖥️ Skip server, use direct Whisper processing",
          "default": null,
          "choices": null,
          "multiple": false
        },
        {
          "name": "output",
          "short": "o",
          "type": "str",
          "desc": "📄 Output format (plain, json, matilda)",
          "default": "plain",
          "choices": [
            "plain",
            "json",
            "matilda"
          ],
          "multiple": false
        },
        {
          "name": "debug",
          "short": null,
          "type": "flag",
          "desc": "🐞 Enable detailed debug logging",
          "default": null,
          "choices": null,
          "multiple": false
        },
        {
          "name": "config",
          "short": null,
          "type": "str",
          "desc": "⚙️ Path to custom config file",
          "default": null,
          "choices": null,
          "multiple": false
        }
      ],
      "subcommands": null
    },
    "status": {
      "desc": "✅ Check system health and device status",
      "icon": "✅",
      "is_default": false,
      "lifecycle": "standard",
      "args": [],
      "options": [
        {
          "name": "json",
          "short": null,
          "type": "flag",
          "desc": "📋 Output status results as JSON",
          "default": null,
          "choices": null,
          "multiple": false
        }
      ],
      "subcommands": null
    },
    "model": {
      "desc": "Manage Whisper models",
      "icon": "🧠",
      "is_default": false,
      "lifecycle": "standard",
      "args": [],
      "options": [],
      "subcommands": {
        "download": {
          "desc": "Download a Whisper model",
          "icon": null,
          "is_default": false,
          "lifecycle": "standard",
          "args": [
            {
              "name": "model_name",
              "desc": "🔽 Model name to download (tiny, base, small, medium, large)",
              "nargs": null,
              "choices": [
                "tiny",
                "base",
                "small",
                "medium",
                "large"
              ],
              "required": true
            }
          ],
          "options": [
            {
              "name": "force",
              "short": "f",
              "type": "flag",
              "desc": "🔄 Force re-download even if model exists",
              "default": null,
              "choices": null,
              "multiple": false
            },
            {
              "name": "device",
              "short": "d",
              "type": "str",
              "desc": "💻 Device type for model optimization (cpu, cuda, auto)",
              "default": "auto",
              "choices": [
                "cpu",
                "cuda",
                "auto"
              ],
              "multiple": false
            }
          ],
          "subcommands": null
        },
        "list": {
          "desc": "List available and downloaded models",
          "icon": null,
          "is_default": false,
          "lifecycle": "standard",
          "args": [],
          "options": [
            {
              "name": "downloaded-only",
              "short": null,
              "type": "flag",
              "desc": "📦 Show only downloaded models",
              "default": null,
              "choices": null,
              "multiple": false
            },
            {
              "name": "json",
              "short": null,
              "type": "flag",
              "desc": "📋 Output as JSON",
              "default": null,
              "choices": null,
              "multiple": false
            }
          ],
          "subcommands": null
        },
        "info": {
          "desc": "Show detailed model information",
          "icon": null,
          "is_default": false,
          "lifecycle": "standard",
          "args": [
            {
              "name": "model_name",
              "desc": "🔍 Model name to inspect",
              "nargs": null,
              "choices": [
                "tiny",
                "base",
                "small",
                "medium",
                "large"
              ],
              "required": true
            }
          ],
          "options": [
            {
              "name": "json",
              "short": null,
              "type": "flag",
              "desc": "📋 Output as JSON",
              "default": null,
              "choices": null,
              "multiple": false
            }
          ],
          "subcommands": null
        },
        "remove": {
          "desc": "Remove downloaded model",
          "icon": null,
          "is_default": false,
          "lifecycle": "standard",
          "args": [
            {
              "name": "model_name",
              "desc": "🗑️ Model name to remove",
              "nargs": null,
              "choices": [
                "tiny",
                "base",
                "small",
                "medium",
                "large"
              ],
              "required": true
            }
          ],
          "options": [
            {
              "name": "force",
              "short": "f",
              "type": "flag",
              "desc": "🔄 Skip confirmation prompt",
              "default": null,
              "choices": null,
              "multiple": false
            }
          ],
          "subcommands": null
        },
        "benchmark": {
          "desc": "Test model performance",
          "icon": null,
          "is_default": false,
          "lifecycle": "standard",
          "args": [
            {
              "name": "model_name",
              "desc": "⚡ Model name to benchmark",
              "nargs": null,
              "choices": [
                "tiny",
                "base",
                "small",
                "medium",
                "large"
              ],
              "required": true
            }
          ],
          "options": [
            {
              "name": "duration",
              "short": "t",
              "type": "int",
              "desc": "⏱️ Test duration in seconds",
              "default": 10,
              "choices": null,
              "multiple": false
            },
            {
              "name": "device",
              "short": "d",
              "type": "str",
              "desc": "💻 Device to test on (cpu, cuda, auto)",
              "default": "auto",
              "choices": [
                "cpu",
                "cuda",
                "auto"
              ],
              "multiple": false
            },
            {
              "name": "json",
              "short": null,
              "type": "flag",
              "desc": "📋 Output results as JSON",
              "default": null,
              "choices": null,
              "multiple": false
            }
          ],
          "subcommands": null
        }
      }
    },
    "config": {
      "desc": "⚙️ Adjust CLI settings and preferences",
      "icon": "⚙️",
      "is_default": false,
      "lifecycle": "standard",
      "args": [],
      "options": [],
      "subcommands": {
        "show": {
          "desc": "👁️ Display current configuration",
          "icon": null,
          "is_default": false,
          "lifecycle": "standard",
          "args": [],
          "options": [
            {
              "name": "json",
              "short": null,
              "type": "flag",
              "desc": "📋 Output configuration as JSON",
              "default": null,
              "choices": null,
              "multiple": false
            }
          ],
          "subcommands": null
        },
        "get": {
          "desc": "🔍 Retrieve configuration value",
          "icon": null,
          "is_default": false,
          "lifecycle": "standard",
          "args": [
            {
              "name": "key",
              "desc": "🔑 Configuration key",
              "nargs": null,
              "choices": null,
              "required": true
            }
          ],
          "options": [],
          "subcommands": null
        },
        "set": {
          "desc": "✏️ Set a configuration value",
          "icon": null,
          "is_default": false,
          "lifecycle": "standard",
          "args": [
            {
              "name": "key",
              "desc": "🔑 Configuration key",
              "nargs": null,
              "choices": null,
              "required": true
            },
            {
              "name": "value",
              "desc": "💾 Configuration value",
              "nargs": null,
              "choices": null,
              "required": true
            }
          ],
          "options": [],
          "subcommands": null
        }
      }
    }
  },
  "command_groups": [
    {
      "name": "Recording Modes",
      "commands": [
        "listen",
        "live"
      ],
      "icon": null
    },
    {
      "name": "File Processing",
      "commands": [
        "transcribe"
      ],
      "icon": null
    },
    {
      "name": "Server & Processing",
      "commands": [
        "serve"
      ],
      "icon": null
    },
    {
      "name": "System",
      "commands": [
        "status",
        "model"
      ],
      "icon": null
    },
    {
      "name": "Configuration",
      "commands": [
        "config"
      ],
      "icon": null
    }
  ],
  "config": {
    "rich_help_panel": true,
    "show_metavars_column": false,
    "append_metavars_help": true,
    "style_errors_suggestion": true,
    "max_width": 120
  },
  "enable_recursive_help": true,
  "enable_help_json": true
}''')
    ctx.exit()





  

  

  

  

  

  

  





@click.group(cls=RichGroup, context_settings={"help_option_names": ["-h", "--help"], "max_content_width": 120})

@click.version_option(version=get_version(), prog_name="GOOBITS STT CLI")
@click.pass_context

@click.option('--help-json', is_flag=True, callback=show_help_json, is_eager=True, help='Output CLI structure as JSON.', hidden=True)


@click.option('--help-all', is_flag=True, is_eager=True, help='Show help for all commands.', hidden=True)


def main(ctx, help_json=False, help_all=False):
    """🎤 [bold color(6)]GOOBITS STT CLI v1.0.2[/bold color(6)] - Real-time speech-to-text with AI-powered Whisper models

    
    \b
    [#B3B8C0]Convert speech into accurate text with multiple operation modes and advanced formatting.[/#B3B8C0]
    

    
    
    [bold yellow]🎯 Most Common Use Cases[/bold yellow]
    
    
    [green]   stt listen                       [/green] [italic][#B3B8C0]# Quick voice note: Record and transcribe once[/#B3B8C0][/italic]
    
    
    [green]   stt transcribe audio.wav --json  [/green] [italic][#B3B8C0]# File transcription: Process audio files with JSON output[/#B3B8C0][/italic]
    
    
    [green]   stt live                         [/green] [italic][#B3B8C0]# Always listening: Hands-free conversation mode[/#B3B8C0][/italic]
    
    
    [green]   stt live --tap-to-talk=F8        [/green] [italic][#B3B8C0]# Press F8 to talk: Controlled conversation mode[/#B3B8C0][/italic]
    
    
    [green]   stt listen --hold-to-talk=space  [/green] [italic][#B3B8C0]# Hold spacebar: Push-to-talk recording[/#B3B8C0][/italic]
    
    
    [green]   stt serve --port=8080            [/green] [italic][#B3B8C0]# Remote transcription: WebSocket server for clients[/#B3B8C0][/italic]
    
    [green] [/green]
    
    [bold yellow]🚀 Quick Start (First Time)[/bold yellow]
    
    
    [#B3B8C0]   1. Check system:     [/#B3B8C0][green]stt status[/green]
    
    [#B3B8C0]   2. Test recording:   [/#B3B8C0][green]stt listen[/green]
    
    [#B3B8C0]   3. Try conversation: [/#B3B8C0][green]stt live[/green]
    [green] [/green]
    
    [bold yellow]💭 Popular Workflows[/bold yellow]
    
    
    [green]   Voice Notes       [/green] [italic][#B3B8C0]# stt listen > notes.txt  # Save transcription to file[/#B3B8C0][/italic]
    
    
    [green]   Batch Processing  [/green] [italic][#B3B8C0]# stt transcribe *.wav --json  # Process multiple audio files[/#B3B8C0][/italic]
    
    
    [green]   Meeting Notes     [/green] [italic][#B3B8C0]# stt live --json > meeting.json  # Structured output[/#B3B8C0][/italic]
    
    
    [green]   Remote Dictation  [/green] [italic][#B3B8C0]# stt serve  # Server + client apps on other devices[/#B3B8C0][/italic]
    
    
    [green]   Gaming/Streaming  [/green] [italic][#B3B8C0]# stt live --tap-to-talk=F8  # Hotkey control[/#B3B8C0][/italic]
    
    [green] [/green]
    
    [bold yellow]💡 Core Commands[/bold yellow]
    
    
    [green]   listen      [/green]  🎙️  Record once and transcribe (default command)
    
    
    [green]   live        [/green]  🗣️  Real-time conversation mode with VAD
    
    
    [green]   transcribe  [/green]  🎯 Transcribe audio files to text
    
    
    [green]   serve       [/green]  🌐 Launch WebSocket transcription server
    
    [green] [/green]
    
    
    
    [#B3B8C0]📚 For detailed help on a command, run: [color(2)]stt [COMMAND][/color(2)] [#ff79c6]--help[/#ff79c6][/#B3B8C0]
    
    """
    
    if help_all:
        # Print main help
        click.echo(ctx.get_help())
        click.echo() # Add a blank line for spacing

        # Get a list of all command names
        commands_to_show = sorted(ctx.command.list_commands(ctx))

        for cmd_name in commands_to_show:
            command = ctx.command.get_command(ctx, cmd_name)

            # Create a new context for the subcommand
            sub_ctx = click.Context(command, info_name=cmd_name, parent=ctx)

            # Print a separator and the subcommand's help
            click.echo("="*20 + f" HELP FOR: {cmd_name} " + "="*20)
            click.echo(sub_ctx.get_help())
            click.echo() # Add a blank line for spacing

        # Exit after printing all help
        ctx.exit()
    
    
    # Store global options in context for use by commands
    

    pass

# Replace the version placeholder with dynamic version in the main command docstring



# Set command groups after main function is defined
click.rich_click.COMMAND_GROUPS = {
    "main": [
        
        {
            "name": "Recording Modes",
            "commands": ['listen', 'live'],
        },
        
        {
            "name": "File Processing",
            "commands": ['transcribe'],
        },
        
        {
            "name": "Server & Processing",
            "commands": ['serve', 'server'],
        },
        
        {
            "name": "System",
            "commands": ['status', 'model'],
        },
        
        {
            "name": "Configuration",
            "commands": ['config'],
        },
        
    ]
}


# Built-in upgrade command (enabled by default)

@main.command()
@click.option('--check', is_flag=True, help='Check for updates without installing')
@click.option('--version', type=str, help='Install specific version')
@click.option('--pre', is_flag=True, help='Include pre-release versions')
@click.option('--dry-run', is_flag=True, help='Show what would be done without doing it')
def upgrade(check, version, pre, dry_run):
    """Upgrade STT - Speech to Text to the latest version."""
    builtin_upgrade_command(check_only=check, version=version, pre=pre, dry_run=dry_run)




@main.command()
@click.pass_context


@click.option("-m", "--model",
    type=click.Choice(['tiny', 'base', 'small', 'medium', 'large']),
    default="base",
    help="🧠 Whisper model size (tiny=fastest, large=most accurate)"
)

@click.option("-l", "--language",
    type=str,
    help="🌍 Language code for transcription (e.g., en, es, fr, auto-detect)"
)

@click.option("-d", "--device",
    type=str,
    help="🎤 Audio input device (microphone name or index)"
)

@click.option("--hold-to-talk",
    type=str,
    help="⌨️  Hold-to-talk key (e.g., space, F8, ctrl)"
)

@click.option("--no-formatting",
    type=bool,
    default=False,
    help="📝 Output unformatted raw text"
)

@click.option("--sample-rate",
    type=int,
    default=16000,
    help="🔊 Audio sampling rate (Hz)"
)

@click.option("--json",
    is_flag=True,
    help="📋 Output transcription results as JSON"
)

@click.option("--debug",
    is_flag=True,
    help="🐞 Enable detailed debug logging"
)

@click.option("--config",
    type=str,
    help="⚙️ Path to custom config file"
)

def listen(ctx, model, language, device, hold_to_talk, no_formatting, sample_rate, json, debug, config):
    """🎙️  🎙️ Record once and transcribe"""
    
    # Check for built-in commands first
    
    # Standard command - use the existing hook pattern
    hook_name = f"on_listen"
    if app_hooks and hasattr(app_hooks, hook_name):
        # Call the hook with all parameters
        hook_func = getattr(app_hooks, hook_name)
        
        # Prepare arguments including global options
        kwargs = {}
        kwargs['command_name'] = 'listen'  # Pass command name for all commands
        
        
        
        
        
        
        kwargs['model'] = model
        
        
        
        
        kwargs['language'] = language
        
        
        
        
        kwargs['device'] = device
        
        
        
        
        kwargs['hold_to_talk'] = hold_to_talk
        
        
        
        
        kwargs['no_formatting'] = no_formatting
        
        
        
        
        kwargs['sample_rate'] = sample_rate
        
        
        
        
        kwargs['json'] = json
        
        
        
        
        kwargs['debug'] = debug
        
        
        
        
        kwargs['config'] = config
        
        
        
        # Add global options from context
        
        
        result = hook_func(**kwargs)
        return result
    else:
        # Default placeholder behavior
        click.echo(f"Executing listen command...")
        
        
        
        click.echo(f"  model: {model}")
        
        click.echo(f"  language: {language}")
        
        click.echo(f"  device: {device}")
        
        click.echo(f"  hold-to-talk: {hold_to_talk}")
        
        click.echo(f"  no-formatting: {no_formatting}")
        
        click.echo(f"  sample-rate: {sample_rate}")
        
        click.echo(f"  json: {json}")
        
        click.echo(f"  debug: {debug}")
        
        click.echo(f"  config: {config}")
        
        
    
    




@main.command()
@click.pass_context


@click.option("-m", "--model",
    type=click.Choice(['tiny', 'base', 'small', 'medium', 'large']),
    default="base",
    help="🧠 Whisper model size (tiny=fastest, large=most accurate)"
)

@click.option("-l", "--language",
    type=str,
    help="🌍 Language code for transcription (e.g., en, es, fr, auto-detect)"
)

@click.option("-d", "--device",
    type=str,
    help="🎤 Audio input device (microphone name or index)"
)

@click.option("--tap-to-talk",
    type=str,
    help="👆 Tap-to-talk key (e.g., F8)"
)

@click.option("--no-formatting",
    type=bool,
    default=False,
    help="📝 Output unformatted raw text"
)

@click.option("--sample-rate",
    type=int,
    default=16000,
    help="🔊 Audio sampling rate (Hz)"
)

@click.option("--json",
    is_flag=True,
    help="📋 Output transcription results as JSON"
)

@click.option("--debug",
    is_flag=True,
    help="🐞 Enable detailed debug logging"
)

@click.option("--config",
    type=str,
    help="⚙️ Path to custom config file"
)

def live(ctx, model, language, device, tap_to_talk, no_formatting, sample_rate, json, debug, config):
    """🗣️  🗣️ Real-time interactive transcription"""
    
    # Check for built-in commands first
    
    # Standard command - use the existing hook pattern
    hook_name = f"on_live"
    if app_hooks and hasattr(app_hooks, hook_name):
        # Call the hook with all parameters
        hook_func = getattr(app_hooks, hook_name)
        
        # Prepare arguments including global options
        kwargs = {}
        kwargs['command_name'] = 'live'  # Pass command name for all commands
        
        
        
        
        
        
        kwargs['model'] = model
        
        
        
        
        kwargs['language'] = language
        
        
        
        
        kwargs['device'] = device
        
        
        
        
        kwargs['tap_to_talk'] = tap_to_talk
        
        
        
        
        kwargs['no_formatting'] = no_formatting
        
        
        
        
        kwargs['sample_rate'] = sample_rate
        
        
        
        
        kwargs['json'] = json
        
        
        
        
        kwargs['debug'] = debug
        
        
        
        
        kwargs['config'] = config
        
        
        
        # Add global options from context
        
        
        result = hook_func(**kwargs)
        return result
    else:
        # Default placeholder behavior
        click.echo(f"Executing live command...")
        
        
        
        click.echo(f"  model: {model}")
        
        click.echo(f"  language: {language}")
        
        click.echo(f"  device: {device}")
        
        click.echo(f"  tap-to-talk: {tap_to_talk}")
        
        click.echo(f"  no-formatting: {no_formatting}")
        
        click.echo(f"  sample-rate: {sample_rate}")
        
        click.echo(f"  json: {json}")
        
        click.echo(f"  debug: {debug}")
        
        click.echo(f"  config: {config}")
        
        
    
    




@main.command()
@click.pass_context


@click.option("-p", "--port",
    type=int,
    default=8769,
    help="🌐 Server port (default 8769)"
)

@click.option("-h", "--host",
    type=str,
    default="0.0.0.0",
    help="🏠 Server host address (default 0.0.0.0)"
)

@click.option("--debug",
    is_flag=True,
    help="🐞 Enable detailed debug logging"
)

@click.option("--config",
    type=str,
    help="⚙️ Path to custom config file"
)

def serve(ctx, port, host, debug, config):
    """🌐 🌐 Launch transcription server"""
    
    # Check for built-in commands first
    
    # Standard command - use the existing hook pattern
    hook_name = f"on_serve"
    if app_hooks and hasattr(app_hooks, hook_name):
        # Call the hook with all parameters
        hook_func = getattr(app_hooks, hook_name)
        
        # Prepare arguments including global options
        kwargs = {}
        kwargs['command_name'] = 'serve'  # Pass command name for all commands
        
        
        
        
        
        
        kwargs['port'] = port
        
        
        
        
        kwargs['host'] = host
        
        
        
        
        kwargs['debug'] = debug
        
        
        
        
        kwargs['config'] = config
        
        
        
        # Add global options from context
        
        
        result = hook_func(**kwargs)
        return result
    else:
        # Default placeholder behavior
        click.echo(f"Executing serve command...")
        
        
        
        click.echo(f"  port: {port}")
        
        click.echo(f"  host: {host}")
        
        click.echo(f"  debug: {debug}")
        
        click.echo(f"  config: {config}")
        
        
    
    




@main.command()
@click.pass_context

@click.argument(
    "AUDIO_FILES",
    nargs=-1,
    required=True
)


@click.option("-m", "--model",
    type=click.Choice(['tiny', 'base', 'small', 'medium', 'large']),
    default="base",
    help="🧠 Whisper model size (tiny=fastest, large=most accurate)"
)

@click.option("-l", "--language",
    type=str,
    help="🌍 Language code for transcription (e.g., en, es, fr, auto-detect)"
)

@click.option("--json",
    is_flag=True,
    help="📋 Output transcription results as JSON"
)

@click.option("--prefer-server",
    is_flag=True,
    help="🌐 Try WebSocket server first, fallback to direct"
)

@click.option("--server-only",
    is_flag=True,
    help="🔒 Require WebSocket server connection"
)

@click.option("--direct-only",
    is_flag=True,
    help="🖥️ Skip server, use direct Whisper processing"
)

@click.option("-o", "--output",
    type=click.Choice(['plain', 'json', 'matilda']),
    default="plain",
    help="📄 Output format (plain, json, matilda)"
)

@click.option("--debug",
    is_flag=True,
    help="🐞 Enable detailed debug logging"
)

@click.option("--config",
    type=str,
    help="⚙️ Path to custom config file"
)

def transcribe(ctx, audio_files, model, language, json, prefer_server, server_only, direct_only, output, debug, config):
    """🎯 🎯 Transcribe audio files to text"""
    
    # Check for built-in commands first
    
    # Standard command - use the existing hook pattern
    hook_name = f"on_transcribe"
    if app_hooks and hasattr(app_hooks, hook_name):
        # Call the hook with all parameters
        hook_func = getattr(app_hooks, hook_name)
        
        # Prepare arguments including global options
        kwargs = {}
        kwargs['command_name'] = 'transcribe'  # Pass command name for all commands
        
        
        kwargs['audio_files'] = audio_files
        
        
        
        
        
        
        
        kwargs['model'] = model
        
        
        
        
        kwargs['language'] = language
        
        
        
        
        kwargs['json'] = json
        
        
        
        
        kwargs['prefer_server'] = prefer_server
        
        
        
        
        kwargs['server_only'] = server_only
        
        
        
        
        kwargs['direct_only'] = direct_only
        
        
        
        
        kwargs['output'] = output
        
        
        
        
        kwargs['debug'] = debug
        
        
        
        
        kwargs['config'] = config
        
        
        
        # Add global options from context
        
        
        result = hook_func(**kwargs)
        return result
    else:
        # Default placeholder behavior
        click.echo(f"Executing transcribe command...")
        
        
        click.echo(f"  audio_files: {audio_files}")
        
        
        
        
        click.echo(f"  model: {model}")
        
        click.echo(f"  language: {language}")
        
        click.echo(f"  json: {json}")
        
        click.echo(f"  prefer-server: {prefer_server}")
        
        click.echo(f"  server-only: {server_only}")
        
        click.echo(f"  direct-only: {direct_only}")
        
        click.echo(f"  output: {output}")
        
        click.echo(f"  debug: {debug}")
        
        click.echo(f"  config: {config}")
        
        
    
    




@main.command()
@click.pass_context


@click.option("--json",
    is_flag=True,
    help="📋 Output status results as JSON"
)

def status(ctx, json):
    """✅ ✅ Check system health and device status"""
    
    # Check for built-in commands first
    
    # Standard command - use the existing hook pattern
    hook_name = f"on_status"
    if app_hooks and hasattr(app_hooks, hook_name):
        # Call the hook with all parameters
        hook_func = getattr(app_hooks, hook_name)
        
        # Prepare arguments including global options
        kwargs = {}
        kwargs['command_name'] = 'status'  # Pass command name for all commands
        
        
        
        
        
        
        kwargs['json'] = json
        
        
        
        # Add global options from context
        
        
        result = hook_func(**kwargs)
        return result
    else:
        # Default placeholder behavior
        click.echo(f"Executing status command...")
        
        
        
        click.echo(f"  json: {json}")
        
        
    
    




@main.group()
def model():
    """🧠 Manage Whisper models"""
    pass


@model.command()
@click.pass_context

@click.argument(
    "MODEL_NAME",
    type=click.Choice(['tiny', 'base', 'small', 'medium', 'large'])
)


@click.option("-f", "--force",
    is_flag=True,
    help="🔄 Force re-download even if model exists"
)

@click.option("-d", "--device",
    type=click.Choice(['cpu', 'cuda', 'auto']),
    default="auto",
    help="💻 Device type for model optimization (cpu, cuda, auto)"
)

def download(ctx, model_name, force, device):
    """Download a Whisper model"""
    # Check if hook function exists
    hook_name = f"on_model_download"
    if app_hooks and hasattr(app_hooks, hook_name):
        # Call the hook with all parameters
        hook_func = getattr(app_hooks, hook_name)
        
        # Prepare arguments including global options
        kwargs = {}
        kwargs['command_name'] = 'download'  # Pass command name for all commands
        
        
        kwargs['model_name'] = model_name
        
        
        
        
        kwargs['force'] = force
        
        kwargs['device'] = device
        
        
        
        # Add global options from context
        
        
        result = hook_func(**kwargs)
        return result
    else:
        # Default placeholder behavior
        click.echo(f"Executing download command...")
        
        
        click.echo(f"  model_name: {model_name}")
        
        
        
        
        click.echo(f"  force: {force}")
        
        click.echo(f"  device: {device}")
        
        

@model.command()
@click.pass_context


@click.option("--downloaded-only",
    is_flag=True,
    help="📦 Show only downloaded models"
)

@click.option("--json",
    is_flag=True,
    help="📋 Output as JSON"
)

def list(ctx, downloaded_only, json):
    """List available and downloaded models"""
    # Check if hook function exists
    hook_name = f"on_model_list"
    if app_hooks and hasattr(app_hooks, hook_name):
        # Call the hook with all parameters
        hook_func = getattr(app_hooks, hook_name)
        
        # Prepare arguments including global options
        kwargs = {}
        kwargs['command_name'] = 'list'  # Pass command name for all commands
        
        
        
        kwargs['downloaded_only'] = downloaded_only
        
        kwargs['json'] = json
        
        
        
        # Add global options from context
        
        
        result = hook_func(**kwargs)
        return result
    else:
        # Default placeholder behavior
        click.echo(f"Executing list command...")
        
        
        
        click.echo(f"  downloaded-only: {downloaded_only}")
        
        click.echo(f"  json: {json}")
        
        

@model.command()
@click.pass_context

@click.argument(
    "MODEL_NAME",
    type=click.Choice(['tiny', 'base', 'small', 'medium', 'large'])
)


@click.option("--json",
    is_flag=True,
    help="📋 Output as JSON"
)

def info(ctx, model_name, json):
    """Show detailed model information"""
    # Check if hook function exists
    hook_name = f"on_model_info"
    if app_hooks and hasattr(app_hooks, hook_name):
        # Call the hook with all parameters
        hook_func = getattr(app_hooks, hook_name)
        
        # Prepare arguments including global options
        kwargs = {}
        kwargs['command_name'] = 'info'  # Pass command name for all commands
        
        
        kwargs['model_name'] = model_name
        
        
        
        
        kwargs['json'] = json
        
        
        
        # Add global options from context
        
        
        result = hook_func(**kwargs)
        return result
    else:
        # Default placeholder behavior
        click.echo(f"Executing info command...")
        
        
        click.echo(f"  model_name: {model_name}")
        
        
        
        
        click.echo(f"  json: {json}")
        
        

@model.command()
@click.pass_context

@click.argument(
    "MODEL_NAME",
    type=click.Choice(['tiny', 'base', 'small', 'medium', 'large'])
)


@click.option("-f", "--force",
    is_flag=True,
    help="🔄 Skip confirmation prompt"
)

def remove(ctx, model_name, force):
    """Remove downloaded model"""
    # Check if hook function exists
    hook_name = f"on_model_remove"
    if app_hooks and hasattr(app_hooks, hook_name):
        # Call the hook with all parameters
        hook_func = getattr(app_hooks, hook_name)
        
        # Prepare arguments including global options
        kwargs = {}
        kwargs['command_name'] = 'remove'  # Pass command name for all commands
        
        
        kwargs['model_name'] = model_name
        
        
        
        
        kwargs['force'] = force
        
        
        
        # Add global options from context
        
        
        result = hook_func(**kwargs)
        return result
    else:
        # Default placeholder behavior
        click.echo(f"Executing remove command...")
        
        
        click.echo(f"  model_name: {model_name}")
        
        
        
        
        click.echo(f"  force: {force}")
        
        

@model.command()
@click.pass_context

@click.argument(
    "MODEL_NAME",
    type=click.Choice(['tiny', 'base', 'small', 'medium', 'large'])
)


@click.option("-t", "--duration",
    type=int,
    default=10,
    help="⏱️ Test duration in seconds"
)

@click.option("-d", "--device",
    type=click.Choice(['cpu', 'cuda', 'auto']),
    default="auto",
    help="💻 Device to test on (cpu, cuda, auto)"
)

@click.option("--json",
    is_flag=True,
    help="📋 Output results as JSON"
)

def benchmark(ctx, model_name, duration, device, json):
    """Test model performance"""
    # Check if hook function exists
    hook_name = f"on_model_benchmark"
    if app_hooks and hasattr(app_hooks, hook_name):
        # Call the hook with all parameters
        hook_func = getattr(app_hooks, hook_name)
        
        # Prepare arguments including global options
        kwargs = {}
        kwargs['command_name'] = 'benchmark'  # Pass command name for all commands
        
        
        kwargs['model_name'] = model_name
        
        
        
        
        kwargs['duration'] = duration
        
        kwargs['device'] = device
        
        kwargs['json'] = json
        
        
        
        # Add global options from context
        
        
        result = hook_func(**kwargs)
        return result
    else:
        # Default placeholder behavior
        click.echo(f"Executing benchmark command...")
        
        
        click.echo(f"  model_name: {model_name}")
        
        
        
        
        click.echo(f"  duration: {duration}")
        
        click.echo(f"  device: {device}")
        
        click.echo(f"  json: {json}")
        
        





@main.group()
def config():
    """⚙️  ⚙️ Adjust CLI settings and preferences"""
    pass


@config.command()
@click.pass_context


@click.option("--json",
    is_flag=True,
    help="📋 Output configuration as JSON"
)

def show(ctx, json):
    """👁️ Display current configuration"""
    # Check if hook function exists
    hook_name = f"on_config_show"
    if app_hooks and hasattr(app_hooks, hook_name):
        # Call the hook with all parameters
        hook_func = getattr(app_hooks, hook_name)
        
        # Prepare arguments including global options
        kwargs = {}
        kwargs['command_name'] = 'show'  # Pass command name for all commands
        
        
        
        kwargs['json'] = json
        
        
        
        # Add global options from context
        
        
        result = hook_func(**kwargs)
        return result
    else:
        # Default placeholder behavior
        click.echo(f"Executing show command...")
        
        
        
        click.echo(f"  json: {json}")
        
        

@config.command()
@click.pass_context

@click.argument(
    "KEY"
)


def get(ctx, key):
    """🔍 Retrieve configuration value"""
    # Check if hook function exists
    hook_name = f"on_config_get"
    if app_hooks and hasattr(app_hooks, hook_name):
        # Call the hook with all parameters
        hook_func = getattr(app_hooks, hook_name)
        
        # Prepare arguments including global options
        kwargs = {}
        kwargs['command_name'] = 'get'  # Pass command name for all commands
        
        
        kwargs['key'] = key
        
        
        
        
        # Add global options from context
        
        
        result = hook_func(**kwargs)
        return result
    else:
        # Default placeholder behavior
        click.echo(f"Executing get command...")
        
        
        click.echo(f"  key: {key}")
        
        
        

@config.command()
@click.pass_context

@click.argument(
    "KEY"
)

@click.argument(
    "VALUE"
)


def set(ctx, key, value):
    """✏️ Set a configuration value"""
    # Check if hook function exists
    hook_name = f"on_config_set"
    if app_hooks and hasattr(app_hooks, hook_name):
        # Call the hook with all parameters
        hook_func = getattr(app_hooks, hook_name)
        
        # Prepare arguments including global options
        kwargs = {}
        kwargs['command_name'] = 'set'  # Pass command name for all commands
        
        
        kwargs['key'] = key
        
        kwargs['value'] = value
        
        
        
        
        # Add global options from context
        
        
        result = hook_func(**kwargs)
        return result
    else:
        # Default placeholder behavior
        click.echo(f"Executing set command...")
        
        
        click.echo(f"  key: {key}")
        
        click.echo(f"  value: {value}")
        
        
        






















@main.group()
def server():
    """🔧 Basic server management"""
    pass


@server.command()
@click.pass_context
@click.option("-p", "--port", type=int, default=8769, help="🌐 Server port to check")
@click.option("--json", is_flag=True, help="📋 Output status as JSON")
def status(ctx, port, json):
    """Check if server is running"""
    hook_name = "on_server"
    if app_hooks and hasattr(app_hooks, hook_name):
        hook_func = getattr(app_hooks, hook_name)
        kwargs = {
            'command': 'status',
            'port': port,
            'json': json
        }
        return hook_func(**kwargs)
    else:
        click.echo(f"Executing server status command...")
        click.echo(f"  port: {port}")
        click.echo(f"  json: {json}")


@server.command()
@click.pass_context
@click.option("-p", "--port", type=int, default=8769, help="🌐 Server port")
@click.option("-h", "--host", type=str, default="0.0.0.0", help="🏠 Server host address")
@click.option("--json", is_flag=True, help="📋 Output result as JSON")
def start(ctx, port, host, json):
    """Start server (simple mode)"""
    hook_name = "on_server"
    if app_hooks and hasattr(app_hooks, hook_name):
        hook_func = getattr(app_hooks, hook_name)
        kwargs = {
            'command': 'start',
            'port': port,
            'host': host,
            'json': json
        }
        return hook_func(**kwargs)
    else:
        click.echo(f"Executing server start command...")
        click.echo(f"  port: {port}")
        click.echo(f"  host: {host}")
        click.echo(f"  json: {json}")


def cli_entry():
    """Entry point for the CLI when installed via pipx."""
    # Load plugins before running the CLI
    load_plugins(main)
    main()

if __name__ == "__main__":
    cli_entry()