from pathlib import Path

from ui_style_contract import read_ui_styles


REPO_ROOT = Path(__file__).resolve().parents[3]
APP_JS = REPO_ROOT / "src" / "main" / "ui" / "js" / "app.js"
PROJECT_ENTITIES_JS = REPO_ROOT / "src" / "main" / "ui" / "js" / "entities" / "projects.js"
SOLUTION_ENTITIES_JS = REPO_ROOT / "src" / "main" / "ui" / "js" / "entities" / "solutions.js"
SUBCOMPONENT_ENTITIES_JS = REPO_ROOT / "src" / "main" / "ui" / "js" / "entities" / "subcomponents.js"
DOM_JS = REPO_ROOT / "src" / "main" / "ui" / "js" / "shell" / "dom.js"
INDEX_HTML = REPO_ROOT / "src" / "main" / "ui" / "index.html"
STYLES_CSS = REPO_ROOT / "src" / "main" / "ui" / "styles.css"


def test_deliverables_forms_have_status_placeholders():
    text = INDEX_HTML.read_text(encoding="utf-8")
    assert 'id="project-form-status"' in text
    assert 'id="solution-form-status"' in text
    assert 'id="subcomponent-form-status"' in text


def test_deliverables_forms_mark_required_fields():
    text = INDEX_HTML.read_text(encoding="utf-8")
    styles_text = read_ui_styles(STYLES_CSS)
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
    project_text = PROJECT_ENTITIES_JS.read_text(encoding="utf-8")
    solution_text = SOLUTION_ENTITIES_JS.read_text(encoding="utf-8")
    subcomponent_text = SUBCOMPONENT_ENTITIES_JS.read_text(encoding="utf-8")
    assert "function setDeliverableFormNotice(" in text
    assert 'setDeliverableFormNotice(els.projectFormStatus, "Saving project...")' in project_text
    assert 'setDeliverableFormNotice(els.solutionFormStatus, "Saving solution...")' in solution_text
    assert 'setDeliverableFormNotice(els.subcomponentFormStatus, "Saving subcomponent...")' in subcomponent_text
    assert "Saved project at ${timestampLabel()}." in project_text
    assert "Saved solution at ${timestampLabel()}." in solution_text
    assert "Saved subcomponent at ${timestampLabel()}." in subcomponent_text


def test_project_form_footer_is_managed_outside_scroll_flow():
    html_text = INDEX_HTML.read_text(encoding="utf-8")
    styles_text = read_ui_styles(STYLES_CSS)

    assert 'id="project-submit-btn" form="project-form"' in html_text
    assert '#project-form.form.compact {' in styles_text
    assert '#project-modal .modal-body {' in styles_text
    assert '#project-modal .modal-body > .modal-form-footer {' in styles_text


def test_subcomponent_form_uses_single_create_or_save_action():
    html_text = INDEX_HTML.read_text(encoding="utf-8")
    app_text = APP_JS.read_text(encoding="utf-8")
    subcomponent_text = SUBCOMPONENT_ENTITIES_JS.read_text(encoding="utf-8")

    assert 'id="subcomponent-submit-btn"' in html_text
    assert 'id="new-subcomponent"' not in html_text
    assert "function setSubcomponentActionButtonLabel(isEditing) {" in app_text
    assert "return subcomponentEntityController.setSubcomponentActionButtonLabel(isEditing);" in app_text
    assert 'els.subcomponentSubmitBtn.textContent = isEditing ? "Save Changes" : "Create Subcomponent";' in subcomponent_text
    assert 'setDeliverableFormNotice(els.subcomponentFormStatus, "Creating subcomponent...")' in subcomponent_text
    assert "Created subcomponent at ${timestampLabel()}." in subcomponent_text


def test_subcomponent_form_footer_is_managed_outside_scroll_flow():
    html_text = INDEX_HTML.read_text(encoding="utf-8")
    app_text = APP_JS.read_text(encoding="utf-8")
    subcomponent_text = SUBCOMPONENT_ENTITIES_JS.read_text(encoding="utf-8")
    dom_text = DOM_JS.read_text(encoding="utf-8")
    styles_text = read_ui_styles(STYLES_CSS)

    assert 'id="subcomponent-form-footer"' in html_text
    assert 'id="subcomponent-submit-btn" form="subcomponent-form"' in html_text
    assert 'subcomponentFormFooter: document.getElementById("subcomponent-form-footer")' in dom_text
    assert "function setSubcomponentFormVisibility(show) {" in app_text
    assert "return subcomponentEntityController.setSubcomponentFormVisibility(show);" in app_text
    assert 'els.subcomponentFormFooter.classList.toggle("hidden", !show);' in subcomponent_text
    assert '#solution-modal .modal-tab[data-tab-panel="subcomponents"].active {' in styles_text
    assert '#solution-modal .modal-tab[data-tab-panel="subcomponents"] > .subcomponent-tab-scroll {' in styles_text


