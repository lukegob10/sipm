from datetime import datetime
from pathlib import Path
import re
from types import SimpleNamespace

import backend.app.models as models
from sqlalchemy import create_engine
from sqlalchemy import Text
from sqlalchemy.schema import CreateTable
from sqlalchemy.dialects import oracle
from sqlalchemy.orm import sessionmaker

from backend.app.db.table_names import physical_table_name
from backend.app.models import Base, ChangeLog, Project, Solution, Subcomponent, Team
from backend.app.schemas import ChangeLogRead, ProjectRead, SolutionRead, SubcomponentRead
from backend.app.utils.enums import ProjectStatus, RagStatus, SolutionStatus, SubcomponentStatus


SCHEMA_DOC_PATH = Path(__file__).resolve().parents[3] / "docs/sql/schema_oracle_ta.sql"
CREATE_TABLE_PATTERN = re.compile(r'CREATE TABLE "([^"]+)" \((.*?)\);', re.S)
CREATE_INDEX_PATTERN = re.compile(r'CREATE INDEX "?([A-Za-z0-9_]+)"? ON "([^"]+)"', re.S)


STALE_MODEL_NAMES = (
    "SOWDocument",
    "ChecklistItem",
    "ProjectCardDigest",
    "SolutionCardDigest",
    "TaskCardDigest",
    "PasswordResetToken",
    "ProjectCharter",
    "ProjectPlan",
    "ProjectDecisionLog",
    "ExternalDocument",
    "ExternalRef",
    "SolutionWeeklySnapshot",
)

STALE_TABLE_NAMES = tuple(
    physical_table_name(table_name)
    for table_name in (
        "sow_documents",
        "checklist_items",
        "project_card_digests",
        "solution_card_digests",
        "task_card_digests",
        "password_reset_tokens",
        "project_charters",
        "project_plans",
        "project_decision_logs",
        "external_documents",
        "external_ref",
        "solution_weekly_snapshot",
    )
)


class FakeLob:
    def __init__(self, value: str):
        self.value = value

    def read(self) -> str:
        return self.value


def _normalize_sql(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip())


def _parse_table_body(body: str) -> tuple[dict[str, str], set[str]]:
    columns: dict[str, str] = {}
    unique_constraints: set[str] = set()
    for raw in body.splitlines():
        line = raw.strip().rstrip(",")
        if not line or line.startswith("--"):
            continue
        if line.startswith("PRIMARY KEY") or line.startswith("FOREIGN KEY"):
            continue
        if line.startswith("CONSTRAINT") and " UNIQUE " in f" {line} ":
            unique_constraints.add(line.split()[1])
            continue
        name, rest = line.split(None, 1)
        columns[name.strip('"').lower()] = _normalize_sql(rest)
    return columns, unique_constraints


def _doc_schema_contract():
    schema = SCHEMA_DOC_PATH.read_text()
    tables = {}
    for table_name, body in CREATE_TABLE_PATTERN.findall(schema):
        columns, unique_constraints = _parse_table_body(body)
        tables[table_name] = {
            "columns": columns,
            "unique_constraints": unique_constraints,
        }
    indexes = {
        index_name
        for index_name, _table_name in CREATE_INDEX_PATTERN.findall(schema)
    }
    return tables, indexes


def _model_schema_contract():
    tables = {}
    indexes: set[str] = set()
    for table_name, table in Base.metadata.tables.items():
        ddl = str(CreateTable(table).compile(dialect=oracle.dialect()))
        body = ddl.split("(", 1)[1].rsplit(")", 1)[0]
        columns, unique_constraints = _parse_table_body(body)
        tables[table_name] = {
            "columns": columns,
            "unique_constraints": unique_constraints,
        }
        indexes.update(index.name for index in table.indexes if index.name)
    return tables, indexes


def test_project_long_text_fields_use_text_type():
    assert isinstance(Project.__table__.c.description.type, Text)
    assert isinstance(Project.__table__.c.success_criteria.type, Text)
    assert isinstance(Project.__table__.c.strategic_objective.type, Text)


def test_solution_long_text_fields_use_text_type():
    assert isinstance(Solution.__table__.c.description.type, Text)
    assert isinstance(Solution.__table__.c.success_criteria.type, Text)
    assert isinstance(Solution.__table__.c.problem_statement.type, Text)
    assert isinstance(Solution.__table__.c.rag_reason.type, Text)
    assert isinstance(Solution.__table__.c.blockers.type, Text)
    assert isinstance(Solution.__table__.c.risks.type, Text)


