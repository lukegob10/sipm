from datetime import date, datetime, timezone
from io import BytesIO
import os
import re
from typing import List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy import func

from ..auth.auth import hash_bootstrap_password
from ..deps import (
    current_space as current_space_dep,
    current_user as current_user_dep,
    get_db,
    require_space_role,
)
from ..models import (
    PlanningWindow,
    Project,
    ResourceAllocation,
    Solution,
    SpaceMembership,
    Subcomponent,
    Team,
    User,
)
from ..schemas import (
    ResourceAllocationCreate,
    ResourceAllocationRead,
    ResourceAllocationUpdate,
    PlanningWindowCreate,
    PlanningWindowRead,
    PlanningWindowUpdate,
)
from ..services.spaces import SpaceContext
from ..services.smart_cache import cached_call, invalidate_space, make_scope_token
from ..utils.enums import ProjectStatus, SolutionStatus, SubcomponentStatus

router = APIRouter()
_PLANNING_LIST_TTL_SECONDS = 20
_PLANNING_DETAIL_TTL_SECONDS = 30
_HOURS_PER_FTE_MONTH = 160.0
_WORK_ALLOCATION_DOMAIN = os.getenv("DOMAIN_NAME", "local.invalid")
_WORK_ALLOCATION_PROJECT_PREFIX = "Work Allocation Board"
_WORK_ALLOCATION_SOLUTION_NAME = "Backlog"
_WORK_ALLOCATION_SOLUTION_VERSION = "1.0.0"
_WORK_ALLOCATION_DEFAULT_ASSIGNEE = "Unassigned"

_WORK_ALLOCATION_UNIQUE_CONSTRAINT = "UIX_ALLOC_UNIQUE_ASSIGNMENT"


class WorkAllocationTeamCreate(BaseModel):
    name: str = Field(min_length=1, max_length=180)


class WorkAllocationTeamUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=180)


class WorkAllocationTeamRead(BaseModel):
    id: str
    name: str


class WorkAllocationPersonCreate(BaseModel):
    name: str = Field(min_length=1, max_length=180)
    team_id: Optional[str] = None
    capacity_fte_months: float = 1.0


class WorkAllocationPersonUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=180)
    team_id: Optional[str] = None
    capacity_fte_months: Optional[float] = None
    active: Optional[bool] = None


class WorkAllocationPersonRead(BaseModel):
    id: str
    name: str
    team_id: Optional[str] = None
    capacity_fte_months: float
    active: bool


class WorkAllocationTaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=240)
    fte_months: float = 0.25


class WorkAllocationTaskUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=240)
    fte_months: Optional[float] = None


class WorkAllocationTaskRead(BaseModel):
    id: str
    title: str
    fte_months: float
    status: Literal["backlog", "assigned"]


class WorkAllocationAssignmentCreate(BaseModel):
    task_id: str = Field(min_length=1)
    assignee_type: Literal["person", "team"]
    assignee_id: str = Field(min_length=1)
    month: str = Field(min_length=7, max_length=7)
    fte_months_allocated: Optional[float] = None


class WorkAllocationAssignmentRead(BaseModel):
    id: str
    task_id: str
    assignee_type: Literal["person", "team"]
    assignee_id: str
    assignee_name: Optional[str] = None
    month: str
    fte_months_allocated: float


def _role_scope(space_ctx: SpaceContext) -> str:
    if space_ctx.is_global_admin:
        return "global_admin"
    return space_ctx.space_role or "member"


def _allocation_query(session: Session, space_ctx: SpaceContext):
    return (
        session.query(ResourceAllocation)
        .filter(ResourceAllocation.deleted_at.is_(None))
        .filter(ResourceAllocation.space_id == space_ctx.space_id)
    )


def _window_query(session: Session, space_ctx: SpaceContext):
    return (
        session.query(PlanningWindow)
        .filter(PlanningWindow.deleted_at.is_(None))
        .filter(PlanningWindow.space_id == space_ctx.space_id)
    )


def _team_query(session: Session, space_ctx: SpaceContext):
    return (
        session.query(Team)
        .filter(Team.deleted_at.is_(None))
        .filter(Team.space_id == space_ctx.space_id)
    )


def _active_team(session: Session, team_id: Optional[str], space_ctx: SpaceContext) -> Optional[Team]:
    if not team_id:
        return None
    row = _team_query(session, space_ctx).filter(Team.team_id == team_id).first()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")
    return row


def _get_allocation(session: Session, alloc_id: str, space_ctx: SpaceContext) -> ResourceAllocation:
    alloc = (
        _allocation_query(session, space_ctx)
        .filter(ResourceAllocation.allocation_id == alloc_id)
        .first()
    )
    if not alloc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Allocation not found")
    return alloc


def _get_window(session: Session, window_id: str, space_ctx: SpaceContext) -> PlanningWindow:
    win = (
        _window_query(session, space_ctx)
        .filter(PlanningWindow.window_id == window_id)
        .first()
    )
    if not win:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Planning window not found")
    return win


def _month_start(value: date) -> date:
    return value.replace(day=1)


def _resolve_month_start(month_start: Optional[date], week_start: Optional[date]) -> date:
    raw = month_start or week_start
    if raw is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="month_start (or legacy week_start) is required",
        )
    return _month_start(raw)


def _resolve_fte_months(fte_months: Optional[float], hours: Optional[int]) -> float:
    if fte_months is not None:
        return round(max(float(fte_months), 0.0), 3)
    if hours is not None:
        return round(max(float(hours), 0.0) / _HOURS_PER_FTE_MONTH, 3)
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="fte_months (or legacy hours) is required",
    )


def _hours_from_fte_months(value: float) -> int:
    return max(int(round(float(value) * _HOURS_PER_FTE_MONTH)), 0)


def _allocation_month_expr():
    return func.coalesce(ResourceAllocation.month_start, ResourceAllocation.week_start)


def _allocation_fte_expr():
    return func.coalesce(ResourceAllocation.fte_months, (ResourceAllocation.hours / _HOURS_PER_FTE_MONTH))


def _allocation_to_payload(alloc: ResourceAllocation) -> dict:
    month_start = alloc.month_start or (_month_start(alloc.week_start) if alloc.week_start else None)
    week_start = alloc.week_start or month_start
    fte_months = float(alloc.fte_months or 0.0)
    if fte_months <= 0 and alloc.hours:
        fte_months = round(float(alloc.hours) / _HOURS_PER_FTE_MONTH, 3)
    hours = alloc.hours if alloc.hours is not None else _hours_from_fte_months(fte_months)
    return {
        "allocation_id": alloc.allocation_id,
        "work_item_type": alloc.work_item_type,
        "work_item_id": alloc.work_item_id,
        "assignee": alloc.assignee,
        "assignee_user_soeid": alloc.assignee_user_soeid,
        "team_id": alloc.team_id,
        "month_start": month_start.isoformat() if month_start else None,
        "fte_months": round(fte_months, 3),
        "week_start": week_start.isoformat() if week_start else None,
        "hours": int(hours or 0),
        "window_id": alloc.window_id,
        "created_at": alloc.created_at,
        "updated_at": alloc.updated_at,
    }


def _active_space_user_query(session: Session, space_ctx: SpaceContext):
    return (
        session.query(User)
        .join(SpaceMembership, SpaceMembership.user_id == User.user_id)
        .filter(SpaceMembership.space_id == space_ctx.space_id)
        .filter(SpaceMembership.deleted_at.is_(None))
        .filter(SpaceMembership.status == "active")
        .filter(User.is_active == True)
    )


def _work_allocation_project_name(space_ctx: SpaceContext) -> str:
    token = (space_ctx.space_id or "default").strip()[:8] or "default"
    return f"{_WORK_ALLOCATION_PROJECT_PREFIX} [{token}]"


def _project_query(session: Session, space_ctx: SpaceContext):
    return (
        session.query(Project)
        .filter(Project.deleted_at.is_(None))
        .filter(Project.space_id == space_ctx.space_id)
    )


def _solution_query(session: Session, space_ctx: SpaceContext):
    return (
        session.query(Solution)
        .filter(Solution.deleted_at.is_(None))
        .filter(Solution.space_id == space_ctx.space_id)
    )


def _board_solution(session: Session, space_ctx: SpaceContext) -> Solution:
    project_name = _work_allocation_project_name(space_ctx)
    now = datetime.now(timezone.utc)
    changed = False

    project = (
        session.query(Project)
        .filter(Project.space_id == space_ctx.space_id)
        .filter(Project.project_name == project_name)
        .first()
    )
    if not project:
        project = Project(
            space_id=space_ctx.space_id,
            project_name=project_name,
            status=ProjectStatus.not_started,
            sponsor="Planning Board",
            priority=3,
            created_at=now,
            updated_at=now,
        )
        session.add(project)
        session.flush()
        changed = True
    elif project.deleted_at is not None:
        project.deleted_at = None
        project.updated_at = now
        session.add(project)
        session.flush()
        changed = True

    solution = (
        session.query(Solution)
        .filter(Solution.space_id == space_ctx.space_id)
        .filter(Solution.project_id == project.project_id)
        .filter(Solution.solution_name == _WORK_ALLOCATION_SOLUTION_NAME)
        .filter(Solution.version == _WORK_ALLOCATION_SOLUTION_VERSION)
        .first()
    )
    if not solution:
        solution = Solution(
            space_id=space_ctx.space_id,
            project_id=project.project_id,
            solution_name=_WORK_ALLOCATION_SOLUTION_NAME,
            version=_WORK_ALLOCATION_SOLUTION_VERSION,
            status=SolutionStatus.not_started,
            priority=3,
            owner="Planning Board",
            assignee=_WORK_ALLOCATION_DEFAULT_ASSIGNEE,
            created_at=now,
            updated_at=now,
        )
        session.add(solution)
        session.flush()
        changed = True
    elif solution.deleted_at is not None:
        solution.deleted_at = None
        solution.updated_at = now
        session.add(solution)
        session.flush()
        changed = True

    if changed:
        session.commit()
        session.refresh(solution)
    return solution


