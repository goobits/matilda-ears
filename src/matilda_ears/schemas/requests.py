from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict


class BaseMessage(BaseModel):
    model_config = ConfigDict(extra="allow")

    type: str


class PingRequest(BaseMessage):
    type: str = "ping"


class AuthRequest(BaseMessage):
    type: str = "auth"
    token: Optional[str] = None


class GenerateTokenRequest(BaseMessage):
    type: str = "generate_token"
    client_name: Optional[str] = None


class TranscribeRequest(BaseMessage):
    type: str = "transcribe"
    token: Optional[str] = None
    audio_data: str
    audio_format: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None


class StartStreamRequest(BaseMessage):
    type: str = "start_stream"
    token: Optional[str] = None
    session_id: Optional[str] = None
    sample_rate: Optional[int] = None
    channels: Optional[int] = None
    binary: Optional[bool] = None
    wake_word_enabled: Optional[bool] = None
    wake_word_debug: Optional[bool] = None


class AudioChunkRequest(BaseMessage):
    type: str = "audio_chunk"
    session_id: str
    audio_data: str
    ack_requested: Optional[bool] = None


class PcmChunkRequest(BaseMessage):
    type: str = "pcm_chunk"
    session_id: str
    audio_data: str
    sample_rate: Optional[int] = None
    channels: Optional[int] = None


class EndStreamRequest(BaseMessage):
    type: str = "end_stream"
    session_id: str
    expected_chunks: Optional[int] = None


class ReloadRequest(BaseMessage):
    type: str = "reload"
