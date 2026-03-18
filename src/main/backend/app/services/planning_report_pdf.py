from datetime import datetime, timezone
from typing import Optional


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
        if parsed != parsed:
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


def build_work_allocation_report_pdf(
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


__all__ = ["build_work_allocation_report_pdf"]
