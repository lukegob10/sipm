from datetime import datetime, timedelta, timezone

import httpx
import pytest

from backend.app import deps
from backend.app.models import AgentChangeRequest, ApiToken, ChangeLog, Space, SpaceMembership, User
from backend.app.services.api_tokens import hash_api_token
from backend.main import app


@pytest.mark.anyio
async def test_audit_feed_only_exposes_own_change_request_history(db_sessionmaker):
    tokens = {name: f"sipm_pat_{name}_audit" for name in ("alice", "bob")}
    with db_sessionmaker() as session:
        session.add(Space(space_id="audit-space", name="Audit Space", slug="audit-space"))
        for name in tokens:
            session.add_all([
                User(user_id=name, soeid=name, email=f"{name}@example.com", display_name=name,
                     password_hash="unused", role="user", is_active=True),
                SpaceMembership(space_id="audit-space", user_id=name, role="member", status="active"),
                ApiToken(user_id=name, name="test", token_hash=hash_api_token(tokens[name]), created_by_user_id=name),
                AgentChangeRequest(change_request_id=f"{name}-request", space_id="audit-space", proposed_by_user_id=name,
                                   reason=f"{name} private reason", idempotency_key=name, operations_json="[]",
                                   validation_json="{}", diff_json="[]"),
            ])
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        session.add_all([
            ChangeLog(change_id="own", entity_type="agent_change_request", entity_id="alice-request", action="update",
                      field="reason", old_value="previous", new_value="alice private reason", user_id="alice",
                      space_id="audit-space", created_at=now),
            ChangeLog(change_id="reviewed", entity_type="agent_change_request", entity_id="alice-request", action="approve",
                      field="status", old_value="pending", new_value="approved", user_id="bob",
                      space_id="audit-space", created_at=now - timedelta(seconds=1)),
            ChangeLog(change_id="foreign", entity_type="agent_change_request", entity_id="bob-request", action="update",
                      field="reason", old_value="previous", new_value="bob private reason", user_id="bob",
                      space_id="audit-space", created_at=now - timedelta(seconds=2)),
            ChangeLog(change_id="orphan", entity_type="agent_change_request", entity_id="missing", action="update",
                      user_id="alice", space_id="audit-space", created_at=now - timedelta(seconds=3)),
            ChangeLog(change_id="work", entity_type="task", entity_id="task-1", action="update", user_id="bob",
                      space_id="audit-space", created_at=now - timedelta(seconds=4)),
        ])
        session.commit()

    def database():
        with db_sessionmaker() as session:
            yield session

    app.dependency_overrides[deps.get_db] = database
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            async def get(user, **params):
                return await client.get("/project-manager/api/agent/audit-feed", params=params,
                                        headers={"Authorization": f"Bearer {tokens[user]}", "X-Space-Id": "audit-space"})
            foreign = await get("alice", entity_type="agent_change_request", entity_id="bob-request")
            assert foreign.status_code == 200 and foreign.json()["records"] == []
            cursor = None
            records = []
            while True:
                params = {"limit": 1}
                if cursor:
                    params["cursor"] = cursor
                response = await get("alice", **params)
                assert response.status_code == 200, response.text
                body = response.json()
                records.extend(body["records"])
                if not body["has_more"]:
                    break
                cursor = body["next_cursor"]
                if len(records) == 1:
                    cross_user = await get("bob", limit=1, cursor=cursor)
                    assert cross_user.status_code == 400
            assert [row["change_id"] for row in records] == ["own", "reviewed", "work"]
            bob = await get("bob", entity_type="agent_change_request")
            assert [row["change_id"] for row in bob.json()["records"]] == ["foreign"]
    finally:
        app.dependency_overrides.clear()


def test_owned_audit_filter_compiles_for_oracle(db_sessionmaker):
    from sqlalchemy import event
    from sqlalchemy.dialects import oracle
    from backend.app.services.agent_audit import list_agent_audit_feed
    from backend.app.services.spaces import SpaceContext

    with db_sessionmaker() as session:
        statements = []

        @event.listens_for(session, "do_orm_execute")
        def capture(execution):
            statements.append(str(execution.statement.compile(dialect=oracle.dialect())))

        ctx = SpaceContext(space_id="audit-space", space_name="Audit", is_global_admin=False, space_role="member")
        assert list_agent_audit_feed(session, ctx, requester_user_id="alice").records == []
        assert len(statements) == 1
        assert "EXISTS" in statements[0]
        assert "proposed_by_user_id" in statements[0]
