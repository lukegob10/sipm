from pathlib import Path

from ui_style_contract import read_ui_styles


REPO_ROOT = Path(__file__).resolve().parents[3]
STYLES_CSS = REPO_ROOT / "src" / "main" / "ui" / "styles.css"
INDEX_HTML = REPO_ROOT / "src" / "main" / "ui" / "index.html"

LISTED_VIEW_IDS = (
    "view-master",
    "view-tasks-workbench",
    "view-pm-dashboard",
    "view-dashboard",
    "view-program-dashboard",
    "view-kanban",
    "view-calendar",
    "view-gantt",
)


def test_view_titles_use_shared_heading_tokens():
    text = read_ui_styles(STYLES_CSS)
    assert "--view-title-font-size:" in text
    assert "--view-title-mobile-size:" in text
    assert ".panel-header h2 {" in text
    assert "font-size: var(--view-title-font-size);" in text
    assert "line-height: var(--view-title-line-height);" in text
    assert "letter-spacing: var(--view-title-letter-spacing);" in text
    assert "font-weight: var(--view-title-weight);" in text


def test_mobile_view_titles_use_one_shared_size():
    text = read_ui_styles(STYLES_CSS)
    assert "@media (max-width: 1024px)" in text
    assert "font-size: var(--view-title-mobile-size);" in text


def test_insight_view_breadcrumbs_are_not_hidden():
    text = read_ui_styles(STYLES_CSS)
    assert "#view-dashboard .view-breadcrumb" not in text
    assert "#view-pm-dashboard .view-breadcrumb" not in text


def test_listed_views_share_standard_heading_markup():
    html = INDEX_HTML.read_text(encoding="utf-8")

    for view_id in LISTED_VIEW_IDS:
        view_start = html.index(f'id="{view_id}"')
        next_view = html.find('<section id="view-', view_start + 1)
        view_html = html[view_start: next_view if next_view != -1 else len(html)]
        assert 'class="panel-header"' in view_html
        assert 'class="view-heading"' in view_html
        assert 'class="view-breadcrumb"' in view_html
        assert '<h1 class="route-title">' in view_html


def test_task_style_route_tokens_are_defined():
    text = read_ui_styles(STYLES_CSS)
    for token in (
        "--route-panel-padding:",
        "--route-header-gap:",
        "--route-surface-radius:",
        "--route-card-radius:",
        "--route-table-header-height:",
        "--route-table-row-height:",
        "--route-table-header-font-size:",
        "--route-table-header-font-weight:",
        "--route-table-header-letter-spacing:",
        "--route-table-body-font-size:",
        "--route-table-body-font-weight:",
        "--route-table-body-letter-spacing:",
        "--route-control-height:",
        "--route-compact-control-height:",
        "--route-control-font-weight:",
        "--route-chip-font-size:",
        "--route-chip-font-weight:",
        "--route-chip-letter-spacing:",
        "--route-label-letter-spacing:",
    ):
        assert token in text


def test_main_work_views_use_shared_table_language():
    text = read_ui_styles(STYLES_CSS)

    for selector in (
        "#view-master #master-table .deliverables-table th {",
        "#view-tasks-workbench .task-workbench-table thead th {",
        ".dashboard-main-table thead th,",
        ".pm-table-wrap thead th {",
        ".program-dashboard-grid-header .program-dashboard-grid-cell {",
    ):
        start = text.index(selector)
        block = text[start:text.index("}", start)]
        assert "var(--route-table-header-font-size)" in block
        assert "var(--route-table-header-font-weight)" in block
        assert "var(--route-table-header-letter-spacing)" in block

    for selector in (
        "#view-master #master-table .deliverables-table th,",
        "#view-tasks-workbench .task-workbench-table th,",
        ".dashboard-main-table th,",
        ".pm-table-wrap td,",
        ".program-dashboard-grid-cell {",
    ):
        start = text.index(selector)
        block = text[start:text.index("}", start)]
        assert "var(--route-table-body-font-size)" in block


def test_route_styles_do_not_reintroduce_removed_typography_drift():
    text = read_ui_styles(STYLES_CSS)

    assert "letter-spacing: 0.005em;" not in text
    assert "color: transparent;" not in text
    assert "background: #f5f7fa;" not in text
    assert "background: #1f2933;" not in text
    assert "border-color: #111827;" not in text
    assert "color: #f8fafc;" not in text
