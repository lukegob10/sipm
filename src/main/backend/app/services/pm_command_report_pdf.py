from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Optional

from .planning_report_pdf import (
    _SimplePdfDoc,
    _TopPdfPainter,
    _draw_report_card,
    _estimate_pdf_text_width,
    _wrap_pdf_text,
)


STALE_STATUS_DAYS = 7


def _text(value: object, fallback: str = "-") -> str:
    text = str(value or "").strip()
    return text or fallback


def _enum_text(value: object) -> str:
    return str(getattr(value, "value", value) or "").strip().lower()


def _label(value: object, fallback: str = "-") -> str:
    text = _text(value, fallback)
    return text.replace("_", " ").title() if text != "-" else text


def _date_value(value: object) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value or "").strip()
    if len(text) < 10:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def _date_label(value: object) -> str:
    parsed = _date_value(value)
    return parsed.isoformat() if parsed else "-"


def _updated_date(value: object, today: date) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return today


def _nonempty(value: object) -> bool:
    return bool(str(value or "").strip())


def _is_closed_solution(status: object) -> bool:
    return _enum_text(status) in {"complete", "abandoned"}


def _is_closed_task(status: object) -> bool:
    return _enum_text(status) in {"complete", "abandoned"}


def _days_until(today: date, due_date: object) -> int | None:
    parsed = _date_value(due_date)
    if not parsed:
        return None
    return (parsed - today).days


def _stale(record: dict[str, object], today: date) -> bool:
    if record.get("is_stale") is True:
        return True
    return (today - _updated_date(record.get("updated_at"), today)).days > STALE_STATUS_DAYS


def _score_color(score: int) -> tuple[int, int, int]:
    if score >= 70:
        return (190, 46, 77)
    if score >= 45:
        return (217, 119, 6)
    return (48, 138, 101)


def _health_color(score: int) -> tuple[int, int, int]:
    if score >= 85:
        return (48, 138, 101)
    if score >= 70:
        return (217, 119, 6)
    return (190, 46, 77)


def _draw_section_title(painter: _TopPdfPainter, x: float, y: float, width: float, title: str) -> float:
    painter.text(x, y, title, size=13, bold=True, color=(23, 35, 72))
    painter.line(x, y + 18, x + width, y + 18, stroke=(218, 224, 235), line_width=1)
    return y + 28


def _draw_table_header(
    painter: _TopPdfPainter,
    x: float,
    y: float,
    width: float,
    columns: list[tuple[str, float]],
) -> float:
    painter.rect(x, y, width, 22, fill=(230, 235, 245), stroke=(212, 219, 232))
    cursor_x = x
    for label, col_width in columns:
        painter.text(cursor_x + 7, y + 6, label, size=8.3, bold=True, color=(44, 55, 80))
        cursor_x += col_width
    return y + 22


def _draw_wrapped_cell(
    painter: _TopPdfPainter,
    x: float,
    y: float,
    lines: list[str],
    *,
    size: float = 8.2,
    bold: bool = False,
    color: tuple[int, int, int] = (44, 55, 80),
) -> None:
    for idx, line in enumerate(lines):
        painter.text(x, y + (idx * (size + 2.4)), line, size=size, bold=bold, color=color)


def _draw_empty(painter: _TopPdfPainter, x: float, y: float, width: float, text: str) -> float:
    painter.rect(x, y, width, 30, fill=(248, 250, 255), stroke=(220, 226, 237))
    painter.text(x + 8, y + 10, text, size=9, color=(104, 112, 133))
    return y + 40


def _due_delta_label(days: int) -> str:
    if days < 0:
        return f"{abs(days)}d overdue"
    if days == 0:
        return "Due today"
    return f"Due in {days}d"