def _board_task_query(session: Session, space_ctx: SpaceContext):
    solution = _board_solution(session, space_ctx)
    query = (
        session.query(Subcomponent)
        .filter(Subcomponent.deleted_at.is_(None))
        .filter(Subcomponent.space_id == space_ctx.space_id)
        .filter(Subcomponent.solution_id == solution.solution_id)
    )
    return solution, query


def _task_fte_months(subcomponent: Subcomponent) -> float:
    hours = int(subcomponent.capacity_hours or subcomponent.estimate_hours or 0)
    if hours <= 0:
        return 0.25
    return round(max(float(hours), 0.0) / _HOURS_PER_FTE_MONTH, 3)


def _month_from_token(month_token: str) -> date:
    token = str(month_token or "").strip()
    if not re.fullmatch(r"\d{4}-\d{2}", token):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="month must use YYYY-MM")
    return date.fromisoformat(f"{token}-01")


def _month_token(value: Optional[date]) -> str:
    if value is None:
        today = datetime.now(timezone.utc).date()
        return f"{today.year:04d}-{today.month:02d}"
    return f"{value.year:04d}-{value.month:02d}"


def _active_person_by_soeid(session: Session, soeid: str, space_ctx: SpaceContext) -> User:
    norm = str(soeid or "").strip().lower()
    if not norm:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Person not found")
    user = _active_space_user_query(session, space_ctx).filter(func.lower(User.soeid) == norm).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Person not found")
    return user


def _team_name_to_id_map(session: Session, space_ctx: SpaceContext) -> dict[str, str]:
    rows = _team_query(session, space_ctx).all()
    return {str(row.name or "").strip().lower(): row.team_id for row in rows if row.name}


def _team_display_name(session: Session, team_id: Optional[str], space_ctx: SpaceContext) -> Optional[str]:
    if not team_id:
        return None
    team = _team_query(session, space_ctx).filter(Team.team_id == team_id).first()
    return team.name if team else None


def _person_payload(user: User, team_map: dict[str, str]) -> WorkAllocationPersonRead:
    team_key = str(user.team_tag or "").strip().lower()
    team_id = team_map.get(team_key) if team_key else None
    cap = user.capacity_fte_month
    if not cap or cap <= 0:
        cap = 1.0
    return WorkAllocationPersonRead(
        id=user.soeid,
        name=user.display_name,
        team_id=team_id,
        capacity_fte_months=round(float(cap), 3),
        active=bool(user.is_active),
    )


def _task_payload(subcomponent: Subcomponent, assigned_ids: set[str]) -> WorkAllocationTaskRead:
    return WorkAllocationTaskRead(
        id=subcomponent.subcomponent_id,
        title=subcomponent.subcomponent_name,
        fte_months=_task_fte_months(subcomponent),
        status="assigned" if subcomponent.subcomponent_id in assigned_ids else "backlog",
    )


def _allocation_for_board_payload(alloc: ResourceAllocation, space_ctx: SpaceContext, session: Session) -> WorkAllocationAssignmentRead:
    month_value = alloc.month_start or alloc.week_start
    fte = float(alloc.fte_months or 0.0)
    if fte <= 0 and alloc.hours:
        fte = float(alloc.hours) / _HOURS_PER_FTE_MONTH
    assignee_type: Literal["person", "team"] = "team" if alloc.team_id else "person"
    assignee_id = alloc.team_id if alloc.team_id else (alloc.assignee_user_soeid or "")
    assignee_name = alloc.assignee
    if assignee_type == "team" and not assignee_name:
        assignee_name = _team_display_name(session, alloc.team_id, space_ctx)
    return WorkAllocationAssignmentRead(
        id=alloc.allocation_id,
        task_id=alloc.work_item_id,
        assignee_type=assignee_type,
        assignee_id=assignee_id,
        assignee_name=assignee_name,
        month=_month_token(month_value),
        fte_months_allocated=round(max(fte, 0.0), 3),
    )


def _raise_on_unique_allocation_conflict(err: IntegrityError) -> None:
    message = str(getattr(err, "orig", err) or "").upper()
    if _WORK_ALLOCATION_UNIQUE_CONSTRAINT in message:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Task is already allocated to this assignee for this month",
        ) from err
    raise err


def _is_window_name_conflict_integrity_error(err: IntegrityError) -> bool:
    text = " ".join(
        [
            str(err),
            str(getattr(err, "orig", "")),
            str(getattr(err, "statement", "")),
        ]
    ).lower()
    if "uix_planning_window_name" in text:
        return True
    has_unique_marker = any(
        marker in text
        for marker in (
            "ora-03301",
            "ora-00001",
            "unique constraint",
            "unique constraint failed",
        )
    )
    if not has_unique_marker:
        return False
    return "tb_ta_pm_planning_windows" in text or "planning_window" in text


def _is_team_name_conflict_integrity_error(err: IntegrityError) -> bool:
    text = " ".join(
        [
            str(err),
            str(getattr(err, "orig", "")),
            str(getattr(err, "statement", "")),
        ]
    ).lower()
    if "uix_team_name" in text:
        return True
    has_unique_marker = any(
        marker in text
        for marker in (
            "ora-03301",
            "ora-00001",
            "unique constraint",
            "unique constraint failed",
        )
    )
    if not has_unique_marker:
        return False
    return "tb_ta_pm_teams" in text or "team" in text


def _pdf_escape(value: str) -> str:
    safe = str(value or "").encode("latin-1", errors="replace").decode("latin-1")
    return safe.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _pdf_number(value: float) -> str:
    text = f"{float(value):.2f}"
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def _pdf_rgb(color: tuple[int, int, int]) -> str:
    red, green, blue = color
    return f"{red / 255.0:.3f} {green / 255.0:.3f} {blue / 255.0:.3f}"


