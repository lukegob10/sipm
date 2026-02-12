from __future__ import annotations

import pytest

import backend.seed as seed_script
from backend.app.db import db as db_module
from backend.app.models import Phase, Project, Solution, Subcomponent
from backend.app.services.sample_seed import seed_sample_data
from backend.app.services.seed import PHASES_SEED, seed_phases


def test_seed_phases_is_idempotent(db_sessionmaker):
    with db_sessionmaker() as session:
        seed_phases(session)
        assert session.query(Phase).count() == len(PHASES_SEED)
        seed_phases(session)
        assert session.query(Phase).count() == len(PHASES_SEED)


def test_seed_sample_data_respects_env_and_is_idempotent(db_sessionmaker, monkeypatch):
    monkeypatch.delenv("SAMPLE_SEED", raising=False)
    with db_sessionmaker() as session:
        seed_sample_data(session)
        assert session.query(Project).filter(Project.project_name == "Sample Project").count() == 0

        monkeypatch.setenv("SAMPLE_SEED", "true")
        seed_sample_data(session)
        assert session.query(Project).filter(Project.project_name == "Sample Project").count() == 1
        assert session.query(Solution).count() == 1
        assert session.query(Subcomponent).count() == 2
        seeded_project = session.query(Project).filter(Project.project_name == "Sample Project").first()
        assert seeded_project is not None
        assert seeded_project.space_id is not None
        seeded_solution = session.query(Solution).first()
        assert seeded_solution is not None
        assert seeded_solution.space_id is not None
        seeded_subs = session.query(Subcomponent).all()
        assert all(sub.space_id is not None for sub in seeded_subs)

        seed_sample_data(session)
        assert session.query(Subcomponent).count() == 2


def test_seed_script_main_calls_init_db(monkeypatch):
    called = {}

    def fake_init_db(*, run_seed: bool = False, create_schema: bool = False) -> None:
        called["run_seed"] = run_seed
        called["create_schema"] = create_schema

    monkeypatch.setattr(seed_script, "init_db", fake_init_db)
    seed_script.main()
    assert called == {"run_seed": True, "create_schema": True}


def test_init_db_creates_tables_and_calls_seed(monkeypatch):
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

    called = {"phases": 0, "sample": 0, "create_all": 0}

    def fake_seed_phases(session):
        called["phases"] += 1

    def fake_seed_sample_data(session):
        called["sample"] += 1

    from backend.app.models import Base

    def fake_create_all(*, bind):
        called["create_all"] += 1
        assert bind is dummy_engine

    import backend.app.services.seed as seed_module
    import backend.app.services.sample_seed as sample_seed_module

    monkeypatch.setattr(Base.metadata, "create_all", fake_create_all)
    monkeypatch.setattr(seed_module, "seed_phases", fake_seed_phases)
    monkeypatch.setattr(sample_seed_module, "seed_sample_data", fake_seed_sample_data)

    db_module.init_db(run_seed=True, create_schema=True)
    assert called == {"phases": 1, "sample": 1, "create_all": 1}

    gen = db_module.get_session()
    session = next(gen)
    assert session is not None
    gen.close()


@pytest.mark.anyio
async def test_health_endpoint(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
