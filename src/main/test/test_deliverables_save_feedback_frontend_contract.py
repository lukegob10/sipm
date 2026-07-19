from pathlib import Path

from ui_style_contract import read_ui_styles


REPO_ROOT = Path(__file__).resolve().parents[3]
APP_JS = REPO_ROOT / "src" / "main" / "ui" / "js" / "app.js"
PROJECT_ENTITIES_JS = REPO_ROOT / "src" / "main" / "ui" / "js" / "entities" / "projects.js"
SOLUTION_ENTITIES_JS = REPO_ROOT / "src" / "main" / "ui" / "js" / "entities" / "solutions.js"
TASK_ENTITIES_JS = REPO_ROOT / "src" / "main" / "ui" / "js" / "entities" / "tasks.js"
DOM_JS = REPO_ROOT / "src" / "main" / "ui" / "js" / "shell" / "dom.js"
INDEX_HTML = REPO_ROOT / "src" / "main" / "ui" / "index.html"
STYLES_CSS = REPO_ROOT / "src" / "main" / "ui" / "styles.css"


def test_deliverables_forms_have_status_placeholders():
    text = INDEX_HTML.read_text(encoding="utf-8")
    assert 'id="project-form-status"' in text
    assert 'id="solution-form-status"' in text
    assert 'id="task-form-status"' in text


def test_deliverables_forms_mark_required_fields():
    text = INDEX_HTML.read_text(encoding="utf-8")
    styles_text = read_ui_styles(STYLES_CSS)
    assert text.count('Fields marked <span class="required-marker" aria-hidden="true">*</span> are required.') == 4
    assert '<span class="field-label">Project<span class="required-marker" aria-hidden="true">*</span></span><input name="project_name" required />' in text
    assert '<span class="field-label">Sponsor<span class="required-marker" aria-hidden="true">*</span></span><input name="sponsor" required />' in text
    assert '<span class="field-label">Project<span class="required-marker" aria-hidden="true">*</span></span>' in text
    assert '<span class="field-label">Solution<span class="required-marker" aria-hidden="true">*</span></span><input name="solution_name" required />' in text
    assert '<span class="field-label">Solution Owner<span class="required-marker" aria-hidden="true">*</span></span><input name="owner" required />' in text
    assert '<span class="field-label">Task<span class="required-marker" aria-hidden="true">*</span></span><input name="task_name" required />' in text
    assert '.field-label {' in styles_text


def test_deliverables_save_handlers_show_inline_feedback():
    text = APP_JS.read_text(encoding="utf-8")
    project_text = PROJECT_ENTITIES_JS.read_text(encoding="utf-8")
    solution_text = SOLUTION_ENTITIES_JS.read_text(encoding="utf-8")
    task_text = TASK_ENTITIES_JS.read_text(encoding="utf-8")
    assert "function setDeliverableFormNotice(" in text
    assert 'setDeliverableFormNotice(els.projectFormStatus, "Saving project...")' in project_text
    assert 'setDeliverableFormNotice(els.solutionFormStatus, "Saving solution...")' in solution_text
    assert 'setDeliverableFormNotice(els.taskFormStatus, "Saving task...")' in task_text
    assert "Saved project at ${timestampLabel()}." in project_text
    assert "Saved solution at ${timestampLabel()}." in solution_text
    assert "Saved task at ${timestampLabel()}." in task_text


def test_project_form_footer_is_managed_outside_scroll_flow():
    html_text = INDEX_HTML.read_text(encoding="utf-8")
    styles_text = read_ui_styles(STYLES_CSS)

    assert 'id="project-submit-btn" form="project-form"' in html_text
    assert '#project-form.form.compact {' in styles_text
    assert '#project-modal .modal-body {' in styles_text
    assert '#project-modal .modal-body > .modal-form-footer {' in styles_text


def test_task_form_uses_single_create_or_save_action():
    html_text = INDEX_HTML.read_text(encoding="utf-8")
    app_text = APP_JS.read_text(encoding="utf-8")
    task_text = TASK_ENTITIES_JS.read_text(encoding="utf-8")

    assert 'id="task-submit-btn"' in html_text
    assert 'id="new-task"' not in html_text
    assert "function setTaskActionButtonLabel(isEditing) {" in app_text
    assert "return taskEntityController.setTaskActionButtonLabel(isEditing);" in app_text
    assert 'els.taskSubmitBtn.textContent = isEditing ? "Save Changes" : "Create Task";' in task_text
    assert 'setDeliverableFormNotice(els.taskFormStatus, "Creating task...")' in task_text
    assert "Created task at ${timestampLabel()}." in task_text