class _SimplePdfDoc:
    def __init__(self, width: float = 842.0, height: float = 595.0) -> None:
        self.width = float(width)
        self.height = float(height)
        self._pages: list[list[str]] = []
        self._active_page: Optional[list[str]] = None

    def new_page(self) -> None:
        page: list[str] = []
        self._pages.append(page)
        self._active_page = page

    def _cmd(self, value: str) -> None:
        if self._active_page is None:
            self.new_page()
        assert self._active_page is not None
        self._active_page.append(value)

    def rect(
        self,
        x: float,
        y: float,
        width: float,
        height: float,
        fill: Optional[tuple[int, int, int]] = None,
        stroke: Optional[tuple[int, int, int]] = None,
        line_width: float = 1.0,
    ) -> None:
        commands: list[str] = []
        if fill:
            commands.append(f"{_pdf_rgb(fill)} rg")
        if stroke:
            commands.append(f"{_pdf_rgb(stroke)} RG {_pdf_number(line_width)} w")
        commands.append(
            f"{_pdf_number(x)} {_pdf_number(y)} {_pdf_number(width)} {_pdf_number(height)} re"
        )
        if fill and stroke:
            commands.append("B")
        elif fill:
            commands.append("f")
        else:
            commands.append("S")
        self._cmd(" ".join(commands))

    def line(
        self,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        stroke: tuple[int, int, int] = (180, 186, 199),
        line_width: float = 1.0,
    ) -> None:
        self._cmd(
            f"{_pdf_rgb(stroke)} RG {_pdf_number(line_width)} w "
            f"{_pdf_number(x1)} {_pdf_number(y1)} m {_pdf_number(x2)} {_pdf_number(y2)} l S"
        )

    def text(
        self,
        x: float,
        y: float,
        value: str,
        size: float = 10.0,
        bold: bool = False,
        color: tuple[int, int, int] = (17, 24, 39),
    ) -> None:
        font_ref = "/F2" if bold else "/F1"
        text = _pdf_escape(value)
        self._cmd(
            f"BT {_pdf_rgb(color)} rg {font_ref} {_pdf_number(size)} Tf "
            f"1 0 0 1 {_pdf_number(x)} {_pdf_number(y)} Tm ({text}) Tj ET"
        )

    def build(self) -> bytes:
        if not self._pages:
            self.new_page()
        page_count = len(self._pages)
        font_regular_id = 3
        font_bold_id = 4
        object_map: dict[int, str] = {
            1: "<< /Type /Catalog /Pages 2 0 R >>",
            font_regular_id: "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
            font_bold_id: "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>",
        }

        next_id = 5
        page_ids: list[int] = []
        content_ids: list[int] = []
        for _ in self._pages:
            page_ids.append(next_id)
            content_ids.append(next_id + 1)
            next_id += 2

        kids = " ".join(f"{page_id} 0 R" for page_id in page_ids)
        object_map[2] = f"<< /Type /Pages /Kids [{kids}] /Count {page_count} >>"

        for idx, commands in enumerate(self._pages):
            content_text = "\n".join(commands) + "\n"
            content_length = len(content_text.encode("latin-1", errors="replace"))
            content_id = content_ids[idx]
            page_id = page_ids[idx]
            object_map[content_id] = (
                f"<< /Length {content_length} >>\nstream\n{content_text}endstream"
            )
            object_map[page_id] = (
                "<< /Type /Page /Parent 2 0 R "
                f"/MediaBox [0 0 {_pdf_number(self.width)} {_pdf_number(self.height)}] "
                f"/Resources << /Font << /F1 {font_regular_id} 0 R /F2 {font_bold_id} 0 R >> >> "
                f"/Contents {content_id} 0 R >>"
            )

        max_id = max(object_map.keys())
        out = bytearray()
        out.extend(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
        offsets: list[int] = [0] * (max_id + 1)
        for object_id in range(1, max_id + 1):
            body = object_map.get(object_id, "<<>>")
            offsets[object_id] = len(out)
            out.extend(f"{object_id} 0 obj\n".encode("latin-1"))
            out.extend(body.encode("latin-1", errors="replace"))
            out.extend(b"\nendobj\n")

        xref_offset = len(out)
        out.extend(f"xref\n0 {max_id + 1}\n".encode("latin-1"))
        out.extend(b"0000000000 65535 f \n")
        for object_id in range(1, max_id + 1):
            out.extend(f"{offsets[object_id]:010d} 00000 n \n".encode("latin-1"))
        out.extend(
            (
                f"trailer\n<< /Size {max_id + 1} /Root 1 0 R >>\n"
                f"startxref\n{xref_offset}\n%%EOF\n"
            ).encode("latin-1")
        )
        return bytes(out)


class _TopPdfPainter:
    def __init__(self, document: _SimplePdfDoc) -> None:
        self.document = document

    def _to_bottom_y(self, top_y: float, height: float = 0.0) -> float:
        return self.document.height - top_y - height

    def rect(
        self,
        x: float,
        y: float,
        width: float,
        height: float,
        fill: Optional[tuple[int, int, int]] = None,
        stroke: Optional[tuple[int, int, int]] = None,
        line_width: float = 1.0,
    ) -> None:
        self.document.rect(
            x=x,
            y=self._to_bottom_y(y, height),
            width=width,
            height=height,
            fill=fill,
            stroke=stroke,
            line_width=line_width,
        )

    def line(
        self,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        stroke: tuple[int, int, int] = (180, 186, 199),
        line_width: float = 1.0,
    ) -> None:
        self.document.line(
            x1=x1,
            y1=self._to_bottom_y(y1),
            x2=x2,
            y2=self._to_bottom_y(y2),
            stroke=stroke,
            line_width=line_width,
        )

    def text(
        self,
        x: float,
        y: float,
        value: str,
        size: float = 10.0,
        bold: bool = False,
        color: tuple[int, int, int] = (17, 24, 39),
    ) -> None:
        self.document.text(
            x=x,
            y=self._to_bottom_y(y, size),
            value=value,
            size=size,
            bold=bold,
            color=color,
        )


def _float_or(value: object, fallback: float = 0.0) -> float:
    try:
        parsed = float(value)  # type: ignore[arg-type]
        if parsed != parsed:  # NaN
            return fallback
        return parsed
    except (TypeError, ValueError):
        return fallback


def _estimate_pdf_text_width(text: str, font_size: float) -> float:
    return max(len(str(text or "")), 1) * font_size * 0.52


def _wrap_pdf_text(
    text: str,
    max_width: float,
    font_size: float,
    max_lines: Optional[int] = None,
) -> list[str]:
    normalized = " ".join(str(text or "").split())
    if not normalized:
        return [""]
    words = normalized.split(" ")
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = word if not current else f"{current} {word}"
        if _estimate_pdf_text_width(candidate, font_size) <= max_width:
            current = candidate
            continue
        if current:
            lines.append(current)
            current = word
        else:
            chunk = word
            while _estimate_pdf_text_width(chunk, font_size) > max_width and len(chunk) > 4:
                slice_size = max(int(max_width / (font_size * 0.52)), 1)
                lines.append(chunk[:slice_size])
                chunk = chunk[slice_size:]
            current = chunk
        if max_lines and len(lines) >= max_lines:
            break
    if current and (not max_lines or len(lines) < max_lines):
        lines.append(current)
    if max_lines and len(lines) > max_lines:
        lines = lines[:max_lines]
    if max_lines and len(lines) == max_lines and words:
        last = lines[-1]
        if not last.endswith("...") and len(last) > 3:
            lines[-1] = f"{last[:-3]}..."
    return lines


def _draw_report_card(
    painter: _TopPdfPainter,
    x: float,
    y: float,
    width: float,
    height: float,
    accent: tuple[int, int, int],
    title: str,
    value: str,
    subtitle: str,
) -> None:
    painter.rect(x, y, width, height, fill=(248, 250, 255), stroke=(218, 225, 236))
    painter.rect(x, y, 6, height, fill=accent)
    painter.text(x + 14, y + 10, title, size=9, color=(96, 107, 129))
    painter.text(x + 14, y + 30, value, size=18, bold=True, color=(20, 35, 72))
    painter.text(x + 14, y + 56, subtitle, size=9, color=(96, 107, 129))


def _build_work_allocation_report_pdf(
    *,
    month_token: str,
    space_name: str,
    teams: list[dict[str, object]],
    people: list[dict[str, object]],
    tasks: list[dict[str, object]],
    allocations: list[dict[str, object]],
) -> bytes:
    document = _SimplePdfDoc(width=842.0, height=595.0)
    painter = _TopPdfPainter(document)
    page_number = 0
    cursor_y = 0.0
    left = 28.0
    right = document.width - 28.0
    content_width = right - left
    bottom_limit = document.height - 36.0

    task_by_id = {str(row.get("id") or ""): row for row in tasks}
    team_by_id = {str(row.get("id") or ""): row for row in teams}
    people_by_team: dict[str, list[dict[str, object]]] = {}
    for person in people:
        key = str(person.get("team_id") or "")
        people_by_team.setdefault(key, []).append(person)

    allocations_by_person: dict[str, list[dict[str, object]]] = {}
    allocations_by_team: dict[str, list[dict[str, object]]] = {}
    allocations_by_task: dict[str, list[dict[str, object]]] = {}
    for allocation in allocations:
        task_id = str(allocation.get("task_id") or "")
        allocations_by_task.setdefault(task_id, []).append(allocation)
        if str(allocation.get("assignee_type") or "") == "person":
            person_id = str(allocation.get("assignee_id") or "")
            allocations_by_person.setdefault(person_id, []).append(allocation)
        elif str(allocation.get("assignee_type") or "") == "team":
            team_id = str(allocation.get("assignee_id") or "")
            allocations_by_team.setdefault(team_id, []).append(allocation)

    total_capacity = sum(max(_float_or(person.get("capacity_fte_months"), 1.0), 0.0) for person in people)
    total_allocated = sum(max(_float_or(alloc.get("fte_months_allocated"), 0.0), 0.0) for alloc in allocations)
    assigned_task_ids = {task_id for task_id, values in allocations_by_task.items() if values}
    backlog_count = max(len(tasks) - len(assigned_task_ids), 0)
    utilization = (total_allocated / total_capacity) if total_capacity > 0 else 0.0
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    def utilization_color(ratio: float) -> tuple[int, int, int]:
        if ratio > 1.0:
            return (190, 46, 77)
        if ratio >= 0.85:
            return (225, 146, 36)
        return (48, 138, 101)

    def start_page() -> None:
        nonlocal page_number, cursor_y
        page_number += 1
        document.new_page()
        painter.rect(0, 0, document.width, document.height, fill=(245, 247, 252))
        painter.rect(0, 0, document.width, 74, fill=(21, 41, 86))
        painter.text(left, 18, "Planning Report: Work Allocation Board", size=20, bold=True, color=(255, 255, 255))
        painter.text(
            left,
            46,
            f"Space: {space_name}   Month: {month_token}   Generated: {timestamp}",
            size=9,
            color=(209, 220, 241),
        )
        painter.text(document.width - 88, 20, f"Page {page_number}", size=9, color=(209, 220, 241))
        painter.line(left, 78, right, 78, stroke=(211, 219, 232), line_width=1.2)
        painter.text(left, document.height - 18, "SIPM planning snapshot", size=8, color=(129, 139, 158))
        cursor_y = 92.0

    def ensure_space(height: float) -> None:
        nonlocal cursor_y
        if cursor_y + height > bottom_limit:
            start_page()

    def section_title(value: str) -> None:
        nonlocal cursor_y
        ensure_space(28)
        painter.text(left, cursor_y, value, size=13, bold=True, color=(23, 35, 72))
        cursor_y += 20
        painter.line(left, cursor_y, right, cursor_y, stroke=(218, 224, 235), line_width=1)
        cursor_y += 8

    start_page()

    card_gap = 12.0
    card_width = (content_width - (card_gap * 3.0)) / 4.0
    card_height = 82.0
    _draw_report_card(
        painter,
        x=left,
        y=cursor_y,
        width=card_width,
        height=card_height,
        accent=(40, 111, 232),
        title="Tasks in scope",
        value=f"{len(tasks)}",
        subtitle=f"{len(assigned_task_ids)} assigned, {backlog_count} backlog",
    )
    _draw_report_card(
        painter,
        x=left + card_width + card_gap,
        y=cursor_y,
        width=card_width,
        height=card_height,
        accent=(22, 163, 74),
        title="People on board",
        value=f"{len(people)}",
        subtitle=f"{len(teams)} named teams",
    )
    _draw_report_card(
        painter,
        x=left + ((card_width + card_gap) * 2.0),
        y=cursor_y,
        width=card_width,
        height=card_height,
        accent=(217, 119, 6),
        title="Allocated effort",
        value=f"{total_allocated:.2f} FTE-mo",
        subtitle=f"of {total_capacity:.2f} total capacity",
    )
    _draw_report_card(
        painter,
        x=left + ((card_width + card_gap) * 3.0),
        y=cursor_y,
        width=card_width,
        height=card_height,
        accent=utilization_color(utilization),
        title="Utilization",
        value=f"{min(max(utilization * 100.0, 0.0), 999.0):.0f}%",
        subtitle="team + person assignments",
    )
    cursor_y += card_height + 18

    section_title("Team Capacity and Current Load")
    header_h = 22.0
    painter.rect(left, cursor_y, content_width, header_h, fill=(230, 235, 245), stroke=(212, 219, 232))
    painter.text(left + 8, cursor_y + 6, "Team", size=9, bold=True, color=(44, 55, 80))
    painter.text(left + 286, cursor_y + 6, "People", size=9, bold=True, color=(44, 55, 80))
    painter.text(left + 352, cursor_y + 6, "Load", size=9, bold=True, color=(44, 55, 80))
    painter.text(left + 430, cursor_y + 6, "Capacity Bar", size=9, bold=True, color=(44, 55, 80))
    painter.text(left + 690, cursor_y + 6, "Direct", size=9, bold=True, color=(44, 55, 80))
    cursor_y += header_h

    team_rows: list[tuple[str, str]] = []
    for team in sorted(teams, key=lambda row: str(row.get("name") or "").lower()):
        team_rows.append((str(team.get("id") or ""), str(team.get("name") or "")))
    if people_by_team.get("") or allocations_by_team.get(""):
        team_rows.append(("", "Unassigned"))

    if not team_rows:
        painter.rect(left, cursor_y, content_width, 28, fill=(248, 250, 255), stroke=(220, 226, 237))
        painter.text(left + 8, cursor_y + 9, "No team structure has been created yet.", size=9, color=(104, 112, 133))
        cursor_y += 36
    else:
        for idx, (team_id, team_name) in enumerate(team_rows):
            row_h = 28.0
            ensure_space(row_h + 4)
            fill = (249, 251, 255) if idx % 2 == 0 else (244, 247, 252)
            painter.rect(left, cursor_y, content_width, row_h, fill=fill, stroke=(224, 230, 241))
            team_people = people_by_team.get(team_id, [])
            team_people_count = len(team_people)
            team_capacity = sum(max(_float_or(person.get("capacity_fte_months"), 1.0), 0.0) for person in team_people)
            person_load = 0.0
            for person in team_people:
                person_allocs = allocations_by_person.get(str(person.get("id") or ""), [])
                person_load += sum(max(_float_or(a.get("fte_months_allocated"), 0.0), 0.0) for a in person_allocs)
            team_direct_allocs = allocations_by_team.get(team_id, [])
            direct_load = sum(max(_float_or(a.get("fte_months_allocated"), 0.0), 0.0) for a in team_direct_allocs)
            team_load = person_load + direct_load
            ratio = (team_load / team_capacity) if team_capacity > 0 else (1.0 if team_load > 0 else 0.0)
            ratio_clamped = max(0.0, min(ratio, 1.0))
            bar_color = utilization_color(ratio)

            painter.text(left + 8, cursor_y + 9, team_name or "Unnamed Team", size=9, bold=True, color=(27, 38, 66))
            painter.text(left + 302, cursor_y + 9, f"{team_people_count}", size=9, color=(39, 47, 63))
            painter.text(left + 352, cursor_y + 9, f"{team_load:.2f} / {team_capacity:.2f}", size=9, color=(39, 47, 63))
            painter.rect(left + 430, cursor_y + 9, 220, 10, fill=(224, 230, 241), stroke=(211, 219, 232))
            painter.rect(left + 430, cursor_y + 9, 220 * ratio_clamped, 10, fill=bar_color)
            painter.text(left + 690, cursor_y + 9, f"{len(team_direct_allocs)}", size=9, color=(39, 47, 63))
            cursor_y += row_h
        cursor_y += 10

    section_title("Who Is Working On What")
    table_h = 22.0
    painter.rect(left, cursor_y, content_width, table_h, fill=(230, 235, 245), stroke=(212, 219, 232))
    painter.text(left + 8, cursor_y + 6, "Person", size=9, bold=True, color=(44, 55, 80))
    painter.text(left + 170, cursor_y + 6, "Team", size=9, bold=True, color=(44, 55, 80))
    painter.text(left + 300, cursor_y + 6, "Load", size=9, bold=True, color=(44, 55, 80))
    painter.text(left + 370, cursor_y + 6, "Assigned Tasks", size=9, bold=True, color=(44, 55, 80))
    cursor_y += table_h

    sorted_people = sorted(
        people,
        key=lambda person: (
            -sum(
                max(_float_or(alloc.get("fte_months_allocated"), 0.0), 0.0)
                for alloc in allocations_by_person.get(str(person.get("id") or ""), [])
            ),
            str(person.get("name") or "").lower(),
        ),
    )
    if not sorted_people:
        painter.rect(left, cursor_y, content_width, 28, fill=(248, 250, 255), stroke=(220, 226, 237))
        painter.text(left + 8, cursor_y + 9, "No active people found in this space.", size=9, color=(104, 112, 133))
        cursor_y += 36
    else:
        for idx, person in enumerate(sorted_people):
            assignee_id = str(person.get("id") or "")
            person_allocs = allocations_by_person.get(assignee_id, [])
            team_name = "Unassigned"
            team_id = str(person.get("team_id") or "")
            if team_id:
                team_name = str(team_by_id.get(team_id, {}).get("name") or "Unassigned")
            person_capacity = max(_float_or(person.get("capacity_fte_months"), 1.0), 0.0)
            person_load = sum(max(_float_or(row.get("fte_months_allocated"), 0.0), 0.0) for row in person_allocs)
            if person_allocs:
                task_text = "; ".join(
                    f"{str(task_by_id.get(str(row.get('task_id') or ''), {}).get('title') or row.get('task_id') or 'Task')} ({_float_or(row.get('fte_months_allocated'), 0.0):.2f})"
                    for row in person_allocs
                )
            else:
                task_text = "No assignments this month."
            wrapped = _wrap_pdf_text(task_text, max_width=430.0, font_size=8.8, max_lines=4)
            row_h = max(24.0, 8.0 + (len(wrapped) * 11.0))
            ensure_space(row_h + 4)
            fill = (249, 251, 255) if idx % 2 == 0 else (244, 247, 252)
            painter.rect(left, cursor_y, content_width, row_h, fill=fill, stroke=(224, 230, 241))
            painter.text(left + 8, cursor_y + 8, str(person.get("name") or assignee_id), size=9, bold=True, color=(27, 38, 66))
            painter.text(left + 170, cursor_y + 8, team_name, size=9, color=(44, 55, 80))
            painter.text(left + 300, cursor_y + 8, f"{person_load:.2f}/{person_capacity:.2f}", size=9, color=(44, 55, 80))
            line_y = cursor_y + 8
            for line in wrapped:
                painter.text(left + 370, line_y, line, size=8.8, color=(44, 55, 80))
                line_y += 11
            cursor_y += row_h
        cursor_y += 10

    section_title("Backlog Tasks")
    backlog_tasks = [
        task for task in tasks if str(task.get("id") or "") not in assigned_task_ids
    ]
    backlog_tasks = sorted(
        backlog_tasks,
        key=lambda task: (-_float_or(task.get("fte_months"), 0.0), str(task.get("title") or "").lower()),
    )
    if not backlog_tasks:
        painter.rect(left, cursor_y, content_width, 28, fill=(237, 252, 243), stroke=(189, 225, 201))
        painter.text(left + 8, cursor_y + 9, "All tasks have at least one assignment for this month.", size=9, color=(29, 110, 62))
        cursor_y += 36
    else:
        painter.rect(left, cursor_y, content_width, 22, fill=(230, 235, 245), stroke=(212, 219, 232))
        painter.text(left + 8, cursor_y + 6, "Task", size=9, bold=True, color=(44, 55, 80))
        painter.text(right - 90, cursor_y + 6, "FTE-mo", size=9, bold=True, color=(44, 55, 80))
        cursor_y += 22
        for idx, task in enumerate(backlog_tasks):
            row_h = 20.0
            ensure_space(row_h + 2)
            fill = (249, 251, 255) if idx % 2 == 0 else (244, 247, 252)
            painter.rect(left, cursor_y, content_width, row_h, fill=fill, stroke=(224, 230, 241))
            title = str(task.get("title") or task.get("id") or "Task")
            wrapped = _wrap_pdf_text(title, max_width=content_width - 128, font_size=9, max_lines=1)
            painter.text(left + 8, cursor_y + 6, wrapped[0], size=9, color=(44, 55, 80))
            painter.text(right - 84, cursor_y + 6, f"{_float_or(task.get('fte_months'), 0.0):.2f}", size=9, color=(44, 55, 80))
            cursor_y += row_h

    return document.build()


def _normalize_soeid_base(name: str) -> str:
    raw = re.sub(r"[^a-z0-9]+", "", str(name or "").strip().lower())
    return raw[:14] or "person"


def _next_available_soeid(session: Session, name: str) -> str:
    base = _normalize_soeid_base(name)
    candidate = base
    counter = 1
    while session.query(User).filter(func.lower(User.soeid) == candidate).first():
        counter += 1
        candidate = f"{base[:10]}{counter:02d}"
    return candidate


def _ensure_membership(session: Session, user_id: str, space_id: str) -> None:
    membership = (
        session.query(SpaceMembership)
        .filter(SpaceMembership.space_id == space_id)
        .filter(SpaceMembership.user_id == user_id)
        .first()
    )
    if not membership:
        membership = SpaceMembership(
            space_id=space_id,
            user_id=user_id,
            role="member",
            status="active",
        )
        session.add(membership)
        return
    membership.deleted_at = None
    membership.status = "active"
    if not (membership.role or "").strip():
        membership.role = "member"
    session.add(membership)


@router.get("/resource-allocations", response_model=List[ResourceAllocationRead])
def list_allocations(
    from_date: Optional[date] = Query(None, alias="from"),
    to_date: Optional[date] = Query(None, alias="to"),
    assignee: Optional[str] = None,
    assignee_user_soeid: Optional[str] = None,
    team_id: Optional[str] = None,
    window_id: Optional[str] = None,
    session: Session = Depends(get_db),
    space_ctx: SpaceContext = Depends(current_space_dep),
    current_user: User = Depends(current_user_dep),
    _authz: SpaceContext = Depends(require_space_role("member")),
):
    assignee_norm = assignee.strip().lower() if assignee else None
    params = {
        "from_date": from_date.isoformat() if from_date else None,
        "to_date": to_date.isoformat() if to_date else None,
        "assignee": assignee_norm,
        "assignee_user_soeid": assignee_user_soeid,
        "team_id": team_id,
        "window_id": window_id,
    }
    scope_token = make_scope_token("planning", space_ctx.space_id)

    def _load():
        month_expr = _allocation_month_expr()
        query = _allocation_query(session, space_ctx)
        if from_date:
            query = query.filter(month_expr >= from_date)
        if to_date:
            query = query.filter(month_expr <= to_date)
        if assignee_norm:
            query = query.filter(func.lower(ResourceAllocation.assignee) == assignee_norm)
        if assignee_user_soeid:
            query = query.filter(ResourceAllocation.assignee_user_soeid == assignee_user_soeid)
        if team_id:
            query = query.filter(ResourceAllocation.team_id == team_id)
        if window_id:
            query = query.filter(ResourceAllocation.window_id == window_id)
        rows = query.order_by(month_expr.asc(), ResourceAllocation.assignee_user_soeid.asc()).all()
        return [_allocation_to_payload(row) for row in rows]

    return cached_call(
        endpoint="planning:allocations:list",
        params=params,
        space_id=space_ctx.space_id,
        user_id=current_user.user_id,
        role_scope=_role_scope(space_ctx),
        ttl_seconds=_PLANNING_LIST_TTL_SECONDS,
        scope_tokens=[scope_token],
        loader=_load,
    )


@router.post("/resource-allocations", response_model=ResourceAllocationRead, status_code=status.HTTP_201_CREATED)
def create_allocation(
    payload: ResourceAllocationCreate,
    session: Session = Depends(get_db),
    space_ctx: SpaceContext = Depends(current_space_dep),
    _authz: SpaceContext = Depends(require_space_role("space_admin")),
) -> ResourceAllocationRead:
    _active_team(session, payload.team_id, space_ctx)
    if payload.window_id:
        _get_window(session, payload.window_id, space_ctx)
    month_start = _resolve_month_start(payload.month_start, payload.week_start)
    fte_months = _resolve_fte_months(payload.fte_months, payload.hours)
    alloc = ResourceAllocation(
        space_id=space_ctx.space_id,
        work_item_type=payload.work_item_type,
        work_item_id=payload.work_item_id,
        assignee_user_soeid=payload.assignee_user_soeid or payload.assignee,
        assignee=payload.assignee,
        team_id=payload.team_id,
        week_start=payload.week_start or month_start,
        month_start=month_start,
        hours=_hours_from_fte_months(fte_months),
        fte_months=fte_months,
        window_id=payload.window_id,
    )
    session.add(alloc)
    session.commit()
    session.refresh(alloc)
    invalidate_space(space_ctx.space_id, ["planning"])
    return ResourceAllocationRead.model_validate(_allocation_to_payload(alloc))


@router.patch("/resource-allocations/{allocation_id}", response_model=ResourceAllocationRead)
def update_allocation(
    allocation_id: str,
    payload: ResourceAllocationUpdate,
    session: Session = Depends(get_db),
    space_ctx: SpaceContext = Depends(current_space_dep),
    _authz: SpaceContext = Depends(require_space_role("space_admin")),
) -> ResourceAllocationRead:
    alloc = _get_allocation(session, allocation_id, space_ctx)
    if payload.team_id is not None:
        _active_team(session, payload.team_id, space_ctx)
    if payload.window_id:
        _get_window(session, payload.window_id, space_ctx)
    update_data = payload.model_dump(exclude_unset=True)
    for field in ["work_item_type", "work_item_id", "assignee", "assignee_user_soeid", "team_id", "window_id"]:
        if field in update_data:
            setattr(alloc, field, update_data[field])

    month_start_set = False
    if "month_start" in update_data and update_data["month_start"] is not None:
        alloc.month_start = _month_start(update_data["month_start"])
        month_start_set = True
        if "week_start" not in update_data:
            alloc.week_start = alloc.month_start
    if "week_start" in update_data and update_data["week_start"] is not None:
        alloc.week_start = update_data["week_start"]
        if not month_start_set:
            alloc.month_start = _month_start(update_data["week_start"])

    if "fte_months" in update_data and update_data["fte_months"] is not None:
        alloc.fte_months = round(max(float(update_data["fte_months"]), 0.0), 3)
        alloc.hours = _hours_from_fte_months(alloc.fte_months)
    elif "hours" in update_data and update_data["hours"] is not None:
        alloc.hours = max(int(update_data["hours"]), 0)
        alloc.fte_months = round(float(alloc.hours) / _HOURS_PER_FTE_MONTH, 3)

    if alloc.month_start is None and alloc.week_start is not None:
        alloc.month_start = _month_start(alloc.week_start)
    if alloc.week_start is None and alloc.month_start is not None:
        alloc.week_start = alloc.month_start

    alloc.updated_at = datetime.now(timezone.utc)
    session.add(alloc)
    session.commit()
    session.refresh(alloc)
    invalidate_space(space_ctx.space_id, ["planning"])
    return ResourceAllocationRead.model_validate(_allocation_to_payload(alloc))


@router.delete("/resource-allocations/{allocation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_allocation(
    allocation_id: str,
    session: Session = Depends(get_db),
    space_ctx: SpaceContext = Depends(current_space_dep),
    _authz: SpaceContext = Depends(require_space_role("space_admin")),
) -> None:
    alloc = _get_allocation(session, allocation_id, space_ctx)
    alloc.deleted_at = datetime.now(timezone.utc)
    session.add(alloc)
    session.commit()
    invalidate_space(space_ctx.space_id, ["planning"])
    return None


@router.get("/resource-allocations/summary")
def allocations_summary(
    from_date: Optional[date] = Query(None, alias="from"),
    to_date: Optional[date] = Query(None, alias="to"),
    window_id: Optional[str] = None,
    session: Session = Depends(get_db),
    space_ctx: SpaceContext = Depends(current_space_dep),
    current_user: User = Depends(current_user_dep),
    _authz: SpaceContext = Depends(require_space_role("space_admin")),
):
    params = {
        "from_date": from_date.isoformat() if from_date else None,
        "to_date": to_date.isoformat() if to_date else None,
        "window_id": window_id,
    }
    scope_token = make_scope_token("planning", space_ctx.space_id)

    def _load():
        month_expr = _allocation_month_expr()
        fte_expr = _allocation_fte_expr()
        query = session.query(
            ResourceAllocation.assignee_user_soeid,
            func.min(ResourceAllocation.assignee).label("assignee"),
            month_expr.label("month_start"),
            func.sum(fte_expr).label("fte_months"),
        ).filter(ResourceAllocation.deleted_at.is_(None)).filter(ResourceAllocation.space_id == space_ctx.space_id)
        if from_date:
            query = query.filter(month_expr >= from_date)
        if to_date:
            query = query.filter(month_expr <= to_date)
        if window_id:
            query = query.filter(ResourceAllocation.window_id == window_id)
        rows = (
            query.group_by(ResourceAllocation.assignee_user_soeid, month_expr)
            .order_by(month_expr.asc(), ResourceAllocation.assignee_user_soeid.asc())
            .all()
        )
        return [
            {
                "assignee_user_soeid": r.assignee_user_soeid,
                "assignee": r.assignee,
                "month_start": str(r.month_start) if r.month_start else None,
                "week_start": str(r.month_start) if r.month_start else None,
                "fte_months": round(float(r.fte_months or 0), 3),
                "hours": _hours_from_fte_months(float(r.fte_months or 0)),
            }
            for r in rows
        ]

    return cached_call(
        endpoint="planning:allocations:summary",
        params=params,
        space_id=space_ctx.space_id,
        user_id=current_user.user_id,
        role_scope=_role_scope(space_ctx),
        ttl_seconds=_PLANNING_LIST_TTL_SECONDS,
        scope_tokens=[scope_token],
        loader=_load,
    )


# Planning windows
@router.get("/planning/windows", response_model=List[PlanningWindowRead])
def list_windows(
    session: Session = Depends(get_db),
    space_ctx: SpaceContext = Depends(current_space_dep),
    current_user: User = Depends(current_user_dep),
    _authz: SpaceContext = Depends(require_space_role("member")),
) -> List[PlanningWindowRead]:
    scope_token = make_scope_token("planning", space_ctx.space_id)

    def _load():
        wins = (
            _window_query(session, space_ctx)
            .order_by(PlanningWindow.start_date.asc())
            .all()
        )
        return [PlanningWindowRead.model_validate(w).model_dump(mode="json") for w in wins]

    return cached_call(
        endpoint="planning:windows:list",
        params={},
        space_id=space_ctx.space_id,
        user_id=current_user.user_id,
        role_scope=_role_scope(space_ctx),
        ttl_seconds=_PLANNING_DETAIL_TTL_SECONDS,
        scope_tokens=[scope_token],
        loader=_load,
    )


@router.post("/planning/windows", response_model=PlanningWindowRead, status_code=status.HTTP_201_CREATED)
def create_window(
    payload: PlanningWindowCreate,
    session: Session = Depends(get_db),
    space_ctx: SpaceContext = Depends(current_space_dep),
    _authz: SpaceContext = Depends(require_space_role("space_admin")),
) -> PlanningWindowRead:
    win = PlanningWindow(
        space_id=space_ctx.space_id,
        name=payload.name,
        start_date=payload.start_date,
        end_date=payload.end_date,
    )
    try:
        session.add(win)
        session.commit()
        session.refresh(win)
    except IntegrityError as err:
        session.rollback()
        if _is_window_name_conflict_integrity_error(err):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Planning window name already exists",
            ) from err
        raise
    invalidate_space(space_ctx.space_id, ["planning"])
    return PlanningWindowRead.model_validate(win)


