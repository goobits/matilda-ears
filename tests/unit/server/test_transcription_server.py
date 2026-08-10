import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from matilda_ears.service import transcription_server


@pytest.mark.asyncio
async def test_start_server_cleans_health_runner_on_shutdown(monkeypatch) -> None:
    entered = asyncio.Event()
    health_runner = SimpleNamespace(cleanup=AsyncMock())
    server = SimpleNamespace(
        host="127.0.0.1",
        port=3211,
        load_model=AsyncMock(),
        _health_runner=None,
        ssl_enabled=False,
        ssl_context=None,
        handle_client=AsyncMock(),
        backend_name="parakeet",
        close=Mock(),
    )

    class RunningServer:
        async def __aenter__(self):
            entered.set()
            return self

        async def __aexit__(self, _exc_type, _exc, _tb):
            return False

    monkeypatch.setattr(
        "matilda_transport.resolve_transport",
        lambda *_args: SimpleNamespace(transport="tcp", endpoint="ws://127.0.0.1:3211"),
    )
    monkeypatch.setattr(transcription_server, "start_health_server", AsyncMock(return_value=health_runner))
    monkeypatch.setattr(transcription_server.websockets, "serve", lambda *_args, **_kwargs: RunningServer())

    task = asyncio.create_task(transcription_server.start_server(server))
    await asyncio.wait_for(entered.wait(), timeout=1)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    health_runner.cleanup.assert_awaited_once()
    assert server._health_runner is None
    server.close.assert_called_once()
