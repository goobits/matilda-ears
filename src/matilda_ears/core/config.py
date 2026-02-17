#!/usr/bin/env python3
"""Configuration loader that reads from config files."""
import logging
import os
import platform
from pathlib import Path
from typing import Any

import tomllib

DEFAULT_CONFIG: dict[str, Any] = {
    "transcription": {"backend": "auto"},
    "whisper": {"model": "base", "device": "auto", "compute_type": "auto", "word_timestamps": True},
    "huggingface": {
        "model": "openai/whisper-tiny",
        "device": "cpu",
        "torch_dtype": "float32",
        "chunk_length_s": 30,
        "batch_size": 1,
    },
    "parakeet": {"model": "mlx-community/parakeet-tdt-0.6b-v3"},
    "streaming": {
        "enabled": False,
        "backend": "auto",
        "simul_streaming": {
            "language": "en",
            "model_size": "tiny",
            "frame_threshold": 25,
            "audio_max_len": 30.0,
            "segment_length": 1.0,
            "never_fire": True,
            "vad_enabled": True,
            "vad_threshold": 0.5,
        },
        "parakeet": {"context_size": (128, 128), "depth": 1},
    },
    "server": {
        "websocket": {
            "port": 3212,
            "host": "localhost",
            "bind_host": "0.0.0.0",
            "connect_host": "localhost",
            "max_message_mb": 50,
            "jwt_secret_key": "GENERATE_RANDOM_SECRET_HERE",
            "jwt_token": "",
            "ssl": {
                "enabled": False,
                "cert_file": "ssl/server.crt",
                "key_file": "ssl/server.key",
                "verify_mode": "none",
                "auto_generate_certs": True,
                "cert_validity_days": 365,
            },
        }
    },
    "audio": {
        "sample_rate": 16000,
        "channels": 1,
        "streaming": {"enabled": False, "opus_bitrate": 24000, "frame_size": 960, "buffer_ms": 100},
    },
    "tools": {"audio": {"linux": "arecord", "darwin": "ffmpeg", "windows": "ffmpeg"}},
    "paths": {
        "venv": {
            "linux": "venv/bin/python",
            "darwin": "venv/bin/python",
            "windows": "venv\\Scripts\\python.exe",
        },
        "temp_dir": {
            "linux": "/tmp/goobits-matilda-ears",
            "darwin": "/tmp/goobits-matilda-ears",
            "windows": "%TEMP%\\goobits-matilda-ears",
        },
    },
    "modes": {
        "conversation": {
            "vad_threshold": 0.5,
            "hysteresis": 0.15,
            "min_speech_duration_s": 0.5,
            "max_silence_duration_s": 1.0,
            "max_speech_duration_s": 30.0,
            "speech_pad_duration_s": 0.3,
        },
        "listen_once": {
            "vad_threshold": 0.5,
            "hysteresis": 0.15,
            "min_speech_duration_s": 0.3,
            "max_silence_duration_s": 0.8,
            "max_speech_duration_s": 30.0,
            "max_recording_duration_s": 30.0,
        },
        "wake_word": {
            "enabled": False,
            "agent_aliases": [{"agent": "Matilda", "aliases": ["hey_matilda", "computer", "hey_jarvis"]}],
            "agents": ["Matilda"],
            "threshold": 0.5,
            "vad_threshold": 0.5,
            "hysteresis": 0.2,
            "max_speech_duration_s": 10.0,
            "min_speech_duration": 0.25,
            "silence_duration": 0.8,
            "noise_suppression": True,
        },
    },
    "ears_tuner": {
        "enabled": False,
        "formatter": "noop",
        # Formatting locale for the Ears Tuner output (separate from STT backend language).
        "locale": "en-US",
        "formatting": {
            "locale": "en-US",
            "imperial_length_style": "ft_in",
            "emoji_requires_keyword": True,
            "unicode_mode": "unicode",
            "collapse_repeated_words": True,
            "collapse_repeated_words_min_run": 2,
            "max_chars_for_punctuation": 800,
            "max_chars_for_full_pipeline": 4000,
        },
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
            "*": "lower_snake",
        },
    },
    "timing": {"server_startup_delay": 1.0, "server_stop_delay": 1.0},
}