@router.patch("/planning/windows/{window_id}", response_model=PlanningWindowRead)
def update_window(
    window_id: str,
    payload: PlanningWindowUpdate,
    session: Session = Depends(get_db),
    space_ctx: SpaceContext = Depends(current_space_dep),
    _authz: SpaceContext = Depends(require_space_role("space_admin")),
) -> PlanningWindowRead:
    win = _get_window(session, window_id, space_ctx)
    update_data = payload.model_dump(exclude_unset=True)
    for field, val in update_data.items():
        if val is not None:
            setattr(win, field, val)
    win.updated_at = datetime.now(timezone.utc)
    try:
        session.add(win)
        session.commit()
        session.refresh(win)
    except IntegrityError as err:
        session.rollback()
        if _is_window_name_conflict_integrity_error(err):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Planning window name already exists",
            ) from err
        raise
    invalidate_space(space_ctx.space_id, ["planning"])
    return PlanningWindowRead.model_validate(win)


@router.delete("/planning/windows/{window_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_window(
    window_id: str,
    session: Session = Depends(get_db),
    space_ctx: SpaceContext = Depends(current_space_dep),
    _authz: SpaceContext = Depends(require_space_role("space_admin")),
) -> None:
    win = _get_window(session, window_id, space_ctx)
    win.deleted_at = datetime.now(timezone.utc)
    session.add(win)
    session.commit()
    invalidate_space(space_ctx.space_id, ["planning"])
    return None


