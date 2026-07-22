from pathlib import Path

from sqlalchemy import create_engine, inspect

from backend.app.db.developer_mode_schema import DEVELOPER_MODE_TABLES, ensure_developer_mode_schema


REPO_ROOT = Path(__file__).resolve().parents[3]


def test_developer_mode_schema_bootstrap_is_additive_and_idempotent():
    engine = create_engine("sqlite://")

    ensure_developer_mode_schema(engine)
    ensure_developer_mode_schema(engine)

    inspector = inspect(engine)
    for table in DEVELOPER_MODE_TABLES:
        assert inspector.has_table(table.name)
        expected_indexes = {index.name for index in table.indexes}
        actual_indexes = {index["name"] for index in inspector.get_indexes(table.name)}
        assert expected_indexes <= actual_indexes


def test_home_lab_deploy_applies_developer_mode_schema_before_starting_app():
    workflow = (REPO_ROOT / ".github" / "workflows" / "deploy-homelab.yml").read_text(encoding="utf-8")

    build = workflow.index("docker compose build")
    migrate = workflow.index("python -m backend.app.db.developer_mode_schema")
    start = workflow.index("docker compose up -d")

    assert build < migrate < start
