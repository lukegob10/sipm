"""
Lightweight, idempotent schema migrations for environments without Alembic.

This focuses on additive changes (new columns/tables/indexes) to align with the
“Solution = Deliverable” schema. It is safe to run multiple times.
"""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine


_STRICT_SPACE_TABLES = (
    "projects",
    "solutions",
    "subcomponents",
    "resource_allocations",
    "teams",
    "team_members",
    "planning_windows",
    "project_charters",
    "project_plans",
    "project_decision_logs",
    "sow_documents",
    "checklist_items",
    "external_documents",
    "ai_requests",
    "ai_sessions",
    "ai_tool_calls",
    "ai_query_metrics",
)


def _has_column(inspector, table: str, column: str) -> bool:
    return any(col["name"] == column for col in inspector.get_columns(table))


def _add_column(engine: Engine, table: str, column: str, ddl: str) -> None:
    inspector = inspect(engine)
    if _has_column(inspector, table, column):
        return
    with engine.begin() as conn:
        conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}"))


def _create_index(engine: Engine, name: str, table: str, columns: str, unique: bool = False) -> None:
    clause = "UNIQUE INDEX" if unique else "INDEX"
    with engine.begin() as conn:
        conn.execute(text(f"CREATE {clause} IF NOT EXISTS {name} ON {table} ({columns})"))


def _create_sqlite_not_null_triggers(engine: Engine, table: str, column: str) -> None:
    insert_trigger = f"trg_{table}_{column}_nn_ins"
    update_trigger = f"trg_{table}_{column}_nn_upd"
    with engine.begin() as conn:
        conn.execute(
            text(
                f"""
                CREATE TRIGGER IF NOT EXISTS {insert_trigger}
                BEFORE INSERT ON {table}
                FOR EACH ROW
                WHEN NEW.{column} IS NULL
                BEGIN
                    SELECT RAISE(ABORT, '{table}.{column} is required');
                END;
                """
            )
        )
        conn.execute(
            text(
                f"""
                CREATE TRIGGER IF NOT EXISTS {update_trigger}
                BEFORE UPDATE ON {table}
                FOR EACH ROW
                WHEN NEW.{column} IS NULL
                BEGIN
                    SELECT RAISE(ABORT, '{table}.{column} is required');
                END;
                """
            )
        )


def _enforce_not_null(engine: Engine, table: str, column: str) -> None:
    dialect = engine.dialect.name
    if dialect == "sqlite":
        _create_sqlite_not_null_triggers(engine, table, column)
        return

    statement = None
    if dialect.startswith("postgres"):
        statement = f"ALTER TABLE {table} ALTER COLUMN {column} SET NOT NULL"
    elif dialect == "oracle":
        statement = f"ALTER TABLE {table} MODIFY ({column} NOT NULL)"
    if not statement:
        return
    try:
        with engine.begin() as conn:
            conn.execute(text(statement))
    except Exception:
        # Keep migrations resilient across heterogeneous managed environments.
        # Application-level guards and strict query scoping still prevent cross-space reads.
        return


