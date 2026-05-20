from __future__ import annotations

import asyncio
import concurrent.futures
import importlib
import os
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from backend.app import config as config_module
from backend.app import lifespan as lifespan_module
from backend.app.db import db as db_module
from backend.app.db import engine as engine_module
from backend.app.db import session as session_module
from backend.app.db import settings as settings_module
from backend.app import runtime as runtime_module


README_PATH = Path(__file__).resolve().parents[1] / "README.md"


def _reload_runtime_module():
    return importlib.reload(runtime_module)


def _reload_db_module():
    return importlib.reload(db_module)


def _reload_engine_module():
    return importlib.reload(engine_module)


def _reload_session_module():
    return importlib.reload(session_module)


def _reload_settings_module():
    return importlib.reload(settings_module)


def test_get_ta_connection_env_uses_profile_value(monkeypatch):
    monkeypatch.setenv("ENV", "uat")

    module = _reload_runtime_module()
    assert module.get_ta_connection_env() == "uat"


def test_get_ta_connection_env_uses_profile_alias(monkeypatch):
    monkeypatch.setenv("ENV", "production")

    module = _reload_runtime_module()
    assert module.get_ta_connection_env() == "prod"


def test_get_ta_connection_env_treats_local_as_dev(monkeypatch):
    monkeypatch.setenv("ENV", "local")

    module = _reload_runtime_module()
    assert module.get_ta_connection_env() == "dev"


def test_get_ta_connection_env_treats_test_as_dev(monkeypatch):
    monkeypatch.setenv("ENV", "test")

    module = _reload_runtime_module()
    assert module.get_ta_connection_env() == "dev"


def test_get_ta_connection_env_rejects_unknown_profile(monkeypatch):
    monkeypatch.setenv("ENV", "stage")

    module = _reload_runtime_module()
    with pytest.raises(
        RuntimeError,
        match="ENV must resolve to dev/local/test, uat, or prod for TAConnection\\(env=...\\).",
    ):
        module.get_ta_connection_env()


def test_get_ta_connection_env_requires_env(monkeypatch):
    monkeypatch.delenv("ENV", raising=False)

    module = _reload_runtime_module()
    with pytest.raises(RuntimeError):
        module.get_ta_connection_env()


def test_db_engine_uses_sqlalchemy_pooling_with_pre_ping(monkeypatch):
    for key in (
        "SIPM_DB_POOL_SIZE",
        "SIPM_DB_MAX_OVERFLOW",
        "SIPM_DB_POOL_TIMEOUT_SECONDS",
        "SIPM_DB_POOL_RECYCLE_SECONDS",
        "SIPM_DB_POOL_PRE_PING",
        "SIPM_DB_POOL_USE_LIFO",
    ):
        monkeypatch.delenv(key, raising=False)

    module = _reload_engine_module()
    captured = {}

    def fake_create_engine(url: str, **kwargs):
        captured["url"] = url
        captured["kwargs"] = kwargs
        return object()

    monkeypatch.setattr(module, "create_engine", fake_create_engine)

    module.build_engine()

    kwargs = captured["kwargs"]
    assert captured["url"] == "oracle+oracledb://"
    assert callable(kwargs["creator"])
    assert kwargs["pool_size"] == 5
    assert kwargs["max_overflow"] == 10
    assert kwargs["pool_timeout"] == 30
    assert kwargs["pool_recycle"] == 1800
    assert kwargs["pool_pre_ping"] is True
    assert kwargs["pool_use_lifo"] is False


def test_db_engine_uses_pooling_env_overrides(monkeypatch):
    monkeypatch.setenv("SIPM_DB_POOL_SIZE", "7")
    monkeypatch.setenv("SIPM_DB_MAX_OVERFLOW", "2")
    monkeypatch.setenv("SIPM_DB_POOL_TIMEOUT_SECONDS", "12")
    monkeypatch.setenv("SIPM_DB_POOL_RECYCLE_SECONDS", "90")
    monkeypatch.setenv("SIPM_DB_POOL_PRE_PING", "false")
    monkeypatch.setenv("SIPM_DB_POOL_USE_LIFO", "true")

    module = _reload_engine_module()
    captured = {}

    def fake_create_engine(url: str, **kwargs):
        captured["kwargs"] = kwargs
        return object()

    monkeypatch.setattr(module, "create_engine", fake_create_engine)

    module.build_engine()

    kwargs = captured["kwargs"]
    assert kwargs["pool_size"] == 7
    assert kwargs["max_overflow"] == 2
    assert kwargs["pool_timeout"] == 12
    assert kwargs["pool_recycle"] == 90
    assert kwargs["pool_pre_ping"] is False
    assert kwargs["pool_use_lifo"] is True


