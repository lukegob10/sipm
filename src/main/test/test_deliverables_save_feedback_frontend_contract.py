from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
APP_JS = REPO_ROOT / "src" / "main" / "ui" / "js" / "app.js"
INDEX_HTML = REPO_ROOT / "src" / "main" / "ui" / "index.html"
STYLES_CSS = REPO_ROOT / "src" / "main" / "ui" / "styles.css"


def test_deliverables_forms_have_status_placeholders():
    text = INDEX_HTML.read_text(encoding="utf-8")
    assert 'id="project-form-status"' in text
    assert 'id="solution-form-status"' in text
    assert 'id="subcomponent-form-status"' in text


def test_deliverables_forms_mark_required_fields():
    text = INDEX_HTML.read_text(encoding="utf-8")
    styles_text = STYLES_CSS.read_text(encoding="utf-8")
    assert text.count('Fields marked <span class="required-marker" aria-hidden="true">*</span> are required.') == 3
    assert '<span class="field-label">Project<span class="required-marker" aria-hidden="true">*</span></span><input name="project_name" required />' in text
    assert '<span class="field-label">Sponsor<span class="required-marker" aria-hidden="true">*</span></span><input name="sponsor" required />' in text
    assert '<span class="field-label">Project<span class="required-marker" aria-hidden="true">*</span></span>' in text
    assert '<span class="field-label">Solution<span class="required-marker" aria-hidden="true">*</span></span><input name="solution_name" required />' in text
    assert '<span class="field-label">Solution Owner<span class="required-marker" aria-hidden="true">*</span></span><input name="owner" required />' in text
    assert '<span class="field-label">Task<span class="required-marker" aria-hidden="true">*</span></span><input name="subcomponent_name" required />' in text
    assert '.field-label {' in styles_text


def test_deliverables_save_handlers_show_inline_feedback():
    text = APP_JS.read_text(encoding="utf-8")
    assert "function setDeliverableFormNotice(" in text
    assert 'setDeliverableFormNotice(els.projectFormStatus, "Saving project...")' in text
    assert 'setDeliverableFormNotice(els.solutionFormStatus, "Saving solution...")' in text
    assert 'setDeliverableFormNotice(els.subcomponentFormStatus, "Saving subcomponent...")' in text
    assert "Saved project at ${timestampLabel()}." in text
    assert "Saved solution at ${timestampLabel()}." in text
    assert "Saved subcomponent at ${timestampLabel()}." in text


def test_subcomponent_form_uses_single_create_or_save_action():
    html_text = INDEX_HTML.read_text(encoding="utf-8")
    js_text = APP_JS.read_text(encoding="utf-8")

    assert 'id="subcomponent-submit-btn"' in html_text
    assert 'id="new-subcomponent"' not in html_text
    assert "function setSubcomponentActionButtonLabel(" in js_text
    assert 'els.subcomponentSubmitBtn.textContent = isEditing ? "Save Changes" : "Create Subcomponent";' in js_text
    assert 'setDeliverableFormNotice(els.subcomponentFormStatus, "Creating subcomponent...")' in js_text
    assert "Created subcomponent at ${timestampLabel()}." in js_text
