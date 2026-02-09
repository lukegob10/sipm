from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
APP_JS = REPO_ROOT / "src" / "main" / "ui" / "js" / "app.js"
CALENDAR_ROUTE = REPO_ROOT / "src" / "main" / "ui" / "js" / "routes" / "calendar.js"


def test_calendar_view_passes_solution_and_subcomponent_filters_to_route_module():
    text = APP_JS.read_text(encoding="utf-8")
    assert "filteredSolutionsForCalendar," in text
    assert "filteredSubcomponentsForCalendar," in text
    assert "mod.openCalendarModal(day, {" in text


def test_calendar_route_renders_solution_and_subcomponent_sections():
    text = CALENDAR_ROUTE.read_text(encoding="utf-8")
    assert "Solutions" in text
    assert "Subcomponents" in text
    assert "calendar-stream-label" in text
    assert "modal-section-title" in text
