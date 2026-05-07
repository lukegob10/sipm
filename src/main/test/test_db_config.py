from __future__ import annotations

import asyncio
import concurrent.futures
import importlib
import os
import sys
import time
from types import SimpleNamespace

import pytest
import anyio.to_thread

from backend import main as main_module
from backend.app.db import db as db_module
from backend.app import runtime as runtime_module


def _reload_runtime_module():
    return importlib.reload(runtime_module)


def _reload_db_module():
    return importlib.reload(db_module)


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

    module = _reload_db_module()
    captured = {}

    def fake_create_engine(url: str, **kwargs):
        captured["url"] = url
        captured["kwargs"] = kwargs
        return object()

    monkeypatch.setattr(module, "create_engine", fake_create_engine)

    module._build_engine()

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

    module = _reload_db_module()
    captured = {}

    def fake_create_engine(url: str, **kwargs):
        captured["kwargs"] = kwargs
        return object()

    monkeypatch.setattr(module, "create_engine", fake_create_engine)

    module._build_engine()

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

    module = _reload_db_module()
    captured = {}

    def fake_create_engine(url: str, **kwargs):
        captured["kwargs"] = kwargs
        return object()

    monkeypatch.setattr(module, "create_engine", fake_create_engine)

    module._build_engine()

    kwargs = captured["kwargs"]
    assert kwargs["pool_size"] == 0
    assert kwargs["max_overflow"] == -1
    assert kwargs["pool_timeout"] == 0
    assert kwargs["pool_recycle"] == -1


def test_db_engine_creator_uses_taconnection(monkeypatch):
    monkeypatch.setenv("ENV", "production")

    module = _reload_db_module()
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

    module._build_engine()

    assert captured["env"] == "prod"
    assert captured["connect_called"] is True
    assert captured["creator_connection"] is fake_connection


def test_db_engine_rejects_non_integer_pool_env(monkeypatch):
    monkeypatch.setenv("SIPM_DB_POOL_SIZE", "five")

    module = _reload_db_module()
    monkeypatch.setattr(
        module,
        "create_engine",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("create_engine should not be called")),
    )

    with pytest.raises(RuntimeError, match="SIPM_DB_POOL_SIZE must be an integer."):
        module._build_engine()


def test_db_engine_rejects_invalid_boolean_pool_env(monkeypatch):
    monkeypatch.setenv("SIPM_DB_POOL_PRE_PING", "sometimes")

    module = _reload_db_module()
    monkeypatch.setattr(
        module,
        "create_engine",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("create_engine should not be called")),
    )

    with pytest.raises(RuntimeError, match="SIPM_DB_POOL_PRE_PING must be a boolean value."):
        module._build_engine()


def test_db_engine_rejects_invalid_boolean_pool_use_lifo_env(monkeypatch):
    monkeypatch.setenv("SIPM_DB_POOL_USE_LIFO", "sometimes")

    module = _reload_db_module()
    monkeypatch.setattr(
        module,
        "create_engine",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("create_engine should not be called")),
    )

    with pytest.raises(RuntimeError, match="SIPM_DB_POOL_USE_LIFO must be a boolean value."):
        module._build_engine()


def test_db_engine_rejects_negative_pool_size(monkeypatch):
    monkeypatch.setenv("SIPM_DB_POOL_SIZE", "-2")

    module = _reload_db_module()
    monkeypatch.setattr(
        module,
        "create_engine",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("create_engine should not be called")),
    )

    with pytest.raises(RuntimeError, match="SIPM_DB_POOL_SIZE must be >= 0."):
        module._build_engine()


def test_db_engine_rejects_invalid_negative_max_overflow(monkeypatch):
    monkeypatch.setenv("SIPM_DB_MAX_OVERFLOW", "-2")

    module = _reload_db_module()
    monkeypatch.setattr(
        module,
        "create_engine",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("create_engine should not be called")),
    )

    with pytest.raises(RuntimeError, match="SIPM_DB_MAX_OVERFLOW must be -1 or >= 0."):
        module._build_engine()