def build_pm_command_report_pdf(
    *,
    space_name: str,
    projects: list[dict[str, object]],
    solutions: list[dict[str, object]],
    tasks: list[dict[str, object]],
    users: list[dict[str, object]],
    allocations: list[dict[str, object]],
    today: Optional[date] = None,
) -> bytes:
    today_value = today or datetime.now(timezone.utc).date()
    document = _SimplePdfDoc(width=842.0, height=595.0)
    painter = _TopPdfPainter(document)
    left = 28.0
    right = document.width - 28.0
    content_width = right - left
    bottom_limit = document.height - 38.0
    page_number = 0
    cursor_y = 0.0
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    project_ids = {str(project.get("project_id") or "").strip() for project in projects}
    project_ids.discard("")
    scoped_solutions = [
        row for row in solutions if str(row.get("project_id") or "").strip() in project_ids
    ]
    solution_ids = {str(row.get("solution_id") or "").strip() for row in scoped_solutions}
    solution_ids.discard("")
    scoped_tasks = [
        row
        for row in tasks
        if str(row.get("project_id") or "").strip() in project_ids
        and str(row.get("solution_id") or "").strip() in solution_ids
    ]
    task_ids = {str(row.get("task_id") or "").strip() for row in scoped_tasks}
    task_ids.discard("")
    active_solutions = [row for row in scoped_solutions if not _is_closed_solution(row.get("status"))]
    active_tasks = [row for row in scoped_tasks if not _is_closed_task(row.get("status"))]

    project_name_by_id = {
        str(row.get("project_id") or ""): _text(row.get("project_name"), "Unnamed Project")
        for row in projects
    }
    solution_name_by_id = {
        str(row.get("solution_id") or ""): _text(row.get("solution_name"), "Unnamed Workstream")
        for row in scoped_solutions
    }
    tasks_by_project: dict[str, list[dict[str, object]]] = {}
    tasks_by_solution: dict[str, list[dict[str, object]]] = {}
    for task in scoped_tasks:
        tasks_by_project.setdefault(str(task.get("project_id") or ""), []).append(task)
        tasks_by_solution.setdefault(str(task.get("solution_id") or ""), []).append(task)

    red_solutions = [row for row in active_solutions if _enum_text(row.get("rag_status")) == "red"]
    amber_solutions = [row for row in active_solutions if _enum_text(row.get("rag_status")) == "amber"]
    on_hold_solutions = [row for row in active_solutions if _enum_text(row.get("status")) == "on_hold"]
    overdue_solutions = [
        row for row in active_solutions if (days := _days_until(today_value, row.get("due_date"))) is not None and days < 0
    ]
    due_soon_solutions = [
        row for row in active_solutions if (days := _days_until(today_value, row.get("due_date"))) is not None and 0 <= days <= 14
    ]
    overdue_tasks = [
        row for row in active_tasks if (days := _days_until(today_value, row.get("due_date"))) is not None and days < 0
    ]
    due_soon_tasks = [
        row for row in active_tasks if (days := _days_until(today_value, row.get("due_date"))) is not None and 0 <= days <= 14
    ]
    blocked_tasks = [row for row in active_tasks if bool(row.get("blocked"))]
    unassigned_tasks = [
        row for row in active_tasks if not _nonempty(row.get("assignee")) and not _nonempty(row.get("assignee_user_soeid"))
    ]
    stale_solutions = [row for row in active_solutions if _stale(row, today_value)]
    stale_tasks = [row for row in active_tasks if _stale(row, today_value)]
    overdue_total = len(overdue_solutions) + len(overdue_tasks)
    due_soon_total = len(due_soon_solutions) + len(due_soon_tasks)
    stale_total = len(stale_solutions) + len(stale_tasks)

    project_summaries = []
    for project in projects:
        project_id = str(project.get("project_id") or "")
        project_solutions = [row for row in scoped_solutions if str(row.get("project_id") or "") == project_id]
        open_solutions = [row for row in project_solutions if not _is_closed_solution(row.get("status"))]
        project_tasks = tasks_by_project.get(project_id, [])
        open_tasks = [row for row in project_tasks if not _is_closed_task(row.get("status"))]
        red_count = sum(1 for row in open_solutions if _enum_text(row.get("rag_status")) == "red")
        amber_count = sum(1 for row in open_solutions if _enum_text(row.get("rag_status")) == "amber")
        on_hold_count = sum(1 for row in open_solutions if _enum_text(row.get("status")) == "on_hold")
        overdue_solution_count = sum(1 for row in open_solutions if (days := _days_until(today_value, row.get("due_date"))) is not None and days < 0)
        overdue_task_count = sum(1 for row in open_tasks if (days := _days_until(today_value, row.get("due_date"))) is not None and days < 0)
        blocked_count = sum(1 for row in open_tasks if bool(row.get("blocked")))
        unassigned_count = sum(1 for row in open_tasks if not _nonempty(row.get("assignee")) and not _nonempty(row.get("assignee_user_soeid")))
        stale_count = sum(1 for row in open_solutions if _stale(row, today_value)) + sum(1 for row in open_tasks if _stale(row, today_value))
        due_candidates = [
            parsed
            for parsed in [_date_value(row.get("due_date")) for row in [*open_solutions, *open_tasks]]
            if parsed is not None
        ]
        risk_score = min(
            100,
            red_count * 28
            + amber_count * 14
            + on_hold_count * 10
            + overdue_solution_count * 10
            + overdue_task_count * 5
            + stale_count * 4
            + blocked_count * 6
            + unassigned_count * 3,
        )
        project_summaries.append(
            {
                "project_name": _text(project.get("project_name"), "Unnamed Project"),
                "health": max(0, 100 - risk_score),
                "open_solutions": len(open_solutions),
                "open_tasks": len(open_tasks),
                "hotspots": [
                    *( [f"Red {red_count}"] if red_count else [] ),
                    *( [f"Amber {amber_count}"] if amber_count else [] ),
                    *( [f"Overdue {overdue_solution_count + overdue_task_count}"] if overdue_solution_count + overdue_task_count else [] ),
                    *( [f"Blocked {blocked_count}"] if blocked_count else [] ),
                    *( [f"Stale {stale_count}"] if stale_count else [] ),
                    *( [f"Unassigned {unassigned_count}"] if unassigned_count else [] ),
                ],
                "nearest_due": min(due_candidates).isoformat() if due_candidates else "-",
            }
        )
    project_summaries.sort(key=lambda row: (int(row["health"]), str(row["project_name"]).lower()))

    risk_rows = []
    for solution in active_solutions:
        linked_tasks = [row for row in tasks_by_solution.get(str(solution.get("solution_id") or ""), []) if not _is_closed_task(row.get("status"))]
        blocked_linked = sum(1 for row in linked_tasks if bool(row.get("blocked")))
        overdue_linked = sum(1 for row in linked_tasks if (days := _days_until(today_value, row.get("due_date"))) is not None and days < 0)
        risk_score = 0
        signals: list[str] = []
        rag = _enum_text(solution.get("rag_status"))
        status = _enum_text(solution.get("status"))
        due_days = _days_until(today_value, solution.get("due_date"))
        if rag == "red":
            risk_score += 50
            signals.append("RAG red")
        elif rag == "amber":
            risk_score += 24
            signals.append("RAG amber")
        if status == "on_hold":
            risk_score += 20
            signals.append("On hold")
        if due_days is not None and due_days < 0:
            risk_score += 20
            signals.append("Overdue")
        elif due_days is not None and due_days <= 14:
            risk_score += 10
            signals.append("Due <=14d")
        if _nonempty(solution.get("blockers")):
            risk_score += 16
            signals.append("Blockers")
        if _nonempty(solution.get("risks")):
            risk_score += 12
            signals.append("Risks noted")
        if _stale(solution, today_value):
            risk_score += 10
            signals.append("Status stale")
        if not _nonempty(solution.get("owner")) and not _nonempty(solution.get("owner_user_soeid")):
            risk_score += 8
            signals.append("No owner")
        if blocked_linked:
            risk_score += min(16, blocked_linked * 4)
            signals.append(f"Blocked deliverables {blocked_linked}")
        if overdue_linked:
            risk_score += min(16, overdue_linked * 4)
            signals.append(f"Overdue deliverables {overdue_linked}")
        risk_rows.append(
            {
                "workstream": _text(solution.get("solution_name"), "Unnamed Workstream"),
                "project": project_name_by_id.get(str(solution.get("project_id") or ""), "Unmapped Project"),
                "owner": _text(solution.get("owner") or solution.get("owner_user_soeid"), "Unassigned"),
                "due": _date_label(solution.get("due_date")),
                "score": min(100, risk_score),
                "signals": signals,
            }
        )
    risk_rows.sort(key=lambda row: (-int(row["score"]), str(row["workstream"]).lower()))

    timeline_rows = []
    for solution in active_solutions:
        days = _days_until(today_value, solution.get("due_date"))
        if days is None or days > 30:
            continue
        timeline_rows.append(
            {
                "type": "Solution",
                "item": _text(solution.get("solution_name"), "Unnamed Workstream"),
                "context": project_name_by_id.get(str(solution.get("project_id") or ""), "Unmapped Project"),
                "owner": _text(solution.get("owner") or solution.get("owner_user_soeid"), "Unassigned"),
                "due": _date_label(solution.get("due_date")),
                "days": days,
            }
        )
    for task in active_tasks:
        days = _days_until(today_value, task.get("due_date"))
        if days is None or days > 30:
            continue
        timeline_rows.append(
            {
                "type": "Task",
                "item": _text(task.get("task_name"), "Unnamed Deliverable"),
                "context": f"{project_name_by_id.get(str(task.get('project_id') or ''), 'Unmapped Project')} / {solution_name_by_id.get(str(task.get('solution_id') or ''), 'Unmapped Workstream')}",
                "owner": _text(task.get("assignee") or task.get("assignee_user_soeid"), "Unassigned"),
                "due": _date_label(task.get("due_date")),
                "days": days,
            }
        )
    timeline_rows.sort(key=lambda row: (int(row["days"]), str(row["context"]).lower()))

    capacity_by_key = {
        str(user.get("soeid") or "").strip(): max(float(user.get("capacity_fte_month") or 0.0), 0.0)
        for user in users
        if user.get("is_active") is not False and str(user.get("soeid") or "").strip()
    }
    user_label_by_key = {
        str(user.get("soeid") or "").strip(): _text(user.get("display_name") or user.get("soeid"), "Unassigned")
        for user in users
    }
    current_month = today_value.replace(day=1)
    allocated_by_key: dict[str, float] = {}
    for allocation in allocations:
        if _enum_text(allocation.get("work_item_type")) != "task":
            continue
        if str(allocation.get("work_item_id") or "").strip() not in task_ids:
            continue
        month = _date_value(allocation.get("month_start") or allocation.get("week_start"))
        if not month or month.replace(day=1) != current_month:
            continue
        key = str(allocation.get("assignee_user_soeid") or allocation.get("assignee") or "unassigned").strip() or "unassigned"
        fte = float(allocation.get("fte_months") or 0.0)
        if fte <= 0 and allocation.get("hours"):
            fte = float(allocation.get("hours") or 0.0) / 160.0
        allocated_by_key[key] = allocated_by_key.get(key, 0.0) + max(fte, 0.0)
    capacity_rows = []
    for key in sorted(set(capacity_by_key) | set(allocated_by_key)):
        capacity = capacity_by_key.get(key, 0.0)
        allocated = allocated_by_key.get(key, 0.0)
        utilization = (allocated / capacity * 100.0) if capacity > 0 else (999.0 if allocated > 0 else 0.0)
        capacity_rows.append(
            {
                "label": user_label_by_key.get(key, key if key != "unassigned" else "Unassigned"),
                "capacity": capacity,
                "allocated": allocated,
                "gap": capacity - allocated,
                "utilization": utilization,
            }
        )
    capacity_rows.sort(key=lambda row: (-float(row["utilization"]), -float(row["allocated"]), str(row["label"]).lower()))
    overloaded_rows = [row for row in capacity_rows if float(row["capacity"]) > 0 and float(row["allocated"]) > float(row["capacity"]) * 1.05]
    total_capacity = sum(float(row["capacity"]) for row in capacity_rows)
    total_allocated = sum(float(row["allocated"]) for row in capacity_rows)

    overdue_item_rows = [row for row in timeline_rows if int(row["days"]) < 0]

    watch_item_map: dict[str, dict[str, object]] = {}

    def add_watch_item(
        key: str,
        *,
        item_type: str,
        item: str,
        context: str,
        owner: str,
        due: str,
        reason: str,
        priority: int,
    ) -> None:
        if key in watch_item_map:
            existing = watch_item_map[key]
            existing["reason"] = f"{existing['reason']}; {reason}"
            existing["priority"] = max(int(existing["priority"]), priority)
            return
        watch_item_map[key] = {
            "type": item_type,
            "item": item,
            "context": context,
            "owner": owner,
            "due": due,
            "reason": reason,
            "priority": priority,
        }

    for row in risk_rows:
        if int(row["score"]) < 45:
            continue
        due_days = _days_until(today_value, row.get("due"))
        if due_days is not None and due_days < 0:
            continue
        add_watch_item(
            f"solution:{row['project']}:{row['workstream']}",
            item_type="Solution",
            item=str(row["workstream"]),
            context=str(row["project"]),
            owner=str(row["owner"]),
            due=str(row["due"]),
            reason=f"Risk {row['score']}: {', '.join(row['signals']) or 'elevated risk'}",
            priority=int(row["score"]),
        )

    for task in active_tasks:
        task_id = str(task.get("task_id") or "")
        project_name = project_name_by_id.get(str(task.get("project_id") or ""), "Unmapped Project")
        solution_name = solution_name_by_id.get(str(task.get("solution_id") or ""), "Unmapped Workstream")
        task_due_days = _days_until(today_value, task.get("due_date"))
        if task_due_days is not None and task_due_days < 0:
            continue
        reasons: list[str] = []
        priority = 0
        if bool(task.get("blocked")):
            reasons.append("Blocked")
            priority += 45
        if not _nonempty(task.get("assignee")) and not _nonempty(task.get("assignee_user_soeid")):
            reasons.append("No owner")
            priority += 30
        if _stale(task, today_value):
            reasons.append("Status stale")
            priority += 20
        if task_due_days is not None and 0 <= task_due_days <= 14:
            reasons.append(_due_delta_label(task_due_days))
            priority += 18
        if reasons:
            add_watch_item(
                f"task:{task_id or task.get('task_name')}",
                item_type="Task",
                item=_text(task.get("task_name"), "Unnamed Deliverable"),
                context=f"{project_name} / {solution_name}",
                owner=_text(task.get("assignee") or task.get("assignee_user_soeid"), "Unassigned"),
                due=_date_label(task.get("due_date")),
                reason=", ".join(reasons),
                priority=priority,
            )

    for row in overloaded_rows:
        add_watch_item(
            f"capacity:{row['label']}",
            item_type="Person",
            item=str(row["label"]),
            context="Current-month planning assignments",
            owner=str(row["label"]),
            due="-",
            reason=f"Capacity load {round(float(row['utilization']))}% ({float(row['allocated']):.2f}/{float(row['capacity']):.2f} FTE-mo)",
            priority=40 + int(float(row["utilization"]) // 10),
        )

    watch_item_rows = sorted(
        watch_item_map.values(),
        key=lambda row: (-int(row["priority"]), str(row["owner"]).lower(), str(row["item"]).lower()),
    )

    risk_units = (
        len(red_solutions) * 7
        + len(amber_solutions) * 4
        + len(on_hold_solutions) * 3
        + overdue_total * 2
        + len(blocked_tasks) * 2
        + len(unassigned_tasks)
        + stale_total
    )
    risk_denominator = max(len(active_solutions) * 7 + len(active_tasks) * 2, 1)
    portfolio_health = round(max(0, min(100, 100 - (risk_units / risk_denominator) * 100)))
    at_risk_workstreams = sum(1 for row in risk_rows if int(row["score"]) >= 45)

    actions = []
    if red_solutions:
        actions.append(("Critical", f"{len(red_solutions)} red workstreams need intervention", "Review health reasons and assign recovery owners."))
    if overdue_total:
        actions.append(("Critical", f"{overdue_total} overdue items require replan", "Rebaseline due dates or de-scope low-value work."))
    if blocked_tasks:
        actions.append(("Watch", f"{len(blocked_tasks)} blocked deliverables are stalling flow", "Clear blocker notes and escalate dependency owners."))
    if overloaded_rows:
        actions.append(("Watch", f"{len(overloaded_rows)} assignees are overloaded", "Reallocate work in the planning window."))
    if unassigned_tasks:
        actions.append(("Watch", f"{len(unassigned_tasks)} active deliverables are unassigned", "Assign owners so execution can start and status can move."))
    if stale_total:
        actions.append(("Watch", f"{stale_total} records need status refresh", f"Records have not changed in more than {STALE_STATUS_DAYS} days."))
    if not actions:
        actions.append(("Stable", "No critical blockers detected", "Track due-soon work and keep cadence."))

    def start_page() -> None:
        nonlocal page_number, cursor_y
        page_number += 1
        document.new_page()
        painter.rect(0, 0, document.width, document.height, fill=(245, 247, 252))
        painter.rect(0, 0, document.width, 76, fill=(21, 41, 86))
        painter.text(left, 18, "PM Command Center Report", size=20, bold=True, color=(255, 255, 255))
        painter.text(
            left,
            46,
            f"Space: {space_name}   As of: {today_value.isoformat()}   Generated: {generated_at}",
            size=9,
            color=(209, 220, 241),
        )
        painter.text(document.width - 88, 20, f"Page {page_number}", size=9, color=(209, 220, 241))
        painter.text(left, document.height - 18, "SIPM PM command snapshot", size=8, color=(129, 139, 158))
        cursor_y = 92.0

    def ensure_space(height: float) -> None:
        nonlocal cursor_y
        if cursor_y + height > bottom_limit:
            start_page()

    def draw_issue_rows(
        title: str,
        columns: list[tuple[str, float]],
        rows: list[dict[str, object]],
        row_builder,
        empty_text: str,
        *,
        max_rows: int,
    ) -> None:
        nonlocal cursor_y
        ensure_space(78)
        cursor_y = _draw_section_title(painter, left, cursor_y, content_width, title)
        if not rows:
            cursor_y = _draw_empty(painter, left, cursor_y, content_width, empty_text)
            return
        cursor_y = _draw_table_header(painter, left, cursor_y, content_width, columns)
        for idx, row in enumerate(rows[:max_rows]):
            cell_lines = row_builder(row)
            line_count = max(len(lines) for lines, *_ in cell_lines)
            row_h = max(28.0, 11.0 + line_count * 10.8)
            if cursor_y + row_h + 2 > bottom_limit:
                start_page()
                cursor_y = _draw_section_title(painter, left, cursor_y, content_width, f"{title} Continued")
                cursor_y = _draw_table_header(painter, left, cursor_y, content_width, columns)
            fill = (249, 251, 255) if idx % 2 == 0 else (244, 247, 252)
            painter.rect(left, cursor_y, content_width, row_h, fill=fill, stroke=(224, 230, 241))
            cursor_x = left
            for lines, col_width, color, bold in cell_lines:
                _draw_wrapped_cell(painter, cursor_x + 7, cursor_y + 8, lines, color=color, bold=bold)
                cursor_x += col_width
            cursor_y += row_h
        cursor_y += 12

    start_page()

    card_gap = 10.0
    card_width = (content_width - (card_gap * 4)) / 5.0
    cards = [
        ("Portfolio Health", str(portfolio_health), f"{at_risk_workstreams} workstreams at risk", _health_color(portfolio_health)),
        ("Open Workstreams", str(len(active_solutions)), f"{len(red_solutions)} red, {len(amber_solutions)} amber", (40, 111, 232)),
        ("Open Deliverables", str(len(active_tasks)), f"{len(blocked_tasks)} blocked, {len(unassigned_tasks)} unassigned", (99, 102, 241)),
        ("Schedule Pressure", str(overdue_total + due_soon_total), f"{overdue_total} overdue, {due_soon_total} due soon", (217, 119, 6) if overdue_total else (40, 111, 232)),
        ("Capacity Gap", f"{total_capacity - total_allocated:+.1f}", f"{total_allocated:.1f} of {total_capacity:.1f} FTE-mo", (190, 46, 77) if total_allocated > total_capacity else (48, 138, 101)),
    ]
    for idx, (title, value, subtitle, accent) in enumerate(cards):
        _draw_report_card(
            painter,
            x=left + idx * (card_width + card_gap),
            y=cursor_y,
            width=card_width,
            height=70,
            accent=accent,
            title=title,
            value=value,
            subtitle=subtitle,
        )
    cursor_y += 88

    cursor_y = _draw_section_title(painter, left, cursor_y, content_width, "Immediate Actions")
    for idx, (tone, title, detail) in enumerate(actions[:6]):
        row_h = 42.0
        ensure_space(row_h + 4)
        tone_color = (190, 46, 77) if tone == "Critical" else (217, 119, 6) if tone == "Watch" else (48, 138, 101)
        fill = (255, 255, 255) if idx % 2 == 0 else (249, 251, 255)
        painter.rect(left, cursor_y, content_width, row_h, fill=fill, stroke=(224, 230, 241))
        painter.rect(left, cursor_y, 5, row_h, fill=tone_color)
        painter.text(left + 14, cursor_y + 8, tone, size=8.2, bold=True, color=tone_color)
        painter.text(left + 86, cursor_y + 8, title, size=9.3, bold=True, color=(27, 38, 66))
        painter.text(left + 86, cursor_y + 24, detail, size=8.5, color=(96, 107, 129))
        cursor_y += row_h
    cursor_y += 12

    draw_issue_rows(
        "Overdue Items",
        [("Type", 70), ("Item", 260), ("Owner", 112), ("Due", 70), ("Why", content_width - 512)],
        overdue_item_rows,
        lambda row: [
            ([str(row["type"])], 70, (190, 46, 77), True),
            (_wrap_pdf_text(f"{row['item']} / {row['context']}", 244, 8.2, 3), 260, (27, 38, 66), True),
            (_wrap_pdf_text(str(row["owner"]), 96, 8.2, 2), 112, (44, 55, 80), False),
            ([str(row["due"])], 70, (44, 55, 80), False),
            ([_due_delta_label(int(row["days"]))], content_width - 512, (190, 46, 77), True),
        ],
        "No overdue items detected.",
        max_rows=18,
    )

    draw_issue_rows(
        "Watch Items",
        [("Type", 70), ("Item", 250), ("Owner", 112), ("Due/Status", 84), ("Why", content_width - 516)],
        watch_item_rows,
        lambda row: [
            ([str(row["type"])], 70, (217, 119, 6), True),
            (_wrap_pdf_text(f"{row['item']} / {row['context']}", 234, 8.2, 3), 250, (27, 38, 66), True),
            (_wrap_pdf_text(str(row["owner"]), 96, 8.2, 2), 112, (44, 55, 80), False),
            (_wrap_pdf_text(str(row["due"]), 68, 8.2, 2), 84, (44, 55, 80), False),
            (_wrap_pdf_text(str(row["reason"]), content_width - 532, 8.2, 3), content_width - 516, (44, 55, 80), False),
        ],
        "No watch items detected.",
        max_rows=18,
    )

    draw_issue_rows(
        "Projects Needing Attention",
        [("Project", 230), ("Health", 56), ("Open", 70), ("Next Due", 70), ("Hotspots", content_width - 426)],
        [row for row in project_summaries if int(row["health"]) < 100][:12],
        lambda row: [
            (_wrap_pdf_text(str(row["project_name"]), 214, 8.2, 2), 230, (27, 38, 66), True),
            ([str(row["health"])], 56, _health_color(int(row["health"])), True),
            ([f"{row['open_solutions']} ws / {row['open_tasks']} del"], 70, (44, 55, 80), False),
            ([str(row["nearest_due"])], 70, (44, 55, 80), False),
            (_wrap_pdf_text(", ".join(row["hotspots"]) or "None", content_width - 442, 8.2, 3), content_width - 426, (44, 55, 80), False),
        ],
        "No project-level issues detected.",
        max_rows=12,
    )

    draw_issue_rows(
        "Workstream Risk Radar",
        [("Workstream", 220), ("Risk", 50), ("Owner", 110), ("Due", 70), ("Signals", content_width - 450)],
        [row for row in risk_rows if int(row["score"]) > 0],
        lambda row: [
            (_wrap_pdf_text(f"{row['workstream']} / {row['project']}", 204, 8.2, 3), 220, (27, 38, 66), True),
            ([str(row["score"])], 50, _score_color(int(row["score"])), True),
            (_wrap_pdf_text(str(row["owner"]), 94, 8.2, 2), 110, (44, 55, 80), False),
            ([str(row["due"])], 70, (44, 55, 80), False),
            (_wrap_pdf_text(", ".join(row["signals"]) or "No strong signals", content_width - 466, 8.2, 3), content_width - 450, (44, 55, 80), False),
        ],
        "No elevated workstream risks detected.",
        max_rows=14,
    )

    draw_issue_rows(
        "Overdue And Upcoming Dates",
        [("Type", 78), ("Item", 260), ("Owner", 110), ("Due", 70), ("Urgency", content_width - 518)],
        timeline_rows,
        lambda row: [
            ([str(row["type"])], 78, (96, 107, 129), True),
            (_wrap_pdf_text(f"{row['item']} / {row['context']}", 244, 8.2, 3), 260, (27, 38, 66), True),
            (_wrap_pdf_text(str(row["owner"]), 94, 8.2, 2), 110, (44, 55, 80), False),
            ([str(row["due"])], 70, (44, 55, 80), False),
            ([_due_delta_label(int(row["days"]))], content_width - 518, (190, 46, 77) if int(row["days"]) < 0 else (217, 119, 6), True),
        ],
        "No overdue work or due dates in the next 30 days.",
        max_rows=16,
    )

    draw_issue_rows(
        "Capacity Watch",
        [("Assignee", 240), ("Capacity", 82), ("Allocated", 82), ("Gap", 82), ("Load", content_width - 486)],
        [row for row in capacity_rows if float(row["utilization"]) >= 85 or float(row["gap"]) < 0],
        lambda row: [
            (_wrap_pdf_text(str(row["label"]), 224, 8.2, 2), 240, (27, 38, 66), True),
            ([f"{float(row['capacity']):.2f}"], 82, (44, 55, 80), False),
            ([f"{float(row['allocated']):.2f}"], 82, (44, 55, 80), False),
            ([f"{float(row['gap']):+.2f}"], 82, (190, 46, 77) if float(row["gap"]) < 0 else (48, 138, 101), True),
            ([f"{round(float(row['utilization']))}%" if float(row["capacity"]) > 0 else "n/a"], content_width - 486, (190, 46, 77) if float(row["utilization"]) >= 100 else (217, 119, 6), True),
        ],
        "No capacity pressure detected for current-month planning deliverable assignments.",
        max_rows=12,
    )

    return document.build()


__all__ = ["build_pm_command_report_pdf"]