# Work Allocation Board (MVP)
@router.get("/planning/work-allocation/teams", response_model=List[WorkAllocationTeamRead])
def list_work_allocation_teams(
    session: Session = Depends(get_db),
    space_ctx: SpaceContext = Depends(current_space_dep),
    _authz: SpaceContext = Depends(require_space_role("member")),
) -> List[WorkAllocationTeamRead]:
    rows = _team_query(session, space_ctx).order_by(Team.name.asc()).all()
    return [WorkAllocationTeamRead(id=row.team_id, name=row.name) for row in rows]


@router.post(
    "/planning/work-allocation/teams",
    response_model=WorkAllocationTeamRead,
    status_code=status.HTTP_201_CREATED,
)
def create_work_allocation_team(
    payload: WorkAllocationTeamCreate,
    session: Session = Depends(get_db),
    space_ctx: SpaceContext = Depends(current_space_dep),
    _authz: SpaceContext = Depends(require_space_role("space_admin")),
) -> WorkAllocationTeamRead:
    name = (payload.name or "").strip()
    if not name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Team name is required")

    existing = (
        session.query(Team)
        .filter(Team.space_id == space_ctx.space_id)
        .filter(func.lower(Team.name) == name.lower())
        .first()
    )
    now = datetime.now(timezone.utc)
    if existing and existing.deleted_at is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Team already exists")
    if existing and existing.deleted_at is not None:
        existing.deleted_at = None
        existing.updated_at = now
        existing.name = name
        session.add(existing)
        session.commit()
        invalidate_space(space_ctx.space_id, ["teams", "planning"])
        return WorkAllocationTeamRead(id=existing.team_id, name=existing.name)

    row = Team(
        space_id=space_ctx.space_id,
        name=name,
        capacity_unit="fte_month",
        default_capacity_per_week=0,
        default_capacity_fte_month=0.0,
        created_at=now,
        updated_at=now,
    )
    try:
        session.add(row)
        session.commit()
        session.refresh(row)
    except IntegrityError as err:
        session.rollback()
        if _is_team_name_conflict_integrity_error(err):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Team already exists") from err
        raise
    invalidate_space(space_ctx.space_id, ["teams", "planning"])
    return WorkAllocationTeamRead(id=row.team_id, name=row.name)


