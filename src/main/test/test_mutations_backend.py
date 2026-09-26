from __future__ import annotations

import pytest

from backend.app.services import mutations


def test_committed_mutation_invalidates_even_if_refresh_fails(monkeypatch):
    events: list[object] = []

    class SessionStub:
        def commit(self) -> None:
            events.append("commit")

        def rollback(self) -> None:
            events.append("rollback")

        def refresh(self, _instance) -> None:
            events.append("refresh")
            raise RuntimeError("database disconnected after commit")

    def publish(space_id, cache_keys, *, broadcast_channel=None):
        events.append(("publish", space_id, tuple(cache_keys), broadcast_channel))

    monkeypatch.setattr(mutations, "publish_space_mutation", publish)

    with pytest.raises(RuntimeError, match="database disconnected after commit"):
        mutations.commit_refresh_and_publish(
            SessionStub(),
            object(),
            space_id="space-1",
            cache_keys=["tasks"],
            broadcast_channel="tasks",
        )

    assert events == [
        "commit",
        "refresh",
        ("publish", "space-1", ("tasks",), "tasks"),
    ]
