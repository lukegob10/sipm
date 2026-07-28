from __future__ import annotations

from typing import Final, TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.orm import Query, Session


CANONICAL_PHASES: Final[tuple[tuple[str, str, str, int], ...]] = (
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

CANONICAL_PHASE_IDS: Final[tuple[str, ...]] = tuple(row[0] for row in CANONICAL_PHASES)
DEFAULT_PHASE_ID: Final[str] = "backlog"

LEGACY_PHASE_ID_MAP: Final[dict[str, str]] = {
    **{phase_id: phase_id for phase_id in CANONICAL_PHASE_IDS},
    "development": "build_docs",
    "testing": "uat_deploy",
    "deployment": "prod_deploy",
    "retired": "handoff_offboarding",
    "uat": "uat_deploy",
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