class ConfigLoader:
    """Load configuration from config files."""

    def __init__(self, config_path: str | Path | None = None) -> None:
        if config_path is None:
            config_path = self._default_config_path()

        self.config_file = str(config_path)
        config_path = Path(config_path)
        if config_path.exists():
            with open(config_path, "rb") as f:
                full_config = tomllib.load(f)
            ears_config = full_config.get("ears", {})
        else:
            ears_config = {}

        self._config = self._merge_dicts(DEFAULT_CONFIG, ears_config)

        # Formatting locale override (for Ears Tuner output).
        # This is intentionally separate from STT backend language (often just "en").
        env_locale = os.environ.get("MATILDA_LOCALE")
        if env_locale:
            self._config.setdefault("ears_tuner", {})
            if isinstance(self._config["ears_tuner"], dict):
                self._config["ears_tuner"]["locale"] = env_locale
                formatting = self._config["ears_tuner"].setdefault("formatting", {})
                if isinstance(formatting, dict):
                    formatting["locale"] = env_locale

        self._platform = platform.system().lower()
        if self._platform == "darwin":
            self._platform = "darwin"  # Keep as darwin for config lookup

        self.project_dir = str(Path(__file__).resolve().parents[2])
        self._setup_paths()

    def _default_config_path(self) -> Path:
        env_path = os.environ.get("MATILDA_CONFIG")
        if env_path:
            return Path(env_path)
        return Path.home() / ".matilda" / "config.toml"

    def _setup_paths(self) -> None:
        """Setup platform-specific paths"""
        # Virtual environment Python
        venv_path = self.get(f"paths.venv.{self._platform}", "venv/bin/python")
        self.venv_python = os.path.join(self.project_dir, venv_path)

        # Temp directory
        if os.environ.get("EARS_TEMP_DIR"):
            self.temp_dir = os.environ["EARS_TEMP_DIR"]
        else:
            temp_dir_template = self.get(f"paths.temp_dir.{self._platform}", "/tmp/goobits-matilda-ears")
            if self._platform == "windows":
                # Expand Windows environment variables
                temp_dir_template = os.path.expandvars(temp_dir_template)
            self.temp_dir = temp_dir_template

        os.makedirs(self.temp_dir, mode=0o700, exist_ok=True)

    def _merge_dicts(self, base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
        merged = base.copy()
        for key, value in override.items():
            if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
                merged[key] = self._merge_dicts(merged[key], value)
            else:
                merged[key] = value
        return merged

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

    @property
    def websocket_port(self) -> int:
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
    def jwt_token(self) -> str:
        return str(self.get("server.websocket.jwt_token", ""))

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
        logger = logging.getLogger(__name__)
        logger.info("No valid JWT secret found in environment or config. Generating temporary secret for this session.")
        # logger.info("For production, set STT_JWT_SECRET environment variable with a secure 32+ character secret.")
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
        # Check environment variable first
        env_model = os.environ.get("EARS_MODEL")
        if env_model:
            return env_model
        return str(self.get("whisper.model", "large-v3-turbo"))

    @property
    def whisper_device(self) -> str:
        # Check environment variable first
        env_device = os.environ.get("EARS_DEVICE")
        if env_device:
            return env_device
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

    @property
    def transcription_backend(self) -> str:
        """Get the transcription backend to use.

        If set to 'auto', automatically selects the best backend:
        - parakeet on Apple Silicon (if available)
        - faster_whisper on other platforms

        Prioritizes 'EARS_BACKEND' environment variable if set.

        Returns:
            Backend name: 'faster_whisper', 'parakeet', or 'huggingface'

        """
        # Check environment variable first
        env_backend = os.environ.get("EARS_BACKEND")
        if env_backend:
            return env_backend

        backend = str(self.get("transcription.backend", "auto"))

        if backend == "auto":
            # Import here to avoid circular imports
            from matilda_ears.transcription.backends import get_recommended_backend

            return get_recommended_backend()

        return backend

    def get_hotkey_config(self, key_name: str) -> dict[str, Any]:
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

    def get_all_hotkeys(self) -> list[dict[str, Any]]:
        """Get all hotkey configurations"""
        return list(self.get("hotkeys", []))

    def get_hotkeys_for_platform(self, platform: str | None = None) -> list[dict[str, Any]]:
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
        template = self.get(f"file_naming.templates.{file_type}", f"matilda_{key_name}_{file_type}")

        # Replace {key} placeholder
        filename = template.replace("{key}", key_name.lower())

        # Log files go to logs directory, everything else to temp
        if file_type == "debug_log":
            log_dir = os.path.join(self.project_dir, "logs")
            os.makedirs(log_dir, mode=0o755, exist_ok=True)
            return os.path.join(log_dir, filename)

        return str(os.path.join(self.temp_dir, filename))

    def get_filter_phrases(self) -> list[str]:
        """Get text filter phrases"""
        return list(self.get("text_filtering.filter_phrases", []))

    def get_exact_filter_phrases(self) -> list[str]:
        """Get exact match filter phrases"""
        return list(self.get("text_filtering.exact_filter_phrases", []))

    def get_add_trailing_space(self) -> bool:
        """Get whether to add trailing space after text insertion"""
        return bool(self.get("text_insertion.add_trailing_space", True))

    def get_typing_speed(self) -> str:
        """Get current typing speed setting"""
        return str(self.get("text_insertion.typing_speed", "fast"))

    def get_available_typing_speeds(self) -> list[str]:
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

    # Wake word configuration
    @property
    def wake_word_enabled(self) -> bool:
        """Check if wake word detection is enabled"""
        return bool(self.get("modes.wake_word.enabled", False))

    @property
    def wake_word_threshold(self) -> float:
        """Get wake word detection threshold"""
        return float(self.get("modes.wake_word.threshold", 0.5))

    @property
    def wake_word_silence_duration(self) -> float:
        """Get silence duration to end utterance capture"""
        return float(self.get("modes.wake_word.silence_duration", 0.8))

    @property
    def wake_word_noise_suppression(self) -> bool:
        """Check if noise suppression is enabled for wake word"""
        return bool(self.get("modes.wake_word.noise_suppression", True))

    # Embedded server configuration
    @property
    def embedded_server_enabled(self) -> bool | str:
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
        """Get the visualizer engine to use (instant or web)"""
        return str(self.get("visualizer.engine", "instant"))

    @property
    def visualizer_enabled(self) -> bool:
        """Get whether visualizer is enabled"""
        return bool(self.get("visualizer.enabled", True))

    # Additional properties needed for daemon functionality
    @property
    def filter_phrases(self) -> list[str]:
        return self.get_filter_phrases()

    @property
    def exact_filter_phrases(self) -> list[str]:
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

    def get_visualizer_command(self, key_name: str, pid_file: str) -> list[str]:
        """Get complete visualizer command with arguments"""
        script_path = os.path.join(self.project_dir, "src", "visualizers", "visualizer.py")
        hotkey_config = self.get_hotkey_config(key_name.lower())
        # Use new "display" field with fallback to old "visualizer" field
        display_type = hotkey_config.get("display", hotkey_config.get("visualizer", "circular"))
        return [self.venv_python, script_path, display_type, pid_file, "--key", key_name.lower()]

    @property
    def filename_formats(self) -> dict[str, str]:
        """Get filename formatting rules per extension"""
        return dict(
            self.get(
                "ears_tuner.filename_formats",
                {
                    "md": "UPPER_SNAKE",
                    "json": "lower_snake",
                    "jsonl": "lower_snake",
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
                    "*": "lower_snake",  # Default fallback
                },
            )
        )

    def get_filename_format(self, extension: str) -> str:
        """Get formatting rule for a specific file extension"""
        formats = self.filename_formats
        # Try exact match first, then fallback to wildcard
        return formats.get(extension.lower(), formats.get("*", "lower_snake"))

    @property
    def ears_tuner_formatting(self) -> dict[str, Any]:
        return dict(
            self.get(
                "ears_tuner.formatting",
                {
                    "locale": self.get("ears_tuner.locale", "en-US"),
                    "imperial_length_style": "ft_in",
                    "emoji_requires_keyword": True,
                    "unicode_mode": "unicode",
                    "collapse_repeated_words": True,
                    "collapse_repeated_words_min_run": 3,
                    "max_chars_for_punctuation": 800,
                    "max_chars_for_full_pipeline": 4000,
                },
            )
        )


# Global singleton instance
_config_loader: ConfigLoader | None = None


def get_config() -> ConfigLoader:
    """Get the global config loader instance"""
    global _config_loader
    if _config_loader is None:
        _config_loader = ConfigLoader()
    return _config_loader


# Re-export logging functions
from .logging import get_logger, setup_logging  # noqa: E402, F401


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
