from .internal import huggingface as _impl

HuggingFaceBackend = _impl.HuggingFaceBackend
_detect_device = _impl._detect_device
pipeline = _impl.pipeline
AutoModelForSpeechSeq2Seq = _impl.AutoModelForSpeechSeq2Seq
AutoProcessor = _impl.AutoProcessor
get_config = _impl.get_config
config = get_config()

__all__ = [
    "HuggingFaceBackend",
    "_detect_device",
    "pipeline",
    "AutoModelForSpeechSeq2Seq",
    "AutoProcessor",
    "config",
    "get_config",
]
