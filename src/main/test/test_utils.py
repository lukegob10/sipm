from __future__ import annotations

import csv
from datetime import date
from io import StringIO

import pytest

from backend.app.utils.enums import ProjectStatus, SolutionStatus
from backend.app.models import Phase, Project, Solution, SolutionPhase
from backend.app.utils import (
    derive_abbreviation,
    enable_all_phases,
    get_default_user_id,
    normalize_status,
    parse_date,
    parse_priority,
    read_csv,
)


def test_get_default_user_id_prefers_env_and_falls_back(monkeypatch):
    monkeypatch.setenv("SIPM_USER_SOEID", "explicit-user")
    assert get_default_user_id() == "explicit-user"

    monkeypatch.delenv("SIPM_USER_SOEID", raising=False)
    for key in ("USER", "USERNAME", "LOGNAME"):
        monkeypatch.delenv(key, raising=False)

    import getpass

    monkeypatch.setattr(getpass, "getuser", lambda: "fallback-user")
    assert get_default_user_id() == "fallback-user"

    def boom():
        raise RuntimeError("no user")

    monkeypatch.setattr(getpass, "getuser", boom)
    assert get_default_user_id() == "unknown"


def test_normalize_status_tolerates_spacing_and_rejects_invalid():
    assert normalize_status("Not Started", ProjectStatus) == ProjectStatus.not_started
    assert normalize_status("on_hold", ProjectStatus) == ProjectStatus.on_hold
    with pytest.raises(ValueError, match="status is required"):
        normalize_status(None, ProjectStatus)
    with pytest.raises(ValueError, match="invalid status"):
        normalize_status("nope", ProjectStatus)


def test_derive_abbreviation_handles_collisions_and_exhaustion():
    assert derive_abbreviation("Alpha Beta", []) == "ALPH"
    assert derive_abbreviation("Alpha Beta", ["ALPH"]) == "ALP1"

    base = "ABCD"
    exhausted = {base}
    exhausted.update(f"{base[:3]}{i}" for i in range(1, 10))
    exhausted.update(f"{base[:2]}{i}" for i in range(10, 100))
    with pytest.raises(ValueError, match="could not derive unique abbreviation"):
        derive_abbreviation("ABCD", sorted(exhausted))


def test_parse_priority_bounds_and_errors():
    assert parse_priority(None, default=3) == 3
    assert parse_priority("", default=2) == 2
    assert parse_priority("-1", default=3) == 0
    assert parse_priority("99", default=3) == 5
    with pytest.raises(ValueError, match="priority must be an integer"):
        parse_priority("not-an-int", default=3)


def test_parse_date_validates_isoformat():
    assert parse_date("") is None
    assert parse_date(None) is None
    assert parse_date("2025-01-02") == date(2025, 1, 2)
    with pytest.raises(ValueError, match="invalid date"):
        parse_date("01/02/2025")


def test_read_csv_parses_rows_and_reports_decode_or_header_errors():
    rows, errors = read_csv("a,b\n1,2\n".encode("utf-8"))
    assert errors == []
    assert rows == [{"a": "1", "b": "2"}]

    rows, errors = read_csv(b"")
    assert rows == []
    assert errors == ["Missing CSV header row"]

    rows, errors = read_csv(b"\xff\xfe\xfd")
    assert rows == []
    assert errors == ["Could not decode file as UTF-8"]


def test_enable_all_phases_is_idempotent_and_resets_overrides(db_sessionmaker):
    with db_sessionmaker() as session:
        project = Project(
            project_name="P",
            status=ProjectStatus.not_started,
            sponsor="S",
        )
        session.add(project)
        session.commit()
        session.refresh(project)

        solution = Solution(
            project_id=project.project_id,
            solution_name="S",
            version="0.1.0",
            status=SolutionStatus.active,
            owner="Owner",
            assignee="",
        )
        session.add(solution)
        session.commit()
        session.refresh(solution)

        phases = [
            Phase(phase_id="p1", phase_group="G", phase_name="P1", sequence=1),
            Phase(phase_id="p2", phase_group="G", phase_name="P2", sequence=2),
        ]
        session.add_all(phases)
        session.commit()

        session.add(
            SolutionPhase(
                solution_id=solution.solution_id,
                phase_id="p1",
                is_enabled=False,
                sequence_override=99,
            )
        )
        session.commit()

        enable_all_phases(session, solution.solution_id)

        rows = (
            session.query(SolutionPhase)
            .filter(SolutionPhase.solution_id == solution.solution_id)
            .order_by(SolutionPhase.phase_id.asc())
            .all()
        )
        assert [r.phase_id for r in rows] == ["p1", "p2"]
        assert all(r.is_enabled is True for r in rows)
        assert all(r.sequence_override is None for r in rows)

        enable_all_phases(session, solution.solution_id)
        assert (
            session.query(SolutionPhase)
            .filter(SolutionPhase.solution_id == solution.solution_id)
            .count()
            == 2
        )