def test_db_engine_allows_documented_zero_or_disabled_pool_values(monkeypatch):
    monkeypatch.setenv("SIPM_DB_POOL_SIZE", "0")
    monkeypatch.setenv("SIPM_DB_MAX_OVERFLOW", "-1")
    monkeypatch.setenv("SIPM_DB_POOL_TIMEOUT_SECONDS", "0")
    monkeypatch.setenv("SIPM_DB_POOL_RECYCLE_SECONDS", "-1")

    module = _reload_engine_module()
    captured = {}

    def fake_create_engine(url: str, **kwargs):
        captured["kwargs"] = kwargs
        return object()

    monkeypatch.setattr(module, "create_engine", fake_create_engine)

    module.build_engine()

    kwargs = captured["kwargs"]
    assert kwargs["pool_size"] == 0
    assert kwargs["max_overflow"] == -1
    assert kwargs["pool_timeout"] == 0
    assert kwargs["pool_recycle"] == -1


def test_db_engine_creator_uses_taconnection(monkeypatch):
    monkeypatch.setenv("ENV", "production")

    module = _reload_engine_module()
    captured = {}
    fake_connection = object()

    class _FakeTAConnection:
        def __init__(self, env: str):
            captured["env"] = env

        def connect(self):
            captured["connect_called"] = True
            return fake_connection

    monkeypatch.setitem(
        sys.modules,
        "treasury_analytics",
        SimpleNamespace(TAConnection=_FakeTAConnection),
    )

    def fake_create_engine(url: str, **kwargs):
        captured["creator_connection"] = kwargs["creator"]()
        return object()

    monkeypatch.setattr(module, "create_engine", fake_create_engine)

    module.build_engine()

    assert captured["env"] == "prod"
    assert captured["connect_called"] is True
    assert captured["creator_connection"] is fake_connection


def test_db_engine_rejects_non_integer_pool_env(monkeypatch):
    monkeypatch.setenv("SIPM_DB_POOL_SIZE", "five")

    module = _reload_engine_module()
    monkeypatch.setattr(
        module,
        "create_engine",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("create_engine should not be called")
        ),
    )

    with pytest.raises(RuntimeError, match="SIPM_DB_POOL_SIZE must be an integer."):
        module.build_engine()


def test_db_engine_rejects_invalid_boolean_pool_env(monkeypatch):
    monkeypatch.setenv("SIPM_DB_POOL_PRE_PING", "sometimes")

    module = _reload_engine_module()
    monkeypatch.setattr(
        module,
        "create_engine",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("create_engine should not be called")
        ),
    )

    with pytest.raises(
        RuntimeError, match="SIPM_DB_POOL_PRE_PING must be a boolean value."
    ):
        module.build_engine()


def test_db_engine_rejects_invalid_boolean_pool_use_lifo_env(monkeypatch):
    monkeypatch.setenv("SIPM_DB_POOL_USE_LIFO", "sometimes")

    module = _reload_engine_module()
    monkeypatch.setattr(
        module,
        "create_engine",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("create_engine should not be called")
        ),
    )

    with pytest.raises(
        RuntimeError, match="SIPM_DB_POOL_USE_LIFO must be a boolean value."
    ):
        module.build_engine()


def test_db_engine_rejects_negative_pool_size(monkeypatch):
    monkeypatch.setenv("SIPM_DB_POOL_SIZE", "-2")

    module = _reload_engine_module()
    monkeypatch.setattr(
        module,
        "create_engine",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("create_engine should not be called")
        ),
    )

    with pytest.raises(RuntimeError, match="SIPM_DB_POOL_SIZE must be >= 0."):
        module.build_engine()


