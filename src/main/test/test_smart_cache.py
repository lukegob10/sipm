from __future__ import annotations

import importlib
import threading

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


def test_scoped_cache_keys_separate_space_user_and_role(monkeypatch):
    module = _reload_smart_cache_module()
    monkeypatch.setattr(module, "_scope_version_snapshot", lambda _tokens: {})

    def build(*, space_id="space-1", user_id="user-1", role_scope="member"):
        return module.build_scoped_cache_key(
            endpoint="projects",
            params={"limit": 20},
            space_id=space_id,
            user_id=user_id,
            role_scope=role_scope,
            scope_tokens=["projects:space-1"],
        )

    base_key = build()
    assert build(space_id="space-2") != base_key
    assert build(user_id="user-2") != base_key
    assert build(role_scope="admin") != base_key


def test_scope_version_lookup_does_not_hold_cache_lock(monkeypatch):
    module = _reload_smart_cache_module()
    module.clear_cache()
    module.set_cached("warm-entry", {"ready": True}, ttl_seconds=60)
    scope_lookup_started = threading.Event()
    allow_scope_lookup = threading.Event()
    warm_lookup_finished = threading.Event()

    def slow_scope_lookup(_tokens):
        scope_lookup_started.set()
        allow_scope_lookup.wait(2)
        return {}

    monkeypatch.setattr(module, "_scope_version_snapshot", slow_scope_lookup)
    key_builder = threading.Thread(
        target=lambda: module.build_scoped_cache_key(
            endpoint="projects",
            params={},
            space_id="space-1",
            user_id="user-1",
            role_scope="member",
            scope_tokens=["projects:space-1"],
        )
    )
    key_builder.start()
    assert scope_lookup_started.wait(1)

    def read_warm_entry():
        module.get_cached("warm-entry")
        warm_lookup_finished.set()

    warm_reader = threading.Thread(target=read_warm_entry)
    warm_reader.start()
    warm_lookup_was_unblocked = warm_lookup_finished.wait(0.5)
    allow_scope_lookup.set()
    key_builder.join(1)
    warm_reader.join(1)

    assert warm_lookup_was_unblocked is True
    assert not key_builder.is_alive()
    assert not warm_reader.is_alive()


def test_cached_call_returns_mutable_miss_result_without_aliasing_cache(monkeypatch):
    module = _reload_smart_cache_module()
    module.clear_cache()
    monkeypatch.setattr(module, "_scope_version_snapshot", lambda _tokens: {})
    source = {"items": [1]}

    result = module.cached_call(
        endpoint="projects",
        params={},
        space_id="space-1",
        user_id="user-1",
        role_scope="member",
        ttl_seconds=60,
        scope_tokens=[],
        loader=lambda: source,
    )
    result["items"].append(2)

    cached_result = module.cached_call(
        endpoint="projects",
        params={},
        space_id="space-1",
        user_id="user-1",
        role_scope="member",
        ttl_seconds=60,
        scope_tokens=[],
        loader=lambda: pytest.fail("cache hit should not call loader"),
    )

    assert source == {"items": [1]}
    assert cached_result == {"items": [1]}
