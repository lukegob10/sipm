from __future__ import annotations

from datetime import datetime, timezone

from .pdf_utils import _SimplePdfDoc, _TopPdfPainter, _estimate_pdf_text_width, _wrap_pdf_text


TABLE_COLUMNS = (
    ("deliverable", "Deliverable", 0.0, 175.0),
    ("owner", "Owner", 175.0, 84.0),
    ("start", "Start", 259.0, 48.0),
    ("end", "End", 307.0, 48.0),
    ("status", "Status", 355.0, 60.0),
    ("phase", "Phase", 415.0, 110.0),
    ("escalation", "Escalation", 525.0, 185.0),
    ("progress", "Progress", 710.0, 88.0),
)


def _text(value: object, fallback: str = "-") -> str:
    text = str(value or "").strip()
    return text or fallback


def _date_text(value: object) -> str:
    text = str(value or "").strip()
    return text[:10] if len(text) >= 10 else "-"


def _status_label(value: object) -> str:
    text = str(getattr(value, "value", value) or "").strip()
    if not text:
        return "-"
    return text.replace("_", " ").title()


def _progress_for_solution(solution: dict[str, object], phases: list[dict[str, object]]) -> int:
    if str(solution.get("status") or "").lower() == "complete":
        return 100
    current_phase = str(solution.get("current_phase") or "")
    if not phases or not current_phase:
        return 0
    phase_ids = [str(phase.get("phase_id") or "") for phase in phases]
    try:
        index = phase_ids.index(current_phase)
    except ValueError:
        return 0
    return round((index / len(phases)) * 100)


def _phase_name(phase_id: object, phase_by_id: dict[str, dict[str, object]]) -> str:
    key = str(phase_id or "")
    if not key:
        return "-"
    phase = phase_by_id.get(key)
    name = str(phase.get("phase_name") if phase else key)
    if key == "poc" or name.lower() == "poc":
        return "Proof of Concept"
    return name


def _progress_color(progress: int) -> tuple[int, int, int]:
    if progress >= 90:
        return (48, 138, 101)
    if progress >= 50:
        return (40, 111, 232)
    if progress > 0:
        return (225, 146, 36)
    return (129, 139, 158)


def _status_color(status: object) -> tuple[int, int, int]:
    normalized = str(getattr(status, "value", status) or "").lower()
    if normalized == "complete":
        return (48, 138, 101)
    if normalized in {"active", "in_progress"}:
        return (40, 111, 232)
    if normalized in {"blocked", "abandoned"}:
        return (190, 46, 77)
    return (107, 114, 128)


def _status_is_closed(status: object) -> bool:
    return str(getattr(status, "value", status) or "").lower() in {"complete", "abandoned"}


def _phase_summary(solutions: list[dict[str, object]], phase_by_id: dict[str, dict[str, object]]) -> str:
    if not solutions:
        return "-"
    active_solutions = [row for row in solutions if not _status_is_closed(row.get("status"))]
    if not active_solutions:
        return "Complete"
    labels = []
    for solution in active_solutions:
        label = _phase_name(solution.get("current_phase"), phase_by_id)
        if label == "-" or label in labels:
            continue
        labels.append(label)
    if not labels:
        return "Unassigned"
    if len(labels) == 1:
        return labels[0]
    return f"{len(labels)} phases"


def _draw_card(
    painter: _TopPdfPainter,
    *,
    x: float,
    y: float,
    width: float,
    title: str,
    value: str,
    accent: tuple[int, int, int],
) -> None:
    painter.rect(x, y, width, 60, fill=(248, 250, 255), stroke=(218, 225, 236))
    painter.rect(x, y, 5, 60, fill=accent)
    painter.text(x + 13, y + 10, title, size=8.8, color=(96, 107, 129))
    painter.text(x + 13, y + 30, value, size=17, bold=True, color=(20, 35, 72))


def _draw_progress(
    painter: _TopPdfPainter,
    x: float,
    y: float,
    width: float,
    progress: int,
) -> None:
    pct = max(0, min(100, int(progress or 0)))
    painter.rect(x, y + 2, width, 9, fill=(224, 230, 241), stroke=(211, 219, 232))
    if pct:
        painter.rect(x, y + 2, width * (pct / 100.0), 9, fill=_progress_color(pct))
    painter.text(x + width + 8, y, f"{pct}%", size=8.8, bold=True, color=(44, 55, 80))