def test_db_engine_rejects_invalid_negative_max_overflow(monkeypatch):
    monkeypatch.setenv("SIPM_DB_MAX_OVERFLOW", "-2")

    module = _reload_engine_module()
    monkeypatch.setattr(
        module,
        "create_engine",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("create_engine should not be called")
        ),
    )

    with pytest.raises(RuntimeError, match="SIPM_DB_MAX_OVERFLOW must be -1 or >= 0."):
        module.build_engine()


def test_db_engine_rejects_negative_pool_timeout(monkeypatch):
    monkeypatch.setenv("SIPM_DB_POOL_TIMEOUT_SECONDS", "-1")

    module = _reload_engine_module()
    monkeypatch.setattr(
        module,
        "create_engine",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("create_engine should not be called")
        ),
    )

    with pytest.raises(
        RuntimeError, match="SIPM_DB_POOL_TIMEOUT_SECONDS must be >= 0."
    ):
        module.build_engine()


def test_db_engine_rejects_invalid_negative_pool_recycle(monkeypatch):
    monkeypatch.setenv("SIPM_DB_POOL_RECYCLE_SECONDS", "-2")

    module = _reload_engine_module()
    monkeypatch.setattr(
        module,
        "create_engine",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("create_engine should not be called")
        ),
    )

    with pytest.raises(
        RuntimeError, match="SIPM_DB_POOL_RECYCLE_SECONDS must be -1 or >= 0."
    ):
        module.build_engine()


def test_ensure_session_local_initializes_once_under_concurrency(monkeypatch):
    module = _reload_session_module()
    module.reset_session_state()

    captured = {"build_calls": 0, "sessionmaker_calls": 0}
    sentinel_engine = object()
    sentinel_session_local = object()

    def fake_build_engine():
        captured["build_calls"] += 1
        time.sleep(0.05)
        return sentinel_engine

    def fake_sessionmaker(*, autocommit, autoflush, bind):
        captured["sessionmaker_calls"] += 1
        assert autocommit is False
        assert autoflush is False
        assert bind is sentinel_engine
        return sentinel_session_local

    monkeypatch.setattr(module, "build_engine", fake_build_engine)
    monkeypatch.setattr(module, "sessionmaker", fake_sessionmaker)

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(lambda _: module._ensure_session_local(), range(8)))

    assert results == [sentinel_session_local] * 8
    assert captured == {"build_calls": 1, "sessionmaker_calls": 1}


def test_warm_db_pool_opens_requested_connection_count(monkeypatch):
    module = _reload_session_module()
    module.SessionLocal = object()

    captured = {"open_now": 0, "max_open": 0, "execute": 0, "commit": 0, "close": 0}

    class FakeConnection:
        def execute(self, statement):
            captured["execute"] += 1
            assert str(statement) == "SELECT 1 FROM DUAL"

        def commit(self):
            captured["commit"] += 1

        def close(self):
            captured["close"] += 1
            captured["open_now"] -= 1

    class FakeEngine:
        def connect(self):
            captured["open_now"] += 1
            captured["max_open"] = max(captured["max_open"], captured["open_now"])
            return FakeConnection()

    module.engine = FakeEngine()

    module.warm_db_pool(connection_count=2)

    assert captured == {
        "open_now": 0,
        "max_open": 2,
        "execute": 2,
        "commit": 2,
        "close": 2,
    }


def test_warm_db_pool_rejects_non_positive_connection_count():
    module = _reload_session_module()

    with pytest.raises(RuntimeError, match="connection_count must be >= 1."):
        module.warm_db_pool(connection_count=0)


def test_db_healthcheck_sql_is_oracle_safe():
    module = _reload_db_module()

    assert str(module.DB_HEALTHCHECK_SQL) == "SELECT 1 FROM DUAL"


def test_db_facade_preserves_public_runtime_exports():
    module = _reload_db_module()

    for name in (
        "DB_HEALTHCHECK_SQL",
        "SessionLocal",
        "_build_engine",
        "_ensure_session_local",
        "check_db_connection",
        "engine",
        "get_session",
        "init_db",
        "warm_db_pool",
    ):
        assert hasattr(module, name)


