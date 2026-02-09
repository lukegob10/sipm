from __future__ import annotations

import sys
from types import ModuleType

import pytest


def _reset_client_cache():
    from backend.app.ai import client as client_module

    client_module._CACHED_CLIENT = None


def test_get_client_returns_cached_client(monkeypatch):
    _reset_client_cache()

    call_count = {"value": 0}
    sentinel = object()
    google_mod = ModuleType("google")
    genai_mod = ModuleType("google.genai")

    def build_client(*_args, **_kwargs):
        call_count["value"] += 1
        return sentinel

    genai_mod.Client = build_client  # type: ignore[attr-defined]
    google_mod.genai = genai_mod  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "google", google_mod)
    monkeypatch.setitem(sys.modules, "google.genai", genai_mod)
    monkeypatch.delenv("GENAI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_GENAI_USE_VERTEXAI", raising=False)
    monkeypatch.delenv("GENAI_USE_VERTEXAI", raising=False)
    monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
    monkeypatch.delenv("GOOGLE_PROJECT_ID", raising=False)
    monkeypatch.delenv("GENAI_PROJECT", raising=False)

    from backend.app.ai.client import get_client

    assert get_client() is sentinel
    assert get_client() is sentinel
    assert call_count["value"] == 1


def test_get_client_raises_config_error_when_sdk_missing(monkeypatch):
    _reset_client_cache()

    monkeypatch.setitem(sys.modules, "google", ModuleType("google"))
    monkeypatch.delitem(sys.modules, "google.genai", raising=False)

    from backend.app.ai.client import get_client
    from backend.app.ai.errors import GenAIConfigError

    with pytest.raises(GenAIConfigError, match="google-genai package is not available"):
        get_client()


def test_get_client_includes_sdk_init_error_details(monkeypatch):
    _reset_client_cache()

    google_mod = ModuleType("google")
    genai_mod = ModuleType("google.genai")

    def broken_client(*_args, **_kwargs):
        raise ValueError("Missing key inputs argument!")

    genai_mod.Client = broken_client  # type: ignore[attr-defined]
    google_mod.genai = genai_mod  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "google", google_mod)
    monkeypatch.setitem(sys.modules, "google.genai", genai_mod)

    monkeypatch.delenv("GENAI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_GENAI_USE_VERTEXAI", raising=False)
    monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
    monkeypatch.delenv("GOOGLE_PROJECT_ID", raising=False)
    monkeypatch.delenv("GENAI_PROJECT", raising=False)

    from backend.app.ai.client import get_client
    from backend.app.ai.errors import GenAIConfigError

    with pytest.raises(GenAIConfigError, match="Failed to initialize genai.Client: Missing key inputs argument!"):
        get_client()


def test_get_client_uses_vertex_mode_when_configured(monkeypatch):
    _reset_client_cache()

    called = {"kwargs": None}
    sentinel = object()
    google_mod = ModuleType("google")
    genai_mod = ModuleType("google.genai")

    def build_client(*_args, **kwargs):
        called["kwargs"] = kwargs
        return sentinel

    genai_mod.Client = build_client  # type: ignore[attr-defined]
    google_mod.genai = genai_mod  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "google", google_mod)
    monkeypatch.setitem(sys.modules, "google.genai", genai_mod)

    monkeypatch.setenv("GOOGLE_GENAI_USE_VERTEXAI", "true")
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "my-proj")
    monkeypatch.setenv("GOOGLE_CLOUD_LOCATION", "us-central1")
    monkeypatch.delenv("GENAI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    from backend.app.ai.client import get_client

    assert get_client() is sentinel
    assert called["kwargs"] == {"vertexai": True, "project": "my-proj", "location": "us-central1"}