def test_subcomponent_long_text_fields_use_text_type():
    assert isinstance(Subcomponent.__table__.c.blocker_note.type, Text)
    assert isinstance(Subcomponent.__table__.c.done_criteria.type, Text)


def test_oracle_solution_repo_url_column_uses_documented_length():
    ddl = str(CreateTable(Solution.__table__).compile(dialect=oracle.dialect()))
    assert "github_repo_url VARCHAR2(1024 CHAR)" in ddl


def test_oracle_subcomponent_repo_url_column_uses_documented_length():
    subcomponents = Base.metadata.tables[physical_table_name("subcomponents")]
    ddl = str(CreateTable(subcomponents).compile(dialect=oracle.dialect()))
    assert "github_repo_url VARCHAR2(1024 CHAR)" in ddl


def test_change_log_value_fields_use_text_type():
    assert isinstance(ChangeLog.__table__.c.old_value.type, Text)
    assert isinstance(ChangeLog.__table__.c.new_value.type, Text)


def test_oracle_schema_document_matches_model_metadata_tables_and_columns():
    doc_tables, _ = _doc_schema_contract()
    model_tables, _ = _model_schema_contract()

    assert set(doc_tables) == set(model_tables)
    for table_name in doc_tables:
        assert doc_tables[table_name]["columns"] == model_tables[table_name]["columns"]


def test_oracle_schema_document_matches_model_uniques_and_indexes():
    doc_tables, doc_indexes = _doc_schema_contract()
    model_tables, model_indexes = _model_schema_contract()

    for table_name in doc_tables:
        assert doc_tables[table_name]["unique_constraints"] == model_tables[table_name]["unique_constraints"]
    assert doc_indexes == model_indexes


def test_oracle_schema_document_creates_indexes_after_target_tables():
    schema = SCHEMA_DOC_PATH.read_text()
    seen_tables: set[str] = set()
    violations: list[str] = []
    for line_number, raw_line in enumerate(schema.splitlines(), 1):
        line = raw_line.strip()
        table_match = re.search(r'CREATE TABLE "([^"]+)"', line)
        if table_match:
            seen_tables.add(table_match.group(1))
            continue
        index_match = re.search(r'CREATE INDEX "?[A-Za-z0-9_]+"? ON "([^"]+)"', line)
        if index_match and index_match.group(1) not in seen_tables:
            violations.append(f"line {line_number}: {line}")
    assert violations == []


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
            strategic_objective=FakeLob("project objective"),
            priority=3,
            created_at=now,
            updated_at=now,
        )
    )
    assert project.description == "project description"
    assert project.success_criteria == "project success"
    assert project.strategic_objective == "project objective"

    solution = SolutionRead.model_validate(
        SimpleNamespace(
            solution_id="solution-1",
            project_id="project-1",
            solution_name="Solution",
            version="1.0.0",
            status=SolutionStatus.not_started,
            rag_status=RagStatus.green,
            rag_reason=FakeLob("solution rag reason"),
            description=FakeLob("solution description"),
            success_criteria=FakeLob("solution success"),
            problem_statement=FakeLob("solution problem"),
            blockers=FakeLob("solution blockers"),
            risks=FakeLob("solution risks"),
            priority=3,
            created_at=now,
            updated_at=now,
        )
    )
    assert solution.description == "solution description"
    assert solution.success_criteria == "solution success"
    assert solution.problem_statement == "solution problem"
    assert solution.rag_reason == "solution rag reason"
    assert solution.blockers == "solution blockers"
    assert solution.risks == "solution risks"

    subcomponent = SubcomponentRead.model_validate(
        SimpleNamespace(
            subcomponent_id="subcomponent-1",
            project_id="project-1",
            solution_id="solution-1",
            subcomponent_name="Subcomponent",
            status=SubcomponentStatus.to_do,
            priority=3,
            assignee="Assignee",
            estimate_hours=None,
            blocked=True,
            blocker_note=FakeLob("subcomponent blocker"),
            done_criteria=FakeLob("subcomponent done"),
            created_at=now,
            updated_at=now,
        )
    )
    assert subcomponent.blocker_note == "subcomponent blocker"
    assert subcomponent.done_criteria == "subcomponent done"

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
            space_id="space-1",
            request_id="request-1",
            created_at=now,
        )
    )
    assert change.old_value == "old value"
    assert change.new_value == "new value"
    assert change.space_id == "space-1"
