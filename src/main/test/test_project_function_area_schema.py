from pathlib import Path

from sqlalchemy import Column, MetaData, String, Table, create_engine, inspect

from backend.app.db.project_function_area_schema import ensure_project_function_area_schema
from backend.app.models import Project


REPO_ROOT = Path(__file__).resolve().parents[3]


def test_project_function_area_schema_adds_missing_columns_and_is_rerunnable(tmp_path):
    engine = create_engine(f"sqlite+pysqlite:///{tmp_path / 'project-schema.db'}")
    metadata = MetaData()
    Table(
        Project.__table__.name,
        metadata,
        Column("project_id", String, primary_key=True),
    )
    metadata.create_all(engine)

    ensure_project_function_area_schema(engine)
    ensure_project_function_area_schema(engine)

    columns = {
        column["name"]: column for column in inspect(engine).get_columns(Project.__table__.name)
    }
    assert columns["function"]["nullable"] is True
    assert columns["area"]["nullable"] is True


def test_home_lab_deploy_applies_project_function_area_schema_before_starting_app():
    workflow = (REPO_ROOT / ".github" / "workflows" / "deploy-homelab.yml").read_text(
        encoding="utf-8"
    )

    build = workflow.index("docker compose build")
    migrate = workflow.index("python -m backend.app.db.project_function_area_schema")
    start = workflow.index("docker compose up -d")

    assert build < migrate < start
