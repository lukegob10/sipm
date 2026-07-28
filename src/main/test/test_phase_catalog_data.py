from backend.app.db.phase_catalog_data import ensure_phase_catalog
from backend.app.models import Phase, Program, Project, Solution, SolutionPhase
from backend.app.phase_catalog import CANONICAL_PHASES, canonical_phase_id


def test_legacy_phase_ids_map_to_the_seven_phase_workflow():
    expected = {
        "backlog": "backlog",
        "requirements": "requirements",
        "controls_scoping": "requirements",
        "resourcing_timeline": "requirements",
        "poc": "requirements",
        "delivery_success": "requirements",
        "design": "requirements",
        "build_docs": "development",
        "sandbox_deploy": "development",
        "development": "development",
        "socialization_signoff": "testing",
        "dev_deploy": "testing",
        "uat": "testing",
        "uat_deploy": "testing",
        "testing": "testing",
        "deployment_prep": "deployment",
        "prod_deploy": "deployment",
        "deployment": "deployment",
        "go_live": "go_live",
        "closure_signoff": "retired",
        "handoff_offboarding": "retired",
        "retired": "retired",
    }

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
                current_phase="build_docs",
            ),
            Solution(
                solution_id="solution-testing",
                project_id=project.project_id,
                solution_name="Testing solution",
                owner="Owner",
                current_phase="uat_deploy",
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
                    phase_name="Backlog",
                    sequence=99,
                ),
                Phase(
                    phase_id="build_docs",
                    phase_group="Build",
                    phase_name="Build Documentation",
                    sequence=10,
                ),
                Phase(
                    phase_id="uat_deploy",
                    phase_group="Testing",
                    phase_name="UAT Deployment",
                    sequence=11,
                ),
            ]
        )
        session.flush()
        session.add(
            SolutionPhase(
                solution_id="solution-development",
                phase_id="build_docs",
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
            (row.phase_id, row.phase_name, row.phase_group, row.sequence)
            for row in phase_rows
        ] == [
            (phase_id, phase_name, phase_name, sequence)
            for phase_id, phase_name, sequence in CANONICAL_PHASES
        ]

        current_phases = {
            row.solution_id: row.current_phase
            for row in session.query(Solution).order_by(Solution.solution_id.asc()).all()
        }
        assert current_phases == {
            "solution-development": "development",
            "solution-testing": "testing",
            "solution-unassigned": None,
            "solution-unknown": "backlog",
        }

        expected_phase_ids = {phase_id for phase_id, _, _ in CANONICAL_PHASES}
        for solution_id in current_phases:
            rows = (
                session.query(SolutionPhase)
                .filter(SolutionPhase.solution_id == solution_id)
                .all()
            )
            assert {row.phase_id for row in rows} == expected_phase_ids
            assert all(row.is_enabled for row in rows)
            assert all(row.sequence_override is None for row in rows)