def _center_text(
    painter: _TopPdfPainter,
    *,
    x: float,
    y: float,
    width: float,
    value: str,
    size: float,
    bold: bool = False,
    color: tuple[int, int, int] = (44, 55, 80),
) -> None:
    text = str(value or "")
    text_width = min(_estimate_pdf_text_width(text, size), width)
    painter.text(x + max((width - text_width) / 2.0, 0.0), y, text, size=size, bold=bold, color=color)


def _center_wrapped_text(
    painter: _TopPdfPainter,
    *,
    x: float,
    y: float,
    width: float,
    value: str,
    size: float,
    max_lines: int = 2,
    bold: bool = False,
    color: tuple[int, int, int] = (44, 55, 80),
) -> None:
    for idx, line in enumerate(_wrap_pdf_text(value, max_width=max(width - 6, 12), font_size=size, max_lines=max_lines)):
        _center_text(
            painter,
            x=x,
            y=y + (idx * (size + 2)),
            width=width,
            value=line,
            size=size,
            bold=bold,
            color=color,
        )


def build_program_dashboard_report_pdf(
    *,
    space_name: str,
    selected_program_label: str,
    programs: list[dict[str, object]],
    projects: list[dict[str, object]],
    solutions: list[dict[str, object]],
    phases: list[dict[str, object]],
    collapsed_program_ids: set[str],
    collapsed_project_ids: set[str],
) -> bytes:
    document = _SimplePdfDoc(width=842.0, height=595.0)
    painter = _TopPdfPainter(document)
    left = 22.0
    right = left + sum(column[3] for column in TABLE_COLUMNS)
    content_width = right - left
    bottom_limit = document.height - 34.0
    page_number = 0
    cursor_y = 0.0
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    phase_by_id = {str(phase.get("phase_id") or ""): phase for phase in phases}

    projects_by_program: dict[str, list[dict[str, object]]] = {}
    for project in projects:
        projects_by_program.setdefault(str(project.get("program_id") or ""), []).append(project)
    solutions_by_project: dict[str, list[dict[str, object]]] = {}
    for solution in solutions:
        solutions_by_project.setdefault(str(solution.get("project_id") or ""), []).append(solution)

    def solution_progress(solution: dict[str, object]) -> int:
        return _progress_for_solution(solution, phases)

    def project_progress(project_solutions: list[dict[str, object]], project: dict[str, object]) -> int:
        if project_solutions:
            return round(sum(solution_progress(row) for row in project_solutions) / len(project_solutions))
        return 100 if str(project.get("status") or "").lower() == "complete" else 0

    visible_project_ids: set[str] = set()
    visible_solutions: list[dict[str, object]] = []
    for program in programs:
        program_id = str(program.get("program_id") or "")
        if program_id in collapsed_program_ids:
            continue
        for project in projects_by_program.get(program_id, []):
            project_id = str(project.get("project_id") or "")
            visible_project_ids.add(project_id)
            if project_id not in collapsed_project_ids:
                visible_solutions.extend(solutions_by_project.get(project_id, []))

    complete_count = sum(1 for row in visible_solutions if str(row.get("status") or "").lower() == "complete")
    active_count = sum(1 for row in visible_solutions if str(row.get("status") or "").lower() in {"active", "in_progress"})
    not_started_count = sum(
        1
        for row in visible_solutions
        if str(row.get("status") or "").lower() in {"", "not_started", "to_do"}
    )

    def start_page() -> None:
        nonlocal page_number, cursor_y
        page_number += 1
        document.new_page()
        painter.rect(0, 0, document.width, document.height, fill=(245, 247, 252))
        painter.rect(0, 0, document.width, 74, fill=(21, 41, 86))
        painter.text(left, 18, "Program Dashboard Report", size=20, bold=True, color=(255, 255, 255))
        painter.text(
            left,
            46,
            f"Space: {space_name}   Programs: {selected_program_label}   Generated: {generated_at}",
            size=9,
            color=(209, 220, 241),
        )
        painter.text(document.width - 88, 20, f"Page {page_number}", size=9, color=(209, 220, 241))
        painter.text(left, document.height - 18, "SIPM program phasing snapshot", size=8, color=(129, 139, 158))
        cursor_y = 92.0

    def ensure_space(height: float) -> None:
        nonlocal cursor_y
        if cursor_y + height > bottom_limit:
            start_page()
            draw_table_header()

    def draw_table_header() -> None:
        nonlocal cursor_y
        painter.rect(left, cursor_y, content_width, 24, fill=(230, 235, 245), stroke=(212, 219, 232))
        for key, label, x_offset, width in TABLE_COLUMNS:
            if key == "deliverable":
                painter.text(left + x_offset + 8, cursor_y + 7, label, size=8.5, bold=True, color=(44, 55, 80))
            else:
                _center_text(
                    painter,
                    x=left + x_offset,
                    y=cursor_y + 7,
                    width=width,
                    value=label,
                    size=8.5,
                    bold=True,
                    color=(44, 55, 80),
                )
        cursor_y += 24

    def draw_row(
        *,
        depth: int,
        title: str,
        owner: str,
        start: str,
        end: str,
        status: str,
        phase: str,
        escalation: str,
        progress: int,
        fill: tuple[int, int, int],
        bold: bool = False,
    ) -> None:
        nonlocal cursor_y
        deliverable_x = left + TABLE_COLUMNS[0][2]
        deliverable_w = TABLE_COLUMNS[0][3]
        wrapped_title = _wrap_pdf_text(title, max_width=deliverable_w - 22 - ((depth - 1) * 18), font_size=8.8, max_lines=2)
        owner_lines = _wrap_pdf_text(owner, max_width=TABLE_COLUMNS[1][3] - 6, font_size=8.0, max_lines=2)
        phase_lines = _wrap_pdf_text(phase, max_width=TABLE_COLUMNS[5][3] - 6, font_size=7.6, max_lines=3)
        escalation_text = str(escalation or "").strip()
        escalation_lines = _wrap_pdf_text(escalation_text, max_width=TABLE_COLUMNS[6][3] - 8, font_size=7.6)
        line_count = max(len(wrapped_title), len(owner_lines), len(phase_lines), len(escalation_lines))
        row_h = max(30.0, 12.0 + (line_count * 11.0))
        ensure_space(row_h)
        painter.rect(left, cursor_y, content_width, row_h, fill=fill, stroke=(224, 230, 241))
        marker_color = [(20, 35, 72), (40, 111, 232), (48, 138, 101)][max(0, min(2, depth - 1))]
        title_x = deliverable_x + 8 + ((depth - 1) * 18)
        painter.rect(title_x, cursor_y + 9, 6, row_h - 18, fill=marker_color)
        line_y = cursor_y + 8
        for line in wrapped_title:
            painter.text(title_x + 12, line_y, line, size=8.8, bold=bold, color=(27, 38, 66))
            line_y += 11
        _center_wrapped_text(
            painter,
            x=left + TABLE_COLUMNS[1][2],
            y=cursor_y + 8,
            width=TABLE_COLUMNS[1][3],
            value=owner,
            size=8.0,
        )
        _center_text(painter, x=left + TABLE_COLUMNS[2][2], y=cursor_y + 10, width=TABLE_COLUMNS[2][3], value=start, size=8.0)
        _center_text(painter, x=left + TABLE_COLUMNS[3][2], y=cursor_y + 10, width=TABLE_COLUMNS[3][3], value=end, size=8.0)
        _center_text(
            painter,
            x=left + TABLE_COLUMNS[4][2],
            y=cursor_y + 10,
            width=TABLE_COLUMNS[4][3],
            value=status,
            size=8.0,
            bold=True,
            color=_status_color(status),
        )
        _center_wrapped_text(
            painter,
            x=left + TABLE_COLUMNS[5][2],
            y=cursor_y + 8,
            width=TABLE_COLUMNS[5][3],
            value=phase,
            size=7.6,
            max_lines=3,
        )
        if escalation_text == "-":
            _center_text(
                painter,
                x=left + TABLE_COLUMNS[6][2],
                y=cursor_y + 10,
                width=TABLE_COLUMNS[6][3],
                value="-",
                size=8.0,
            )
        elif escalation_text:
            escalation_y = cursor_y + 8
            for idx, line in enumerate(escalation_lines):
                _center_text(
                    painter,
                    x=left + TABLE_COLUMNS[6][2],
                    y=escalation_y + (idx * 10.2),
                    width=TABLE_COLUMNS[6][3],
                    value=line,
                    size=7.6,
                    color=(44, 55, 80),
                )
        progress_col_x = left + TABLE_COLUMNS[7][2]
        progress_col_w = TABLE_COLUMNS[7][3]
        progress_pct = max(0, min(100, int(progress or 0)))
        percent_text = f"{progress_pct}%"
        percent_w = _estimate_pdf_text_width(percent_text, 8.0)
        gap = 4.0
        bar_w = min(44.0, max(28.0, progress_col_w - gap - percent_w - 4.0))
        total_progress_w = bar_w + gap + percent_w
        progress_x = progress_col_x + max((progress_col_w - total_progress_w) / 2.0, 0.0)
        painter.rect(progress_x, cursor_y + 11, bar_w, 8, fill=(224, 230, 241), stroke=(211, 219, 232))
        if progress_pct:
            painter.rect(progress_x, cursor_y + 11, bar_w * (progress_pct / 100.0), 8, fill=_progress_color(progress_pct))
        painter.text(progress_x + bar_w + gap, cursor_y + 8, percent_text, size=8.0, bold=True, color=(44, 55, 80))
        cursor_y += row_h

    start_page()

    card_gap = 10.0
    card_width = (content_width - (card_gap * 4)) / 5
    cards = [
        ("Visible Projects", str(len(visible_project_ids)), (40, 111, 232)),
        ("Visible Solutions", str(len(visible_solutions)), (99, 102, 241)),
        ("Active", str(active_count), (22, 163, 74)),
        ("Complete", str(complete_count), (48, 138, 101)),
        ("Not Started", str(not_started_count), (107, 114, 128)),
    ]
    for idx, (title, value, accent) in enumerate(cards):
        _draw_card(
            painter,
            x=left + (idx * (card_width + card_gap)),
            y=cursor_y,
            width=card_width,
            title=title,
            value=value,
            accent=accent,
        )
    cursor_y += 78
    draw_table_header()

    if not programs:
        painter.rect(left, cursor_y, content_width, 34, fill=(248, 250, 255), stroke=(220, 226, 237))
        painter.text(left + 8, cursor_y + 12, "No selected programs are available in this space.", size=9, color=(104, 112, 133))
        return document.build()

    for program in programs:
        program_id = str(program.get("program_id") or "")
        program_projects = projects_by_program.get(program_id, [])
        program_solutions = [
            solution
            for project in program_projects
            for solution in solutions_by_project.get(str(project.get("project_id") or ""), [])
        ]
        progress = round(sum(solution_progress(row) for row in program_solutions) / len(program_solutions)) if program_solutions else 0
        draw_row(
            depth=1,
            title=_text(program.get("program_name"), "Unnamed Program"),
            owner="-",
            start="-",
            end="-",
            status="-",
            phase=_phase_summary(program_solutions, phase_by_id),
            escalation="",
            progress=progress,
            fill=(236, 241, 250),
            bold=True,
        )
        if program_id in collapsed_program_ids:
            continue
        for project in program_projects:
            project_id = str(project.get("project_id") or "")
            project_solutions = solutions_by_project.get(project_id, [])
            draw_row(
                depth=2,
                title=_text(project.get("project_name"), "Unnamed Project"),
                owner=_text(project.get("sponsor") or project.get("sponsor_user_soeid")),
                start="-",
                end="-",
                status=_status_label(project.get("status")),
                phase=_phase_summary(project_solutions, phase_by_id) if project_solutions else (
                    "Complete" if _status_is_closed(project.get("status")) else "-"
                ),
                escalation="",
                progress=project_progress(project_solutions, project),
                fill=(249, 251, 255),
                bold=True,
            )
            if project_id in collapsed_project_ids:
                continue
            for solution in project_solutions:
                draw_row(
                    depth=3,
                    title=_text(solution.get("solution_name"), "Unnamed Solution"),
                    owner=_text(solution.get("owner") or solution.get("owner_user_soeid") or solution.get("assignee") or solution.get("key_stakeholder")),
                    start=_date_text(solution.get("planned_start_date")),
                    end=_date_text(solution.get("due_date")),
                    status=_status_label(solution.get("status")),
                    phase=_phase_name(solution.get("current_phase"), phase_by_id),
                    escalation=_text(solution.get("escalation")),
                    progress=solution_progress(solution),
                    fill=(255, 255, 255),
                )

    return document.build()


__all__ = ["build_program_dashboard_report_pdf"]
