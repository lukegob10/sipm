from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ...deps import current_space as current_space_dep
from ...deps import current_user as current_user_dep
from ...deps import get_db, require_space_role
from ...models import Subcomponent, User
from ...schemas import (
    SubcomponentBatchUpdate,
    SubcomponentCreate,
    SubcomponentRead,
    SubcomponentUpdate,
)
from ...services.audit_log import log_changes
from ...services.spaces import SpaceContext
from ...utils import normalize_str
from ...utils.enums import SubcomponentStatus
from .._mutations import commit_refresh_and_publish, commit_session
from .common import (
    _apply_subcomponent_completion_state,
    _ensure_solution,
    _get_subcomponent,
    _publish_subcomponent_mutation,
    _resolve_subcomponent_assignee,
    _solution_repo_map,
    _subcomponent_payload,
    _subcomponent_query,
    normalize_github_repo_url,
)

router = APIRouter()


def _required_subcomponent_name(value: object) -> str:
    subcomponent_name = normalize_str(value)
    if not subcomponent_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="subcomponent_name is required",
        )
    return subcomponent_name


@router.post(
    "/solutions/{solution_id}/subcomponents",
    response_model=SubcomponentRead,
    status_code=status.HTTP_201_CREATED,
)
def create_subcomponent(
    solution_id: str,
    payload: SubcomponentCreate,
    session: Session = Depends(get_db),
    tasks: BackgroundTasks = None,
    current_user: User = Depends(current_user_dep),
    space_ctx: SpaceContext = Depends(current_space_dep),
    _authz: SpaceContext = Depends(require_space_role("member")),
):
    solution = _ensure_solution(session, solution_id, space_ctx)
    subcomponent_name = _required_subcomponent_name(payload.subcomponent_name)
    try:
        github_repo_url = normalize_github_repo_url(payload.github_repo_url)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    conflict = (
        _subcomponent_query(session, space_ctx)
        .filter(Subcomponent.solution_id == solution_id)
        .filter(Subcomponent.subcomponent_name == subcomponent_name)
        .first()
    )
    if conflict:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Subcomponent name already exists in this solution",
        )

    now = datetime.now(timezone.utc)
    completed_at = now if payload.status == SubcomponentStatus.complete else None
    blocked = payload.blocked or False

    assignee, assignee_user_soeid = _resolve_subcomponent_assignee(
        payload.assignee,
        payload.assignee_user_soeid,
        current_user,
    )

    subcomponent = Subcomponent(
        space_id=space_ctx.space_id,
        project_id=solution.project_id,
        solution_id=solution_id,
        subcomponent_name=subcomponent_name,
        status=payload.status,
        priority=payload.priority,
        due_date=payload.due_date,
        completed_at=completed_at,
        assignee=assignee,
        assignee_user_soeid=assignee_user_soeid,
        github_repo_url=github_repo_url,
        estimate_hours=payload.estimate_hours,
        blocked=blocked,
        blocker_note=payload.blocker_note if blocked else None,
        done_criteria=payload.done_criteria,
        capacity_hours=payload.capacity_hours or 0,
        created_at=now,
        updated_at=now,
    )
    session.add(subcomponent)
    session.flush()
    log_changes(
        session,
        entity_type="subcomponent",
        entity_id=subcomponent.subcomponent_id,
        user_id=current_user.user_id,
        action="create",
        space_id=space_ctx.space_id,
        changes={
            "subcomponent_name": (None, subcomponent.subcomponent_name),
            "status": (None, subcomponent.status),
            "priority": (None, subcomponent.priority),
            "due_date": (None, subcomponent.due_date),
            "assignee": (None, subcomponent.assignee),
            "assignee_user_soeid": (None, subcomponent.assignee_user_soeid),
            "github_repo_url": (None, subcomponent.github_repo_url),
            "estimate_hours": (None, subcomponent.estimate_hours),
            "blocked": (None, subcomponent.blocked),
            "blocker_note": (None, subcomponent.blocker_note),
            "done_criteria": (None, subcomponent.done_criteria),
            "completed_at": (None, subcomponent.completed_at),
        },
    )
    commit_refresh_and_publish(
        session,
        subcomponent,
        space_id=space_ctx.space_id,
        cache_keys=["subcomponents"],
        broadcast_channel="subcomponents",
    )
    return _subcomponent_payload(
        subcomponent, solution_repo_url=solution.github_repo_url
    )


