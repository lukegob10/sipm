from datetime import datetime
from types import SimpleNamespace

import backend.app.models as models
from sqlalchemy import create_engine
from sqlalchemy import Text
from sqlalchemy.orm import sessionmaker

from backend.app.db.table_names import physical_table_name
from backend.app.models import Base, ChangeLog, Project, Solution, Team
from backend.app.schemas import ChangeLogRead, ProjectRead, SolutionRead
from backend.app.utils.enums import ProjectStatus, RagStatus, SolutionStatus


STALE_MODEL_NAMES = (
    "SOWDocument",
    "ChecklistItem",
    "ProjectCardDigest",
    "SolutionCardDigest",
    "TaskCardDigest",
    "ProjectCharter",
    "ProjectPlan",
    "ProjectDecisionLog",
    "ExternalDocument",
)

STALE_TABLE_NAMES = tuple(
    physical_table_name(table_name)
    for table_name in (
        "sow_documents",
        "checklist_items",
        "project_card_digests",
        "solution_card_digests",
        "task_card_digests",
        "project_charters",
        "project_plans",
        "project_decision_logs",
        "external_documents",
    )
)


class FakeLob:
    def __init__(self, value: str):
        self.value = value

    def read(self) -> str:
        return self.value


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


def test_models_package_reexports_and_registers_metadata():
    assert models.User is not None
    assert models.Project is not None
    assert Project.__table__.name in Base.metadata.tables
    assert Solution.__table__.name in Base.metadata.tables
    for model_name in STALE_MODEL_NAMES:
        assert not hasattr(models, model_name)
    for table_name in STALE_TABLE_NAMES:
        assert table_name not in Base.metadata.tables


def test_timestamp_mixin_updates_updated_at_on_row_change():
    engine = create_engine("sqlite+pysqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    original = datetime(2000, 1, 1, 0, 0, 0)

    with SessionLocal() as session:
        team = Team(name="Platform", created_at=original, updated_at=original)
        session.add(team)
        session.commit()
        session.refresh(team)

        team.description = "Updated description"
        session.add(team)
        session.commit()
        session.refresh(team)

        assert team.updated_at > original


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
