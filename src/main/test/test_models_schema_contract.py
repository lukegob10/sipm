from datetime import datetime
from types import SimpleNamespace

from sqlalchemy import Text

from backend.app.models import ChangeLog, ChecklistItem, Project, SOWDocument, Solution
from backend.app.schemas import ChangeLogRead, ProjectRead, SolutionRead
from backend.app.utils.enums import ProjectStatus, RagStatus, SolutionStatus


class FakeLob:
    def __init__(self, value: str):
        self.value = value

    def read(self) -> str:
        return self.value


def test_sow_document_content_uses_text_type():
    assert isinstance(SOWDocument.__table__.c.content.type, Text)


def test_checklist_item_title_uses_text_type():
    assert isinstance(ChecklistItem.__table__.c.title.type, Text)


def test_project_long_text_fields_use_text_type():
    assert isinstance(Project.__table__.c.description.type, Text)
    assert isinstance(Project.__table__.c.success_criteria.type, Text)


def test_solution_long_text_fields_use_text_type():
    assert isinstance(Solution.__table__.c.description.type, Text)
    assert isinstance(Solution.__table__.c.success_criteria.type, Text)
    assert isinstance(Solution.__table__.c.problem_statement.type, Text)


def test_change_log_value_fields_use_text_type():
    assert isinstance(ChangeLog.__table__.c.old_value.type, Text)
    assert isinstance(ChangeLog.__table__.c.new_value.type, Text)


def test_long_text_read_schemas_coerce_lob_values():
    now = datetime(2026, 3, 17, 12, 0, 0)

    project = ProjectRead.model_validate(
        SimpleNamespace(
            project_id="project-1",
            project_name="Long Form Project",
            status=ProjectStatus.not_started,
            description=FakeLob("project description"),
            success_criteria=FakeLob("project success"),
            sponsor="Sponsor",
            sponsor_user_soeid="abc123",
            strategic_objective="Objective",
            priority=3,
            created_at=now,
            updated_at=now,
        )
    )
    assert project.description == "project description"
    assert project.success_criteria == "project success"

    solution = SolutionRead.model_validate(
        SimpleNamespace(
            solution_id="solution-1",
            project_id="project-1",
            solution_name="Solution",
            version="1.0.0",
            status=SolutionStatus.not_started,
            rag_status=RagStatus.green,
            description=FakeLob("solution description"),
            success_criteria=FakeLob("solution success"),
            problem_statement=FakeLob("solution problem"),
            priority=3,
            created_at=now,
            updated_at=now,
        )
    )
    assert solution.description == "solution description"
    assert solution.success_criteria == "solution success"
    assert solution.problem_statement == "solution problem"

    change = ChangeLogRead.model_validate(
        SimpleNamespace(
            change_id="change-1",
            entity_type="project",
            entity_id="project-1",
            action="update",
            field="description",
            old_value=FakeLob("old value"),
            new_value=FakeLob("new value"),
            user_id="user-1",
            request_id="request-1",
            created_at=now,
        )
    )
    assert change.old_value == "old value"
    assert change.new_value == "new value"