def test_task_form_footer_is_managed_outside_scroll_flow():
    html_text = INDEX_HTML.read_text(encoding="utf-8")
    app_text = APP_JS.read_text(encoding="utf-8")
    task_text = TASK_ENTITIES_JS.read_text(encoding="utf-8")
    dom_text = DOM_JS.read_text(encoding="utf-8")
    styles_text = read_ui_styles(STYLES_CSS)

    assert 'id="task-form-footer"' in html_text
    assert 'id="task-submit-btn" form="task-form"' in html_text
    assert 'taskFormFooter: document.getElementById("task-form-footer")' in dom_text
    assert "function setTaskFormVisibility(show) {" in app_text
    assert "return taskEntityController.setTaskFormVisibility(show);" in app_text
    assert 'els.taskFormFooter.classList.toggle("hidden", !show);' in task_text
    assert '#solution-modal .modal-tab[data-tab-panel="tasks"].active {' in styles_text
    assert '#solution-modal .modal-tab[data-tab-panel="tasks"] > .task-tab-scroll {' in styles_text


def test_new_solution_requires_saved_parent_before_tasks_can_be_added():
    js_text = APP_JS.read_text(encoding="utf-8")
    solution_text = SOLUTION_ENTITIES_JS.read_text(encoding="utf-8")
    task_text = TASK_ENTITIES_JS.read_text(encoding="utf-8")

    assert "function setTaskCreateAvailability(solutionId) {" in js_text
    assert "return solutionEntityController.setTaskCreateAvailability(solutionId);" in js_text
    assert 'els.showTaskFormBtn.disabled = !hasSolution;' in solution_text
    assert '? "Add a task to this solution"' in solution_text
    assert ': "Save the solution before adding tasks.";' in solution_text
    assert 'setTaskCreateAvailability(solution?.solution_id || "");' in solution_text
    assert 'setTaskCreateAvailability("");' in solution_text
    assert 'els.solutionTaskTable.innerHTML = "<p class=\'muted\'>Save the solution to add tasks.</p>";' in js_text
    assert 'setDeliverableFormNotice(els.taskFormStatus, "Save the solution before adding tasks.", "error");' in task_text
    assert 'alert("Save the solution before adding tasks.");' not in js_text


def test_solution_task_table_sorts_from_the_task_header_without_a_dropdown():
    html_text = INDEX_HTML.read_text(encoding="utf-8")
    app_text = APP_JS.read_text(encoding="utf-8")

    assert 'id="task-sort"' not in html_text
    assert 'class="task-sort-control"' not in html_text
    assert 'data-task-name-sort' in app_text
    assert 'aria-sort="${sortPresentation.ariaSort}"' in app_text
    assert 'state.taskSort = nextTaskNameSort(state.taskSort);' in app_text


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


def test_task_form_uses_inline_feedback_for_failures():
    task_text = TASK_ENTITIES_JS.read_text(encoding="utf-8")
    task_section = task_text.split("function bindTaskForm() {", 1)[1].split("return {", 1)[0]

    assert "setDeliverableFormNotice(" in task_section
    assert '`${isEditing ? "Save" : "Create"} failed: ${err.message}`' in task_section
    assert '`Delete failed: ${result.failed[0]?.error?.message || "Unable to delete task."}`' in task_section
    assert 'alert(`${isEditing ? "Save" : "Create"} failed: ${err.message}`);' not in task_section


def test_solution_phases_use_inline_feedback_for_failures():
    js_text = APP_JS.read_text(encoding="utf-8")
    phases_section = js_text.split("async function renderSolutionPhases(selectedId) {", 1)[1].split("function bindTaskForm() {", 1)[0]

    assert 'els.phasesTable.innerHTML = "<p class=\'muted\'>Unable to load phases.</p>";' in phases_section
    assert 'setDeliverableFormNotice(\n        els.solutionFormStatus,\n        `Unable to load phases: ${err.message}`,\n        "error"\n      );' in phases_section
    assert 'setDeliverableFormNotice(\n          els.solutionFormStatus,\n          `Phase update failed: ${err.message}`,\n          "error"\n        );' in phases_section
    assert 'alert(`Load failed: ${err.message}`);' not in phases_section
    assert 'alert(`Save failed: ${err.message}`);' not in phases_section