@router.patch("/planning/work-allocation/teams/{team_id}", response_model=WorkAllocationTeamRead)
def update_work_allocation_team(
    team_id: str,
    payload: WorkAllocationTeamUpdate,
    session: Session = Depends(get_db),
    space_ctx: SpaceContext = Depends(current_space_dep),
    _authz: SpaceContext = Depends(require_space_role("space_admin")),
) -> WorkAllocationTeamRead:
    row = _active_team(session, team_id, space_ctx)
    next_name = (payload.name or "").strip() if payload.name is not None else None
    if next_name:
        conflict = (
            session.query(Team)
            .filter(Team.space_id == space_ctx.space_id)
            .filter(Team.deleted_at.is_(None))
            .filter(func.lower(Team.name) == next_name.lower())
            .filter(Team.team_id != team_id)
            .first()
        )
        if conflict:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Team name already exists")
        old_name = row.name
        row.name = next_name
        for user in _active_space_user_query(session, space_ctx).filter(User.team_tag == old_name).all():
            user.team_tag = next_name
            session.add(user)
    row.updated_at = datetime.now(timezone.utc)
    try:
        session.add(row)
        session.commit()
        session.refresh(row)
    except IntegrityError as err:
        session.rollback()
        if _is_team_name_conflict_integrity_error(err):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Team name already exists",
            ) from err
        raise
    invalidate_space(space_ctx.space_id, ["teams", "users", "planning"])
    return WorkAllocationTeamRead(id=row.team_id, name=row.name)


@router.delete("/planning/work-allocation/teams/{team_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_work_allocation_team(
    team_id: str,
    session: Session = Depends(get_db),
    space_ctx: SpaceContext = Depends(current_space_dep),
    _authz: SpaceContext = Depends(require_space_role("space_admin")),
) -> None:
    row = _active_team(session, team_id, space_ctx)
    now = datetime.now(timezone.utc)
    old_name = row.name
    row.deleted_at = now
    session.add(row)
    for user in _active_space_user_query(session, space_ctx).filter(User.team_tag == old_name).all():
        user.team_tag = None
        user.updated_at = now
        session.add(user)
    session.commit()
    invalidate_space(space_ctx.space_id, ["teams", "users", "planning"])
    return None


@router.get("/planning/work-allocation/people", response_model=List[WorkAllocationPersonRead])
def list_work_allocation_people(
    session: Session = Depends(get_db),
    space_ctx: SpaceContext = Depends(current_space_dep),
    _authz: SpaceContext = Depends(require_space_role("member")),
) -> List[WorkAllocationPersonRead]:
    team_map = _team_name_to_id_map(session, space_ctx)
    rows = _active_space_user_query(session, space_ctx).order_by(User.display_name.asc()).all()
    return [_person_payload(row, team_map) for row in rows]


