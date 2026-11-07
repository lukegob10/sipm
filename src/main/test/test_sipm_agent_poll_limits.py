import importlib.util
import sys
from pathlib import Path

import pytest


script = Path(__file__).resolve().parents[3] / "skills/sipm-agent/scripts/sipm_agent.py"
spec = importlib.util.spec_from_file_location("sipm_agent_poll_test", script)
assert spec and spec.loader
sipm_agent = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sipm_agent)


@pytest.mark.parametrize("option", ["--timeout", "--interval"])
@pytest.mark.parametrize("value", ["nan", "inf", "-inf"])
def test_poll_rejects_nonfinite_timing_before_network(monkeypatch, option, value):
    monkeypatch.setattr(sys, "argv", ["sipm_agent.py", "poll-change-request", "--request-id", "request", f"{option}={value}"])

    def unexpected_client(*_args, **_kwargs):
        raise AssertionError("invalid timing must fail before making a client")

    monkeypatch.setattr(sipm_agent, "client_from_args", unexpected_client)
    with pytest.raises(SystemExit) as error:
        sipm_agent.main()
    assert error.value.code == 2


def test_poll_does_not_sleep_past_its_deadline(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", [
        "sipm_agent.py", "--space-id", "space", "poll-change-request", "--request-id", "request",
        "--timeout", "1", "--interval", "30",
    ])
    values = iter([{"status": "pending"}, {"status": "approved"}])

    class Client:
        def resolve_space_id(self, _space):
            return "space"

        def request(self, *_args, **_kwargs):
            return next(values)

    monkeypatch.setattr(sipm_agent, "client_from_args", lambda *_args, **_kwargs: Client())
    monkeypatch.setattr(sipm_agent.time, "monotonic", lambda: 100.0)
    sleeps = []
    monkeypatch.setattr(sipm_agent.time, "sleep", sleeps.append)

    assert sipm_agent.main() == 0
    assert sleeps == [1.0]
    assert '"approved"' in capsys.readouterr().out


def test_poll_does_not_make_another_request_after_timeout(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", [
        "sipm_agent.py", "--space-id", "space", "poll-change-request", "--request-id", "request",
        "--timeout", "1", "--interval", "30",
    ])
    now = [100.0]
    calls = []

    class Client:
        def resolve_space_id(self, _space):
            return "space"

        def request(self, *_args, **_kwargs):
            calls.append(1)
            return {"status": "pending"}

    monkeypatch.setattr(sipm_agent, "client_from_args", lambda *_args, **_kwargs: Client())
    monkeypatch.setattr(sipm_agent.time, "monotonic", lambda: now[0])
    monkeypatch.setattr(sipm_agent.time, "sleep", lambda seconds: now.__setitem__(0, now[0] + seconds))

    assert sipm_agent.main() == 1
    assert calls == [1]
    assert '"pending"' in capsys.readouterr().out
