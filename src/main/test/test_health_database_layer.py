from __future__ import annotations

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.pool import QueuePool

from backend.app.db import db as db_module


@pytest.mark.parametrize("failure_phase", [None, "connect", "execute", "commit"])
def test_warm_db_pool_returns_all_connections_when_one_close_fails(monkeypatch, failure_phase):
    engine = create_engine("sqlite://", poolclass=QueuePool, pool_size=3, max_overflow=0)
    original_connect = engine.connect
    acquired = []
    original_closes = []

    def connect():
        if failure_phase == "connect" and len(acquired) == 2:
            raise RuntimeError("connection acquisition failed")
        connection = original_connect()
        acquired.append(connection)
        original_close = connection.close
        original_closes.append(original_close)
        last_connection = 2 if failure_phase == "connect" else 3
        if len(acquired) == last_connection:
            def close():
                original_close()
                raise RuntimeError("pool checkin failed")

            monkeypatch.setattr(connection, "close", close)
            if failure_phase in {"execute", "commit"}:
                def fail_healthcheck(*args, **kwargs):
                    raise RuntimeError("healthcheck failed")

                monkeypatch.setattr(connection, failure_phase, fail_healthcheck)
        return connection

    monkeypatch.setattr(engine, "connect", connect)
    monkeypatch.setattr(db_module, "engine", engine)
    monkeypatch.setattr(db_module, "SessionLocal", object())
    monkeypatch.setattr(db_module, "DB_HEALTHCHECK_SQL", text("SELECT 1"))
    try:
        with pytest.raises(RuntimeError, match="pool checkin failed"):
            db_module.warm_db_pool(connection_count=3)

        assert engine.pool.checkedout() == 0
        assert all(connection.closed for connection in acquired)
    finally:
        for close in original_closes:
            close()
        engine.dispose()
