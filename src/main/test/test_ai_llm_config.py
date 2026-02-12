from __future__ import annotations


def test_resolve_model_with_source_prefers_genai_model(monkeypatch):
    from backend.app.ai.llm import resolve_model_with_source

    monkeypatch.setenv("GENAI_MODEL", "gemini-primary")

    model, source = resolve_model_with_source()
    assert model == "gemini-primary"
    assert source == "GENAI_MODEL"


def test_resolve_model_with_source_uses_default_when_unset(monkeypatch):
    from backend.app.ai.llm import resolve_model_with_source

    monkeypatch.delenv("GENAI_MODEL", raising=False)

    model, source = resolve_model_with_source()
    assert model == "gemini-2.5-flash"
    assert source == "default"


def test_config_diagnostics_includes_model_and_trace(monkeypatch):
    from backend.app.ai.llm import config_diagnostics

    monkeypatch.delenv("GENAI_MODEL", raising=False)
    monkeypatch.setenv("AI_DEBUG_TRACE", "true")

    output = config_diagnostics()
    assert "model=gemini-2.5-flash" in output
    assert "model_from=default" in output
    assert "trace_enabled=true" in output
