from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np


class SessionConflictError(ValueError):
    pass


@dataclass
class PcmBuffer:
    sample_rate: int
    channels: int
    needs_resampling: bool
    samples: list[np.ndarray] = field(default_factory=list)
    chunk_count: int = 0
    total_samples: int = 0

    def append(self, samples: np.ndarray, max_samples: int) -> None:
        self.samples.append(samples)
        self.total_samples += len(samples)
        while self.samples and self.total_samples > max_samples:
            self.total_samples -= len(self.samples.pop(0))

    @property
    def buffer_bytes(self) -> int:
        return sum(int(samples.nbytes) for samples in self.samples)


@dataclass
class ServerSession:
    session_id: str
    client_id: str
    transport: str
    sample_rate: int = 16000
    channels: int = 1
    decoder: Any | None = None
    pcm: PcmBuffer | None = None
    streaming: Any | None = None
    chunks_received: int = 0
    expected_chunks: int | None = None
    opus_log: list[dict[str, Any]] = field(default_factory=list)
    ending: bool = False
    wake_word_enabled: bool = False
    wake_word_buffer: np.ndarray = field(default_factory=lambda: np.array([], dtype=np.int16))
    wake_word_debug_last_sent: float | None = None

    def record_chunk(self) -> int:
        self.chunks_received += 1
        return self.chunks_received


class SessionRegistry:
    def __init__(self) -> None:
        self._sessions: dict[str, ServerSession] = {}

    def __len__(self) -> int:
        return len(self._sessions)

    def __contains__(self, session_id: str) -> bool:
        return session_id in self._sessions

    def create(
        self,
        session_id: str,
        client_id: str,
        transport: str,
        *,
        sample_rate: int = 16000,
        channels: int = 1,
    ) -> ServerSession:
        if session_id in self._sessions:
            raise SessionConflictError(f"Session already exists: {session_id}")
        if transport == "binary" and self.binary_for_client(client_id) is not None:
            raise SessionConflictError(f"Client already has an active binary session: {client_id}")

        session = ServerSession(
            session_id=session_id,
            client_id=client_id,
            transport=transport,
            sample_rate=sample_rate,
            channels=channels,
        )
        self._sessions[session_id] = session
        return session

    def get(self, session_id: str) -> ServerSession | None:
        return self._sessions.get(session_id)

    def get_owned(self, session_id: str, client_id: str) -> ServerSession | None:
        session = self.get(session_id)
        if session is None or session.client_id != client_id:
            return None
        return session

    def binary_for_client(self, client_id: str) -> ServerSession | None:
        return next(
            (
                session
                for session in self._sessions.values()
                if session.client_id == client_id and session.transport == "binary"
            ),
            None,
        )

    def count_for_client(self, client_id: str) -> int:
        return sum(session.client_id == client_id for session in self._sessions.values())

    def pop(self, session_id: str) -> ServerSession | None:
        return self._sessions.pop(session_id, None)

    def pop_owned(self, session_id: str, client_id: str) -> ServerSession | None:
        session = self.get_owned(session_id, client_id)
        if session is None:
            return None
        return self.pop(session_id)

    def pop_client(self, client_id: str) -> list[ServerSession]:
        session_ids = [session.session_id for session in self._sessions.values() if session.client_id == client_id]
        return [session for session_id in session_ids if (session := self.pop(session_id)) is not None]

    def values(self) -> tuple[ServerSession, ...]:
        return tuple(self._sessions.values())

    @property
    def streaming_count(self) -> int:
        return sum(session.streaming is not None for session in self._sessions.values())

    @property
    def pcm_count(self) -> int:
        return sum(session.pcm is not None for session in self._sessions.values())

    @property
    def opus_count(self) -> int:
        return sum(session.decoder is not None for session in self._sessions.values())

    @property
    def ending_count(self) -> int:
        return sum(session.ending for session in self._sessions.values())

    @property
    def pcm_buffer_bytes(self) -> int:
        return sum(session.pcm.buffer_bytes for session in self._sessions.values() if session.pcm is not None)

    @property
    def opus_buffer_bytes(self) -> int:
        return sum(
            int(session.decoder.get_stats()["buffer_size_bytes"])
            for session in self._sessions.values()
            if session.decoder is not None
        )

    @property
    def wake_word_buffer_bytes(self) -> int:
        return sum(int(session.wake_word_buffer.nbytes) for session in self._sessions.values())
