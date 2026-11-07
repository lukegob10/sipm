import asyncio

import pytest
from fastapi import HTTPException

from backend.app.models import Program, Project, Solution, SolutionDocument, Space, SpaceMembership, User
from backend.app.routes.solutions import documents, write
from backend.app.services.spaces import SpaceContext


@pytest.mark.anyio
@pytest.mark.parametrize("change", ["solution_deleted", "access_revoked"])
async def test_upload_rechecks_parent_and_access_after_file_read(db_sessionmaker, change):
    with db_sessionmaker() as session:
        actor = User(user_id="actor", soeid="actor", email="actor@example.com", display_name="Actor", password_hash="unused", role="user", is_active=True)
        session.add_all([
            actor, Space(space_id="space", name="Space", slug="space"),
            SpaceMembership(space_id="space", user_id="actor", role="member", status="active"),
            Program(program_id="program", space_id="space", program_name="Program"),
            Project(project_id="project", space_id="space", program_id="program", project_name="Project"),
            Solution(solution_id="solution", space_id="space", project_id="project", solution_name="Solution"),
        ])
        session.commit()
        session.refresh(actor)
        session.expunge(actor)
    ctx = SpaceContext(space_id="space", space_name="Space", space_role="member", is_global_admin=False)
    reading, release = asyncio.Event(), asyncio.Event()

    class DelayedUpload:
        filename = "note.txt"
        content_type = "text/plain"

        async def read(self, _limit):
            reading.set()
            await release.wait()
            return b"content"

    def change_during_read():
        with db_sessionmaker() as session:
            if change == "solution_deleted":
                write.delete_solution("solution", session=session, current_user=actor, space_ctx=ctx)
            else:
                session.query(SpaceMembership).filter_by(space_id="space", user_id="actor").one().status = "inactive"
                session.commit()

    with db_sessionmaker() as session:
        upload = asyncio.create_task(documents.upload_solution_document(
            "solution", DelayedUpload(), session=session, current_user=actor, space_ctx=ctx,
        ))
        try:
            await asyncio.wait_for(reading.wait(), timeout=10)
            await asyncio.to_thread(change_during_read)
        finally:
            release.set()
        with pytest.raises(HTTPException) as exc:
            await upload
        assert exc.value.status_code == (404 if change == "solution_deleted" else 403)
    with db_sessionmaker() as session:
        assert session.query(SolutionDocument).count() == 0


@pytest.mark.anyio
async def test_upload_lock_wait_does_not_block_event_loop(db_sessionmaker, monkeypatch):
    from threading import Event

    with db_sessionmaker() as session:
        actor = User(user_id="actor", soeid="actor", email="actor@example.com", display_name="Actor", password_hash="unused", role="user", is_active=True)
        session.add_all([
            actor, Space(space_id="space", name="Space", slug="space"),
            SpaceMembership(space_id="space", user_id="actor", role="member", status="active"),
            Program(program_id="program", space_id="space", program_name="Program"),
            Project(project_id="project", space_id="space", program_id="program", project_name="Project"),
            Solution(solution_id="solution", space_id="space", project_id="project", solution_name="Solution"),
        ])
        session.commit()
        session.refresh(actor)
        session.expunge(actor)
    ctx = SpaceContext(space_id="space", space_name="Space", space_role="member", is_global_admin=False)
    locked, release = Event(), Event()
    original = write._get_solution_or_404

    def pause_delete(*args, **kwargs):
        solution = original(*args, **kwargs)
        locked.set()
        assert release.wait(10)
        return solution

    monkeypatch.setattr(write, "_get_solution_or_404", pause_delete)

    class Upload:
        filename = "note.txt"
        content_type = "text/plain"

        async def read(self, _limit):
            return b"content"

    def delete_solution():
        with db_sessionmaker() as session:
            return write.delete_solution("solution", session=session, current_user=actor, space_ctx=ctx)

    deletion = asyncio.create_task(asyncio.to_thread(delete_solution))
    with db_sessionmaker() as session:
        try:
            assert await asyncio.to_thread(locked.wait, 10)
            upload = asyncio.create_task(documents.upload_solution_document(
                "solution", Upload(), session=session, current_user=actor, space_ctx=ctx,
            ))
            # If the database lock runs on the event loop, even this timeout cannot fire.
            with pytest.raises(TimeoutError):
                await asyncio.wait_for(asyncio.shield(upload), timeout=0.25)
        finally:
            release.set()
        await deletion
        with pytest.raises(HTTPException) as exc:
            await upload
        assert exc.value.status_code == 404
    with db_sessionmaker() as session:
        assert session.query(SolutionDocument).count() == 0


