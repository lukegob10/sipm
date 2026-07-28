from __future__ import annotations

from datetime import date, datetime, timezone
from io import BytesIO

import xlsxwriter

from .program_dashboard_report_pdf import (
    _phase_name,
    _phase_summary,
    _progress_for_solution,
    _status_is_closed,
    _status_label,
)


REPORT_COLUMNS = (
    ("deliverable", "Deliverable", 34),
    ("entity_type", "Entity Type", 14),
    ("function", "Function", 18),
    ("area", "Area", 22),
    ("description", "Description", 34),
    ("owner", "Owner", 20),
    ("stakeholder", "Stakeholder", 22),
    ("start", "Start", 12),
    ("end", "End", 12),
    ("status", "Status", 15),
    ("phase", "Phase", 20),
    ("escalation", "Escalation", 34),
    ("progress", "% Complete", 14),
)


def _excel_date(value: object) -> date | datetime | str:
    if isinstance(value, datetime):
        return value.replace(tzinfo=None)
    if isinstance(value, date):
        return value
    text = str(value or "").strip()
    if not text:
        return ""
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return text[:10]


def _text(value: object, fallback: str = "-") -> str:
    text = str(value or "").strip()
    return text or fallback


def _program_function_area(value: object) -> tuple[str, str]:
    text = str(value or "").strip()
    if not text:
        return "-", "-"
    hits = [
        (text.find(separator), separator)
        for separator in (" - ", " / ", " – ", " — ")
        if text.find(separator) >= 0
    ]
    if not hits:
        return "-", text
    index, separator = min(hits, key=lambda item: item[0])
    function = text[:index].strip() or "-"
    area = text[index + len(separator):].strip() or text
    return function, area


