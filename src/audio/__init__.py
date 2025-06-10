"""Audio processing functionality.
"""

from .linux_recorder import AudioRecorder
from .mac_recorder import MacAudioRecorder
from .recorder_factory import get_audio_recorder

# Note: StreamingAudioProcessor and FacebookDenoiserPipeline have external dependencies
# Import them directly when needed: from src.audio.streaming_processor import StreamingAudioProcessor

__all__ = [
    "AudioRecorder",
    "MacAudioRecorder", 
    "get_audio_recorder"
]
