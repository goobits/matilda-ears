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
try:
    # Try to import from the project root directory
    script_dir = Path(__file__).parent.parent.parent
    hooks_path = script_dir / "app_hooks.py"
    
    if hooks_path.exists():
        spec = importlib.util.spec_from_file_location("app_hooks", hooks_path)
        app_hooks = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(app_hooks)
    else:
        # Try to import from Python path
        import app_hooks
except (ImportError, FileNotFoundError):
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
        Path.cwd() / "setup.sh",  # Current directory
        Path(__file__).parent.parent / "setup.sh",  # Package directory
        Path.home() / ".local" / "share" / "goobits-stt" / "setup.sh",  # User data
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
        toml_path = Path(__file__).parent.parent / "pyproject.toml"
        if toml_path.exists():
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
    return "1.0.1"


def show_help_json(ctx, param, value):
    """Callback for --help-json option."""
    if not value or ctx.resilient_parsing:
        return
    # The triple quotes are important to correctly handle the multi-line JSON string
    click.echo('''{
  "name": "GOOBITS STT CLI",
  "version": "1.0.1",
  "display_version": true,
  "tagline": "Speech to Text",
  "description": "Real-time speech transcription powered by Whisper",
  "icon": "🎤",
  "header_sections": [
    {
      "title": "💡 Quick Start",
      "icon": null,
      "items": [
        {
          "item": "stt listen",
          "desc": "Record once and transcribe",
          "style": "example"
        },
        {
          "item": "stt live",
          "desc": "Interactive conversation mode",
          "style": "example"
        },
        {
          "item": "stt serve",
          "desc": "Start WebSocket server",
          "style": "example"
        },
        {
          "item": "stt models",
          "desc": "List available Whisper models",
          "style": "example"
        }
      ]
    },
    {
      "title": "🔑 Initial Setup",
      "icon": null,
      "items": [
        {
          "item": "1. Check status",
          "desc": "stt status",
          "style": "setup"
        },
        {
          "item": "2. Select model",
          "desc": "stt config set model base",
          "style": "setup"
        },
        {
          "item": "3. Start listening",
          "desc": "stt listen",
          "style": "setup"
        }
      ]
    }
  ],
  "footer_note": "📚 For detailed help on a command, run: [color(2)]stt [COMMAND][/color(2)] [#ff79c6]--help[/#ff79c6]",
  "options": [],
  "commands": {
    "listen": {
      "desc": "Record once and transcribe",
      "icon": "🎙️",
      "is_default": false,
      "lifecycle": "standard",
      "args": [],
      "options": [
        {
          "name": "model",
          "short": "m",
          "type": "str",
          "desc": "Whisper model size",
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
          "desc": "Language code (e.g., en, es, fr)",
          "default": null,
          "choices": null,
          "multiple": false
        },
        {
          "name": "device",
          "short": "d",
          "type": "str",
          "desc": "Audio input device name",
          "default": null,
          "choices": null,
          "multiple": false
        },
        {
          "name": "hold-to-talk",
          "short": null,
          "type": "str",
          "desc": "Hold key to record (e.g., space, f8)",
          "default": null,
          "choices": null,
          "multiple": false
        },
        {
          "name": "no-formatting",
          "short": null,
          "type": "bool",
          "desc": "Disable text formatting",
          "default": false,
          "choices": null,
          "multiple": false
        },
        {
          "name": "sample-rate",
          "short": null,
          "type": "int",
          "desc": "Audio sample rate in Hz",
          "default": 16000,
          "choices": null,
          "multiple": false
        },
        {
          "name": "json",
          "short": null,
          "type": "flag",
          "desc": "Output as JSON",
          "default": null,
          "choices": null,
          "multiple": false
        },
        {
          "name": "debug",
          "short": null,
          "type": "flag",
          "desc": "Enable debug logging",
          "default": null,
          "choices": null,
          "multiple": false
        },
        {
          "name": "config",
          "short": null,
          "type": "str",
          "desc": "Path to config file",
          "default": null,
          "choices": null,
          "multiple": false
        }
      ],
      "subcommands": null
    },
    "live": {
      "desc": "Interactive conversation mode",
      "icon": "💬",
      "is_default": false,
      "lifecycle": "standard",
      "args": [],
      "options": [
        {
          "name": "model",
          "short": "m",
          "type": "str",
          "desc": "Whisper model size",
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
          "desc": "Language code (e.g., en, es, fr)",
          "default": null,
          "choices": null,
          "multiple": false
        },
        {
          "name": "device",
          "short": "d",
          "type": "str",
          "desc": "Audio input device name",
          "default": null,
          "choices": null,
          "multiple": false
        },
        {
          "name": "tap-to-talk",
          "short": null,
          "type": "str",
          "desc": "Key to tap for push-to-talk (e.g., f8)",
          "default": null,
          "choices": null,
          "multiple": false
        },
        {
          "name": "no-formatting",
          "short": null,
          "type": "bool",
          "desc": "Disable text formatting",
          "default": false,
          "choices": null,
          "multiple": false
        },
        {
          "name": "sample-rate",
          "short": null,
          "type": "int",
          "desc": "Audio sample rate in Hz",
          "default": 16000,
          "choices": null,
          "multiple": false
        },
        {
          "name": "json",
          "short": null,
          "type": "flag",
          "desc": "Output as JSON",
          "default": null,
          "choices": null,
          "multiple": false
        },
        {
          "name": "debug",
          "short": null,
          "type": "flag",
          "desc": "Enable debug logging",
          "default": null,
          "choices": null,
          "multiple": false
        },
        {
          "name": "config",
          "short": null,
          "type": "str",
          "desc": "Path to config file",
          "default": null,
          "choices": null,
          "multiple": false
        }
      ],
      "subcommands": null
    },
    "serve": {
      "desc": "Start transcription server",
      "icon": "🌐",
      "is_default": false,
      "lifecycle": "standard",
      "args": [],
      "options": [
        {
          "name": "port",
          "short": "p",
          "type": "int",
          "desc": "Port to run server on",
          "default": 8769,
          "choices": null,
          "multiple": false
        },
        {
          "name": "host",
          "short": "h",
          "type": "str",
          "desc": "Host to bind to",
          "default": "0.0.0.0",
          "choices": null,
          "multiple": false
        },
        {
          "name": "debug",
          "short": null,
          "type": "flag",
          "desc": "Enable debug logging",
          "default": null,
          "choices": null,
          "multiple": false
        },
        {
          "name": "config",
          "short": null,
          "type": "str",
          "desc": "Path to config file",
          "default": null,
          "choices": null,
          "multiple": false
        }
      ],
      "subcommands": null
    },
    "status": {
      "desc": "Check system and device status",
      "icon": "✅",
      "is_default": false,
      "lifecycle": "standard",
      "args": [],
      "options": [
        {
          "name": "json",
          "short": null,
          "type": "flag",
          "desc": "Output as JSON",
          "default": null,
          "choices": null,
          "multiple": false
        }
      ],
      "subcommands": null
    },
    "models": {
      "desc": "List available Whisper models",
      "icon": "📦",
      "is_default": false,
      "lifecycle": "standard",
      "args": [],
      "options": [
        {
          "name": "json",
          "short": null,
          "type": "flag",
          "desc": "Output as JSON",
          "default": null,
          "choices": null,
          "multiple": false
        }
      ],
      "subcommands": null
    },
    "config": {
      "desc": "Manage configuration",
      "icon": "⚙️",
      "is_default": false,
      "lifecycle": "standard",
      "args": [],
      "options": [],
      "subcommands": {
        "show": {
          "desc": "Show all configuration",
          "icon": null,
          "is_default": false,
          "lifecycle": "standard",
          "args": [],
          "options": [
            {
              "name": "json",
              "short": null,
              "type": "flag",
              "desc": "Output as JSON",
              "default": null,
              "choices": null,
              "multiple": false
            }
          ],
          "subcommands": null
        },
        "get": {
          "desc": "Get configuration value",
          "icon": null,
          "is_default": false,
          "lifecycle": "standard",
          "args": [
            {
              "name": "key",
              "desc": "Configuration key",
              "nargs": null,
              "choices": null,
              "required": true
            }
          ],
          "options": [],
          "subcommands": null
        },
        "set": {
          "desc": "Set configuration value",
          "icon": null,
          "is_default": false,
          "lifecycle": "standard",
          "args": [
            {
              "name": "key",
              "desc": "Configuration key",
              "nargs": null,
              "choices": null,
              "required": true
            },
            {
              "name": "value",
              "desc": "Configuration value",
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
        "models"
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
    """🎤 [bold color(6)]GOOBITS STT CLI v1.0.1[/bold color(6)] - Speech to Text

    
    \b
    [#B3B8C0]Real-time speech transcription powered by Whisper[/#B3B8C0]
    

    
    \b
    [bold yellow]💡 Quick Start:[/bold yellow][green]stt listen  [/green] [italic][#B3B8C0]# Record once and transcribe[/#B3B8C0][/italic][green]stt live    [/green] [italic][#B3B8C0]# Interactive conversation mode[/#B3B8C0][/italic][green]stt serve   [/green] [italic][#B3B8C0]# Start WebSocket server[/#B3B8C0][/italic][green]stt models  [/green] [italic][#B3B8C0]# List available Whisper models[/#B3B8C0][/italic]
    \b
    [bold yellow]🔑 Initial Setup:[/bold yellow]1. Check status:    [green]stt status[/green]2. Select model:    [green]stt config set model base[/green]3. Start listening: [green]stt listen[/green]
    \b
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


# Set command groups after main function is defined
click.rich_click.COMMAND_GROUPS = {
    "main": [
        
        {
            "name": "Recording Modes",
            "commands": ['listen', 'live'],
        },
        
        {
            "name": "Server & Processing",
            "commands": ['serve'],
        },
        
        {
            "name": "System",
            "commands": ['status', 'models'],
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
    help="Whisper model size"
)

@click.option("-l", "--language",
    type=str,
    help="Language code (e.g., en, es, fr)"
)

@click.option("-d", "--device",
    type=str,
    help="Audio input device name"
)

@click.option("--hold-to-talk",
    type=str,
    help="Hold key to record (e.g., space, f8)"
)

@click.option("--no-formatting",
    type=bool,
    default=False,
    help="Disable text formatting"
)

@click.option("--sample-rate",
    type=int,
    default=16000,
    help="Audio sample rate in Hz"
)

@click.option("--json",
    is_flag=True,
    help="Output as JSON"
)

@click.option("--debug",
    is_flag=True,
    help="Enable debug logging"
)

@click.option("--config",
    type=str,
    help="Path to config file"
)

def listen(ctx, model, language, device, hold_to_talk, no_formatting, sample_rate, json, debug, config):
    """🎙️  Record once and transcribe"""
    
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
    help="Whisper model size"
)

@click.option("-l", "--language",
    type=str,
    help="Language code (e.g., en, es, fr)"
)

@click.option("-d", "--device",
    type=str,
    help="Audio input device name"
)

@click.option("--tap-to-talk",
    type=str,
    help="Key to tap for push-to-talk (e.g., f8)"
)

@click.option("--no-formatting",
    type=bool,
    default=False,
    help="Disable text formatting"
)

@click.option("--sample-rate",
    type=int,
    default=16000,
    help="Audio sample rate in Hz"
)

@click.option("--json",
    is_flag=True,
    help="Output as JSON"
)

@click.option("--debug",
    is_flag=True,
    help="Enable debug logging"
)

@click.option("--config",
    type=str,
    help="Path to config file"
)

def live(ctx, model, language, device, tap_to_talk, no_formatting, sample_rate, json, debug, config):
    """💬 Interactive conversation mode"""
    
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
    help="Port to run server on"
)

@click.option("-h", "--host",
    type=str,
    default="0.0.0.0",
    help="Host to bind to"
)

@click.option("--debug",
    is_flag=True,
    help="Enable debug logging"
)

@click.option("--config",
    type=str,
    help="Path to config file"
)

def serve(ctx, port, host, debug, config):
    """🌐 Start transcription server"""
    
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


@click.option("--json",
    is_flag=True,
    help="Output as JSON"
)

def status(ctx, json):
    """✅ Check system and device status"""
    
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
        
        
    
    




@main.command()
@click.pass_context


@click.option("--json",
    is_flag=True,
    help="Output as JSON"
)

def models(ctx, json):
    """📦 List available Whisper models"""
    
    # Check for built-in commands first
    
    # Standard command - use the existing hook pattern
    hook_name = f"on_models"
    if app_hooks and hasattr(app_hooks, hook_name):
        # Call the hook with all parameters
        hook_func = getattr(app_hooks, hook_name)
        
        # Prepare arguments including global options
        kwargs = {}
        kwargs['command_name'] = 'models'  # Pass command name for all commands
        
        
        
        
        
        
        kwargs['json'] = json
        
        
        
        # Add global options from context
        
        
        result = hook_func(**kwargs)
        return result
    else:
        # Default placeholder behavior
        click.echo(f"Executing models command...")
        
        
        
        click.echo(f"  json: {json}")
        
        
    
    




@main.group()
def config():
    """⚙️  Manage configuration"""
    pass


@config.command()
@click.pass_context


@click.option("--json",
    is_flag=True,
    help="Output as JSON"
)

def show(ctx, json):
    """Show all configuration"""
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
    """Get configuration value"""
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
    """Set configuration value"""
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
        
        
        






















def cli_entry():
    """Entry point for the CLI when installed via pipx."""
    # Load plugins before running the CLI
    load_plugins(main)
    main()

if __name__ == "__main__":
    cli_entry()