@router.patch("/subcomponents/{subcomponent_id}", response_model=SubcomponentRead)
def update_subcomponent(
    subcomponent_id: str,
    payload: SubcomponentUpdate,
    session: Session = Depends(get_db),
    tasks: BackgroundTasks = None,
    current_user: User = Depends(current_user_dep),
    space_ctx: SpaceContext = Depends(current_space_dep),
    _authz: SpaceContext = Depends(require_space_role("member")),
):
    subcomponent = _get_subcomponent(session, subcomponent_id, space_ctx)

    update_data = payload.model_dump(exclude_unset=True)
    if "subcomponent_name" in update_data:
        update_data["subcomponent_name"] = _required_subcomponent_name(
            update_data["subcomponent_name"]
        )
    if "capacity_hours" in update_data and update_data["capacity_hours"] is None:
        update_data["capacity_hours"] = 0
    if "blocked" in update_data and update_data["blocked"] is None:
        update_data["blocked"] = False
    if update_data.get("blocked") is False:
        update_data["blocker_note"] = None
    if "github_repo_url" in update_data:
        try:
            update_data["github_repo_url"] = normalize_github_repo_url(
                update_data["github_repo_url"]
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
            )
    fields_to_compare = set(update_data.keys())
    if "status" in update_data:
        fields_to_compare.add("completed_at")
    before = {field: getattr(subcomponent, field) for field in fields_to_compare}
    for field, value in update_data.items():
        setattr(subcomponent, field, value)

    if "status" in update_data:
        _apply_subcomponent_completion_state(
            subcomponent,
            next_status=update_data["status"],
            now=datetime.now(timezone.utc),
        )

    subcomponent.updated_at = datetime.now(timezone.utc)

    if "subcomponent_name" in update_data and update_data["subcomponent_name"]:
        conflict = (
            _subcomponent_query(session, space_ctx)
            .filter(Subcomponent.solution_id == subcomponent.solution_id)
            .filter(Subcomponent.subcomponent_name == update_data["subcomponent_name"])
            .filter(Subcomponent.subcomponent_id != subcomponent.subcomponent_id)
            .first()
        )
        if conflict:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Subcomponent name already exists in this solution",
            )

    session.add(subcomponent)
    if update_data:
        log_changes(
            session,
            entity_type="subcomponent",
            entity_id=subcomponent.subcomponent_id,
            user_id=current_user.user_id,
            action="update",
            space_id=space_ctx.space_id,
            changes={
                field: (before.get(field), getattr(subcomponent, field))
                for field in fields_to_compare
            },
        )
    commit_refresh_and_publish(
        session,
        subcomponent,
        space_id=space_ctx.space_id,
        cache_keys=["subcomponents"],
        broadcast_channel="subcomponents",
    )
    solution = _ensure_solution(session, subcomponent.solution_id, space_ctx)
    return _subcomponent_payload(
        subcomponent, solution_repo_url=solution.github_repo_url
    )


