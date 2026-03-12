from __future__ import annotations

import importlib
import os
import sys
from types import SimpleNamespace

import pytest

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


def test_db_engine_uses_pooling_env_overrides(monkeypatch):
    monkeypatch.setenv("SIPM_DB_POOL_SIZE", "7")
    monkeypatch.setenv("SIPM_DB_MAX_OVERFLOW", "2")
    monkeypatch.setenv("SIPM_DB_POOL_TIMEOUT_SECONDS", "12")
    monkeypatch.setenv("SIPM_DB_POOL_RECYCLE_SECONDS", "90")
    monkeypatch.setenv("SIPM_DB_POOL_PRE_PING", "false")

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


@pytest.mark.anyio
async def test_app_lifespan_validates_auth_configuration(monkeypatch):
    calls = {"count": 0}

    def fake_validate() -> None:
        calls["count"] += 1

    monkeypatch.setattr(main_module, "validate_auth_configuration", fake_validate)

    async with main_module.app.router.lifespan_context(main_module.app):
        pass

    assert calls["count"] == 1
