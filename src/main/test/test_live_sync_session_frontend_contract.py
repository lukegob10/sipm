from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
APP_JS = REPO_ROOT / "src" / "main" / "ui" / "js" / "app.js"
INDEX_HTML = REPO_ROOT / "src" / "main" / "ui" / "index.html"


def test_live_sync_controller_uses_explicit_close_codes_and_space_query_param():
    text = APP_JS.read_text(encoding="utf-8")

    assert 'const LIVE_SYNC_CLOSE_AUTH = 4401;' in text
    assert 'const LIVE_SYNC_CLOSE_SPACE = 4403;' in text
    assert 'const LIVE_SYNC_CLOSE_LIMIT = 4408;' in text
    assert 'const LIVE_SYNC_CLOSE_BUSY = 1013;' in text
    assert 'url.searchParams.set("space_id", state.activeSpace.space_id);' in text
    assert "function startLiveSync(options = {})" in text
    assert "liveSyncStarted" not in text


def test_live_sync_controller_stops_on_terminal_failures_and_pauses_hidden_tabs():
    text = APP_JS.read_text(encoding="utf-8")

    assert "function handleSessionExpired() {" in text
    assert "stopLiveSync();" in text
    assert "async function recoverLiveSyncAuth()" in text
    assert "async function recoverLiveSyncSpace()" in text
    assert 'if (event.code === LIVE_SYNC_CLOSE_AUTH)' in text
    assert 'if (event.code === LIVE_SYNC_CLOSE_SPACE)' in text
    assert 'if (event.code === LIVE_SYNC_CLOSE_LIMIT)' in text
    assert 'document.addEventListener("visibilitychange", handleLiveSyncVisibilityChange);' in text
    assert "state.liveSync.pausedForHidden" in text


def test_shell_keeps_existing_status_surface_for_live_sync_state():
    html = INDEX_HTML.read_text(encoding="utf-8")
    text = APP_JS.read_text(encoding="utf-8")

    assert 'id="connection-status"' in html
    assert "function renderTopbarStatus()" in text
    assert "state.liveSync.statusText" in text
