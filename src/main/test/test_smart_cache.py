from __future__ import annotations

import importlib

import pytest

from backend.app.services import smart_cache as smart_cache_module


def _reload_smart_cache_module():
    return importlib.reload(smart_cache_module)


def test_cache_enabled_accepts_common_falsey_values(monkeypatch):
    monkeypatch.setenv("SIPM_SMART_CACHE_ENABLED", "off")

    module = _reload_smart_cache_module()
    assert module._cache_enabled() is False


def test_cache_enabled_rejects_invalid_boolean(monkeypatch):
    monkeypatch.setenv("SIPM_SMART_CACHE_ENABLED", "sometimes")

    module = _reload_smart_cache_module()
    with pytest.raises(RuntimeError, match="SIPM_SMART_CACHE_ENABLED must be a boolean value."):
        module._cache_enabled()


def test_cache_max_entries_rejects_non_integer(monkeypatch):
    monkeypatch.setenv("SIPM_SMART_CACHE_MAX_ENTRIES", "many")

    module = _reload_smart_cache_module()
    with pytest.raises(RuntimeError, match="SIPM_SMART_CACHE_MAX_ENTRIES must be an integer."):
        module._cache_max_entries()


def test_cache_max_entries_rejects_zero(monkeypatch):
    monkeypatch.setenv("SIPM_SMART_CACHE_MAX_ENTRIES", "0")

    module = _reload_smart_cache_module()
    with pytest.raises(
        RuntimeError,
        match="SIPM_SMART_CACHE_MAX_ENTRIES must be greater than or equal to 1.",
    ):
        module._cache_max_entries()


def test_cache_max_entries_rejects_negative_values(monkeypatch):
    monkeypatch.setenv("SIPM_SMART_CACHE_MAX_ENTRIES", "-5")

    module = _reload_smart_cache_module()
    with pytest.raises(
        RuntimeError,
        match="SIPM_SMART_CACHE_MAX_ENTRIES must be greater than or equal to 1.",
    ):
        module._cache_max_entries()


def test_cache_max_entries_keeps_existing_minimum_floor(monkeypatch):
    monkeypatch.setenv("SIPM_SMART_CACHE_MAX_ENTRIES", "32")

    module = _reload_smart_cache_module()
    assert module._cache_max_entries() == 256