def test_new_solution_requires_saved_parent_before_subcomponents_can_be_added():
    js_text = APP_JS.read_text(encoding="utf-8")
    solution_text = SOLUTION_ENTITIES_JS.read_text(encoding="utf-8")
    subcomponent_text = SUBCOMPONENT_ENTITIES_JS.read_text(encoding="utf-8")

    assert "function setSubcomponentCreateAvailability(solutionId) {" in js_text
    assert "return solutionEntityController.setSubcomponentCreateAvailability(solutionId);" in js_text
    assert 'els.showSubcomponentFormBtn.disabled = !hasSolution;' in solution_text
    assert '? "Add a task to this solution"' in solution_text
    assert ': "Save the solution before adding subcomponents.";' in solution_text
    assert 'setSubcomponentCreateAvailability(solution?.solution_id || "");' in solution_text
    assert 'setSubcomponentCreateAvailability("");' in solution_text
    assert 'els.solutionSubcomponentTable.innerHTML = "<p class=\'muted\'>Save the solution to add subcomponents.</p>";' in js_text
    assert 'setDeliverableFormNotice(els.subcomponentFormStatus, "Save the solution before adding subcomponents.", "error");' in subcomponent_text
    assert 'alert("Save the solution before adding subcomponents.");' not in js_text


def test_solution_form_uses_inline_feedback_for_required_project_and_failures():
    solution_text = SOLUTION_ENTITIES_JS.read_text(encoding="utf-8")
    solution_section = solution_text.split("function bindSolutionForm() {", 1)[1].split("return {", 1)[0]

    assert "setDeliverableFormNotice(" in solution_section
    assert '"Select a project before creating a solution."' in solution_section
    assert 'setDeliverableFormNotice(els.solutionFormStatus, "Deleting solution...");' in solution_section
    assert '`Delete failed: ${err.message}`' in solution_section
    assert 'alert("Project is required.");' not in solution_section
    assert 'alert(`${isEditing ? "Save" : "Create"} failed: ${err.message}`);' not in solution_section
    assert 'alert(`Delete failed: ${err.message}`);' not in solution_section


def test_project_form_uses_inline_feedback_for_failures():
    project_text = PROJECT_ENTITIES_JS.read_text(encoding="utf-8")
    project_section = project_text.split("function bindProjectForm() {", 1)[1].split("return {", 1)[0]

    assert "setDeliverableFormNotice(" in project_section
    assert '`${isEditing ? "Save" : "Create"} failed: ${err.message}`' in project_section
    assert 'setDeliverableFormNotice(els.projectFormStatus, "Deleting project...");' in project_section
    assert '`Delete failed: ${err.message}`' in project_section
    assert 'alert(`${isEditing ? "Save" : "Create"} failed: ${err.message}`);' not in project_section
    assert 'alert(`Delete failed: ${err.message}`);' not in project_section


def test_subcomponent_form_uses_inline_feedback_for_failures():
    subcomponent_text = SUBCOMPONENT_ENTITIES_JS.read_text(encoding="utf-8")
    subcomponent_section = subcomponent_text.split("function bindSubcomponentForm() {", 1)[1].split("return {", 1)[0]

    assert "setDeliverableFormNotice(" in subcomponent_section
    assert '`${isEditing ? "Save" : "Create"} failed: ${err.message}`' in subcomponent_section
    assert '`Delete failed: ${result.failed[0]?.error?.message || "Unable to delete subcomponent."}`' in subcomponent_section
    assert 'alert(`${isEditing ? "Save" : "Create"} failed: ${err.message}`);' not in subcomponent_section


def test_solution_phases_use_inline_feedback_for_failures():
    js_text = APP_JS.read_text(encoding="utf-8")
    phases_section = js_text.split("async function renderSolutionPhases(selectedId) {", 1)[1].split("function bindSubcomponentForm() {", 1)[0]

    assert 'els.phasesTable.innerHTML = "<p class=\'muted\'>Unable to load phases.</p>";' in phases_section
    assert 'setDeliverableFormNotice(\n        els.solutionFormStatus,\n        `Unable to load phases: ${err.message}`,\n        "error"\n      );' in phases_section
    assert 'setDeliverableFormNotice(\n          els.solutionFormStatus,\n          `Phase update failed: ${err.message}`,\n          "error"\n        );' in phases_section
    assert 'alert(`Load failed: ${err.message}`);' not in phases_section
    assert 'alert(`Save failed: ${err.message}`);' not in phases_section
