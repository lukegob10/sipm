import pytest


@pytest.mark.anyio
async def test_work_allocation_report_download_returns_pdf(client):
    response = await client.get("/project-manager/api/planning/work-allocation/report.pdf?month=2026-02")
    assert response.status_code == 200, response.text
    assert response.headers.get("content-type", "").startswith("application/pdf")
    assert "attachment; filename=" in response.headers.get("content-disposition", "")
    assert response.content.startswith(b"%PDF-")
