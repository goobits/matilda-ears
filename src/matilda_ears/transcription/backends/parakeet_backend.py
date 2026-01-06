from .internal import parakeet as _impl

ParakeetBackend = _impl.ParakeetBackend
get_config = _impl.get_config

__all__ = ["ParakeetBackend", "get_config"]
