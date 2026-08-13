from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
APP_JS = REPO_ROOT / "src" / "main" / "ui" / "js" / "app.js"
LIVE_SYNC_JS = REPO_ROOT / "src" / "main" / "ui" / "js" / "shell" / "live-sync.js"
INDEX_HTML = REPO_ROOT / "src" / "main" / "ui" / "index.html"


def test_live_sync_controller_uses_explicit_close_codes_and_space_query_param():
    text = LIVE_SYNC_JS.read_text(encoding="utf-8")

    assert 'export const LIVE_SYNC_CLOSE_AUTH = 4401;' in text
    assert 'export const LIVE_SYNC_CLOSE_SPACE = 4403;' in text
    assert 'export const LIVE_SYNC_CLOSE_LIMIT = 4408;' in text
    assert 'export const LIVE_SYNC_CLOSE_BUSY = 1013;' in text
    assert 'url.searchParams.set("space_id", state.activeSpace.space_id);' in text
    assert "function startLiveSync(options = {})" in text
    assert "liveSyncStarted" not in text


def test_live_sync_controller_stops_on_terminal_failures_and_pauses_hidden_tabs():
    text = LIVE_SYNC_JS.read_text(encoding="utf-8")
    app_text = APP_JS.read_text(encoding="utf-8")

    assert "handleSessionExpired" in text
    assert "return sessionController.handleSessionExpired();" in app_text
    assert "async function recoverLiveSyncAuth()" in text
    assert "async function recoverLiveSyncSpace()" in text
    assert 'if (event.code === LIVE_SYNC_CLOSE_AUTH)' in text
    assert 'if (event.code === LIVE_SYNC_CLOSE_SPACE)' in text
    assert 'if (event.code === LIVE_SYNC_CLOSE_LIMIT)' in text
    assert 'document.addEventListener("visibilitychange", handleLiveSyncVisibilityChange);' in app_text
    assert "state.liveSync.pausedForHidden" in text


def test_shell_keeps_existing_status_surface_for_live_sync_state():
    html = INDEX_HTML.read_text(encoding="utf-8")
    text = APP_JS.read_text(encoding="utf-8")

    assert 'id="connection-status"' in html
    assert "function renderTopbarStatus()" in text
    assert "state.liveSync.statusText" in text


def test_bootstrap_auth_reapplies_requested_route_from_location_after_session_restore():
    text = (REPO_ROOT / "src" / "main" / "ui" / "js" / "shell" / "session.js").read_text(encoding="utf-8")
    app_text = APP_JS.read_text(encoding="utf-8")

    assert "function restoreRouteFromLocationAfterAuth() {" in text
    assert "const nextView = viewFromLocationPath(window.location.pathname);" in text
    assert 'setView(nextView, { fromHistory: true });' in text
    assert "viewFromLocationPath," in app_text
    assert "setView," in app_text


def test_context_refresh_invalidates_and_reloads_data_when_the_active_space_changes():
    app_text = APP_JS.read_text(encoding="utf-8")
    live_sync_text = LIVE_SYNC_JS.read_text(encoding="utf-8")
    apply_context_block = app_text[
        app_text.index("function applySpaceContext"):app_text.index("async function refreshSpaceContext")
    ]
    refresh_context_block = app_text[
        app_text.index("async function refreshSpaceContext"):app_text.index("function setAuthed")
    ]

    assert "const dataInvalidated = invalidateDataForSpaceContextChange({" in apply_context_block
    assert "previousSpaceId: previousActiveSpaceId," in apply_context_block
    assert "nextSpaceId: nextActiveSpaceId," in apply_context_block
    assert "clearDataState," in apply_context_block
    assert "suppress: suppressDataInvalidation," in apply_context_block
    assert "return dataInvalidated;" in apply_context_block
    assert "return refreshSpaceContextData({" in refresh_context_block
    assert 'loadSpaces: () => api("/spaces", apiOptions),' in refresh_context_block
    assert 'loadActiveSpace: () => api("/auth/active-space", apiOptions),' in refresh_context_block
    assert "applySpaceContext," in refresh_context_block
    assert "reloadCurrentViewData," in refresh_context_block
    assert "renderActiveView," in refresh_context_block
    assert "suppressDataInvalidation: true," in live_sync_text


def test_session_controller_preserves_auth_error_codes_and_terminal_messages():
    text = (REPO_ROOT / "src" / "main" / "ui" / "js" / "shell" / "session.js").read_text(encoding="utf-8")

    assert 'err.code = res.headers?.get?.("X-Error-Code") || "";' in text
    assert 'err.code === "PASSWORD_RESET_REQUIRED"' in text
    assert 'err.code === "ACCOUNT_LOCKED"' in text
    assert 'err.code === "TOKEN_REVOKED"' in text
    terminal_block = text[text.index("const terminalCodes = new Set(["):text.index("if (err.code) return terminalCodes.has(err.code);")]
    assert '"LOGIN_FAILED"' not in terminal_block
    assert "const terminalCodes = new Set([" in text
    assert "function isTerminalAuthFailure(err)" in text
    assert 'handleSessionExpired({ message: authErrorMessage(err) });' in text


def test_auth_forms_disable_submit_buttons_while_requests_are_pending():
    text = (REPO_ROOT / "src" / "main" / "ui" / "js" / "shell" / "session.js").read_text(encoding="utf-8")

    assert "const pendingAuthActions = new Set();" in text
    assert "async function withPendingAuthAction(key, form, action)" in text
    assert 'button.setAttribute("aria-busy", "true");' in text
    assert 'button.removeAttribute("aria-busy");' in text
    assert 'withPendingAuthAction("login", els.loginForm' in text
    assert 'withPendingAuthAction("register", els.registerForm' in text
    assert 'withPendingAuthAction("reset-password", els.resetForm' in text
