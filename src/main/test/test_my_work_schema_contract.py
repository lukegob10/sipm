from pathlib import Path

from sqlalchemy import Text
from sqlalchemy.dialects import oracle
from sqlalchemy.schema import CreateTable

from backend.app import models


MY_WORK_PERSONAL_STATE_SQL_PATH = (
    Path(__file__).resolve().parents[3] / "docs/sql/20260729_my_work_personal_state_v1.sql"
)


def test_my_work_personal_state_migration_is_rerunnable_and_matches_metadata():
    sql = MY_WORK_PERSONAL_STATE_SQL_PATH.read_text(encoding="utf-8")
    table = models.UserTaskState.__table__
    ddl = str(CreateTable(table).compile(dialect=oracle.dialect()))

    assert "WHERE table_name = 'TB_TA_PM_USER_TASK_STATES'" in sql
    assert "AND column_name = 'BUCKET'" in sql
    assert "AND column_name = 'REMINDER_AT'" in sql
    assert "AND column_name = 'PRIVATE_NOTE'" in sql
    assert "ADD (bucket VARCHAR2(16 CHAR) DEFAULT ''later'' NOT NULL)" in sql
    assert "ADD (reminder_at DATE)" in sql
    assert "ADD (private_note CLOB)" in sql
    assert "bucket VARCHAR2(16 CHAR) NOT NULL" in ddl
    assert "reminder_at DATE" in ddl
    assert "private_note CLOB" in ddl
    assert isinstance(table.c.private_note.type, Text)