def test_db_engine_rejects_negative_pool_timeout(monkeypatch):
    monkeypatch.setenv("SIPM_DB_POOL_TIMEOUT_SECONDS", "-1")

    module = _reload_db_module()
    monkeypatch.setattr(
        module,
        "create_engine",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("create_engine should not be called")),
    )

    with pytest.raises(RuntimeError, match="SIPM_DB_POOL_TIMEOUT_SECONDS must be >= 0."):
        module._build_engine()


def test_db_engine_rejects_invalid_negative_pool_recycle(monkeypatch):
    monkeypatch.setenv("SIPM_DB_POOL_RECYCLE_SECONDS", "-2")

    module = _reload_db_module()
    monkeypatch.setattr(
        module,
        "create_engine",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("create_engine should not be called")),
    )

    with pytest.raises(RuntimeError, match="SIPM_DB_POOL_RECYCLE_SECONDS must be -1 or >= 0."):
        module._build_engine()


def test_ensure_session_local_initializes_once_under_concurrency(monkeypatch):
    module = _reload_db_module()
    module.engine = None
    module.SessionLocal = None

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

    monkeypatch.setattr(module, "_build_engine", fake_build_engine)
    monkeypatch.setattr(module, "sessionmaker", fake_sessionmaker)

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(lambda _: module._ensure_session_local(), range(8)))

    assert results == [sentinel_session_local] * 8
    assert captured == {"build_calls": 1, "sessionmaker_calls": 1}


def test_warm_db_pool_opens_requested_connection_count(monkeypatch):
    module = _reload_db_module()
    module.SessionLocal = object()

    captured = {"open_now": 0, "max_open": 0, "execute": 0, "commit": 0, "close": 0}

    class FakeConnection:
        def execute(self, statement):
            captured["execute"] += 1
            assert str(statement) == "SELECT 1"

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

    assert captured == {"open_now": 0, "max_open": 2, "execute": 2, "commit": 2, "close": 2}


def test_warm_db_pool_rejects_non_positive_connection_count():
    module = _reload_db_module()

    with pytest.raises(RuntimeError, match="connection_count must be >= 1."):
        module.warm_db_pool(connection_count=0)


