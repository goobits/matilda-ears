from .internal import faster_whisper as _impl

FasterWhisperBackend = _impl.FasterWhisperBackend
get_config = _impl.get_config
config = get_config()

__all__ = ["FasterWhisperBackend", "config", "get_config"]