@router.post(
    "/planning/work-allocation/people",
    response_model=WorkAllocationPersonRead,
    status_code=status.HTTP_201_CREATED,
)
def create_work_allocation_person(
    payload: WorkAllocationPersonCreate,
    session: Session = Depends(get_db),
    space_ctx: SpaceContext = Depends(current_space_dep),
    _authz: SpaceContext = Depends(require_space_role("space_admin")),
) -> WorkAllocationPersonRead:
    name = (payload.name or "").strip()
    if not name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Person name is required")
    team = _active_team(session, payload.team_id, space_ctx) if payload.team_id else None
    soeid = _next_available_soeid(session, name)
    now = datetime.now(timezone.utc)
    cap = max(float(payload.capacity_fte_months or 1.0), 0.0)
    row = User(
        soeid=soeid,
        email=f"{soeid}@{_WORK_ALLOCATION_DOMAIN}",
        display_name=name,
        password_hash=hash_bootstrap_password(),
        role="user",
        is_active=True,
        team_tag=team.name if team else None,
        capacity_fte_month=round(cap, 3),
        capacity_hours=max(int(round(cap * 40.0)), 0),
        created_at=now,
        updated_at=now,
    )
    session.add(row)
    session.flush()
    _ensure_membership(session, row.user_id, space_ctx.space_id)
    session.commit()
    session.refresh(row)
    invalidate_space(space_ctx.space_id, ["users", "planning"])
    team_map = _team_name_to_id_map(session, space_ctx)
    return _person_payload(row, team_map)


@router.patch("/planning/work-allocation/people/{person_id}", response_model=WorkAllocationPersonRead)
def update_work_allocation_person(
    person_id: str,
    payload: WorkAllocationPersonUpdate,
    session: Session = Depends(get_db),
    space_ctx: SpaceContext = Depends(current_space_dep),
    _authz: SpaceContext = Depends(require_space_role("space_admin")),
) -> WorkAllocationPersonRead:
    row = _active_person_by_soeid(session, person_id, space_ctx)
    updates = payload.model_dump(exclude_unset=True)

    if "name" in updates:
        row.display_name = (str(updates.get("name") or "").strip() or row.display_name)

    if "team_id" in updates:
        next_team_id = updates.get("team_id")
        team = _active_team(session, next_team_id, space_ctx) if next_team_id else None
        row.team_tag = team.name if team else None

    if "capacity_fte_months" in updates and updates.get("capacity_fte_months") is not None:
        cap = max(float(updates["capacity_fte_months"]), 0.0)
        row.capacity_fte_month = round(cap, 3)
        row.capacity_hours = max(int(round(cap * 40.0)), 0)

    if "active" in updates and updates.get("active") is not None:
        row.is_active = bool(updates["active"])

    row.updated_at = datetime.now(timezone.utc)
    session.add(row)
    session.commit()
    session.refresh(row)
    invalidate_space(space_ctx.space_id, ["users", "planning"])
    team_map = _team_name_to_id_map(session, space_ctx)
    return _person_payload(row, team_map)


@router.delete("/planning/work-allocation/people/{person_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_work_allocation_person(
    person_id: str,
    session: Session = Depends(get_db),
    space_ctx: SpaceContext = Depends(current_space_dep),
    _authz: SpaceContext = Depends(require_space_role("space_admin")),
) -> None:
    row = _active_person_by_soeid(session, person_id, space_ctx)
    now = datetime.now(timezone.utc)
    row.is_active = False
    row.updated_at = now
    session.add(row)
    membership = (
        session.query(SpaceMembership)
        .filter(SpaceMembership.space_id == space_ctx.space_id)
        .filter(SpaceMembership.user_id == row.user_id)
        .first()
    )
    if membership:
        membership.status = "inactive"
        membership.updated_at = now
        session.add(membership)
    session.commit()
    invalidate_space(space_ctx.space_id, ["users", "planning"])
    return None


@router.get("/planning/work-allocation/tasks", response_model=List[WorkAllocationTaskRead])
def list_work_allocation_tasks(
    month: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    session: Session = Depends(get_db),
    space_ctx: SpaceContext = Depends(current_space_dep),
    _authz: SpaceContext = Depends(require_space_role("member")),
) -> List[WorkAllocationTaskRead]:
    month_start = _month_from_token(month or _month_token(None))
    _solution, query = _board_task_query(session, space_ctx)
    if search:
        term = f"%{search.strip().lower()}%"
        query = query.filter(func.lower(Subcomponent.subcomponent_name).like(term))
    tasks = query.order_by(Subcomponent.created_at.asc()).all()
    task_ids = [t.subcomponent_id for t in tasks]
    assigned_ids: set[str] = set()
    if task_ids:
        for row in (
            _allocation_query(session, space_ctx)
            .filter(ResourceAllocation.work_item_type == "subcomponent")
            .filter(ResourceAllocation.work_item_id.in_(task_ids))
            .filter(_allocation_month_expr() == month_start)
            .all()
        ):
            assigned_ids.add(row.work_item_id)
    return [_task_payload(task, assigned_ids) for task in tasks]


