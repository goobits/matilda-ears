from __future__ import annotations

from collections import deque
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

import numpy as np


class SessionConflictError(ValueError):
    pass


@dataclass
class WakeWordState:
    detector: Any
    debug_last_sent: float | None = None
    _buffer: np.ndarray = field(init=False, repr=False)
    _buffered_samples: int = field(default=0, init=False, repr=False)

    def __post_init__(self) -> None:
        self._buffer = np.empty(int(self.detector.CHUNK_SAMPLES), dtype=np.int16)

    def frames(self, samples: np.ndarray) -> Iterator[np.ndarray]:
        samples = samples.astype(np.int16, copy=False)
        frame_size = len(self._buffer)
        offset = 0

        while offset < len(samples):
            if self._buffered_samples == 0 and len(samples) - offset >= frame_size:
                yield samples[offset : offset + frame_size]
                offset += frame_size
                continue

            copied = min(frame_size - self._buffered_samples, len(samples) - offset)
            end = self._buffered_samples + copied
            self._buffer[self._buffered_samples : end] = samples[offset : offset + copied]
            self._buffered_samples = end
            offset += copied

            if self._buffered_samples == frame_size:
                self._buffered_samples = 0
                yield self._buffer

    def reset(self) -> None:
        self._buffered_samples = 0
        self.detector.reset()

    def close(self) -> None:
        self.detector.close()

    @property
    def buffer_bytes(self) -> int:
        return self._buffered_samples * self._buffer.itemsize


@dataclass
class PcmBuffer:
    sample_rate: int
    channels: int
    needs_resampling: bool
    samples: deque[np.ndarray] = field(default_factory=deque)
    chunk_count: int = 0
    total_samples: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.samples, deque):
            self.samples = deque(self.samples)

    def append(self, samples: np.ndarray, max_samples: int) -> None:
        self.samples.append(samples)
        self.total_samples += len(samples)
        while self.samples and self.total_samples > max_samples:
            self.total_samples -= len(self.samples.popleft())

    def as_array(self) -> np.ndarray:
        if not self.samples:
            return np.array([], dtype=np.int16)
        return np.concatenate(self.samples)

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
    wake_word: WakeWordState | None = None

    def record_chunk(self) -> int:
        self.chunks_received += 1
        return self.chunks_received

    def close_wake_word(self) -> None:
        state = self.wake_word
        self.wake_word = None
        if state is not None:
            state.close()


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
        return sum(
            session.wake_word.buffer_bytes for session in self._sessions.values() if session.wake_word is not None
        )
