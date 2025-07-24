#!/usr/bin/env python3
"""Configuration loader that reads from config.json"""
import json
import logging
import os
import platform
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Union


class ConfigLoader:
    """Load configuration from config.json"""

    def __init__(self, config_path: Optional[Union[str, Path]] = None) -> None:
        if config_path is None:
            config_path = self._find_config_file()

        # Store config file path for later use
        self.config_file = str(config_path)

        # Read and strip comments for JSONC support
        with open(config_path) as f:
            content = f.read()

        # Remove single-line comments (// ...)
        import re

        content = re.sub(r"//.*$", "", content, flags=re.MULTILINE)

        # Parse the cleaned JSON
        self._config = json.loads(content)

        self._platform = platform.system().lower()
        if self._platform == "darwin":
            self._platform = "darwin"  # Keep as darwin for config lookup

        # Cache commonly used values
        self.project_dir = str(Path(config_path).parent)
        self._setup_paths()

    def _find_config_file(self) -> Path:
        """Find config file in multiple locations"""
        
        # Method 1: Try package data (for installed packages)
        try:
            import importlib.resources
            try:
                # Python 3.9+ syntax
                package_data = importlib.resources.files("src") / "config.json"
                if package_data.is_file():
                    return package_data
            except AttributeError:
                # Python 3.8 fallback
                with importlib.resources.path("src", "config.json") as config_path:
                    if config_path.exists():
                        return config_path
        except (ImportError, FileNotFoundError, ModuleNotFoundError):
            pass
        
        # Method 2: Try relative to source code (development mode)
        current = Path(__file__).parent.parent.parent  # Go up 3 levels: core -> src -> project root
        for filename in ["config.jsonc", "config.json"]:
            config_path = current / filename
            if config_path.exists():
                return config_path
        
        # Method 3: Try current working directory
        for filename in ["config.jsonc", "config.json"]:
            config_path = Path.cwd() / filename
            if config_path.exists():
                return config_path
        
        # Method 4: Create a default config
        return self._create_default_config()

    def _create_default_config(self) -> Path:
        """Create a default config file in temp directory"""
        import tempfile
        import json
        
        default_config = {
            "whisper": {
                "model": "base",
                "device": "auto",
                "compute_type": "auto"
            },
            "server": {
                "websocket": {
                    "port": 8769,
                    "host": "localhost",
                    "bind_host": "0.0.0.0",
                    "connect_host": "localhost",
                    "auth_token": "stt-2024",
                    "jwt_secret_key": "GENERATE_RANDOM_SECRET_HERE",
                    "ssl": {
                        "enabled": False,
                        "cert_file": "ssl/server.crt",
                        "key_file": "ssl/server.key",
                        "verify_mode": "none",
                        "auto_generate_certs": True,
                        "cert_validity_days": 365
                    }
                }
            },
            "audio": {
                "sample_rate": 16000,
                "channels": 1,
                "streaming": {
                    "enabled": False,
                    "opus_bitrate": 24000,
                    "frame_size": 960,
                    "buffer_ms": 100
                }
            },
            "tools": {
                "audio": {
                    "linux": "arecord",
                    "darwin": "arecord",
                    "windows": "ffmpeg"
                }
            },
            "paths": {
                "venv": {
                    "linux": "venv/bin/python",
                    "darwin": "venv/bin/python",
                    "windows": "venv\\Scripts\\python.exe"
                },
                "temp_dir": {
                    "linux": "/tmp/goobits-stt",
                    "darwin": "/tmp/goobits-stt",
                    "windows": "%TEMP%\\goobits-stt"
                }
            },
            "modes": {
                "conversation": {
                    "vad_threshold": 0.5,
                    "min_speech_duration_s": 0.5,
                    "max_silence_duration_s": 1.0,
                    "speech_pad_duration_s": 0.3
                },
                "listen_once": {
                    "vad_threshold": 0.5,
                    "min_speech_duration_s": 0.3,
                    "max_silence_duration_s": 0.8,
                    "max_recording_duration_s": 30.0
                }
            },
            "text_formatting": {
                "filename_formats": {
                    "md": "UPPER_SNAKE",
                    "json": "lower_snake",
                    "py": "lower_snake",
                    "js": "camelCase",
                    "jsx": "camelCase",
                    "ts": "PascalCase",
                    "tsx": "PascalCase",
                    "java": "PascalCase",
                    "cs": "PascalCase",
                    "css": "kebab-case",
                    "scss": "kebab-case",
                    "sass": "kebab-case",
                    "less": "kebab-case",
                    "*": "lower_snake"
                }
            },
            "timing": {
                "server_startup_delay": 1.0,
                "server_stop_delay": 1.0
            }
        }
        
        # Create temporary config file
        temp_config = Path(tempfile.gettempdir()) / "goobits-stt-config.json"
        with open(temp_config, 'w') as f:
            json.dump(default_config, f, indent=2)
        
        return temp_config

    def _setup_paths(self) -> None:
        """Setup platform-specific paths"""
        # Virtual environment Python
        venv_path = self._config["paths"]["venv"][self._platform]
        self.venv_python = os.path.join(self.project_dir, venv_path)

        # Temp directory
        temp_dir_template = self._config["paths"]["temp_dir"][self._platform]
        if self._platform == "windows":
            # Expand Windows environment variables
            temp_dir_template = os.path.expandvars(temp_dir_template)
        self.temp_dir = temp_dir_template
        os.makedirs(self.temp_dir, mode=0o700, exist_ok=True)

    def get(self, key_path: str, default: Any = None) -> Any:
        """Get a value using dot notation (e.g., 'server.websocket.port')"""
        keys = key_path.split(".")
        value = self._config

        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default

        return value

    def __setitem__(self, key: str, value: Any) -> None:
        """Set a value in the config dictionary to support item assignment"""
        self._config[key] = value

    def __getitem__(self, key: str) -> Any:
        """Get a value from the config dictionary to support item access"""
        return self._config[key]

    def set(self, key_path: str, value: Any) -> None:
        """Set a value using dot notation (e.g., 'server.websocket.port')"""
        keys = key_path.split(".")
        target = self._config
        
        # Navigate to the parent of the target key
        for key in keys[:-1]:
            if key not in target:
                target[key] = {}
            target = target[key]
        
        # Set the final value
        target[keys[-1]] = value

    @property
    def websocket_port(self) -> int:
        # Check environment variable first, then config, then default
        env_port = os.environ.get("WEBSOCKET_SERVER_PORT")
        if env_port:
            return int(env_port)
        return int(self.get("server.websocket.port", 8769))

    @property
    def websocket_host(self) -> str:
        return str(self.get("server.websocket.host", "localhost"))

    @property
    def websocket_bind_host(self) -> str:
        return str(self.get("server.websocket.bind_host", "0.0.0.0"))

    @property
    def websocket_connect_host(self) -> str:
        return str(self.get("server.websocket.connect_host", "localhost"))

    @property
    def auth_token(self) -> str:
        return str(self.get("server.websocket.auth_token", "matilda-2024"))

    @property
    def jwt_secret_key(self) -> str:
        """Get JWT secret key with security-first approach.
        
        Priority order:
        1. Environment variable STT_JWT_SECRET (production)
        2. Config file value (development)
        3. Auto-generated temporary secret (fallback)
        """
        # 1. Environment variable (highest priority - production use)
        env_key = os.environ.get("STT_JWT_SECRET")
        if env_key and self._validate_secret_key(env_key):
            return env_key
        
        # 2. Config file (fallback for development)
        config_key = self.get("server.websocket.jwt_secret_key")
        if config_key and config_key != "GENERATE_RANDOM_SECRET_HERE" and self._validate_secret_key(config_key):
            return str(config_key)
        
        # 3. Auto-generate in memory only (no file modification)
        import logging
        logger = logging.getLogger(__name__)
        logger.warning("No valid JWT secret found in environment or config. Generating temporary secret for this session.")
        logger.info("For production, set STT_JWT_SECRET environment variable with a secure 32+ character secret.")
        return self._generate_secret_key()

    def _generate_secret_key(self) -> str:
        """Generate a cryptographically secure secret key."""
        import secrets

        return secrets.token_urlsafe(32)

    def _validate_secret_key(self, key: str) -> bool:
        """Validate that secret key meets minimum security requirements."""
        if not key or len(key) < 32:
            return False
        # Check for minimum entropy (not all same character, etc.)
        if len(set(key)) < 8:  # At least 8 unique characters
            return False
        return True


    @property
    def whisper_model(self) -> str:
        return str(self.get("whisper.model", "large-v3-turbo"))

    @property
    def whisper_device(self) -> str:
        return str(self.get("whisper.device", "cuda"))

    @property
    def whisper_compute_type(self) -> str:
        return str(self.get("whisper.compute_type", "float16"))

    def detect_cuda_support(self) -> tuple[bool, str]:
        """Detect if CUDA is available and supported by CTranslate2.

        Returns:
            (cuda_available, reason): Boolean indicating CUDA availability and reason string

        """
        try:
            import ctranslate2

            # Try to get CUDA device count
            cuda_device_count = ctranslate2.get_cuda_device_count()
            if cuda_device_count > 0:
                return True, f"CUDA available with {cuda_device_count} device(s)"
            return False, "CUDA not available (no devices detected)"
        except ImportError:
            return False, "CTranslate2 not installed"
        except AttributeError:
            return False, "CTranslate2 version does not support CUDA detection"
        except Exception as e:
            return False, f"CUDA detection failed: {e!s}"

    @property
    def whisper_device_auto(self) -> str:
        """Auto-detect the best device for Whisper based on CUDA availability."""
        configured_device = self.get("whisper.device", "auto")

        if configured_device != "auto":
            return str(configured_device)

        cuda_available, reason = self.detect_cuda_support()
        if cuda_available:
            return "cuda"
        return "cpu"

    @property
    def whisper_compute_type_auto(self) -> str:
        """Auto-detect the best compute type based on device."""
        device = self.whisper_device_auto
        configured_compute_type = self.get("whisper.compute_type", "auto")

        if configured_compute_type != "auto":
            return str(configured_compute_type)

        if device == "cuda":
            return "float16"
        return "int8"

    def get_hotkey_config(self, key_name: str) -> Dict[str, Any]:
        """Get configuration for a specific hotkey from array"""
        hotkeys = self.get("hotkeys", [])
        platform_key = self._get_platform_key()

        # Search for hotkey that matches the key_name on current platform
        for hotkey in hotkeys:
            if hotkey.get(platform_key, "").lower() == key_name.lower():
                return dict(hotkey)

        # Fallback: search all platforms for the key
        for hotkey in hotkeys:
            for platform_name in ["linux", "mac", "windows"]:
                if hotkey.get(platform_name, "").lower() == key_name.lower():
                    return dict(hotkey)

        return {}

    def get_all_hotkeys(self) -> List[Dict[str, Any]]:
        """Get all hotkey configurations"""
        return list(self.get("hotkeys", []))

    def get_hotkeys_for_platform(self, platform: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get all hotkeys for a specific platform"""
        if platform is None:
            platform = self._get_platform_key()

        hotkeys = self.get("hotkeys", [])
        result = []
        for hotkey in hotkeys:
            if platform in hotkey:
                result.append({"key": hotkey[platform], "name": hotkey.get("name", "Unknown"), "config": hotkey})
        return result

    def _get_platform_key(self) -> str:
        """Get platform key for hotkey config"""
        if self._platform == "darwin":
            return "mac"
        if self._platform == "win32":
            return "windows"
        return "linux"

    def get_audio_tool(self) -> str:
        """Get platform-specific audio tool"""
        tools = self.get(f"tools.audio.{self._platform}", "arecord")
        if isinstance(tools, list):
            # Return first available tool
            for tool in tools:
                # Could check if tool exists here
                return str(tool)
            return str(tools[0])
        return str(tools)

    def get_timing(self, name: str) -> float:
        """Get timing value with preset support"""
        typing_speed = self.get("text_insertion.typing_speed", "fast")

        # If using a preset, get values from presets
        if typing_speed != "custom" and name in ["typing_delay", "char_delay", "xdotool_delay"]:
            preset = self.get(f"typing_speed_presets.{typing_speed}")
            if preset and name in preset:
                return float(preset[name])

        # Fall back to custom timing values
        return float(self.get(f"timing.{name}", 0.1))

    def get_file_path(self, file_type: str, key_name: str = "f8") -> str:
        """Get file path for a specific file type and key"""
        # Check for legacy F8 naming
        if key_name.lower() == "f8" and self.get(f"file_naming.legacy_f8.{file_type}") is not None:
            template = self.get(f"file_naming.legacy_f8.{file_type}")
        else:
            template = self.get(f"file_naming.templates.{file_type}", f"matilda_{key_name}_{file_type}")

        # Replace {key} placeholder
        filename = template.replace("{key}", key_name.lower())

        # Log files go to logs directory, everything else to temp
        if file_type == "debug_log":
            log_dir = os.path.join(self.project_dir, "logs")
            os.makedirs(log_dir, mode=0o755, exist_ok=True)
            return os.path.join(log_dir, filename)

        return str(os.path.join(self.temp_dir, filename))

    def get_filter_phrases(self) -> List[str]:
        """Get text filter phrases"""
        return list(self.get("text_filtering.filter_phrases", []))

    def get_exact_filter_phrases(self) -> List[str]:
        """Get exact match filter phrases"""
        return list(self.get("text_filtering.exact_filter_phrases", []))

    def get_add_trailing_space(self) -> bool:
        """Get whether to add trailing space after text insertion"""
        return bool(self.get("text_insertion.add_trailing_space", True))

    def get_typing_speed(self) -> str:
        """Get current typing speed setting"""
        return str(self.get("text_insertion.typing_speed", "fast"))

    def get_available_typing_speeds(self) -> List[str]:
        """Get list of available typing speed presets"""
        presets = self.get("typing_speed_presets", {})
        return ["custom"] + list(presets.keys())

    def get_recording_controls_enabled(self) -> bool:
        """Get whether recording control keys are enabled"""
        return bool(self.get("recording_controls.enable_during_recording", True))

    def get_cancel_key(self) -> str:
        """Get the configured cancel key (default: escape)"""
        return str(self.get("recording_controls.cancel_key", "escape"))

    def get_end_with_enter_key(self) -> str:
        """Get the configured end-with-enter key (default: enter)"""
        return str(self.get("recording_controls.end_with_enter_key", "enter"))

    @property
    def ssl_enabled(self) -> bool:
        return bool(self.get("server.websocket.ssl.enabled", False))

    @property
    def ssl_cert_file(self) -> str:
        return str(self.get("server.websocket.ssl.cert_file", "ssl/server.crt"))

    @property
    def ssl_key_file(self) -> str:
        return str(self.get("server.websocket.ssl.key_file", "ssl/server.key"))

    @property
    def ssl_verify_mode(self) -> str:
        return str(self.get("server.websocket.ssl.verify_mode", "optional"))

    @property
    def ssl_auto_generate_certs(self) -> bool:
        return bool(self.get("server.websocket.ssl.auto_generate_certs", True))

    @property
    def ssl_cert_validity_days(self) -> int:
        return int(self.get("server.websocket.ssl.cert_validity_days", 365))

    # Audio streaming configuration
    @property
    def audio_streaming_enabled(self) -> bool:
        """Check if Opus audio streaming is enabled"""
        return bool(self.get("audio.streaming.enabled", False))

    @property
    def opus_bitrate(self) -> int:
        """Get Opus encoder bitrate"""
        return int(self.get("audio.streaming.opus_bitrate", 24000))

    @property
    def opus_frame_size(self) -> int:
        """Get Opus frame size in samples"""
        return int(self.get("audio.streaming.frame_size", 960))

    @property
    def streaming_buffer_ms(self) -> int:
        """Get client-side buffering in milliseconds"""
        return int(self.get("audio.streaming.buffer_ms", 100))

    @property
    def audio_sample_rate(self) -> int:
        """Get audio sample rate"""
        return int(self.get("audio.sample_rate", 16000))

    @property
    def audio_channels(self) -> int:
        """Get number of audio channels"""
        return int(self.get("audio.channels", 1))

    # Embedded server configuration
    @property
    def embedded_server_enabled(self) -> Union[bool, str]:
        """Get embedded server enabled setting"""
        value = self.get("server.embedded_server.enabled", "auto")
        if isinstance(value, bool):
            return value
        return str(value)

    @property
    def auto_detect_whisper(self) -> bool:
        """Get whether to auto-detect whisper for server mode"""
        return bool(self.get("server.embedded_server.auto_detect_whisper", True))

    @property
    def visualizer_engine(self) -> str:
        """Get the visualizer engine to use (legacy, instant, or web)"""
        # First check the new unified location
        engine = self.get("visualizer.engine")
        if engine is not None:
            return str(engine)

        # Fallback to old location for backward compatibility
        return str(self.get("visualizers.engine", "legacy"))

    @property
    def visualizer_enabled(self) -> bool:
        """Get whether visualizer is enabled"""
        return bool(self.get("visualizer.enabled", True))

    # Additional properties needed for daemon functionality
    @property
    def filter_phrases(self) -> List[str]:
        return self.get_filter_phrases()

    @property
    def exact_filter_phrases(self) -> List[str]:
        return self.get_exact_filter_phrases()

    # Timing properties needed for daemon functionality
    @property
    def typing_delay(self) -> float:
        return self.get_timing("typing_delay")

    @property
    def focus_delay(self) -> float:
        return self.get_timing("focus_delay")

    @property
    def char_delay(self) -> float:
        return self.get_timing("char_delay")

    @property
    def xdotool_delay(self) -> float:
        return self.get_timing("xdotool_delay")

    # Minimal properties needed for current functionality
    @property
    def server_startup_delay(self) -> float:
        return self.get_timing("server_startup_delay")

    @property
    def server_stop_delay(self) -> float:
        return self.get_timing("server_stop_delay")

    def get_visualizer_file(self, key_name: str = "f8") -> str:
        return self.get_file_path("visualizer_pid", key_name)

    def get_audio_file(self, key_name: str = "f8") -> str:
        return self.get_file_path("audio", key_name)

    def get_visualizer_command(self, key_name: str, pid_file: str) -> List[str]:
        """Get complete visualizer command with arguments"""
        script_path = os.path.join(self.project_dir, "src", "visualizers", "visualizer.py")
        hotkey_config = self.get_hotkey_config(key_name.lower())
        # Use new "display" field with fallback to old "visualizer" field
        display_type = hotkey_config.get("display", hotkey_config.get("visualizer", "circular"))
        return [self.venv_python, script_path, display_type, pid_file, "--key", key_name.lower()]

    @property
    def filename_formats(self) -> Dict[str, str]:
        """Get filename formatting rules per extension"""
        return dict(self.get(
            "text_formatting.filename_formats",
            {
                "md": "UPPER_SNAKE",
                "json": "lower_snake",
                "jsonl": "lower_snake",
                "py": "lower_snake",
                "*": "lower_snake",  # Default fallback
            },
        ))

    def get_filename_format(self, extension: str) -> str:
        """Get formatting rule for a specific file extension"""
        formats = self.filename_formats
        # Try exact match first, then fallback to wildcard
        return formats.get(extension.lower(), formats.get("*", "lower_snake"))

    def save(self) -> None:
        """Save the current configuration back to the config file"""
        import json
        with open(self.config_file, 'w') as f:
            json.dump(self._config, f, indent=2)


# Create a global instance for backward compatibility
_config_loader: Optional[ConfigLoader] = None


def get_config() -> ConfigLoader:
    """Get the global config loader instance"""
    global _config_loader
    if _config_loader is None:
        _config_loader = ConfigLoader()
    return _config_loader


# LegacyConfig removed - use get_config() instead


# ========================= CENTRALIZED LOGGING SETUP =========================


def setup_logging(
    module_name: str,
    log_level: str = "INFO",
    include_console: bool = True,
    include_file: bool = True,
    log_filename: Optional[str] = None,
) -> logging.Logger:
    """Setup standardized logging for STT modules.

    Args:
        module_name: Name of the module (usually __name__)
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
        include_console: Whether to log to console
        include_file: Whether to log to file
        log_filename: Optional custom log filename (defaults to module-based name)

    Returns:
        Configured logger instance

    """
    logger = logging.getLogger(module_name)

    # Avoid duplicate handlers if already configured
    if logger.handlers:
        return logger

    logger.setLevel(getattr(logging, log_level.upper()))

    # Create formatter
    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S")

    # Console handler
    if include_console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
    
    # Prevent propagation to root logger to avoid duplicate console output
    logger.propagate = False

    # File handler
    if include_file:
        # Ensure logs directory exists
        logs_dir = Path(get_config().project_dir) / "logs"
        logs_dir.mkdir(exist_ok=True)

        # Generate log filename
        if log_filename is None:
            module_basename = module_name.split(".")[-1] if "." in module_name else module_name
            log_filename = f"{module_basename}.txt"

        log_path = logs_dir / log_filename
        file_handler = logging.FileHandler(log_path)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger


def get_logger(module_name: str) -> logging.Logger:
    """Get a logger for a module with default STT settings."""
    return setup_logging(module_name)


def load_config(config_path: Optional[Union[str, Path]] = None) -> ConfigLoader:
    """Load configuration from config file (alias for creating ConfigLoader)."""
    return ConfigLoader(config_path)


if __name__ == "__main__":
    # Test the config loader
    logger = get_logger(__name__)
    loader = get_config()
    logger.info(f"WebSocket Port: {loader.websocket_port}")
    logger.info(f"Whisper Model: {loader.whisper_model}")
    logger.info(f"F8 Config: {loader.get_hotkey_config('f8')}")
    logger.info(f"Audio Tool: {loader.get_audio_tool()}")
    logger.info(f"Recording file (f8): {loader.get_file_path('recording_pid', 'f8')}")
    logger.info(f"Recording file (f9): {loader.get_file_path('recording_pid', 'f9')}")
