import asyncio

import pytest

from backend.app.routes.sync import _run_websocket_session
from backend.app.services import realtime


@pytest.mark.anyio
async def test_cancelled_websocket_session_releases_connection_slot():
    class WaitingSocket:
        def __init__(self):
            self.receiving = asyncio.Event()

        async def accept(self):
            pass

        async def receive_text(self):
            self.receiving.set()
            await asyncio.Event().wait()

    ws = WaitingSocket()
    await realtime.register(ws, user_id="cancel-test-user", space_id="cancel-test-space")
    task = asyncio.create_task(_run_websocket_session(ws))
    try:
        await ws.receiving.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert ws not in realtime.connections
        assert realtime._user_connection_count("cancel-test-user") == 0
    finally:
        realtime.unregister(ws)
