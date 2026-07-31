from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
MY_WORK_ROUTE = REPO_ROOT / "src" / "main" / "ui" / "js" / "routes" / "my-work.js"
MY_WORK_STYLES = REPO_ROOT / "src" / "main" / "ui" / "styles" / "routes" / "my-work.css"
INDEX_HTML = REPO_ROOT / "src" / "main" / "ui" / "index.html"


def _rule_body(styles: str, selector: str) -> str:
    start = styles.index(f"{selector} {{")
    body_start = styles.index("{", start) + 1
    return styles[body_start : styles.index("}", body_start)]


def test_my_work_uses_two_full_height_independently_scrollable_lanes():
    route = MY_WORK_ROUTE.read_text(encoding="utf-8")
    styles = MY_WORK_STYLES.read_text(encoding="utf-8")

    assert 'const LANE_ORDER = ["today", "later"]' in route
    assert "SECTION_ORDER" not in route
    assert "grid-template-columns: repeat(2, minmax(0, 1fr))" in _rule_body(
        styles,
        ".my-work-lanes",
    )
    assert "grid-template-rows: auto minmax(0, 1fr)" in _rule_body(
        styles,
        ".my-work-lane",
    )
    card_list_rule = _rule_body(styles, ".my-work-card-list")
    assert "min-height: 0" in card_list_rule
    assert "overflow-y: auto" in card_list_rule


def test_my_work_keeps_private_notes_in_a_task_attached_workspace():
    route = MY_WORK_ROUTE.read_text(encoding="utf-8")
    styles = MY_WORK_STYLES.read_text(encoding="utf-8")
    html = INDEX_HTML.read_text(encoding="utf-8")

    assert "They stay attached to this task." in route
    assert 'data-my-work-detail-tab="notes"' in route
    assert 'name="bucket"' not in route
    assert "min-height: 260px" in _rule_body(styles, ".my-work-notes-panel textarea")
    assert "Stage assigned tasks for today or later" in html


def test_my_work_plan_can_collapse_and_resize_without_changing_task_data():
    route = MY_WORK_ROUTE.read_text(encoding="utf-8")
    styles = MY_WORK_STYLES.read_text(encoding="utf-8")

    assert 'data-my-work-plan-toggle' in route
    assert 'role="separator"' in route
    assert 'aria-orientation="vertical"' in route
    assert 'data-my-work-plan-size="smaller"' in route
    assert 'data-my-work-plan-size="larger"' in route
    assert "--my-work-plan-width" in _rule_body(styles, ".my-work-layout")
    assert "grid-template-columns: 56px minmax(0, 1fr)" in _rule_body(
        styles,
        ".my-work-layout.is-plan-collapsed",
    )
