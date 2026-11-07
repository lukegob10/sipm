from pathlib import Path


APP_JS = Path(__file__).resolve().parents[1] / "ui" / "js" / "app.js"


def test_task_delete_checks_confirmation_before_sending_requests():
    source = APP_JS.read_text(encoding="utf-8")
    helper = source[
        source.index("async function deleteTasksById("):
        source.index("function clearTasksWorkbenchBulkFeedback(")
    ]
    cancelled = helper.index("return { cancelled: true, deletedIds: [], failed: [] };")
    deletion = helper.index('await api(`/tasks/${encodeURIComponent(id)}`, { method: "DELETE" });')
    assert cancelled < deletion
