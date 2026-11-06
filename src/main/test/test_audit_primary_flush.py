from __future__ import annotations

import pytest
from sqlalchemy import event
from sqlalchemy.exc import IntegrityError

from backend.app.models import ChangeLog, Program, Project, Space
from backend.app.services.audit_log import safe_log_changes


def _seed(session):
    session.add_all([
        Space(space_id="audit-flush", name="Audit Flush", slug="audit-flush"),
        Program(program_id="audit-program", space_id="audit-flush", program_name="Program"),
        Project(project_id="audit-project", space_id="audit-flush", program_id="audit-program",
                project_name="Original", sponsor="Sponsor", owner="Owner"),
    ])
    session.commit()


def _log(session):
    safe_log_changes(
        session, entity_type="project", entity_id="audit-project", user_id="actor",
        action="update", space_id="audit-flush", changes={"project_name": ("Original", "Changed")},
    )


def test_primary_flush_error_propagates_before_audit_savepoint(db_sessionmaker):
    with db_sessionmaker() as session:
        _seed(session)
        project = session.get(Project, "audit-project")
        project.status = None
        with pytest.raises(IntegrityError):
            _log(session)
        session.rollback()

    with db_sessionmaker() as session:
        assert session.get(Project, "audit-project").status is not None
        assert session.query(ChangeLog).count() == 0


def test_audit_failure_rolls_back_savepoint_but_commits_primary_write(db_sessionmaker, caplog):
    with db_sessionmaker() as session:
        _seed(session)
        project = session.get(Project, "audit-project")
        project.project_name = "Changed"

        def fail_audit(_mapper, _connection, _target):
            raise RuntimeError("audit-secret-marker")

        event.listen(ChangeLog, "before_insert", fail_audit)
        try:
            _log(session)
        finally:
            event.remove(ChangeLog, "before_insert", fail_audit)
        session.commit()

    assert "audit-secret-marker" not in caplog.text
    assert "RuntimeError" in caplog.text
    with db_sessionmaker() as session:
        assert session.get(Project, "audit-project").project_name == "Changed"
        assert session.query(ChangeLog).count() == 0
