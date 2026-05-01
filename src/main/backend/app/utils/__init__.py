import csv
import getpass
import os
import re
from datetime import date
from io import StringIO
from typing import Any, Optional, Sequence, Tuple, Type, TypeVar

from .enums import ProjectStatus, SolutionStatus, SubcomponentStatus

EnumType = TypeVar("EnumType", ProjectStatus, SolutionStatus, SubcomponentStatus)


def get_default_user_id() -> str:
    """Return a best-effort user soeid based on the machine's username or overrides."""
    env_user = (
        os.getenv("SIPM_USER_SOEID")
        or os.getenv("USER")
        or os.getenv("USERNAME")
        or os.getenv("LOGNAME")
    )
    if env_user:
        return env_user
    try:
        return getpass.getuser()
    except Exception:
        return "unknown"


def read_text_value(value: Any) -> Optional[str]:
    """Coerce Oracle-style text/LOB values into plain strings."""
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, bytes):
        return value.decode("utf-8")

    reader = getattr(value, "read", None)
    if callable(reader):
        try:
            loaded = reader()
        except Exception:
            return str(value)
        if loaded is None:
            return None
        if isinstance(loaded, bytes):
            return loaded.decode("utf-8")
        return loaded if isinstance(loaded, str) else str(loaded)

    return str(value)


def normalize_str(value: Optional[str]) -> str:
    return value.strip() if isinstance(value, str) else ""


def normalize_status(raw: Optional[str], enum_cls: Type[EnumType]) -> EnumType:
    """Normalize user-provided status to an Enum value, tolerant of case/spacing/underscores."""
    if raw is None or raw == "":
        raise ValueError("status is required")
    cleaned = re.sub(r"[\s_]+", "", str(raw)).lower()
    for candidate in enum_cls:
        if re.sub(r"[\s_]+", "", candidate.value).lower() == cleaned:
            return candidate
    raise ValueError(f"invalid status '{raw}'")


def derive_abbreviation(name: str, existing: Sequence[str]) -> str:
    """Generate a 4-char abbreviation from a name and avoid collisions within `existing`."""
    alnum = re.sub(r"[^A-Za-z0-9]", "", name.upper())
    base = (alnum[:4] or "PRJX").ljust(4, "X")[:4]
    existing_set = set(existing)
    if base not in existing_set:
        return base
    # Try suffixing digits while keeping length 4 (e.g., ABC1, AB12)
    for suffix in range(1, 100):
        suffix_str = str(suffix)
        candidate = f"{base[: 4 - len(suffix_str)]}{suffix_str}"
        candidate = candidate.ljust(4, "X")[:4]
        if candidate not in existing_set:
            return candidate
    raise ValueError("could not derive unique abbreviation")


def parse_priority(raw: Optional[str], default: int = 3) -> int:
    if raw is None or raw == "":
        return default
    try:
        val = int(raw)
    except (TypeError, ValueError):
        raise ValueError("priority must be an integer")
    return max(0, min(5, val))


def parse_date(raw: Optional[str]) -> Optional[date]:
    if not raw:
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError:
        raise ValueError(f"invalid date '{raw}', expected YYYY-MM-DD")


def read_csv(file_bytes: bytes) -> Tuple[list, list]:
    """Return (rows, errors) from a CSV byte stream using utf-8 decode."""
    errors = []
    try:
        text = file_bytes.decode("utf-8-sig")
    except UnicodeDecodeError:
        return [], ["Could not decode file as UTF-8"]
    reader = csv.DictReader(StringIO(text))
    if reader.fieldnames is None:
        return [], ["Missing CSV header row"]
    rows = [row for row in reader]
    return rows, errors


def enable_all_phases(session, solution_id: str) -> None:
    """Ensure all phases are enabled for a solution (idempotent)."""
    from ..models import Phase, SolutionPhase

    phases = session.query(Phase).order_by(Phase.sequence.asc()).all()
    now_phases = []
    for ph in phases:
        existing = (
            session.query(SolutionPhase)
            .filter(SolutionPhase.solution_id == solution_id)
            .filter(SolutionPhase.phase_id == ph.phase_id)
            .first()
        )
        if existing:
            existing.is_enabled = True
            existing.sequence_override = None
            now_phases.append(existing)
        else:
            now_phases.append(
                SolutionPhase(
                    solution_id=solution_id,
                    phase_id=ph.phase_id,
                    is_enabled=True,
                    sequence_override=None,
                )
            )
    for row in now_phases:
        session.add(row)
