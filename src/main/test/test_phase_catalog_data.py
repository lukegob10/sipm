from pathlib import Path

from backend.app.db.phase_catalog_data import ensure_phase_catalog
from backend.app.models import Phase, Program, Project, Solution, SolutionPhase
from backend.app.phase_catalog import CANONICAL_PHASE_IDS, CANONICAL_PHASES, canonical_phase_id


ROOT = Path(__file__).resolve().parents[3]
RESTORE_PHASES_SQL = ROOT / "docs" / "sql" / "20260728_restore_full_solution_phases_v1.sql"
DEPLOY_WORKFLOW = ROOT / ".github" / "workflows" / "deploy-homelab.yml"

EXPECTED_PHASES = (
    ("backlog", "Backlog", "Backlog", 1),
    ("requirements", "Planning", "Requirements", 2),
    ("controls_scoping", "Planning", "Controls & Scoping", 3),
    ("resourcing_timeline", "Planning", "Resourcing & Timeline", 4),
    ("poc", "Planning", "Proof of Concept", 5),
    ("delivery_success", "Planning", "Delivery and Success Criteria", 6),
    ("design", "Development", "Design", 7),
    ("build_docs", "Development", "Build & Documentation", 8),
    ("sandbox_deploy", "Development", "Sandbox Deployment", 9),
    ("socialization_signoff", "Development", "Socialization & Signoff", 10),
    ("deployment_prep", "Deployment & Testing", "Deployment Preparation", 11),
    ("dev_deploy", "Deployment & Testing", "DEV Deployment", 12),
    ("uat_deploy", "Deployment & Testing", "UAT Deployment", 13),
    ("prod_deploy", "Deployment & Testing", "PROD Deployment", 14),
    ("go_live", "Closure", "Go Live", 15),
    ("closure_signoff", "Closure", "Closure and Signoff", 16),
    ("handoff_offboarding", "Closure", "Handoff and offboarding", 17),
)


def test_canonical_catalog_restores_the_full_seventeen_phase_workflow():
    assert CANONICAL_PHASES == EXPECTED_PHASES
    assert CANONICAL_PHASE_IDS == tuple(row[0] for row in EXPECTED_PHASES)


def test_phase_ids_and_seven_phase_aliases_map_to_the_full_workflow():
    expected = {phase_id: phase_id for phase_id in CANONICAL_PHASE_IDS}
    expected.update(
        {
            "development": "build_docs",
            "testing": "uat_deploy",
            "deployment": "prod_deploy",
            "retired": "handoff_offboarding",
            "uat": "uat_deploy",
        }
    )

    assert {phase_id: canonical_phase_id(phase_id) for phase_id in expected} == expected
    assert canonical_phase_id("unknown-phase") == "backlog"
    assert canonical_phase_id(None) is None


def test_catalog_migration_is_idempotent_and_normalizes_solutions(db_sessionmaker):
    with db_sessionmaker() as session:
        program = Program(program_id="program-1", program_name="Program")
        project = Project(
            project_id="project-1",
            program_id=program.program_id,
            project_name="Project",
            sponsor="Sponsor",
            owner="Owner",
        )
        solutions = [
            Solution(
                solution_id="solution-development",
                project_id=project.project_id,
                solution_name="Development solution",
                owner="Owner",
                current_phase="development",
            ),
            Solution(
                solution_id="solution-testing",
                project_id=project.project_id,
                solution_name="Testing solution",
                owner="Owner",
                current_phase="testing",
            ),
            Solution(
                solution_id="solution-deployment",
                project_id=project.project_id,
                solution_name="Deployment solution",
                owner="Owner",
                current_phase="deployment",
            ),
            Solution(
                solution_id="solution-retired",
                project_id=project.project_id,
                solution_name="Retired solution",
                owner="Owner",
                current_phase="retired",
            ),
            Solution(
                solution_id="solution-unknown",
                project_id=project.project_id,
                solution_name="Unknown solution",
                owner="Owner",
                current_phase="custom_phase",
            ),
            Solution(
                solution_id="solution-unassigned",
                project_id=project.project_id,
                solution_name="Unassigned solution",
                owner="Owner",
                current_phase=None,
            ),
        ]
        session.add_all(
            [
                program,
                project,
                *solutions,
                Phase(
                    phase_id="backlog",
                    phase_group="Legacy",
                    phase_name="Intake / Backlog",
                    sequence=99,
                ),
                Phase(
                    phase_id="development",
                    phase_group="Development",
                    phase_name="Development",
                    sequence=3,
                ),
                Phase(
                    phase_id="testing",
                    phase_group="Testing",
                    phase_name="Testing",
                    sequence=4,
                ),
                Phase(
                    phase_id="deployment",
                    phase_group="Deployment",
                    phase_name="Deployment",
                    sequence=5,
                ),
                Phase(
                    phase_id="retired",
                    phase_group="Retired",
                    phase_name="Retired",
                    sequence=7,
                ),
            ]
        )
        session.flush()
        session.add(
            SolutionPhase(
                solution_id="solution-development",
                phase_id="development",
                is_enabled=False,
                sequence_override=42,
            )
        )
        session.commit()
        engine = session.get_bind()

    ensure_phase_catalog(engine)
    ensure_phase_catalog(engine)

    with db_sessionmaker() as session:
        phase_rows = session.query(Phase).order_by(Phase.sequence.asc()).all()
        assert [
            (row.phase_id, row.phase_group, row.phase_name, row.sequence)
            for row in phase_rows
        ] == list(EXPECTED_PHASES)

        current_phases = {
            row.solution_id: row.current_phase
            for row in session.query(Solution).order_by(Solution.solution_id.asc()).all()
        }
        assert current_phases == {
            "solution-deployment": "prod_deploy",
            "solution-development": "build_docs",
            "solution-retired": "handoff_offboarding",
            "solution-testing": "uat_deploy",
            "solution-unassigned": None,
            "solution-unknown": "backlog",
        }

        expected_phase_ids = set(CANONICAL_PHASE_IDS)
        for solution_id in current_phases:
            rows = (
                session.query(SolutionPhase)
                .filter(SolutionPhase.solution_id == solution_id)
                .all()
            )
            assert {row.phase_id for row in rows} == expected_phase_ids
            assert all(row.is_enabled for row in rows)
            assert all(row.sequence_override is None for row in rows)


def test_restore_sql_and_home_lab_deploy_use_the_full_catalog_migration():
    sql = RESTORE_PHASES_SQL.read_text(encoding="utf-8")
    workflow = DEPLOY_WORKFLOW.read_text(encoding="utf-8")

    for phase_id in CANONICAL_PHASE_IDS:
        assert f"'{phase_id}'" in sql
    assert "python -m backend.app.db.phase_catalog_data" in workflow
