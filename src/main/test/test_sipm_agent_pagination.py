import importlib.util
from pathlib import Path

import pytest


script = Path(__file__).resolve().parents[3] / "skills/sipm-agent/scripts/sipm_agent.py"
spec = importlib.util.spec_from_file_location("sipm_agent_pagination_test", script)
assert spec and spec.loader
sipm_agent = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sipm_agent)


def test_all_pages_collects_complete_results(monkeypatch):
    client = sipm_agent.SipmClient("http://example.invalid", "token")
    pages = iter([
        {"records": [{"id": 1}], "has_more": True, "next_cursor": "next"},
        {"records": [{"id": 2}], "has_more": False, "next_cursor": None},
    ])
    monkeypatch.setattr(client, "request", lambda *_args, **_kwargs: next(pages))
    result = client.all_pages("/test")
    assert result["records"] == [{"id": 1}, {"id": 2}]
    assert result["has_more"] is False and result["next_cursor"] is None


@pytest.mark.parametrize("responses", [
    [{"records": [], "has_more": True, "next_cursor": None}],
    [{"records": [], "has_more": True, "next_cursor": "same"}] * 2,
], ids=["missing-cursor", "repeated-cursor"])
def test_all_pages_rejects_incomplete_or_stalled_pagination(monkeypatch, responses):
    client = sipm_agent.SipmClient("http://example.invalid", "token")
    pages = iter(responses)

    def request(*_args, **_kwargs):
        try:
            return next(pages)
        except StopIteration as exc:
            raise RuntimeError("pagination continued unexpectedly") from exc

    monkeypatch.setattr(client, "request", request)
    with pytest.raises(SystemExit, match="cursor"):
        client.all_pages("/test")