@pytest.mark.anyio
async def test_deletion_waits_for_upload_to_commit(db_sessionmaker, monkeypatch):
    from threading import Event

    with db_sessionmaker() as session:
        actor = User(user_id="actor", soeid="actor", email="actor@example.com", display_name="Actor", password_hash="unused", role="user", is_active=True)
        session.add_all([
            actor, Space(space_id="space", name="Space", slug="space"),
            SpaceMembership(space_id="space", user_id="actor", role="member", status="active"),
            Program(program_id="program", space_id="space", program_name="Program"),
            Project(project_id="project", space_id="space", program_id="program", project_name="Project"),
            Solution(solution_id="solution", space_id="space", project_id="project", solution_name="Solution"),
        ])
        session.commit()
        session.refresh(actor)
        session.expunge(actor)
    ctx = SpaceContext(space_id="space", space_name="Space", space_role="member", is_global_admin=False)
    saved, release = Event(), Event()
    original = documents.safe_log_changes

    def pause_upload(*args, **kwargs):
        result = original(*args, **kwargs)
        saved.set()
        assert release.wait(10)
        return result

    monkeypatch.setattr(documents, "safe_log_changes", pause_upload)

    class Upload:
        filename = "note.txt"
        content_type = "text/plain"

        async def read(self, _limit):
            return b"content"

    def delete_solution():
        with db_sessionmaker() as session:
            return write.delete_solution("solution", session=session, current_user=actor, space_ctx=ctx)

    with db_sessionmaker() as session:
        upload = asyncio.create_task(documents.upload_solution_document(
            "solution", Upload(), session=session, current_user=actor, space_ctx=ctx,
        ))
        try:
            assert await asyncio.to_thread(saved.wait, 10)
            deletion = asyncio.create_task(asyncio.to_thread(delete_solution))
            with pytest.raises(TimeoutError):
                await asyncio.wait_for(asyncio.shield(deletion), timeout=0.25)
        finally:
            release.set()
        result = await upload
        await deletion
    with db_sessionmaker() as session:
        assert session.get(Solution, "solution").deleted_at is not None
        assert session.get(SolutionDocument, result["document_id"]) is not None


@pytest.mark.anyio
async def test_cancelled_upload_keeps_session_alive_until_database_worker_finishes(db_sessionmaker, monkeypatch):
    from threading import Event

    with db_sessionmaker() as session:
        actor = User(user_id="actor", soeid="actor", email="actor@example.com", display_name="Actor", password_hash="unused", role="user", is_active=True)
        session.add_all([
            actor, Space(space_id="space", name="Space", slug="space"),
            SpaceMembership(space_id="space", user_id="actor", role="member", status="active"),
            Program(program_id="program", space_id="space", program_name="Program"),
            Project(project_id="project", space_id="space", program_id="program", project_name="Project"),
            Solution(solution_id="solution", space_id="space", project_id="project", solution_name="Solution"),
        ])
        session.commit()
        session.refresh(actor)
        session.expunge(actor)
    ctx = SpaceContext(space_id="space", space_name="Space", space_role="member", is_global_admin=False)
    locked, release, finished = Event(), Event(), Event()
    original = documents.lock_work_space
    original_publish = documents._publish_solution_mutation

    def pause_lock(*args, **kwargs):
        locked.set()
        assert release.wait(10)
        original(*args, **kwargs)

    def signal_finish(*args, **kwargs):
        try:
            return original_publish(*args, **kwargs)
        finally:
            finished.set()

    monkeypatch.setattr(documents, "lock_work_space", pause_lock)
    monkeypatch.setattr(documents, "_publish_solution_mutation", signal_finish)

    class Upload:
        filename = "note.txt"
        content_type = "text/plain"

        async def read(self, _limit):
            return b"content"

    with db_sessionmaker() as session:
        upload = asyncio.create_task(documents.upload_solution_document(
            "solution", Upload(), session=session, current_user=actor, space_ctx=ctx,
        ))
        assert await asyncio.to_thread(locked.wait, 10)
        upload.cancel()
        await asyncio.sleep(0.05)
        upload.cancel()
        await asyncio.sleep(0.05)
        cancelled_before_worker_finished = upload.done()
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await upload
        assert await asyncio.to_thread(finished.wait, 10)
        assert not cancelled_before_worker_finished
