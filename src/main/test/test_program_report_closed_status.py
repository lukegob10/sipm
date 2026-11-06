from io import BytesIO
from zipfile import ZipFile

import pytest

from backend.app.services.program_dashboard_report_pdf import (
    _phase_summary, _project_phase_summary, build_program_dashboard_report_pdf,
)
from backend.app.services.program_dashboard_report_xlsx import build_program_dashboard_report_xlsx


@pytest.mark.parametrize(
    ("statuses", "expected"),
    [(["complete"], "Complete"), (["abandoned"], "Closed"), (["complete", "abandoned"], "Closed")],
)
def test_report_does_not_describe_abandoned_solutions_as_completed(statuses, expected):
    assert _phase_summary([{"status": status} for status in statuses], {}) == expected


@pytest.mark.parametrize(("status", "expected"), [("complete", "Complete"), ("abandoned", "Closed"), ("active", "-")])
def test_report_labels_closed_projects_without_solutions(status, expected):
    assert _project_phase_summary([], {"status": status}, {}) == expected


def test_pdf_and_spreadsheet_use_closed_label_for_abandoned_work():
    data = dict(
        space_name="Space", selected_program_label="Program",
        programs=[{"program_id": "program", "program_name": "Program"}],
        projects=[{"project_id": "project", "program_id": "program", "project_name": "Project"}],
        solutions=[{"solution_id": "solution", "project_id": "project", "solution_name": "Solution", "status": "abandoned"}],
        phases=[], collapsed_program_ids=set(), collapsed_project_ids=set(),
    )
    assert b"Closed" in build_program_dashboard_report_pdf(**data)
    with ZipFile(BytesIO(build_program_dashboard_report_xlsx(**data))) as workbook:
        assert b"Closed" in workbook.read("xl/sharedStrings.xml")