def test_db_settings_loader_exposes_immutable_pool_settings(monkeypatch):
    monkeypatch.setenv("SIPM_DB_POOL_SIZE", "3")
    monkeypatch.setenv("SIPM_DB_MAX_OVERFLOW", "4")
    monkeypatch.setenv("SIPM_DB_POOL_TIMEOUT_SECONDS", "5")
    monkeypatch.setenv("SIPM_DB_POOL_RECYCLE_SECONDS", "6")
    monkeypatch.setenv("SIPM_DB_POOL_PRE_PING", "off")
    monkeypatch.setenv("SIPM_DB_POOL_USE_LIFO", "on")
    module = _reload_settings_module()

    settings = module.load_database_pool_settings()

    assert settings == module.DatabasePoolSettings(
        pool_size=3,
        max_overflow=4,
        pool_timeout_seconds=5,
        pool_recycle_seconds=6,
        pool_pre_ping=False,
        pool_use_lifo=True,
    )


def test_database_runtime_environment_knobs_are_documented():
    readme = README_PATH.read_text(encoding="utf-8")

    for expected in (
        "TAConnection",
        "SIPM_DB_POOL_SIZE",
        "SIPM_DB_MAX_OVERFLOW",
        "SIPM_DB_POOL_TIMEOUT_SECONDS",
        "SIPM_DB_POOL_RECYCLE_SECONDS",
        "SIPM_DB_POOL_PRE_PING",
        "SIPM_DB_POOL_USE_LIFO",
        "SIPM_DB_PREWARM_ON_STARTUP",
        "SIPM_DB_PREWARM_CONNECTIONS",
        "SIPM_DB_KEEPWARM_INTERVAL_SECONDS",
        "compact JSON",
        "auth_method",
    ):
        assert expected in readme


def test_load_env_file_respects_explicit_env_by_default(monkeypatch, tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "SIPM_SECRET_KEY=from-file\nSIPM_EMPTY_TEST=from-file\n", encoding="utf-8"
    )

    monkeypatch.delenv("SIPM_ENV_OVERRIDE", raising=False)
    monkeypatch.setenv("SIPM_SECRET_KEY", "from-env")
    monkeypatch.setenv("SIPM_EMPTY_TEST", "")

    config_module.load_env_file(env_file)

    assert os.environ["SIPM_SECRET_KEY"] == "from-env"
    assert os.environ["SIPM_EMPTY_TEST"] == "from-file"


