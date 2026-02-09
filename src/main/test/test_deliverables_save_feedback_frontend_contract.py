from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
APP_JS = REPO_ROOT / "src" / "main" / "ui" / "js" / "app.js"
INDEX_HTML = REPO_ROOT / "src" / "main" / "ui" / "index.html"


def test_deliverables_forms_have_status_placeholders():
    text = INDEX_HTML.read_text(encoding="utf-8")
    assert 'id="project-form-status"' in text
    assert 'id="solution-form-status"' in text
    assert 'id="subcomponent-form-status"' in text


def test_deliverables_save_handlers_show_inline_feedback():
    text = APP_JS.read_text(encoding="utf-8")
    assert "function setDeliverableFormNotice(" in text
    assert 'setDeliverableFormNotice(els.projectFormStatus, "Saving project...")' in text
    assert 'setDeliverableFormNotice(els.solutionFormStatus, "Saving solution...")' in text
    assert 'setDeliverableFormNotice(els.subcomponentFormStatus, "Saving subcomponent...")' in text
    assert "Saved project at ${timestampLabel()}." in text
    assert "Saved solution at ${timestampLabel()}." in text
    assert "Saved subcomponent at ${timestampLabel()}." in text
