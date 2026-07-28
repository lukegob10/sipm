from __future__ import annotations

from typing import Final, TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.orm import Query, Session


CANONICAL_PHASES: Final[tuple[tuple[str, str, int], ...]] = (
    ("backlog", "Intake / Backlog", 1),
    ("requirements", "Requirements / Specification", 2),
    ("development", "Development", 3),
    ("testing", "Testing", 4),
    ("deployment", "Deployment", 5),
    ("go_live", "Go Live", 6),
    ("retired", "Retired", 7),
)

CANONICAL_PHASE_IDS: Final[tuple[str, ...]] = tuple(row[0] for row in CANONICAL_PHASES)
DEFAULT_PHASE_ID: Final[str] = "backlog"

LEGACY_PHASE_ID_MAP: Final[dict[str, str]] = {
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


def canonical_phase_id(value: object) -> str | None:
    phase_id = str(value or "").strip()
    if not phase_id:
        return None
    return LEGACY_PHASE_ID_MAP.get(phase_id, DEFAULT_PHASE_ID)


def canonical_phase_query(session: "Session") -> "Query":
    from .models import Phase

    return session.query(Phase).filter(Phase.phase_id.in_(CANONICAL_PHASE_IDS))


def get_canonical_phase(session: "Session", phase_id: str):
    from .models import Phase

    return canonical_phase_query(session).filter(Phase.phase_id == phase_id).first()


__all__ = [
    "CANONICAL_PHASES",
    "CANONICAL_PHASE_IDS",
    "DEFAULT_PHASE_ID",
    "LEGACY_PHASE_ID_MAP",
    "canonical_phase_id",
    "canonical_phase_query",
    "get_canonical_phase",
]
