from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
PLANNING_ROUTE = REPO_ROOT / "src" / "main" / "ui" / "js" / "routes" / "planning.js"
STYLES_CSS = REPO_ROOT / "src" / "main" / "ui" / "styles.css"


def test_planning_header_uses_compact_toggle_panels_instead_of_always_open_stacks():
    text = PLANNING_ROUTE.read_text(encoding="utf-8")

    assert 'topPanel: ""' in text
    assert 'data-wab-action="toggle-filters"' in text
    assert 'data-wab-action="toggle-create"' in text
    assert 'data-wab-action="toggle-guide"' in text
    assert 'data-wab-action="toggle-tools"' in text
    assert 'data-wab-action="reset-filters"' in text
    assert "wab-toolbar-main" in text
    assert "wab-toolbar-meta" in text
    assert "wab-toolbar-panel" in text
    assert "wab-selected-pill" in text
    assert "wab-selection-summary" not in text
    assert "wab-summary-strip" not in text
    assert "wab-legend" not in text


def test_planning_styles_define_compact_toolbar_and_disclosure_panel_layout():
    text = STYLES_CSS.read_text(encoding="utf-8")

    snippets = [
        ".wab-toolbar-main {",
        ".wab-toolbar-actions {",
        ".wab-toolbar-toggle {",
        ".wab-toolbar-toggle-count {",
        ".wab-toolbar-panel {",
        ".wab-toolbar-create-grid {",
        ".wab-toolbar-guide-grid {",
        ".wab-toolbar-tools-grid {",
        ".wab-toolbar-meta {",
        ".wab-stat-chip,",
        ".wab-selected-pill {",
    ]
    for snippet in snippets:
        assert snippet in text
