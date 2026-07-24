from pathlib import Path

from ui_style_contract import read_ui_styles


REPO_ROOT = Path(__file__).resolve().parents[3]
STYLES_CSS = REPO_ROOT / "src" / "main" / "ui" / "styles.css"
INDEX_HTML = REPO_ROOT / "src" / "main" / "ui" / "index.html"


def test_dark_mode_tokens_exist_and_light_theme_values_remain_pinned():
    text = read_ui_styles(STYLES_CSS)

    dark_snippets = [
        "--surface-0: #0b1118;",
        "--surface-1: #111923;",
        "--surface-2: #182332;",
        "--surface-3: #223044;",
        "--surface-elevated: #2b3a4d;",
        "--text-strong: #f4f8fc;",
        "--text: #dce6f1;",
        "--text-subtle: #9dafc2;",
        "--accent-strong: #5f9fe0;",
        "--accent-2: #9fc7f2;",
        "--border-soft: rgba(156, 174, 197, 0.22);",
        "--border-strong: rgba(156, 174, 197, 0.38);",
        "--app-shell-bg: var(--surface-0);",
        "--surface-raised: var(--surface-2);",
        "--surface-sunken: #0d151e;",
        "--data-canvas: #101821;",
        "--section-header-bg: linear-gradient(180deg, #314053, #263548);",
        "--table-row-bg: #111a24;",
        "--table-row-alt-bg: #172231;",
        "--table-header-bg: linear-gradient(180deg, #44566e, #33445a);",
        "--field-bg: #0f1721;",
    ]
    for snippet in dark_snippets:
        assert snippet in text

    light_snippets = [
        ".theme-light {",
        "--base: #f5f6f8;",
        "--panel: #ffffff;",
        "--panel-soft: #eef1f4;",
        "--text: #1b1e23;",
        "--muted: #5f6a75;",
        "--accent-strong: #003a72;",
        "--field-bg: #ffffff;",
        "--button-primary-border-width: 0px;",
        "--shadow: 0 10px 24px rgba(16, 42, 67, 0.08);",
    ]
    for snippet in light_snippets:
        assert snippet in text


def test_dark_mode_component_families_use_shared_tokens_without_legacy_dark_hacks():
    text = read_ui_styles(STYLES_CSS)
    assert "body:not(.theme-light)" not in text

    shared_token_snippets = [
        ".nav-btn.active {",
        "background: var(--nav-active-bg);",
        ".modal-backdrop {",
        "background: var(--modal-scrim);",
        ".modal-tabs .tab.active {",
        "background: var(--tab-active-bg);",
        ".auth-tab.active {",
        "box-shadow: inset 3px 0 0 var(--nav-active-inset), var(--tab-active-shadow);",
        ".space-hero-card {",
        "background: var(--hero-surface);",
        ".space-inline-callout {",
        "background: var(--callout-bg);",
        "#view-master #master-table {",
        "background: var(--data-canvas);",
        ".dashboard-table-shell {",
        "background: var(--data-canvas);",
        ".pm-table-wrap {",
        "background: var(--data-canvas);",
        ".task-workbench-main {",
        "background: var(--surface-sunken);",
        ".kanban {",
        "background: var(--data-canvas);",
        ".modal-content {",
        "background: var(--surface-raised);",
    ]
    for snippet in shared_token_snippets:
        assert snippet in text


def test_additional_dark_schemes_use_the_shared_token_system_and_appear_in_preferences():
    text = read_ui_styles(STYLES_CSS)
    html = INDEX_HTML.read_text(encoding="utf-8")

    for snippet in [
        ".theme-midnight {",
        "--surface-0: #070812;",
        "--accent-strong: #a9b6ff;",
        "--button-primary-bg: #596ab8;",
        ".theme-forest {",
        "--surface-0: #07110e;",
        "--accent-strong: #8fd8b2;",
        "--button-primary-bg: #2f7655;",
    ]:
        assert snippet in text

    assert '<option value="midnight">Midnight</option>' in html
    assert '<option value="forest">Forest</option>' in html
    assert 'id="theme-preview"' in html

def test_light_mode_fidelity_overrides_exist_for_components_with_exact_preserved_look():
    text = read_ui_styles(STYLES_CSS)

    fidelity_snippets = [
        ".theme-light .pill.positive {",
        ".theme-light .pill.warn {",
        ".theme-light .pill.danger {",
        ".theme-light .kanban-project {",
        ".theme-light .kanban-solution {",
        ".theme-light .capacity-badge.ok {",
        ".theme-light .capacity-badge.warn {",
        ".theme-light .capacity-badge.over {",
        ".theme-light .space-directory-row.is-selected td {",
        ".theme-light .space-directory-overview {",
        ".theme-light .space-directory-preview {",
        ".theme-light .auth-tab.active {",
    ]
    for snippet in fidelity_snippets:
        assert snippet in text
