from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


class BaseMessage(BaseModel):
    model_config = ConfigDict(extra="allow")

    type: str


class PingRequest(BaseMessage):
    type: str = "ping"


class AuthRequest(BaseMessage):
    type: str = "auth"
    token: str | None = None


class GenerateTokenRequest(BaseMessage):
    type: str = "generate_token"
    client_name: str | None = None


class TranscribeRequest(BaseMessage):
    type: str = "transcribe"
    token: str | None = None
    audio_data: str
    audio_format: str | None = None
    metadata: dict[str, Any] | None = None


class StartStreamRequest(BaseMessage):
    type: str = "start_stream"
    token: str | None = None
    session_id: str | None = None
    sample_rate: int | None = None
    channels: int | None = None
    binary: bool | None = None
    wake_word_enabled: bool | None = None
    wake_word_debug: bool | None = None


class AudioChunkRequest(BaseMessage):
    type: str = "audio_chunk"
    session_id: str
    audio_data: str
    ack_requested: bool | None = None


class PcmChunkRequest(BaseMessage):
    type: str = "pcm_chunk"
    session_id: str
    audio_data: str
    sample_rate: int | None = None
    channels: int | None = None


class EndStreamRequest(BaseMessage):
    type: str = "end_stream"
    session_id: str
    expected_chunks: int | None = None


class ReloadRequest(BaseMessage):
    type: str = "reload"
