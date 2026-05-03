from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from matilda_ears.transcription.client.unified import TranscriptionClient


@pytest.mark.asyncio
async def test_cleanup_streaming_session_removes_client_after_session_id_is_cleared():
    client = TranscriptionClient.__new__(TranscriptionClient)
    client.debug_callback = lambda _msg: None

    streaming_client = SimpleNamespace(session_id=None, disconnect=AsyncMock())
    client.active_streaming_sessions = {"finished-session": streaming_client}

    await TranscriptionClient.cleanup_streaming_session(client, streaming_client)

    assert client.active_streaming_sessions == {}
    streaming_client.disconnect.assert_awaited_once()