@router.post(
    "/planning/work-allocation/tasks",
    response_model=WorkAllocationTaskRead,
    status_code=status.HTTP_201_CREATED,
)
def create_work_allocation_task(
    payload: WorkAllocationTaskCreate,
    month: Optional[str] = Query(None),
    session: Session = Depends(get_db),
    space_ctx: SpaceContext = Depends(current_space_dep),
    _authz: SpaceContext = Depends(require_space_role("space_admin")),
) -> WorkAllocationTaskRead:
    solution, query = _board_task_query(session, space_ctx)
    title = (payload.title or "").strip()
    if not title:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Task title is required")
    conflict = query.filter(func.lower(Subcomponent.subcomponent_name) == title.lower()).first()
    if conflict:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Task title already exists")
    fte = round(max(float(payload.fte_months or 0.25), 0.05), 3)
    hours = max(int(round(fte * _HOURS_PER_FTE_MONTH)), 1)
    now = datetime.now(timezone.utc)
    row = Subcomponent(
        space_id=space_ctx.space_id,
        project_id=solution.project_id,
        solution_id=solution.solution_id,
        subcomponent_name=title,
        status=SubcomponentStatus.to_do,
        priority=3,
        assignee=_WORK_ALLOCATION_DEFAULT_ASSIGNEE,
        estimate_hours=hours,
        capacity_hours=hours,
        blocked=False,
        created_at=now,
        updated_at=now,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    invalidate_space(space_ctx.space_id, ["subcomponents", "planning"])
    month_start = _month_from_token(month or _month_token(None))
    assigned_ids: set[str] = set()
    if (
        _allocation_query(session, space_ctx)
        .filter(ResourceAllocation.work_item_type == "subcomponent")
        .filter(ResourceAllocation.work_item_id == row.subcomponent_id)
        .filter(_allocation_month_expr() == month_start)
        .first()
    ):
        assigned_ids.add(row.subcomponent_id)
    return _task_payload(row, assigned_ids)


@router.patch("/planning/work-allocation/tasks/{task_id}", response_model=WorkAllocationTaskRead)
def update_work_allocation_task(
    task_id: str,
    month: Optional[str] = Query(None),
    payload: WorkAllocationTaskUpdate = ...,
    session: Session = Depends(get_db),
    space_ctx: SpaceContext = Depends(current_space_dep),
    _authz: SpaceContext = Depends(require_space_role("space_admin")),
) -> WorkAllocationTaskRead:
    _solution, query = _board_task_query(session, space_ctx)
    row = query.filter(Subcomponent.subcomponent_id == task_id).first()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    if payload.title is not None:
        title = payload.title.strip()
        if not title:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Task title is required")
        conflict = (
            query.filter(func.lower(Subcomponent.subcomponent_name) == title.lower())
            .filter(Subcomponent.subcomponent_id != task_id)
            .first()
        )
        if conflict:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Task title already exists")
        row.subcomponent_name = title
    if payload.fte_months is not None:
        fte = round(max(float(payload.fte_months), 0.05), 3)
        hours = max(int(round(fte * _HOURS_PER_FTE_MONTH)), 1)
        row.estimate_hours = hours
        row.capacity_hours = hours
    row.updated_at = datetime.now(timezone.utc)
    session.add(row)
    session.commit()
    session.refresh(row)
    invalidate_space(space_ctx.space_id, ["subcomponents", "planning"])
    month_start = _month_from_token(month or _month_token(None))
    assigned_ids: set[str] = set()
    if (
        _allocation_query(session, space_ctx)
        .filter(ResourceAllocation.work_item_type == "subcomponent")
        .filter(ResourceAllocation.work_item_id == row.subcomponent_id)
        .filter(_allocation_month_expr() == month_start)
        .first()
    ):
        assigned_ids.add(row.subcomponent_id)
    return _task_payload(row, assigned_ids)


@router.delete("/planning/work-allocation/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_work_allocation_task(
    task_id: str,
    session: Session = Depends(get_db),
    space_ctx: SpaceContext = Depends(current_space_dep),
    _authz: SpaceContext = Depends(require_space_role("space_admin")),
) -> None:
    _solution, query = _board_task_query(session, space_ctx)
    row = query.filter(Subcomponent.subcomponent_id == task_id).first()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    now = datetime.now(timezone.utc)
    row.deleted_at = now
    row.updated_at = now
    session.add(row)
    for alloc in (
        _allocation_query(session, space_ctx)
        .filter(ResourceAllocation.work_item_type == "subcomponent")
        .filter(ResourceAllocation.work_item_id == task_id)
        .all()
    ):
        alloc.deleted_at = now
        alloc.updated_at = now
        session.add(alloc)
    session.commit()
    invalidate_space(space_ctx.space_id, ["subcomponents", "planning"])
    return None


@router.get("/planning/work-allocation/allocations", response_model=List[WorkAllocationAssignmentRead])
def list_work_allocation_allocations(
    month: Optional[str] = Query(None),
    session: Session = Depends(get_db),
    space_ctx: SpaceContext = Depends(current_space_dep),
    _authz: SpaceContext = Depends(require_space_role("member")),
) -> List[WorkAllocationAssignmentRead]:
    month_start = _month_from_token(month or _month_token(None))
    _solution, query = _board_task_query(session, space_ctx)
    task_ids = [row.subcomponent_id for row in query.all()]
    if not task_ids:
        return []
    rows = (
        _allocation_query(session, space_ctx)
        .filter(ResourceAllocation.work_item_type == "subcomponent")
        .filter(ResourceAllocation.work_item_id.in_(task_ids))
        .filter(_allocation_month_expr() == month_start)
        .order_by(ResourceAllocation.created_at.asc())
        .all()
    )
    return [_allocation_for_board_payload(row, space_ctx, session) for row in rows]


@router.get("/planning/work-allocation/report.pdf")
def download_work_allocation_report_pdf(
    month: Optional[str] = Query(None),
    session: Session = Depends(get_db),
    space_ctx: SpaceContext = Depends(current_space_dep),
    _authz: SpaceContext = Depends(require_space_role("member")),
) -> StreamingResponse:
    month_start = _month_from_token(month or _month_token(None))
    month_token = _month_token(month_start)

    team_rows = _team_query(session, space_ctx).order_by(Team.name.asc()).all()
    team_map = _team_name_to_id_map(session, space_ctx)
    people_rows = _active_space_user_query(session, space_ctx).order_by(User.display_name.asc()).all()
    people_payload = [_person_payload(row, team_map).model_dump() for row in people_rows]

    _solution, task_query = _board_task_query(session, space_ctx)
    task_rows = task_query.order_by(Subcomponent.subcomponent_name.asc()).all()
    task_payload = [
        {
            "id": row.subcomponent_id,
            "title": row.subcomponent_name,
            "fte_months": _task_fte_months(row),
        }
        for row in task_rows
    ]
    task_ids = [row.subcomponent_id for row in task_rows]
    allocation_rows: list[ResourceAllocation] = []
    if task_ids:
        allocation_rows = (
            _allocation_query(session, space_ctx)
            .filter(ResourceAllocation.work_item_type == "subcomponent")
            .filter(ResourceAllocation.work_item_id.in_(task_ids))
            .filter(_allocation_month_expr() == month_start)
            .order_by(ResourceAllocation.created_at.asc())
            .all()
        )

    allocation_payload = [
        _allocation_for_board_payload(row, space_ctx, session).model_dump()
        for row in allocation_rows
    ]
    pdf_bytes = _build_work_allocation_report_pdf(
        month_token=month_token,
        space_name=space_ctx.space_name,
        teams=[{"id": row.team_id, "name": row.name} for row in team_rows],
        people=people_payload,
        tasks=task_payload,
        allocations=allocation_payload,
    )
    filename = f"work-allocation-report-{month_token}.pdf"
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return StreamingResponse(BytesIO(pdf_bytes), media_type="application/pdf", headers=headers)


@router.post(
    "/planning/work-allocation/allocations",
    response_model=WorkAllocationAssignmentRead,
    status_code=status.HTTP_201_CREATED,
)
def create_work_allocation_allocation(
    payload: WorkAllocationAssignmentCreate,
    session: Session = Depends(get_db),
    space_ctx: SpaceContext = Depends(current_space_dep),
    _authz: SpaceContext = Depends(require_space_role("space_admin")),
) -> WorkAllocationAssignmentRead:
    month_start = _month_from_token(payload.month)
    _solution, task_query = _board_task_query(session, space_ctx)
    task = task_query.filter(Subcomponent.subcomponent_id == payload.task_id).first()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    assignee_user_soeid: Optional[str] = None
    assignee_name: Optional[str] = None
    team_id: Optional[str] = None
    if payload.assignee_type == "person":
        user = _active_person_by_soeid(session, payload.assignee_id, space_ctx)
        assignee_user_soeid = user.soeid
        assignee_name = user.display_name
    else:
        team = _active_team(session, payload.assignee_id, space_ctx)
        team_id = team.team_id
        assignee_name = team.name

    same_assignee = (
        _allocation_query(session, space_ctx)
        .filter(ResourceAllocation.work_item_type == "subcomponent")
        .filter(ResourceAllocation.work_item_id == payload.task_id)
        .filter(_allocation_month_expr() == month_start)
    )
    if assignee_user_soeid:
        same_assignee = same_assignee.filter(ResourceAllocation.assignee_user_soeid == assignee_user_soeid)
    else:
        same_assignee = (
            same_assignee
            .filter(ResourceAllocation.assignee_user_soeid.is_(None))
            .filter(ResourceAllocation.team_id == team_id)
        )
    if same_assignee.first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Task is already allocated to this assignee for this month",
        )

    if team_id:
        other_team_allocation = (
            _allocation_query(session, space_ctx)
            .filter(ResourceAllocation.work_item_type == "subcomponent")
            .filter(ResourceAllocation.work_item_id == payload.task_id)
            .filter(_allocation_month_expr() == month_start)
            .filter(ResourceAllocation.assignee_user_soeid.is_(None))
            .first()
        )
        if other_team_allocation and other_team_allocation.team_id != team_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Task already has a team-level allocation for this month",
            )

    fte = payload.fte_months_allocated
    if fte is None:
        fte = _task_fte_months(task)
    fte = round(max(float(fte), 0.05), 3)
    hours = max(int(round(fte * _HOURS_PER_FTE_MONTH)), 1)
    now = datetime.now(timezone.utc)

    # Oracle unique key on allocations includes assignee_user_soeid/week_start/window_id but not deleted_at.
    # Reuse a matching soft-deleted row to avoid ORA-00001 on re-assignment flows.
    revive_query = (
        session.query(ResourceAllocation)
        .filter(ResourceAllocation.space_id == space_ctx.space_id)
        .filter(ResourceAllocation.work_item_type == "subcomponent")
        .filter(ResourceAllocation.work_item_id == payload.task_id)
        .filter(ResourceAllocation.week_start == month_start)
        .filter(ResourceAllocation.window_id.is_(None))
    )
    if assignee_user_soeid:
        revive_query = revive_query.filter(ResourceAllocation.assignee_user_soeid == assignee_user_soeid)
    else:
        revive_query = revive_query.filter(ResourceAllocation.assignee_user_soeid.is_(None))
    revive_row = revive_query.first()
    if revive_row:
        revive_row.assignee_user_soeid = assignee_user_soeid
        revive_row.assignee = assignee_name
        revive_row.team_id = team_id
        revive_row.week_start = month_start
        revive_row.month_start = month_start
        revive_row.hours = hours
        revive_row.fte_months = fte
        revive_row.window_id = None
        revive_row.deleted_at = None
        revive_row.updated_at = now
        session.add(revive_row)
        try:
            session.commit()
        except IntegrityError as err:
            session.rollback()
            _raise_on_unique_allocation_conflict(err)
        session.refresh(revive_row)
        invalidate_space(space_ctx.space_id, ["planning"])
        return _allocation_for_board_payload(revive_row, space_ctx, session)

    row = ResourceAllocation(
        space_id=space_ctx.space_id,
        work_item_type="subcomponent",
        work_item_id=payload.task_id,
        assignee_user_soeid=assignee_user_soeid,
        assignee=assignee_name,
        team_id=team_id,
        week_start=month_start,
        month_start=month_start,
        hours=hours,
        fte_months=fte,
        window_id=None,
        created_at=now,
        updated_at=now,
    )
    session.add(row)
    try:
        session.commit()
    except IntegrityError as err:
        session.rollback()
        _raise_on_unique_allocation_conflict(err)
    session.refresh(row)
    invalidate_space(space_ctx.space_id, ["planning"])
    return _allocation_for_board_payload(row, space_ctx, session)


@router.delete("/planning/work-allocation/allocations/{allocation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_work_allocation_allocation(
    allocation_id: str,
    session: Session = Depends(get_db),
    space_ctx: SpaceContext = Depends(current_space_dep),
    _authz: SpaceContext = Depends(require_space_role("space_admin")),
) -> None:
    row = _get_allocation(session, allocation_id, space_ctx)
    now = datetime.now(timezone.utc)
    row.deleted_at = now
    row.updated_at = now
    session.add(row)
    session.commit()
    invalidate_space(space_ctx.space_id, ["planning"])
    return None



