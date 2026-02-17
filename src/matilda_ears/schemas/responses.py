from __future__ import annotations


from pydantic import BaseModel, ConfigDict


class ErrorMessage(BaseModel):
    model_config = ConfigDict(extra="allow")

    type: str = "error"
    message: str
    success: bool = False


class WelcomeMessage(BaseModel):
    model_config = ConfigDict(extra="allow")

    type: str = "welcome"
    message: str
    client_id: str
    server_ready: bool


class PongMessage(BaseModel):
    model_config = ConfigDict(extra="allow")

    type: str = "pong"
    timestamp: float


class AuthSuccess(BaseModel):
    model_config = ConfigDict(extra="allow")

    type: str = "auth_success"
    message: str
    client_id: str


class TokenGenerated(BaseModel):
    model_config = ConfigDict(extra="allow")

    type: str = "token_generated"
    token: str
    token_id: str
    expires: str
    client_name: str


class TranscriptionComplete(BaseModel):
    model_config = ConfigDict(extra="allow")

    type: str = "transcription_complete"
    text: str
    success: bool
    audio_duration: float
    language: str


class StreamStarted(BaseModel):
    model_config = ConfigDict(extra="allow")

    type: str = "stream_started"
    session_id: str
    success: bool
    streaming_enabled: bool
    backend: str
    strategy: str
    wake_word_enabled: bool


class PartialResult(BaseModel):
    model_config = ConfigDict(extra="allow")

    type: str = "partial_result"
    session_id: str
    confirmed_text: str
    tentative_text: str
    is_final: bool


class ChunkReceived(BaseModel):
    model_config = ConfigDict(extra="allow")

    type: str = "chunk_received"
    session_id: str
    samples_decoded: int
    total_duration: float


class WakeWordDetected(BaseModel):
    model_config = ConfigDict(extra="allow")

    type: str = "wake_word_detected"
    session_id: str
    agent: str
    phrase: str
    confidence: float


class WakeWordScore(BaseModel):
    model_config = ConfigDict(extra="allow")

    type: str = "wake_word_score"
    session_id: str
    phrase: str
    confidence: float
    rms: float
    peak: float


class StreamTranscriptionComplete(BaseModel):
    model_config = ConfigDict(extra="allow")

    type: str = "stream_transcription_complete"
    session_id: str
    confirmed_text: str
    tentative_text: str
    success: bool
    audio_duration: float
    language: str
    backend: str
    streaming_mode: bool


class ReloadResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    type: str = "reload_response"
    status: str
    message: str


class SimpleTranscriptionResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    text: str
    is_final: bool
    error: str | None = None
