from __future__ import annotations

import logging


def test_call_chat_completion_extracts_openai_style_dict(monkeypatch):
    from backend.app.ai import llm

    class DummyModels:
        def generate_content(self, model, contents):
            assert model
            assert contents
            return {
                "id": "chatcmpl-1",
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": '{"action":"final","reply":"Use Build > Deliverables, then Create Project.","requires_approval":false}',
                        },
                    }
                ],
            }

    class DummyClient:
        models = DummyModels()

    monkeypatch.setattr(llm, "get_client", lambda: DummyClient())
    monkeypatch.setenv("GENAI_MODEL", "gemini-2.5-flash")

    out = llm.call_chat_completion("system", "user")
    assert '"action":"final"' in out
    assert "Create Project" in out


def test_call_chat_completion_extracts_gemini_candidates_parts(monkeypatch):
    from backend.app.ai import llm

    class DummyModels:
        def generate_content(self, model, contents):
            assert model
            assert contents
            return {
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {
                                    "text": '{"action":"final","reply":"Go to Build > Deliverables and click Create Project.","requires_approval":false}'
                                }
                            ]
                        }
                    }
                ]
            }

    class DummyClient:
        models = DummyModels()

    monkeypatch.setattr(llm, "get_client", lambda: DummyClient())
    monkeypatch.setenv("GENAI_MODEL", "gemini-2.5-flash")

    out = llm.call_chat_completion("system", "user")
    assert '"action":"final"' in out
    assert "Build > Deliverables" in out


def test_call_chat_completion_logs_client_validity_only_when_trace_enabled(monkeypatch, caplog):
    from backend.app.ai import llm

    class DummyResponse:
        text = "ok"

    class DummyModels:
        def generate_content(self, model, contents):
            assert model
            assert contents
            return DummyResponse()

    class DummyClient:
        models = DummyModels()

    monkeypatch.setattr(llm, "get_client", lambda: DummyClient())
    monkeypatch.setenv("GENAI_MODEL", "gemini-2.5-flash")
    monkeypatch.setenv("AI_DEBUG_TRACE", "true")
    caplog.set_level(logging.INFO, logger="backend.app.ai.llm")

    llm.call_chat_completion("system", "user")

    assert any("got a real object that works=true" in rec.message for rec in caplog.records)


def test_call_chat_completion_does_not_log_client_validity_when_trace_disabled(monkeypatch, caplog):
    from backend.app.ai import llm

    class DummyResponse:
        text = "ok"

    class DummyModels:
        def generate_content(self, model, contents):
            assert model
            assert contents
            return DummyResponse()

    class DummyClient:
        models = DummyModels()

    monkeypatch.setattr(llm, "get_client", lambda: DummyClient())
    monkeypatch.setenv("GENAI_MODEL", "gemini-2.5-flash")
    monkeypatch.delenv("AI_DEBUG_TRACE", raising=False)
    monkeypatch.delenv("GENAI_TRACE", raising=False)
    caplog.set_level(logging.INFO, logger="backend.app.ai.llm")

    llm.call_chat_completion("system", "user")

    assert not any("got a real object that works=" in rec.message for rec in caplog.records)
