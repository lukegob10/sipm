import pytest

from backend.app.services.planning_report_pdf import build_work_allocation_report_pdf


def test_build_work_allocation_report_pdf_returns_pdf_bytes_for_empty_inputs():
    pdf_bytes = build_work_allocation_report_pdf(
        month_token="2026-02",
        space_name="Planning Space",
        teams=[],
        people=[],
        tasks=[],
        allocations=[],
    )

    assert pdf_bytes.startswith(b"%PDF-")
    assert b"Planning Report: Work Allocation Board" in pdf_bytes


@pytest.mark.anyio
async def test_work_allocation_report_download_returns_pdf(client):
    response = await client.get(
        "/project-manager/api/planning/work-allocation/report.pdf?month=2026-02"
    )
    assert response.status_code == 200, response.text
    assert response.headers.get("content-type", "").startswith("application/pdf")
    assert "attachment; filename=" in response.headers.get("content-disposition", "")
    assert response.content.startswith(b"%PDF-")