def test_load_env_file_can_override_when_enabled(monkeypatch, tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("SIPM_SECRET_KEY=from-file\n", encoding="utf-8")

    monkeypatch.setenv("SIPM_ENV_OVERRIDE", "true")
    monkeypatch.setenv("SIPM_SECRET_KEY", "from-env")

    config_module.load_env_file(env_file)

    assert os.environ["SIPM_SECRET_KEY"] == "from-file"


def test_load_env_file_accepts_truthy_env_override_values(monkeypatch, tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("SIPM_SECRET_KEY=from-file\n", encoding="utf-8")

    monkeypatch.setenv("SIPM_ENV_OVERRIDE", "yes")
    monkeypatch.setenv("SIPM_SECRET_KEY", "from-env")

    config_module.load_env_file(env_file)

    assert os.environ["SIPM_SECRET_KEY"] == "from-file"


def test_load_env_file_rejects_invalid_env_override_boolean(monkeypatch, tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("SIPM_SECRET_KEY=from-file\n", encoding="utf-8")

    monkeypatch.setenv("SIPM_ENV_OVERRIDE", "sometimes")

    with pytest.raises(
        RuntimeError, match="SIPM_ENV_OVERRIDE must be a boolean value."
    ):
        config_module.load_env_file(env_file)


def test_runtime_env_files_prefers_repo_root_env_files(tmp_path):
    repo_dir = tmp_path / "repo"
    base_dir = repo_dir / "src" / "main"
    repo_dir.mkdir()
    base_dir.mkdir(parents=True)
    repo_env = repo_dir / ".env"
    repo_env_local = repo_dir / ".env.local"
    repo_env.write_text("SIPM_FROM_REPO=true\n", encoding="utf-8")
    (base_dir / ".env").write_text("SIPM_FROM_LEGACY=true\n", encoding="utf-8")
    paths = config_module.RuntimePaths(
        base_dir=base_dir,
        repo_dir=repo_dir,
        frontend_dir=base_dir / "ui",
        frontend_required_files=(),
    )

    assert config_module.runtime_env_files(paths) == (repo_env, repo_env_local)


def test_runtime_env_files_uses_legacy_main_env_when_repo_env_absent(tmp_path):
    repo_dir = tmp_path / "repo"
    base_dir = repo_dir / "src" / "main"
    base_dir.mkdir(parents=True)
    paths = config_module.RuntimePaths(
        base_dir=base_dir,
        repo_dir=repo_dir,
        frontend_dir=base_dir / "ui",
        frontend_required_files=(),
    )

    assert config_module.runtime_env_files(paths) == (
        base_dir / ".env",
        base_dir / ".env.local",
    )


def test_load_runtime_env_is_idempotent_and_force_reloadable(monkeypatch, tmp_path):
    repo_dir = tmp_path / "repo"
    base_dir = repo_dir / "src" / "main"
    base_dir.mkdir(parents=True)
    env_file = repo_dir / ".env"
    env_file.write_text("SIPM_RUNTIME_ONCE=one\n", encoding="utf-8")
    paths = config_module.RuntimePaths(
        base_dir=base_dir,
        repo_dir=repo_dir,
        frontend_dir=base_dir / "ui",
        frontend_required_files=(),
    )

    monkeypatch.delenv("SIPM_RUNTIME_ONCE", raising=False)
    monkeypatch.delenv("SIPM_RUNTIME_FORCE", raising=False)
    monkeypatch.setattr(config_module, "_ENV_LOADED", False)

    config_module.load_runtime_env(paths=paths)
    env_file.write_text(
        "SIPM_RUNTIME_ONCE=changed\nSIPM_RUNTIME_FORCE=two\n", encoding="utf-8"
    )
    config_module.load_runtime_env(paths=paths)

    assert os.environ["SIPM_RUNTIME_ONCE"] == "one"
    assert "SIPM_RUNTIME_FORCE" not in os.environ

    config_module.load_runtime_env(paths=paths, force=True)

    assert os.environ["SIPM_RUNTIME_ONCE"] == "one"
    assert os.environ["SIPM_RUNTIME_FORCE"] == "two"


@pytest.mark.anyio
async def test_app_lifespan_validates_auth_configuration(monkeypatch):
    calls = {"count": 0}

    def fake_validate() -> None:
        calls["count"] += 1

    monkeypatch.setattr(lifespan_module, "validate_auth_configuration", fake_validate)

    from backend.main import create_app

    app = create_app()
    async with app.router.lifespan_context(app):
        pass

    assert calls["count"] == 1


@pytest.mark.anyio
async def test_app_lifespan_accepts_truthy_disable_startup_value(monkeypatch):
    monkeypatch.setattr(lifespan_module, "validate_auth_configuration", lambda: None)
    monkeypatch.setenv("SIPM_DISABLE_STARTUP", "1")

    calls = {"init_db": 0}

    def fake_init_db() -> None:
        calls["init_db"] += 1

    monkeypatch.setattr(lifespan_module, "init_db", fake_init_db)

    from backend.main import create_app

    app = create_app()
    async with app.router.lifespan_context(app):
        pass

    assert calls["init_db"] == 0


@pytest.mark.anyio
async def test_app_lifespan_does_not_disable_startup_for_pytest_presence(monkeypatch):
    monkeypatch.setattr(lifespan_module, "validate_auth_configuration", lambda: None)
    monkeypatch.setenv("SIPM_DISABLE_STARTUP", "false")

    calls = {"init_db": 0}

    def fake_init_db() -> None:
        calls["init_db"] += 1

    monkeypatch.setattr(lifespan_module, "init_db", fake_init_db)

    from backend.main import create_app

    app = create_app()
    async with app.router.lifespan_context(app):
        pass

    assert calls["init_db"] == 1


@pytest.mark.anyio
async def test_db_keepwarm_loop_checks_connection_each_interval(monkeypatch):
    calls = {"sleep": 0, "check": 0}

    async def fake_sleep(seconds: int) -> None:
        calls["sleep"] += 1
        assert seconds == 15
        if calls["sleep"] > 1:
            raise asyncio.CancelledError()

    def fake_check_db_connection() -> None:
        calls["check"] += 1

    async def fake_to_thread(func):
        return func()

    monkeypatch.setattr(lifespan_module.asyncio, "sleep", fake_sleep)
    monkeypatch.setattr(
        lifespan_module, "check_db_connection", fake_check_db_connection
    )
    monkeypatch.setattr(lifespan_module.asyncio, "to_thread", fake_to_thread)

    with pytest.raises(asyncio.CancelledError):
        await lifespan_module.db_keepwarm_loop(15)

    assert calls == {"sleep": 2, "check": 1}


@pytest.mark.anyio
async def test_app_lifespan_prewarms_pool_when_enabled(monkeypatch):
    monkeypatch.setattr(lifespan_module, "validate_auth_configuration", lambda: None)
    monkeypatch.setattr(
        lifespan_module.coordination, "validate_configuration", lambda: None
    )
    monkeypatch.setenv("SIPM_DISABLE_STARTUP", "false")
    monkeypatch.delenv("SIPM_DB_KEEPWARM_INTERVAL_SECONDS", raising=False)
    monkeypatch.setenv("SIPM_DB_PREWARM_ON_STARTUP", "true")
    monkeypatch.setenv("SIPM_DB_PREWARM_CONNECTIONS", "2")

    calls = {"init_db": 0, "warm": []}

    async def fake_start_runtime() -> None:
        return None

    async def fake_stop_runtime() -> None:
        return None

    def fake_init_db() -> None:
        calls["init_db"] += 1

    def fake_warm_db_pool(*, connection_count: int) -> None:
        calls["warm"].append(connection_count)

    monkeypatch.setattr(lifespan_module, "start_realtime_runtime", fake_start_runtime)
    monkeypatch.setattr(lifespan_module, "stop_realtime_runtime", fake_stop_runtime)
    monkeypatch.setattr(lifespan_module, "init_db", fake_init_db)
    monkeypatch.setattr(lifespan_module, "warm_db_pool", fake_warm_db_pool)

    from backend.main import create_app

    app = create_app()
    async with app.router.lifespan_context(app):
        pass

    assert calls == {"init_db": 1, "warm": [2]}


@pytest.mark.anyio
async def test_app_lifespan_starts_keepwarm_task_when_enabled(monkeypatch):
    monkeypatch.setattr(lifespan_module, "validate_auth_configuration", lambda: None)
    monkeypatch.setattr(
        lifespan_module.coordination, "validate_configuration", lambda: None
    )
    monkeypatch.setenv("SIPM_DISABLE_STARTUP", "false")
    monkeypatch.delenv("SIPM_DB_PREWARM_ON_STARTUP", raising=False)
    monkeypatch.setenv("SIPM_DB_KEEPWARM_INTERVAL_SECONDS", "60")

    calls = {"init_db": 0, "check": 0, "create_task": 0}

    async def fake_start_runtime() -> None:
        return None

    async def fake_stop_runtime() -> None:
        return None

    def fake_init_db() -> None:
        calls["init_db"] += 1

    def fake_check_db_connection() -> None:
        calls["check"] += 1

    class FakeTask:
        def __init__(self, coro):
            self._coro = coro
            self._cancelled = False

        def cancel(self) -> None:
            self._cancelled = True
            self._coro.close()

        def __await__(self):
            async def _wait():
                if self._cancelled:
                    raise asyncio.CancelledError()
                return None

            return _wait().__await__()

    def fake_create_task(coro):
        calls["create_task"] += 1
        return FakeTask(coro)

    monkeypatch.setattr(lifespan_module, "start_realtime_runtime", fake_start_runtime)
    monkeypatch.setattr(lifespan_module, "stop_realtime_runtime", fake_stop_runtime)
    monkeypatch.setattr(lifespan_module, "init_db", fake_init_db)
    monkeypatch.setattr(
        lifespan_module, "check_db_connection", fake_check_db_connection
    )
    monkeypatch.setattr(lifespan_module.asyncio, "create_task", fake_create_task)

    from backend.main import create_app

    app = create_app()
    async with app.router.lifespan_context(app):
        pass

    assert calls == {"init_db": 1, "check": 1, "create_task": 1}
