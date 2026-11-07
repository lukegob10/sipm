import importlib.util
import json
import sys
import urllib.error
from pathlib import Path

import pytest


script = Path(__file__).resolve().parents[3] / "skills/sipm-agent/scripts/sipm_agent.py"
spec = importlib.util.spec_from_file_location("sipm_agent_idempotency", script)
assert spec and spec.loader
sipm_agent = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sipm_agent)


@pytest.mark.parametrize("command", ["propose-update", "propose-archive"])
def test_generated_key_can_recover_proposal_after_lost_response(command, monkeypatch, capsys):
    class Client:
        def __init__(self):
            self.requests = {}
            self.attempts = 0

        def resolve_space_id(self, _space):
            return "space"

        def get_detail(self, *_args, **_kwargs):
            return {"updated_at": "2026-01-01T00:00:00"}

        def request(self, method, path, *, space_id, body=None, query=None):
            assert space_id == "space"
            if method == "GET":
                assert path == "/agent/change-requests"
                key = query["idempotency_key"]
                assert query["status"] == "all"
                return {"records": [{"request_id": "existing", "idempotency_key": key}] if key in self.requests else []}
            self.attempts += 1
            key = body["idempotency_key"]
            self.requests.setdefault(key, body)
            raise urllib.error.URLError("response lost")

    client = Client()
    monkeypatch.setattr(sipm_agent, "client_from_args", lambda *_args, **_kwargs: client)
    args = ["sipm_agent.py", command, "--space", "space", "--entity-type", "task", "--id", "task", "--reason", "reason"]
    if command == "propose-update":
        args.extend(["--fields-json", '{"description":"updated"}'])
    monkeypatch.setattr(sys, "argv", args)
    with pytest.raises(urllib.error.URLError):
        sipm_agent.main()
    output = capsys.readouterr()
    assert output.out == ""
    assert output.err.startswith("Idempotency key: ")
    key = output.err.splitlines()[0].removeprefix("Idempotency key: ").strip()
    assert key in client.requests
    assert "list-change-requests --status all --idempotency-key" in output.err
    monkeypatch.setattr(sys, "argv", ["sipm_agent.py", "list-change-requests", "--space", "space", "--status", "all", "--idempotency-key", key])
    assert sipm_agent.main() == 0
    recovered = capsys.readouterr()
    assert json.loads(recovered.out) == {"records": [{"request_id": "existing", "idempotency_key": key}]}
    assert len(client.requests) == 1
