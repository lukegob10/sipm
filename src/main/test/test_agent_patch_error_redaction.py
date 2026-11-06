import logging

import pytest
from sqlalchemy.exc import IntegrityError

from backend.app.models import Space, SpaceMembership, User
from backend.app.schemas.agent import AgentPatchRequest
from backend.app.services import agent_patch_plan
from backend.app.services.spaces import SpaceContext


@pytest.mark.parametrize("commit", [True, False])
@pytest.mark.parametrize("conflict", [False, True])
def test_patch_apply_does_not_return_or_log_exception_secrets(db_sessionmaker, monkeypatch, caplog, commit, conflict):
    secret = "synthetic-password-DO-NOT-EXPOSE"
    payload = AgentPatchRequest(
        dry_run=False,
        reason="Create a project",
        idempotency_key="redaction-test",
        operations=[{"client_operation_id": "one", "op": "create", "entity": "project",
                     "fields": {"project_name": "Test project"}}],
    )
    ctx = SpaceContext(space_id="space", space_name="Space", space_role="member", is_global_admin=False)
    with db_sessionmaker() as session:
        session.add_all([
            Space(space_id="space", name="Space", slug="space"),
            User(user_id="reviewer", soeid="reviewer", email="reviewer@example.com",
                 display_name="Reviewer", password_hash="unused", role="user", is_active=True),
            SpaceMembership(space_id="space", user_id="reviewer", role="member", status="active"),
        ])
        session.commit()

        def fail(*_args, **_kwargs):
            if conflict:
                raise IntegrityError("insert secret", {"password": secret}, RuntimeError(secret))
            raise RuntimeError(f"database connection password={secret}")

        monkeypatch.setattr(agent_patch_plan, "_apply_project", fail)
        with caplog.at_level(logging.ERROR, logger=agent_patch_plan.__name__):
            result = agent_patch_plan.apply_patch_plan(session, ctx, session.get(User, "reviewer"), payload, commit=commit)

        assert result.valid is False and result.applied is False
        assert result.results[0].code == "APPLY_FAILED"
        expected = ("Patch application failed due to a data conflict" if conflict
                    else "Patch application failed due to an unexpected error")
        assert result.results[0].message == expected
        assert secret not in result.model_dump_json()
        assert secret not in caplog.text
        if not conflict:
            assert "Patch application failed (RuntimeError)" in caplog.text