def build_program_dashboard_report_xlsx(
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
    """Build a formatted Excel report for every row under the selected programs."""
    del collapsed_program_ids, collapsed_project_ids
    output = BytesIO()
    workbook = xlsxwriter.Workbook(
        output,
        {
            "in_memory": True,
            "strings_to_formulas": False,
            "strings_to_urls": False,
        },
    )
    worksheet = workbook.add_worksheet("Program Dashboard")
    worksheet.hide_gridlines(2)
    worksheet.set_landscape()
    worksheet.fit_to_pages(1, 0)
    worksheet.set_margins(left=0.25, right=0.25, top=0.5, bottom=0.5)
    worksheet.set_header("&LProgram Dashboard Report&RPage &P of &N")
    worksheet.set_footer("&LSIPM program phasing snapshot&RGenerated &D &T")
    worksheet.outline_settings(symbols_below=False)

    navy = "#152956"
    blue = "#286FE8"
    green = "#308A65"
    purple = "#6366F1"
    slate = "#6B7280"
    light_border = "#DCE2ED"

    title_format = workbook.add_format({
        "bold": True, "font_color": "#FFFFFF", "font_size": 20,
        "bg_color": navy, "align": "left", "valign": "vcenter",
    })
    metadata_format = workbook.add_format({
        "font_color": "#D1DCF1", "font_size": 9, "bg_color": navy,
        "align": "left", "valign": "vcenter",
    })
    header_base = {
        "bold": True, "font_color": "#2C3750", "bg_color": "#E6EBF5",
        "border": 1, "border_color": "#D4DBE8", "valign": "vcenter",
    }
    header_format = workbook.add_format({**header_base, "align": "center"})
    header_left_format = workbook.add_format({**header_base, "align": "left"})
    card_label_format = workbook.add_format({
        "font_color": "#606B81", "font_size": 9, "bg_color": "#F8FAFF",
        "top": 1, "left": 1, "right": 1, "border_color": light_border, "align": "center",
    })
    card_value_formats = [
        workbook.add_format({
            "bold": True, "font_color": color, "font_size": 16, "bg_color": "#F8FAFF",
            "bottom": 1, "left": 1, "right": 1, "border_color": light_border, "align": "center",
        })
        for color in (blue, purple, "#16A34A", green, slate)
    ]
    row_formats: dict[str, dict[str, xlsxwriter.format.Format]] = {}
    for name, fill, bold, font_color in (
        ("program", "#ECF1FA", True, "#142348"),
        ("project", "#F9FBFF", True, "#1B2642"),
        ("solution", "#FFFFFF", False, "#2C3750"),
    ):
        common = {
            "bg_color": fill, "font_color": font_color, "bold": bold,
            "bottom": 1, "bottom_color": "#E0E6F1", "valign": "vcenter",
        }
        row_formats[name] = {
            "text": workbook.add_format({**common, "text_wrap": True, "align": "left"}),
            "center": workbook.add_format({**common, "text_wrap": True, "align": "center"}),
            "date": workbook.add_format({**common, "align": "center", "num_format": "yyyy-mm-dd"}),
            "progress": workbook.add_format({**common, "align": "center", "num_format": "0%"}),
        }

    projects_by_program: dict[str, list[dict[str, object]]] = {}
    for project in projects:
        projects_by_program.setdefault(str(project.get("program_id") or ""), []).append(project)
    solutions_by_project: dict[str, list[dict[str, object]]] = {}
    for solution in solutions:
        solutions_by_project.setdefault(str(solution.get("project_id") or ""), []).append(solution)
    phase_by_id = {str(phase.get("phase_id") or ""): phase for phase in phases}

    # Collapse state is a screen preference, not an export filter. Program
    # selection is the sole report scope; all descendant rows are included.
    report_project_ids = {
        str(project.get("project_id") or "")
        for program in programs
        for project in projects_by_program.get(str(program.get("program_id") or ""), [])
    }
    report_solutions = [
        solution
        for project_id in report_project_ids
        for solution in solutions_by_project.get(project_id, [])
    ]

    complete_count = sum(1 for row in report_solutions if str(row.get("status") or "").lower() == "complete")
    active_count = sum(
        1 for row in report_solutions if str(row.get("status") or "").lower() in {"active", "in_progress"}
    )
    not_started_count = sum(
        1 for row in report_solutions if str(row.get("status") or "").lower() in {"", "not_started", "to_do"}
    )

    last_col = len(REPORT_COLUMNS) - 1
    worksheet.merge_range(0, 0, 0, last_col, "Program Dashboard Report", title_format)
    worksheet.merge_range(
        1, 0, 1, last_col,
        f"Space: {space_name}   |   Programs: {selected_program_label}   |   Generated: {datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC}",
        metadata_format,
    )
    worksheet.set_row(0, 30)
    worksheet.set_row(1, 20)

    cards = (
        ("Projects", len(report_project_ids)),
        ("Solutions", len(report_solutions)),
        ("Active", active_count),
        ("Complete", complete_count),
        ("Not Started", not_started_count),
    )
    for idx, ((label, value), start_col) in enumerate(zip(cards, (0, 2, 4, 6, 8))):
        end_col = min(start_col + 1, last_col)
        if start_col == end_col:
            worksheet.write(3, start_col, label, card_label_format)
            worksheet.write(4, start_col, value, card_value_formats[idx])
        else:
            worksheet.merge_range(3, start_col, 3, end_col, label, card_label_format)
            worksheet.merge_range(4, start_col, 4, end_col, value, card_value_formats[idx])
    worksheet.set_row(3, 18)
    worksheet.set_row(4, 26)

    header_row = 6
    for col_idx, (_key, label, width) in enumerate(REPORT_COLUMNS):
        worksheet.write(header_row, col_idx, label, header_left_format if col_idx == 0 else header_format)
        worksheet.set_column(col_idx, col_idx, width)
    worksheet.set_row(header_row, 25)
    worksheet.freeze_panes(header_row + 1, 1)
    current_row = header_row + 1

    def write_report_row(kind: str, values: dict[str, object], *, level: int) -> None:
        nonlocal current_row
        formats = row_formats[kind]
        worksheet.set_row(current_row, 31 if kind == "solution" else 27, None, {"level": level})
        for col_idx, (key, _label, _width) in enumerate(REPORT_COLUMNS):
            value = values.get(key, "")
            if key in {"start", "end"} and isinstance(value, (date, datetime)):
                worksheet.write_datetime(current_row, col_idx, value, formats["date"])
            elif key == "progress":
                worksheet.write_number(current_row, col_idx, max(0, min(100, int(value or 0))) / 100, formats["progress"])
            else:
                is_text_column = key in {
                    "deliverable", "function", "area", "description", "owner", "stakeholder", "escalation"
                }
                text_format = formats["text"] if is_text_column and value != "-" else formats["center"]
                worksheet.write(current_row, col_idx, value, text_format)
        current_row += 1

    for program in programs:
        program_id = str(program.get("program_id") or "")
        program_function, program_area = _program_function_area(program.get("program_name"))
        program_projects = projects_by_program.get(program_id, [])
        program_solutions = [
            solution for project in program_projects
            for solution in solutions_by_project.get(str(project.get("project_id") or ""), [])
        ]
        program_progress = (
            round(sum(_progress_for_solution(row, phases) for row in program_solutions) / len(program_solutions))
            if program_solutions else 0
        )
        write_report_row("program", {
            "deliverable": _text(program.get("program_name"), "Unnamed Program"),
            "entity_type": "Program",
            "function": program_function, "area": program_area,
            "description": "-",
            "owner": "-", "stakeholder": "-", "start": "-", "end": "-", "status": "-",
            "phase": _phase_summary(program_solutions, phase_by_id), "escalation": "", "progress": program_progress,
        }, level=0)
        for project in program_projects:
            project_id = str(project.get("project_id") or "")
            project_solutions = solutions_by_project.get(project_id, [])
            project_progress = (
                round(sum(_progress_for_solution(row, phases) for row in project_solutions) / len(project_solutions))
                if project_solutions else (100 if str(project.get("status") or "").lower() == "complete" else 0)
            )
            write_report_row("project", {
                "deliverable": f"  {_text(project.get('project_name'), 'Unnamed Project')}",
                "entity_type": "Project",
                "function": program_function,
                "area": program_area,
                "description": _text(project.get("description")),
                "owner": _text(
                    project.get("owner")
                    or project.get("owner_user_soeid")
                    or project.get("sponsor")
                    or project.get("sponsor_user_soeid")
                ),
                "stakeholder": "-", "start": "-", "end": "-", "status": _status_label(project.get("status")),
                "phase": _phase_summary(project_solutions, phase_by_id) if project_solutions else (
                    "Complete" if _status_is_closed(project.get("status")) else "-"
                ),
                "escalation": "", "progress": project_progress,
            }, level=1)
            for solution in project_solutions:
                write_report_row("solution", {
                    "deliverable": f"    {_text(solution.get('solution_name'), 'Unnamed Solution')}",
                    "entity_type": "Solution",
                    "function": program_function,
                    "area": program_area,
                    "description": _text(solution.get("description")),
                    "owner": _text(
                        solution.get("owner")
                        or solution.get("owner_user_soeid")
                        or solution.get("assignee")
                        or solution.get("key_stakeholder")
                    ),
                    "stakeholder": _text(solution.get("key_stakeholder")),
                    "start": _excel_date(solution.get("planned_start_date")),
                    "end": _excel_date(solution.get("due_date")),
                    "status": _status_label(solution.get("status")),
                    "phase": _phase_name(solution.get("current_phase"), phase_by_id),
                    "escalation": _text(solution.get("escalation")),
                    "progress": _progress_for_solution(solution, phases),
                }, level=2)

    if current_row == header_row + 1:
        worksheet.merge_range(
            current_row, 0, current_row, last_col,
            "No selected programs are available in this space.", row_formats["solution"]["text"],
        )
        current_row += 1

    worksheet.autofilter(header_row, 0, max(header_row, current_row - 1), last_col)
    worksheet.repeat_rows(header_row)
    worksheet.print_area(0, 0, max(header_row, current_row - 1), last_col)
    worksheet.set_tab_color(blue)

    workbook.close()
    return output.getvalue()


__all__ = ["REPORT_COLUMNS", "build_program_dashboard_report_xlsx"]
