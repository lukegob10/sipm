from pathlib import Path


APP_JS = Path(__file__).resolve().parents[1] / "ui" / "js" / "app.js"


def test_task_delete_suppresses_refresh_only_after_confirmation():
    source = APP_JS.read_text(encoding="utf-8")
    helper = source[
        source.index("async function deleteTasksById("):
        source.index("function clearTasksWorkbenchBulkFeedback(")
    ]
    cancelled = helper.index("return { cancelled: true, deletedIds: [], failed: [] };")
    marker = helper.index('markIgnoreRefresh("tasks");')
    deletion = helper.index('await api(`/tasks/${encodeURIComponent(id)}`, { method: "DELETE" });')
    assert cancelled < marker < deletion
    assert helper.count('markIgnoreRefresh("tasks");') == 1