def test_load_env_file_respects_explicit_env_by_default(monkeypatch, tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("SIPM_SECRET_KEY=from-file\nSIPM_EMPTY_TEST=from-file\n", encoding="utf-8")

    monkeypatch.delenv("SIPM_ENV_OVERRIDE", raising=False)
    monkeypatch.setenv("SIPM_SECRET_KEY", "from-env")
    monkeypatch.setenv("SIPM_EMPTY_TEST", "")

    main_module._load_env_file(env_file)

    assert os.environ["SIPM_SECRET_KEY"] == "from-env"
    assert os.environ["SIPM_EMPTY_TEST"] == "from-file"


def test_load_env_file_can_override_when_enabled(monkeypatch, tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("SIPM_SECRET_KEY=from-file\n", encoding="utf-8")

    monkeypatch.setenv("SIPM_ENV_OVERRIDE", "true")
    monkeypatch.setenv("SIPM_SECRET_KEY", "from-env")

    main_module._load_env_file(env_file)

    assert os.environ["SIPM_SECRET_KEY"] == "from-file"


def test_load_env_file_accepts_truthy_env_override_values(monkeypatch, tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("SIPM_SECRET_KEY=from-file\n", encoding="utf-8")

    monkeypatch.setenv("SIPM_ENV_OVERRIDE", "yes")
    monkeypatch.setenv("SIPM_SECRET_KEY", "from-env")

    main_module._load_env_file(env_file)

    assert os.environ["SIPM_SECRET_KEY"] == "from-file"


def test_load_env_file_rejects_invalid_env_override_boolean(monkeypatch, tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("SIPM_SECRET_KEY=from-file\n", encoding="utf-8")

    monkeypatch.setenv("SIPM_ENV_OVERRIDE", "sometimes")

    with pytest.raises(RuntimeError, match="SIPM_ENV_OVERRIDE must be a boolean value."):
        main_module._load_env_file(env_file)


@pytest.mark.anyio
async def test_app_lifespan_validates_auth_configuration(monkeypatch):
    calls = {"count": 0}

    def fake_validate() -> None:
        calls["count"] += 1

    monkeypatch.setattr(main_module, "validate_auth_configuration", fake_validate)

    async with main_module.app.router.lifespan_context(main_module.app):
        pass

    assert calls["count"] == 1


@pytest.mark.anyio
async def test_app_lifespan_restores_anyio_threadpool_patch(monkeypatch):
    monkeypatch.setattr(main_module, "validate_auth_configuration", lambda: None)
    original_run_sync = anyio.to_thread.run_sync

    async with main_module.app.router.lifespan_context(main_module.app):
        patched_run_sync = anyio.to_thread.run_sync
        assert patched_run_sync is not original_run_sync
        assert getattr(patched_run_sync, "_jira_lite_patched", False) is True

    assert anyio.to_thread.run_sync is original_run_sync


@pytest.mark.anyio
async def test_app_lifespan_accepts_truthy_disable_startup_value(monkeypatch):
    monkeypatch.setattr(main_module, "validate_auth_configuration", lambda: None)
    monkeypatch.setattr(main_module, "sys", SimpleNamespace(modules={}))
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.setenv("SIPM_DISABLE_STARTUP", "1")

    calls = {"init_db": 0}

    def fake_init_db() -> None:
        calls["init_db"] += 1

    monkeypatch.setattr(main_module, "init_db", fake_init_db)

    async with main_module.app.router.lifespan_context(main_module.app):
        pass

    assert calls["init_db"] == 0


@pytest.mark.anyio
async def test_app_lifespan_accepts_truthy_disable_threadpool_value(monkeypatch):
    monkeypatch.setattr(main_module, "validate_auth_configuration", lambda: None)
    monkeypatch.setattr(main_module, "sys", SimpleNamespace(modules={}))
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.setenv("SIPM_DISABLE_THREADPOOL", "on")

    original_run_sync = anyio.to_thread.run_sync
    monkeypatch.setattr(main_module, "init_db", lambda: None)

    async with main_module.app.router.lifespan_context(main_module.app):
        patched_run_sync = anyio.to_thread.run_sync
        assert patched_run_sync is not original_run_sync
        assert getattr(patched_run_sync, "_jira_lite_patched", False) is True

    assert anyio.to_thread.run_sync is original_run_sync


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

    monkeypatch.setattr(main_module.asyncio, "sleep", fake_sleep)
    monkeypatch.setattr(main_module, "check_db_connection", fake_check_db_connection)

    with pytest.raises(asyncio.CancelledError):
        await main_module._db_keepwarm_loop(15)

    assert calls == {"sleep": 2, "check": 1}


@pytest.mark.anyio
async def test_app_lifespan_prewarms_pool_when_enabled(monkeypatch):
    monkeypatch.setattr(main_module, "validate_auth_configuration", lambda: None)
    monkeypatch.setattr(main_module.coordination, "validate_configuration", lambda: None)
    monkeypatch.setattr(main_module, "sys", SimpleNamespace(modules={}))
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
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

    monkeypatch.setattr(main_module, "start_realtime_runtime", fake_start_runtime)
    monkeypatch.setattr(main_module, "stop_realtime_runtime", fake_stop_runtime)
    monkeypatch.setattr(main_module, "init_db", fake_init_db)
    monkeypatch.setattr(main_module, "warm_db_pool", fake_warm_db_pool)

    async with main_module.app.router.lifespan_context(main_module.app):
        pass

    assert calls == {"init_db": 1, "warm": [2]}


@pytest.mark.anyio
async def test_app_lifespan_starts_keepwarm_task_when_enabled(monkeypatch):
    monkeypatch.setattr(main_module, "validate_auth_configuration", lambda: None)
    monkeypatch.setattr(main_module.coordination, "validate_configuration", lambda: None)
    monkeypatch.setattr(main_module, "sys", SimpleNamespace(modules={}))
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
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

    monkeypatch.setattr(main_module, "start_realtime_runtime", fake_start_runtime)
    monkeypatch.setattr(main_module, "stop_realtime_runtime", fake_stop_runtime)
    monkeypatch.setattr(main_module, "init_db", fake_init_db)
    monkeypatch.setattr(main_module, "check_db_connection", fake_check_db_connection)
    monkeypatch.setattr(main_module.asyncio, "create_task", fake_create_task)

    async with main_module.app.router.lifespan_context(main_module.app):
        pass

    assert calls == {"init_db": 1, "check": 1, "create_task": 1}
