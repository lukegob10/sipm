from __future__ import annotations

from datetime import datetime

import pytest

from backend.app.services.audit_log import log_changes
from backend.app.models import ChangeLog


@pytest.mark.anyio
async def test_audit_endpoint_supports_filters(client):
    project = (
        await client.post(
            "/project-manager/api/projects/",
            json={
                "project_name": "Audit Project",
                "status": "active",
                "sponsor": "CFO Office",
            },
        )
    ).json()

    all_rows = await client.get("/project-manager/api/audit")
    assert all_rows.status_code == 200
    assert len(all_rows.json()) > 0

    filtered = await client.get(
        "/project-manager/api/audit",
        params={
            "entity_type": "project",
            "entity_id": project["project_id"],
            "field": "project_name",
            "user_id": "test-user",
            "since": "1970-01-01T00:00:00",
            "until": "2999-01-01T00:00:00",
            "limit": 50,
        },
    )
    assert filtered.status_code == 200
    rows = filtered.json()
    assert len(rows) >= 1
    assert all(row["entity_type"] == "project" for row in rows)
    assert all(row["entity_id"] == project["project_id"] for row in rows)
    assert all(row["field"] == "project_name" for row in rows)
    assert all(row["user_id"] == "test-user" for row in rows)


@pytest.mark.anyio
async def test_audit_all_spaces_rows_include_space_id(client):
    project = (
        await client.post(
            "/project-manager/api/projects/",
            json={
                "project_name": "Cross Space Audit Project",
                "status": "active",
                "sponsor": "Architecture",
            },
        )
    ).json()

    rows = (
        await client.get(
            "/project-manager/api/audit",
            params={
                "entity_type": "project",
                "entity_id": project["project_id"],
                "all_spaces": "true",
            },
        )
    ).json()

    assert rows
    assert all("space_id" in row for row in rows)
    assert all(row["space_id"] for row in rows)


def test_log_changes_stringifies_and_ignores_invalid_or_noop_pairs(db_sessionmaker):
    class BadIso:
        def isoformat(self):
            raise RuntimeError("boom")

    with db_sessionmaker() as session:
        # invalid pair => ignored
        log_changes(
            session,
            entity_type="project",
            entity_id="p1",
            user_id="u1",
            action="update",
            changes={"x": "not-a-tuple"},
        )

        # old == new => ignored (should not create rows)
        log_changes(
            session,
            entity_type="project",
            entity_id="p1",
            user_id="u1",
            action="update",
            changes={"same": ("a", "a")},
        )

        # changes None => one row without field values
        log_changes(
            session,
            entity_type="project",
            entity_id="p1",
            user_id="u1",
            action="create",
            changes=None,
        )

        # stringify isoformat exception path
        bad = BadIso()
        log_changes(
            session,
            entity_type="project",
            entity_id="p1",
            user_id="u1",
            action="update",
            changes={"bad": (None, bad)},
        )

        session.commit()

        rows = (
            session.query(ChangeLog)
            .filter(ChangeLog.entity_type == "project")
            .filter(ChangeLog.entity_id == "p1")
            .order_by(ChangeLog.created_at.asc())
            .all()
        )
        assert len(rows) == 2
        assert rows[0].field is None
        assert rows[1].field == "bad"
        assert rows[1].new_value == str(bad)


def test_log_changes_reads_lob_values_and_skips_equal_text(db_sessionmaker):
    class FakeLob:
        def __init__(self, value: str):
            self.value = value

        def read(self) -> str:
            return self.value

    with db_sessionmaker() as session:
        log_changes(
            session,
            entity_type="project",
            entity_id="p-lob",
            user_id="u1",
            action="update",
            changes={
                "same": (FakeLob("unchanged"), "unchanged"),
                "description": (None, FakeLob("expanded project description")),
            },
        )
        session.commit()

        rows = (
            session.query(ChangeLog)
            .filter(ChangeLog.entity_type == "project")
            .filter(ChangeLog.entity_id == "p-lob")
            .order_by(ChangeLog.created_at.asc())
            .all()
        )
        assert len(rows) == 1
        assert rows[0].field == "description"
        assert rows[0].new_value == "expanded project description"

