from datetime import datetime, timezone
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Phase

# Ordered seed list used by phase dropdowns and solution phase validation.
PHASES_SEED = [
    ("backlog", "Backlog", "Backlog"),
    ("requirements", "Planning", "Requirements"),
    ("controls_scoping", "Planning", "Controls & Scoping"),
    ("resourcing_timeline", "Planning", "Resourcing & Timeline"),
    ("poc", "Planning", "Proof of Concept"),
    ("delivery_success", "Planning", "Delivery and Success Criteria"),
    ("design", "Development", "Design"),
    ("build_docs", "Development", "Build & Documentation"),
    ("sandbox_deploy", "Development", "Sandbox Deployment"),
    ("socialization_signoff", "Development", "Socialization & Signoff"),
    ("deployment_prep", "Deployment & Testing", "Deployment Preparation"),
    ("dev_deploy", "Deployment & Testing", "DEV Deployment"),
    ("uat_deploy", "Deployment & Testing", "UAT Deployment"),
    ("prod_deploy", "Deployment & Testing", "PROD Deployment"),
    ("go_live", "Closure", "Go Live"),
    ("closure_signoff", "Closure", "Closure and Signoff"),
    ("handoff_offboarding", "Closure", "Handoff and offboarding"),
]


def seed_phases(session: Session) -> None:
    """Idempotently seed the global phases table."""
    existing = {row.phase_id for row in session.execute(select(Phase)).scalars().all()}
    now = datetime.now(timezone.utc)
    inserts: list[Phase] = []
    for seq, (phase_id, phase_group, phase_name) in enumerate(PHASES_SEED, start=1):
        if phase_id in existing:
            continue
        inserts.append(
            Phase(
                phase_id=phase_id,
                phase_group=phase_group,
                phase_name=phase_name,
                sequence=seq,
                created_at=now,
                updated_at=now,
            )
        )
    if inserts:
        session.add_all(inserts)
        session.commit()