def run_schema_migrations(engine: Engine) -> None:
    from ..models import (
        Base,
        Space,
        SpaceMembership,
        ExternalRef,
        SolutionWeeklySnapshot,
        SOWDocument,
        ChecklistItem,
        AIRequest,
        AISession,
        AIToolCall,
        AIQueryMetric,
        ProjectCardDigest,
        SolutionCardDigest,
        TaskCardDigest,
        ProjectCharter,
        ProjectPlan,
        ProjectDecisionLog,
        ExternalDocument,
    )  # avoid circular imports

    inspector = inspect(engine)

    # New tables
    Base.metadata.create_all(
        bind=engine,
        tables=[
            Space.__table__,
            SpaceMembership.__table__,
            SolutionWeeklySnapshot.__table__,
            ExternalRef.__table__,
            SOWDocument.__table__,
            ChecklistItem.__table__,
            AIRequest.__table__,
            AISession.__table__,
            AIToolCall.__table__,
            AIQueryMetric.__table__,
            ProjectCardDigest.__table__,
            SolutionCardDigest.__table__,
            TaskCardDigest.__table__,
            ProjectCharter.__table__,
            ProjectPlan.__table__,
            ProjectDecisionLog.__table__,
            ExternalDocument.__table__,
        ],
        checkfirst=True,
    )

    inspector = inspect(engine)
    if inspector.has_table("spaces"):
        with engine.begin() as conn:
            row = conn.execute(
                text(
                    "SELECT space_id FROM spaces "
                    "WHERE slug = :slug AND deleted_at IS NULL "
                    "ORDER BY created_at ASC LIMIT 1"
                ),
                {"slug": "main"},
            ).first()
            if row:
                default_space_id = row[0]
            else:
                default_space_id = str(uuid4())
                now = datetime.now(timezone.utc).replace(tzinfo=None)
                conn.execute(
                    text(
                        "INSERT INTO spaces (space_id, name, slug, is_active, archived_at, created_at, updated_at, deleted_at) "
                        "VALUES (:space_id, :name, :slug, :is_active, :archived_at, :created_at, :updated_at, :deleted_at)"
                    ),
                    {
                        "space_id": default_space_id,
                        "name": "Main",
                        "slug": "main",
                        "is_active": True,
                        "archived_at": None,
                        "created_at": now,
                        "updated_at": now,
                        "deleted_at": None,
                    },
                )

            users = conn.execute(text("SELECT user_id, role FROM users")).all()
            now = datetime.now(timezone.utc).replace(tzinfo=None)
            for user_id, role in users:
                membership_role = "space_admin" if (role or "").strip().lower() == "global_admin" else "member"
                existing = conn.execute(
                    text(
                        "SELECT membership_id, role, deleted_at "
                        "FROM space_memberships "
                        "WHERE space_id = :space_id AND user_id = :user_id "
                        "ORDER BY created_at ASC LIMIT 1"
                    ),
                    {"space_id": default_space_id, "user_id": user_id},
                ).first()
                if existing:
                    membership_id, existing_role, deleted_at = existing
                    if deleted_at is not None:
                        reactivated_role = (
                            "space_admin"
                            if membership_role == "space_admin"
                            else ((existing_role or "").strip().lower() or "member")
                        )
                        conn.execute(
                            text(
                                "UPDATE space_memberships "
                                "SET role = :role, status = :status, updated_at = :updated_at, deleted_at = :deleted_at "
                                "WHERE membership_id = :membership_id"
                            ),
                            {
                                "membership_id": membership_id,
                                "role": reactivated_role,
                                "status": "active",
                                "updated_at": now,
                                "deleted_at": None,
                            },
                        )
                    continue
                conn.execute(
                    text(
                        "INSERT INTO space_memberships "
                        "(membership_id, space_id, user_id, role, status, created_at, updated_at, deleted_at) "
                        "VALUES (:membership_id, :space_id, :user_id, :role, :status, :created_at, :updated_at, :deleted_at)"
                    ),
                    {
                        "membership_id": str(uuid4()),
                        "space_id": default_space_id,
                        "user_id": user_id,
                        "role": membership_role,
                        "status": "active",
                        "created_at": now,
                        "updated_at": now,
                        "deleted_at": None,
                    },
                )

    # Projects: governance/strategy fields
    _add_column(engine, "projects", "space_id", "TEXT")
    _create_index(engine, "idx_project_space_id", "projects", "space_id")
    _add_column(engine, "projects", "sponsor_user_soeid", "TEXT")
    _add_column(engine, "projects", "strategic_objective", "TEXT")
    _add_column(engine, "projects", "priority", "INTEGER DEFAULT 3")
    _create_index(engine, "idx_project_sponsor_user_soeid", "projects", "sponsor_user_soeid")

    # Solutions: core workflow fields
    _add_column(engine, "solutions", "space_id", "TEXT")
    _create_index(engine, "idx_solution_space_id", "solutions", "space_id")
    _add_column(engine, "solutions", "problem_statement", "TEXT")
    _add_column(engine, "solutions", "owner_user_soeid", "TEXT")
    _add_column(engine, "solutions", "assignee_user_soeid", "TEXT")
    _add_column(engine, "solutions", "approver_user_soeid", "TEXT")
    _add_column(engine, "solutions", "key_stakeholder", "TEXT")
    _add_column(engine, "solutions", "blockers", "TEXT")
    _add_column(engine, "solutions", "risks", "TEXT")
    _add_column(engine, "solutions", "impact_confidence", "TEXT")
    _add_column(engine, "solutions", "planned_start_date", "DATE")
    _add_column(engine, "solutions", "rag_reason", "TEXT")
    _add_column(engine, "solutions", "rag_confidence", "REAL")
    _add_column(engine, "solutions", "capacity_hours", "INTEGER DEFAULT 0")
    _add_column(engine, "solutions", "completed_at", "DATETIME")

    # Solution indexes for ownership and status
    _create_index(engine, "idx_solution_owner_user_soeid", "solutions", "owner_user_soeid")
    _create_index(engine, "idx_solution_assignee_user_soeid", "solutions", "assignee_user_soeid")
    _create_index(engine, "idx_solution_status", "solutions", "status")
    _create_index(engine, "idx_solution_rag_status", "solutions", "rag_status")
    _create_index(engine, "idx_solution_due_date", "solutions", "due_date")

    # Subcomponents: assignee + execution helpers
    _add_column(engine, "subcomponents", "space_id", "TEXT")
    _create_index(engine, "idx_subcomponent_space_id", "subcomponents", "space_id")
    _add_column(engine, "subcomponents", "assignee_user_soeid", "TEXT")
    _add_column(engine, "subcomponents", "estimate_hours", "INTEGER")
    _add_column(engine, "subcomponents", "blocked", "BOOLEAN DEFAULT 0")
    _add_column(engine, "subcomponents", "blocker_note", "TEXT")
    _add_column(engine, "subcomponents", "done_criteria", "TEXT")
    _add_column(engine, "subcomponents", "capacity_hours", "INTEGER DEFAULT 0")
    _create_index(engine, "idx_subcomponent_assignee_user_soeid", "subcomponents", "assignee_user_soeid")
    _create_index(engine, "idx_subcomponent_blocked", "subcomponents", "blocked")

    # Resource allocations: assignee + uniqueness
    _add_column(engine, "resource_allocations", "space_id", "TEXT")
    _create_index(engine, "idx_resource_allocations_space_id", "resource_allocations", "space_id")
    _add_column(engine, "resource_allocations", "assignee_user_soeid", "TEXT")
    _add_column(engine, "resource_allocations", "month_start", "DATE")
    _add_column(engine, "resource_allocations", "fte_months", "REAL DEFAULT 0")
    _create_index(engine, "idx_alloc_week_assignee_user_soeid", "resource_allocations", "week_start, assignee_user_soeid")
    _create_index(engine, "idx_alloc_month_assignee_user_soeid", "resource_allocations", "month_start, assignee_user_soeid")
    _create_index(
        engine,
        "uix_alloc_unique_assignment",
        "resource_allocations",
        "work_item_type, work_item_id, assignee_user_soeid, week_start, window_id",
        unique=True,
    )

    _add_column(engine, "teams", "space_id", "TEXT")
    _create_index(engine, "idx_teams_space_id", "teams", "space_id")
    _add_column(engine, "teams", "default_capacity_fte_month", "REAL DEFAULT 0")
    _add_column(engine, "team_members", "space_id", "TEXT")
    _create_index(engine, "idx_team_members_space_id", "team_members", "space_id")
    _add_column(engine, "team_members", "capacity_fte_month", "REAL")
    _add_column(engine, "planning_windows", "space_id", "TEXT")
    _create_index(engine, "idx_planning_windows_space_id", "planning_windows", "space_id")

    # Users: capacity + team tag
    _add_column(engine, "users", "team_tag", "TEXT")
    _add_column(engine, "users", "capacity_hours", "INTEGER DEFAULT 40")
    _add_column(engine, "users", "capacity_fte_month", "REAL DEFAULT 1")
    _create_index(engine, "idx_user_team_tag", "users", "team_tag")
    _add_column(engine, "users", "temp_password_hash", "TEXT")
    _add_column(engine, "users", "temp_password_expires_at", "DATETIME")
    _add_column(engine, "users", "force_password_reset", "BOOLEAN DEFAULT 0")
    _add_column(engine, "users", "password_changed_at", "DATETIME")

    _add_column(engine, "change_log", "space_id", "TEXT")
    _create_index(engine, "idx_change_log_space_id", "change_log", "space_id")

    # AI sessions: persist last entity context
    _add_column(engine, "ai_requests", "space_id", "TEXT")
    _create_index(engine, "idx_ai_requests_space_id", "ai_requests", "space_id")
    _add_column(engine, "ai_sessions", "space_id", "TEXT")
    _create_index(engine, "idx_ai_sessions_space_id", "ai_sessions", "space_id")
    _add_column(engine, "ai_sessions", "entity_type", "TEXT")
    _add_column(engine, "ai_sessions", "entity_id", "TEXT")
    _add_column(engine, "ai_tool_calls", "space_id", "TEXT")
    _create_index(engine, "idx_ai_tool_calls_space_id", "ai_tool_calls", "space_id")
    _add_column(engine, "ai_query_metrics", "space_id", "TEXT")
    _create_index(engine, "idx_ai_query_metrics_space_id", "ai_query_metrics", "space_id")

    # AI tool telemetry fields
    _add_column(engine, "ai_tool_calls", "payload_bytes", "INTEGER")
    _add_column(engine, "ai_tool_calls", "output_bytes", "INTEGER")
    _add_column(engine, "ai_tool_calls", "payload_tokens", "INTEGER")
    _add_column(engine, "ai_tool_calls", "output_tokens", "INTEGER")
    _add_column(engine, "ai_tool_calls", "cache_hit", "BOOLEAN")
    _add_column(engine, "ai_tool_calls", "drilldown", "BOOLEAN")
    _add_column(engine, "ai_tool_calls", "context_bytes", "INTEGER")
    _create_index(engine, "idx_ai_tool_calls_tool_name", "ai_tool_calls", "tool_name")
    _create_index(engine, "idx_ai_tool_calls_created", "ai_tool_calls", "created_at")

    # Document workbench: revision state + SOW approvals
    _add_column(engine, "project_charters", "space_id", "TEXT")
    _create_index(engine, "idx_project_charters_space_id", "project_charters", "space_id")
    _add_column(engine, "project_plans", "space_id", "TEXT")
    _create_index(engine, "idx_project_plans_space_id", "project_plans", "space_id")
    _add_column(engine, "project_decision_logs", "space_id", "TEXT")
    _create_index(engine, "idx_project_decision_logs_space_id", "project_decision_logs", "space_id")
    _add_column(engine, "sow_documents", "space_id", "TEXT")
    _create_index(engine, "idx_sow_documents_space_id", "sow_documents", "space_id")
    _add_column(engine, "checklist_items", "space_id", "TEXT")
    _create_index(engine, "idx_checklist_items_space_id", "checklist_items", "space_id")
    _add_column(engine, "external_documents", "space_id", "TEXT")
    _create_index(engine, "idx_external_documents_space_id", "external_documents", "space_id")

    _add_column(engine, "project_charters", "state", "TEXT DEFAULT 'draft'")
    _add_column(engine, "project_plans", "state", "TEXT DEFAULT 'draft'")

    _add_column(engine, "sow_documents", "title", "TEXT")
    _add_column(engine, "sow_documents", "state", "TEXT DEFAULT 'draft'")
    _add_column(engine, "sow_documents", "approval_state", "TEXT DEFAULT 'draft'")
    _add_column(engine, "sow_documents", "approval_requested_at", "DATETIME")
    _add_column(engine, "sow_documents", "approval_requested_by_user_id", "TEXT")
    _add_column(engine, "sow_documents", "approval_decided_at", "DATETIME")
    _add_column(engine, "sow_documents", "approval_decided_by_user_id", "TEXT")
    _add_column(engine, "sow_documents", "approval_note", "TEXT")

    _create_index(engine, "idx_project_charter_state", "project_charters", "state")
    _create_index(engine, "idx_project_plan_state", "project_plans", "state")
    _create_index(engine, "idx_sow_state", "sow_documents", "state")
    _create_index(engine, "idx_sow_approval_state", "sow_documents", "approval_state")

    # Best-effort backfill for legacy rows.
    inspector = inspect(engine)
    if inspector.has_table("spaces"):
        with engine.begin() as conn:
            row = conn.execute(
                text(
                    "SELECT space_id FROM spaces "
                    "WHERE slug = :slug AND deleted_at IS NULL "
                    "ORDER BY created_at ASC LIMIT 1"
                ),
                {"slug": "main"},
            ).first()
            if row:
                default_space_id = row[0]
                for table in _STRICT_SPACE_TABLES:
                    try:
                        conn.execute(
                            text(f"UPDATE {table} SET space_id = :space_id WHERE space_id IS NULL"),
                            {"space_id": default_space_id},
                        )
                    except Exception:
                        continue

    # Backfill FTE-month compatibility fields from legacy hour-based columns.
    inspector = inspect(engine)
    with engine.begin() as conn:
        dialect = engine.dialect.name
        if inspector.has_table("users"):
            try:
                conn.execute(
                    text(
                        "UPDATE users "
                        "SET capacity_fte_month = ROUND(COALESCE(capacity_hours, 40) / 40.0, 3) "
                        "WHERE capacity_fte_month IS NULL OR capacity_fte_month <= 0"
                    )
                )
            except Exception:
                pass
        if inspector.has_table("teams"):
            try:
                conn.execute(
                    text(
                        "UPDATE teams "
                        "SET default_capacity_fte_month = ROUND(COALESCE(default_capacity_per_week, 0) / 40.0, 3) "
                        "WHERE default_capacity_fte_month IS NULL OR default_capacity_fte_month = 0"
                    )
                )
            except Exception:
                pass
        if inspector.has_table("team_members"):
            try:
                conn.execute(
                    text(
                        "UPDATE team_members "
                        "SET capacity_fte_month = ROUND(COALESCE(hours_capacity, 0) / 40.0, 3) "
                        "WHERE capacity_fte_month IS NULL AND hours_capacity IS NOT NULL"
                    )
                )
            except Exception:
                pass
        if inspector.has_table("resource_allocations"):
            try:
                if dialect == "sqlite":
                    conn.execute(
                        text(
                            "UPDATE resource_allocations "
                            "SET month_start = COALESCE(month_start, DATE(week_start, 'start of month')) "
                            "WHERE week_start IS NOT NULL"
                        )
                    )
                else:
                    conn.execute(
                        text(
                            "UPDATE resource_allocations "
                            "SET month_start = COALESCE(month_start, week_start) "
                            "WHERE week_start IS NOT NULL"
                        )
                    )
                conn.execute(
                    text(
                        "UPDATE resource_allocations "
                        "SET fte_months = ROUND(COALESCE(hours, 0) / 160.0, 3) "
                        "WHERE fte_months IS NULL OR fte_months = 0"
                    )
                )
            except Exception:
                pass

    # Enforce strict non-null space IDs for scoped data.
    inspector = inspect(engine)
    for table in _STRICT_SPACE_TABLES:
        if not inspector.has_table(table):
            continue
        _enforce_not_null(engine, table, "space_id")
