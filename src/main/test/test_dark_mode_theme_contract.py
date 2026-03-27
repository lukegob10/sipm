from pathlib import Path

from ui_style_contract import read_ui_styles


REPO_ROOT = Path(__file__).resolve().parents[3]
STYLES_CSS = REPO_ROOT / "src" / "main" / "ui" / "styles.css"


def test_dark_mode_tokens_exist_and_light_theme_values_remain_pinned():
    text = read_ui_styles(STYLES_CSS)

    dark_snippets = [
        "--surface-0: #0f141b;",
        "--surface-elevated: #314050;",
        "--focus-ring: rgba(150, 197, 255, 0.52);",
        "--success-soft: rgba(73, 163, 106, 0.18);",
        "--warning-soft: rgba(216, 162, 75, 0.18);",
        "--danger-soft: rgba(210, 103, 95, 0.18);",
        "--hero-surface: linear-gradient(180deg, rgba(79, 127, 196, 0.14), rgba(255, 255, 255, 0.02));",
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
        "--button-primary-border-width: 0px;",
        "--shadow: 0 10px 24px rgba(16, 42, 67, 0.08);",
    ]
    for snippet in light_snippets:
        assert snippet in text


def test_dark_mode_component_families_use_shared_tokens_without_legacy_dark_hacks():
    text = read_ui_styles(STYLES_CSS)
    compact = "".join(text.split())

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
    ]
    for snippet in shared_token_snippets:
        assert snippet in text

    for snippet in [
        ".wab-task-chip.is-selected{",
        "background:var(--backlog-bg-strong);",
    ]:
        assert snippet in compact


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
        ".theme-light .space-directory-card.is-selected {",
        ".theme-light .space-directory-overview {",
        ".theme-light .space-directory-preview {",
        ".theme-light .auth-tab.active {",
    ]
    for snippet in fidelity_snippets:
        assert snippet in text
