import asyncio

import pytest

import backend.main as main


@pytest.mark.anyio
async def test_keepwarm_retries_after_transient_database_failure(monkeypatch, caplog):
    calls = []

    async def sleep(_seconds):
        if len(calls) == 2:
            raise asyncio.CancelledError

    def check():
        calls.append("probe")
        if len(calls) == 1:
            raise ConnectionError("synthetic-password-DO-NOT-EXPOSE")

    async def to_thread(fn):
        return fn()

    monkeypatch.setattr(main.asyncio, "sleep", sleep)
    monkeypatch.setattr(main.asyncio, "to_thread", to_thread)
    monkeypatch.setattr(main, "check_db_connection", check)
    with pytest.raises(asyncio.CancelledError):
        await main._db_keepwarm_loop(15)
    assert calls == ["probe", "probe"]
    assert "Database keepwarm check failed (ConnectionError)" in caplog.text
    assert "synthetic-password-DO-NOT-EXPOSE" not in caplog.text


@pytest.mark.anyio
async def test_keepwarm_cancellation_still_propagates(monkeypatch):
    checked = asyncio.Event()

    async def to_thread(_fn):
        checked.set()

    monkeypatch.setattr(main.asyncio, "to_thread", to_thread)
    task = asyncio.create_task(main._db_keepwarm_loop(0))
    try:
        await asyncio.wait_for(checked.wait(), timeout=2)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    finally:
        if not task.done():
            task.cancel()


@pytest.mark.anyio
@pytest.mark.parametrize("path", ["/project-manager/api", "/project-manager/api/missing", "/project-manager/api/missing/nested"])
async def test_unknown_api_paths_return_404_instead_of_spa(client, path):
    response = await client.get(path)
    assert response.status_code == 404
    assert "text/html" not in response.headers.get("content-type", "")


@pytest.mark.anyio
async def test_unknown_frontend_route_still_uses_spa(client):
    response = await client.get("/project-manager/an-unknown-view")
    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")
