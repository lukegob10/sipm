from __future__ import annotations

import importlib

import pytest

from backend.app.db import db as db_module
from backend.app import runtime as runtime_module


def _reload_db_module():
    return importlib.reload(db_module)


def _reload_runtime_module():
    return importlib.reload(runtime_module)


def test_explicit_database_url_takes_precedence(monkeypatch):
    monkeypatch.setenv("SIPM_DATABASE_URL", "sqlite:///explicit.db")
    monkeypatch.setenv("SIPM_DB_PROFILE", "prod")
    monkeypatch.setenv("SIPM_DATABASE_URL_PROD", "sqlite:///prod.db")

    module = _reload_db_module()
    assert module.DATABASE_URL == "sqlite:///explicit.db"


def test_profile_dev_uses_dev_url(monkeypatch):
    monkeypatch.delenv("SIPM_DATABASE_URL", raising=False)
    monkeypatch.setenv("SIPM_DB_PROFILE", "dev")
    monkeypatch.setenv("SIPM_DATABASE_URL_DEV", "sqlite:///dev.db")

    module = _reload_db_module()
    assert module.DATABASE_URL == "sqlite:///dev.db"


def test_profile_uat_uses_uat_url(monkeypatch):
    monkeypatch.delenv("SIPM_DATABASE_URL", raising=False)
    monkeypatch.setenv("SIPM_DB_PROFILE", "uat")
    monkeypatch.setenv("SIPM_DATABASE_URL_UAT", "sqlite:///uat.db")

    module = _reload_db_module()
    assert module.DATABASE_URL == "sqlite:///uat.db"


def test_profile_prod_uses_prod_url(monkeypatch):
    monkeypatch.delenv("SIPM_DATABASE_URL", raising=False)
    monkeypatch.setenv("SIPM_DB_PROFILE", "prod")
    monkeypatch.setenv("SIPM_DATABASE_URL_PROD", "sqlite:///prod.db")

    module = _reload_db_module()
    assert module.DATABASE_URL == "sqlite:///prod.db"


def test_profile_aliases(monkeypatch):
    monkeypatch.delenv("SIPM_DATABASE_URL", raising=False)
    monkeypatch.setenv("SIPM_DB_PROFILE", "production")
    monkeypatch.setenv("SIPM_DATABASE_URL_PROD", "sqlite:///prod.db")

    module = _reload_db_module()
    assert module.DATABASE_URL == "sqlite:///prod.db"


def test_missing_profile_url_falls_back_to_sqlite(monkeypatch):
    monkeypatch.delenv("SIPM_DATABASE_URL", raising=False)
    monkeypatch.delenv("SIPM_DB_PROFILE", raising=False)
    monkeypatch.delenv("SIPM_DATABASE_URL_DEV", raising=False)
    monkeypatch.delenv("SIPM_DATABASE_URL_UAT", raising=False)
    monkeypatch.delenv("SIPM_DATABASE_URL_PROD", raising=False)

    module = _reload_db_module()
    assert module.DATABASE_URL.startswith("sqlite:///")


def test_ta_oracle_mode_switches_engine_by_user(monkeypatch):
    monkeypatch.setenv("USER", "TA_ECS_DS1_RW")
    monkeypatch.setenv("SIPM_DB_PROFILE", "prod")

    captured = {}

    def _fake_create_engine(url, **kwargs):
        captured["url"] = url
        captured["kwargs"] = kwargs
        return object()

    monkeypatch.setattr(db_module, "create_engine", _fake_create_engine)
    db_module._build_engine()

    assert captured["url"] == "oracle+oracledb://"
    assert captured["kwargs"]["poolclass"] is db_module.NullPool
    assert callable(captured["kwargs"]["creator"])


def test_non_ta_user_uses_regular_database_url_engine(monkeypatch):
    monkeypatch.setenv("USER", "developer")
    monkeypatch.setattr(db_module, "DATABASE_URL", "sqlite:///explicit.db")

    captured = {}

    def _fake_create_engine(url, **kwargs):
        captured["url"] = url
        captured["kwargs"] = kwargs
        return object()

    monkeypatch.setattr(db_module, "create_engine", _fake_create_engine)
    db_module._build_engine()

    assert captured["url"] == "sqlite:///explicit.db"
    assert captured["kwargs"]["connect_args"] == {"check_same_thread": False}


def test_get_ta_connection_env_uses_profile_value(monkeypatch):
    monkeypatch.setenv("SIPM_DB_PROFILE", "uat")

    module = _reload_runtime_module()
    assert module.get_ta_connection_env() == "uat"


def test_get_ta_connection_env_uses_profile_alias(monkeypatch):
    monkeypatch.setenv("SIPM_DB_PROFILE", "production")

    module = _reload_runtime_module()
    assert module.get_ta_connection_env() == "prod"


def test_get_ta_connection_env_requires_profile(monkeypatch):
    monkeypatch.delenv("SIPM_DB_PROFILE", raising=False)

    module = _reload_runtime_module()
    with pytest.raises(RuntimeError):
        module.get_ta_connection_env()
