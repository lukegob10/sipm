from __future__ import annotations

from sqlalchemy import inspect
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from ..models import Phase, Solution, SolutionPhase
from ..phase_catalog import CANONICAL_PHASE_IDS, CANONICAL_PHASES, canonical_phase_id
from .db import get_engine


REQUIRED_TABLES = (Phase.__table__, Solution.__table__, SolutionPhase.__table__)


def ensure_phase_catalog(bind: Engine | None = None) -> None:
    """Restore the canonical 17-phase workflow and enable it for every solution."""
    target = bind or get_engine()
    inspector = inspect(target)
    missing = [table.name for table in REQUIRED_TABLES if not inspector.has_table(table.name)]
    if missing:
        raise RuntimeError(f"Required phase catalog tables do not exist: {', '.join(missing)}")

    with Session(target) as session, session.begin():
        phases_by_id = {row.phase_id: row for row in session.query(Phase).all()}
        for phase_id, phase_group, phase_name, sequence in CANONICAL_PHASES:
            phase = phases_by_id.get(phase_id)
            if phase is None:
                phase = Phase(phase_id=phase_id)
                session.add(phase)
            phase.phase_group = phase_group
            phase.phase_name = phase_name
            phase.sequence = sequence

        session.flush()
        solution_phase_rows = session.query(SolutionPhase).all()
        rows_by_solution: dict[str, dict[str, SolutionPhase]] = {}
        for row in solution_phase_rows:
            rows_by_solution.setdefault(row.solution_id, {})[row.phase_id] = row

        for solution in session.query(Solution).all():
            solution.current_phase = canonical_phase_id(solution.current_phase)
            existing = rows_by_solution.get(solution.solution_id, {})
            for phase_id in CANONICAL_PHASE_IDS:
                row = existing.get(phase_id)
                if row is None:
                    session.add(
                        SolutionPhase(
                            solution_id=solution.solution_id,
                            phase_id=phase_id,
                            is_enabled=True,
                            sequence_override=None,
                        )
                    )
                    continue
                row.is_enabled = True
                row.sequence_override = None

        session.flush()
        session.query(SolutionPhase).filter(
            SolutionPhase.phase_id.notin_(CANONICAL_PHASE_IDS)
        ).delete(synchronize_session=False)
        session.flush()
        session.query(Phase).filter(Phase.phase_id.notin_(CANONICAL_PHASE_IDS)).delete(
            synchronize_session=False
        )


def main() -> None:
    ensure_phase_catalog()
    print("Canonical phase catalog is ready.")


if __name__ == "__main__":
    main()
