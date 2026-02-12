from __future__ import annotations

import importlib

import pytest

from backend.app import runtime as runtime_module


def _reload_runtime_module():
    return importlib.reload(runtime_module)


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
