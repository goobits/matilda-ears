from types import SimpleNamespace

import numpy as np
import pytest

from matilda_ears.transcription.server.internal.session_registry import (
    PcmBuffer,
    SessionConflictError,
    SessionRegistry,
)


def test_registry_enforces_unique_session_ids_and_ownership():
    sessions = SessionRegistry()
    session = sessions.create("s1", "client-1", "opus")

    with pytest.raises(SessionConflictError):
        sessions.create("s1", "client-2", "opus")

    assert sessions.get_owned("s1", "client-1") is session
    assert sessions.get_owned("s1", "client-2") is None
    assert sessions.pop_owned("s1", "client-2") is None
    assert sessions.get("s1") is session


def test_registry_tracks_binary_session_without_parallel_client_map():
    sessions = SessionRegistry()
    binary = sessions.create("binary", "client-1", "binary")

    assert sessions.binary_for_client("client-1") is binary
    with pytest.raises(SessionConflictError):
        sessions.create("second", "client-1", "binary")


def test_registry_pop_client_removes_only_owned_sessions():
    sessions = SessionRegistry()
    first = sessions.create("first", "client-1", "opus")
    second = sessions.create("second", "client-1", "pcm")
    sessions.create("other", "client-2", "opus")

    assert sessions.pop_client("client-1") == [first, second]
    assert sessions.get("other") is not None
    assert len(sessions) == 1


def test_registry_reports_buffer_and_lifecycle_totals():
    sessions = SessionRegistry()
    session = sessions.create("s1", "client-1", "opus")
    session.decoder = SimpleNamespace(get_stats=lambda: {"buffer_size_bytes": 12})
    session.pcm = PcmBuffer(16000, 1, False, samples=[np.zeros(4, dtype=np.int16)], total_samples=4)
    session.streaming = object()
    session.ending = True
    session.wake_word_buffer = np.zeros(3, dtype=np.int16)

    assert sessions.streaming_count == 1
    assert sessions.pcm_count == 1
    assert sessions.opus_count == 1
    assert sessions.ending_count == 1
    assert sessions.pcm_buffer_bytes == 8
    assert sessions.opus_buffer_bytes == 12
    assert sessions.wake_word_buffer_bytes == 6