@router.patch("/subcomponents/actions/batch", response_model=list[SubcomponentRead])
def batch_update_subcomponents(
    payload: SubcomponentBatchUpdate,
    session: Session = Depends(get_db),
    current_user: User = Depends(current_user_dep),
    space_ctx: SpaceContext = Depends(current_space_dep),
    _authz: SpaceContext = Depends(require_space_role("member")),
):
    unique_ids: list[str] = []
    seen: set[str] = set()
    for raw_id in payload.subcomponent_ids or []:
        sub_id = (raw_id or "").strip()
        if not sub_id or sub_id in seen:
            continue
        seen.add(sub_id)
        unique_ids.append(sub_id)
    if not unique_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="subcomponent_ids must include at least one item",
        )
    if payload.due_date is not None and payload.due_date_shift_days is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide either due_date or due_date_shift_days, not both",
        )

    rows = (
        _subcomponent_query(session, space_ctx)
        .filter(Subcomponent.subcomponent_id.in_(unique_ids))
        .all()
    )
    rows_by_id = {row.subcomponent_id: row for row in rows}
    missing = [sub_id for sub_id in unique_ids if sub_id not in rows_by_id]
    if missing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Subcomponents not found in current space: {', '.join(missing)}",
        )

    now = datetime.now(timezone.utc)
    updated_rows: list[Subcomponent] = []
    for sub_id in unique_ids:
        row = rows_by_id[sub_id]
        changes = {}

        def track(field: str, value):
            old = getattr(row, field)
            if old != value:
                setattr(row, field, value)
                changes[field] = (old, value)

        if payload.status is not None:
            track("status", payload.status)
            if payload.status == SubcomponentStatus.complete and not row.completed_at:
                track("completed_at", now)
            elif (
                payload.status != SubcomponentStatus.complete
                and row.completed_at is not None
            ):
                track("completed_at", None)
        if payload.priority is not None:
            track("priority", payload.priority)
        if payload.blocked is not None:
            track("blocked", payload.blocked)

        if payload.due_date is not None:
            track("due_date", payload.due_date)
        elif payload.due_date_shift_days is not None and row.due_date is not None:
            track(
                "due_date", row.due_date + timedelta(days=payload.due_date_shift_days)
            )

        if payload.clear_assignee:
            track("assignee", "")
            track("assignee_user_soeid", None)
        else:
            if payload.assignee is not None:
                track("assignee", payload.assignee)
            if payload.assignee_user_soeid is not None:
                track("assignee_user_soeid", payload.assignee_user_soeid)

        if not changes:
            updated_rows.append(row)
            continue

        track("updated_at", now)
        session.add(row)
        log_changes(
            session,
            entity_type="subcomponent",
            entity_id=row.subcomponent_id,
            user_id=current_user.user_id,
            action="update",
            space_id=space_ctx.space_id,
            changes=changes,
        )
        updated_rows.append(row)

    commit_session(session)
    for row in updated_rows:
        session.refresh(row)
    _publish_subcomponent_mutation(space_ctx.space_id)
    solution_repo_map = _solution_repo_map(
        session,
        space_ctx,
        [row.solution_id for row in updated_rows],
    )
    return [
        _subcomponent_payload(
            row, solution_repo_url=solution_repo_map.get(row.solution_id)
        )
        for row in updated_rows
    ]


@router.delete(
    "/subcomponents/{subcomponent_id}", status_code=status.HTTP_204_NO_CONTENT
)
def delete_subcomponent(
    subcomponent_id: str,
    session: Session = Depends(get_db),
    current_user: User = Depends(current_user_dep),
    space_ctx: SpaceContext = Depends(current_space_dep),
    _authz: SpaceContext = Depends(require_space_role("member")),
):
    subcomponent = _get_subcomponent(session, subcomponent_id, space_ctx)
    now = datetime.now(timezone.utc)
    subcomponent.deleted_at = now
    subcomponent.updated_at = now
    session.add(subcomponent)
    log_changes(
        session,
        entity_type="subcomponent",
        entity_id=subcomponent.subcomponent_id,
        user_id=current_user.user_id,
        action="delete",
        space_id=space_ctx.space_id,
        changes={"deleted_at": (None, now)},
    )
    commit_session(session)
    _publish_subcomponent_mutation(space_ctx.space_id)
    return None
