from __future__ import annotations

import pytest
from sqlalchemy import event

from backend.app.models import AgentChangeRequest, Program, Project, SpaceMembership, User
from backend.app.schemas.agent import AgentChangeRequestUpdate
from backend.app.services import agent_change_requests as service
from test_agent_change_request_idempotency import _request, _seed_actor, _space_context


@pytest.fixture
def review_request(db_sessionmaker):
    user_id, space_id = _seed_actor(db_sessionmaker)
    with db_sessionmaker() as session:
        session.add(SpaceMembership(
            space_id=space_id, user_id=user_id, role="member", status="active",
        ))
        session.commit()
        proposed = service.create_change_request(
            session, _space_context(space_id), session.get(User, user_id), _request(),
        )
    return user_id, space_id, proposed


@pytest.mark.parametrize("action", [
    "create", "update", "cancel", "reject", "approve", "approve-operations",
    "approve-invalid", "approve-operations-invalid",
])
def test_committed_request_publishes_when_response_refresh_fails(
    db_sessionmaker, monkeypatch, review_request, action,
):
    user_id, space_id, proposed = review_request
    publications = []

    def publish_request(changed_space_id):
        assert changed_space_id == space_id
        with db_sessionmaker() as verification:
            row = verification.get(AgentChangeRequest, proposed.change_request_id)
            expected_status = {
                "cancel": "cancelled", "reject": "rejected", "approve": "approved",
                "approve-operations": "approved", "approve-invalid": "failed",
                "approve-operations-invalid": "failed",
            }.get(action, "pending")
            assert row.status == expected_status
            if action == "create":
                assert verification.query(AgentChangeRequest).count() == 2
            elif action == "update":
                assert row.reason == "Updated proposal"
            elif expected_status == "approved":
                assert verification.query(Project).filter_by(project_name="Created Once").count() == 1
        publications.append("requests")

    monkeypatch.setattr(service, "_publish_change_requests", publish_request)
    monkeypatch.setattr(service, "publish_patch_plan_mutations", lambda *_args: publications.append("patch"))
    with db_sessionmaker() as session:
        actor = session.get(User, user_id)
        if action.endswith("-invalid"):
            session.add(Program(program_id="existing-program", space_id=space_id, program_name="Existing Program"))
            session.flush()
            session.add(Project(space_id=space_id, program_id="existing-program", project_name="Created Once"))
            session.commit()

        def fail_refresh(_row, *_args, **_kwargs):
            raise RuntimeError("response refresh failed after commit")

        monkeypatch.setattr(session, "refresh", fail_refresh)
        with pytest.raises(RuntimeError, match="response refresh failed after commit"):
            if action == "create":
                service.create_change_request(
                    session, _space_context(space_id), actor, _request(idempotency_key="second-key"),
                )
            elif action == "update":
                service.update_change_request(
                    session, _space_context(space_id), actor, proposed.change_request_id,
                    AgentChangeRequestUpdate(
                        if_request_updated_at=proposed.updated_at,
                        if_request_fingerprint=proposed.content_fingerprint,
                        reason="Updated proposal", operations=proposed.operations,
                    ),
                )
            elif action == "cancel":
                service.cancel_change_request(session, _space_context(space_id), actor, proposed.change_request_id)
            elif action == "reject":
                service.reject_change_request(
                    session, _space_context(space_id), actor, proposed.change_request_id,
                    if_request_fingerprint=proposed.content_fingerprint,
                )
            elif action.startswith("approve-operations"):
                service.approve_change_request_operations(
                    session, _space_context(space_id), actor, proposed.change_request_id,
                    ["create-project"], if_request_fingerprint=proposed.content_fingerprint,
                )
            else:
                service.approve_change_request(
                    session, _space_context(space_id), actor, proposed.change_request_id,
                    if_request_fingerprint=proposed.content_fingerprint,
                )
    assert publications == (["patch", "requests"] if action in {"approve", "approve-operations"} else ["requests"])


@pytest.mark.parametrize("action", ["approve", "reject"])
def test_bulk_review_does_not_publish_if_deferred_refresh_fails(
    db_sessionmaker, monkeypatch, review_request, action,
):
    user_id, space_id, proposed = review_request
    publications = []
    monkeypatch.setattr(service, "_publish_change_requests", lambda *_args: publications.append("requests"))
    monkeypatch.setattr(service, "publish_patch_plan_mutations", lambda *_args: publications.append("patch"))
    with db_sessionmaker() as session:
        actor = session.get(User, user_id)

        def fail_refresh(_row, *_args, **_kwargs):
            raise RuntimeError("deferred response refresh failed")

        monkeypatch.setattr(session, "refresh", fail_refresh)
        with pytest.raises(RuntimeError, match="deferred response refresh failed"):
            review = service.approve_selected_change_requests if action == "approve" else service.reject_selected_change_requests
            review(
                session, _space_context(space_id), actor, [proposed.change_request_id],
                if_request_fingerprints={proposed.change_request_id: proposed.content_fingerprint},
            )
    assert publications == []
    with db_sessionmaker() as session:
        assert session.get(AgentChangeRequest, proposed.change_request_id).status == "pending"
        assert session.query(Project).filter_by(project_name="Created Once").count() == 0


def test_failed_request_commit_does_not_publish(db_sessionmaker, monkeypatch, review_request):
    user_id, space_id, proposed = review_request
    publications = []
    monkeypatch.setattr(service, "_publish_change_requests", lambda *_args: publications.append("requests"))
    with db_sessionmaker() as session:
        actor = session.get(User, user_id)

        def fail_commit(_session):
            raise RuntimeError("request commit failed")

        event.listen(session, "before_commit", fail_commit)
        with pytest.raises(RuntimeError, match="request commit failed"):
            service.reject_change_request(
                session, _space_context(space_id), actor, proposed.change_request_id,
                if_request_fingerprint=proposed.content_fingerprint,
            )
    assert publications == []
    with db_sessionmaker() as session:
        assert session.get(AgentChangeRequest, proposed.change_request_id).status == "pending"


@pytest.mark.parametrize("selected_operations", [False, True])
def test_committed_approval_publishes_request_if_patch_notification_fails(
    db_sessionmaker, monkeypatch, review_request, selected_operations,
):
    user_id, space_id, proposed = review_request
    publications = []

    def fail_patch_publication(*_args):
        raise RuntimeError("patch notification failed after commit")

    def publish_request(changed_space_id):
        assert changed_space_id == space_id
        with db_sessionmaker() as verification:
            assert verification.get(AgentChangeRequest, proposed.change_request_id).status == "approved"
            assert verification.query(Project).filter_by(project_name="Created Once").count() == 1
        publications.append("requests")

    monkeypatch.setattr(service, "publish_patch_plan_mutations", fail_patch_publication)
    monkeypatch.setattr(service, "_publish_change_requests", publish_request)
    with db_sessionmaker() as session:
        actor = session.get(User, user_id)
        with pytest.raises(RuntimeError, match="patch notification failed after commit"):
            if selected_operations:
                service.approve_change_request_operations(
                    session, _space_context(space_id), actor, proposed.change_request_id,
                    ["create-project"], if_request_fingerprint=proposed.content_fingerprint,
                )
            else:
                service.approve_change_request(
                    session, _space_context(space_id), actor, proposed.change_request_id,
                    if_request_fingerprint=proposed.content_fingerprint,
                )
    assert publications == ["requests"]
