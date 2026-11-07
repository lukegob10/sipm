import importlib.util
import sys
from pathlib import Path

import pytest


script = Path(__file__).resolve().parents[3] / "skills/sipm-agent/scripts/sipm_agent.py"
spec = importlib.util.spec_from_file_location("sipm_agent_delegated_space", script)
sipm_agent = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sipm_agent)


@pytest.mark.parametrize("command", ["review-request", "delegated-approve", "delegated-reject"])
def test_delegated_space_lookup_uses_agent_token_only(monkeypatch, command, capsys):
    calls = []

    class Client:
        def __init__(self, kind):
            self.kind = kind

        def resolve_space_id(self, space):
            calls.append((self.kind, "resolve", space))
            return "space-id"

        def request(self, method, path, **kwargs):
            calls.append((self.kind, method, path, kwargs))
            return {"status": "pending"}

    monkeypatch.setenv("SIPM_AGENT_TOKEN", "api-token")
    monkeypatch.setattr(sipm_agent, "client_from_args", lambda _args, human=False: Client("human" if human else "agent"))
    args = ["sipm_agent.py", command, "--space", "main", "--request-id", "request"]
    if command != "review-request":
        args += ["--observed-updated-at", "2026-01-01", "--observed-fingerprint", "f" * 64]
    monkeypatch.setattr(sys, "argv", args)
    assert sipm_agent.main() == 0
    assert calls[0] == ("agent", "resolve", "main")
    assert calls[1][0] == "human"
    assert calls[1][3]["space_id"] == "space-id"
    capsys.readouterr()


def test_delegated_explicit_space_id_needs_no_agent_token(monkeypatch):
    monkeypatch.delenv("SIPM_AGENT_TOKEN", raising=False)
    monkeypatch.delenv("SIPM_TOKEN", raising=False)
    calls = []

    class Client:
        def resolve_space_id(self, space):
            calls.append(space)
            return "exact-space"

        def request(self, method, path, **kwargs):
            assert kwargs["space_id"] == "exact-space"
            return {"status": "pending"}

    monkeypatch.setattr(sipm_agent, "client_from_args", lambda _args, human=False: Client())
    monkeypatch.setattr(sys, "argv", ["sipm_agent.py", "--space-id", "exact-space", "review-request", "--request-id", "r"])
    assert sipm_agent.main() == 0
    assert calls == [None]


def test_delegated_named_space_requires_agent_token_or_exact_id(monkeypatch):
    monkeypatch.delenv("SIPM_AGENT_TOKEN", raising=False)
    monkeypatch.delenv("SIPM_TOKEN", raising=False)
    monkeypatch.setattr(sipm_agent, "client_from_args", lambda _args, human=False: object())
    monkeypatch.setattr(sys, "argv", ["sipm_agent.py", "review-request", "--space", "main", "--request-id", "r"])
    with pytest.raises(SystemExit, match="requires SIPM_AGENT_TOKEN"):
        sipm_agent.main()
