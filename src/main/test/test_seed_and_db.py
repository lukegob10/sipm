from __future__ import annotations

import pytest

from backend.app.db import db as db_module
from backend.app.models import Base


def test_init_db_without_create_schema_is_noop(monkeypatch):
    monkeypatch.setattr(
        db_module,
        "_ensure_session_local",
        lambda: (_ for _ in ()).throw(AssertionError("_ensure_session_local should not be called")),
    )
    db_module.init_db()


def test_init_db_creates_tables_when_requested(monkeypatch):
    class _DummySession:
        def __init__(self) -> None:
            self.closed = False

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            self.close()
            return False

        def close(self):
            self.closed = True

    def _session_local():
        return _DummySession()

    dummy_engine = object()
    monkeypatch.setattr(db_module, "engine", dummy_engine)
    monkeypatch.setattr(db_module, "_ensure_session_local", lambda: _session_local)

    called = {"create_all": 0}

    def fake_create_all(*, bind):
        called["create_all"] += 1
        assert bind is dummy_engine

    monkeypatch.setattr(Base.metadata, "create_all", fake_create_all)

    db_module.init_db(create_schema=True)
    assert called == {"create_all": 1}


def test_get_session_yields_and_closes(monkeypatch):
    class _DummySession:
        def __init__(self) -> None:
            self.closed = False

        def close(self):
            self.closed = True

    session = _DummySession()
    monkeypatch.setattr(db_module, "_ensure_session_local", lambda: (lambda: session))

    gen = db_module.get_session()
    yielded = next(gen)
    assert yielded is session
    gen.close()
    assert session.closed is True


@pytest.mark.anyio
async def test_health_endpoint(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
