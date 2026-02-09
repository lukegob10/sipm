#!/usr/bin/env python3 [Convert]::ToBase64String((1..64 | % {Get-Random -Minimum 0 -Maximum 256}))
"""Grant, revoke, or list Jira-lite global_admin users."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Optional


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_MAIN = REPO_ROOT / "src" / "main"
if str(SRC_MAIN) not in sys.path:
    sys.path.insert(0, str(SRC_MAIN))

try:
    from sqlalchemy.orm import Session
    from backend.app.db.db import SessionLocal
    from backend.app.models import User
except Exception as exc:  # pragma: no cover - CLI import guard
    sys.stderr.write(f"Failed to load backend modules: {exc}\n")
    raise SystemExit(1)


def _normalize_identifier(identifier: str) -> str:
    return identifier.strip().lower()


def _count_active_global_admins(session: Session) -> int:
    return (
        session.query(User)
        .filter(User.is_active.is_(True))
        .filter(User.role == "global_admin")
        .count()
    )


def _find_user(session: Session, identifier: str) -> Optional[User]:
    ident = _normalize_identifier(identifier)
    if not ident:
        return None
    if "@" in ident:
        return session.query(User).filter(User.email == ident).first()

    user = session.query(User).filter(User.soeid == ident).first()
    if user:
        return user
    return session.query(User).filter(User.user_id == ident).first()


def _print_user(prefix: str, user: User) -> None:
    print(
        f"{prefix} user_id={user.user_id} soeid={user.soeid} "
        f"email={user.email} role={user.role} active={user.is_active}"
    )


def _cmd_list(_args: argparse.Namespace) -> int:
    with SessionLocal() as session:
        admins = (
            session.query(User)
            .filter(User.role == "global_admin")
            .order_by(User.is_active.desc(), User.display_name.asc())
            .all()
        )
        if not admins:
            print("No global_admin users found.")
            return 0
        print("global_admin users:")
        for user in admins:
            _print_user("-", user)
    return 0


def _cmd_grant(args: argparse.Namespace) -> int:
    with SessionLocal() as session:
        user = _find_user(session, args.identifier)
        if not user:
            sys.stderr.write(f"User not found: {args.identifier}\n")
            return 1
        if (user.role or "").strip().lower() == "global_admin":
            _print_user("Already global_admin:", user)
            return 0

        before = user.role
        user.role = "global_admin"
        session.add(user)
        if args.dry_run:
            session.rollback()
            print(f"DRY RUN: would change role {before!r} -> 'global_admin'")
            _print_user("Target:", user)
            return 0

        session.commit()
        session.refresh(user)
        print(f"Updated role {before!r} -> 'global_admin'")
        _print_user("Target:", user)
    return 0


def _cmd_revoke(args: argparse.Namespace) -> int:
    with SessionLocal() as session:
        user = _find_user(session, args.identifier)
        if not user:
            sys.stderr.write(f"User not found: {args.identifier}\n")
            return 1
        if (user.role or "").strip().lower() != "global_admin":
            _print_user("Already non-global_admin:", user)
            return 0

        if user.is_active and _count_active_global_admins(session) <= 1:
            sys.stderr.write("Refusing to revoke: at least one active global_admin is required.\n")
            _print_user("Last active admin:", user)
            return 1

        before = user.role
        user.role = "user"
        session.add(user)
        if args.dry_run:
            session.rollback()
            print(f"DRY RUN: would change role {before!r} -> 'user'")
            _print_user("Target:", user)
            return 0

        session.commit()
        session.refresh(user)
        print(f"Updated role {before!r} -> 'user'")
        _print_user("Target:", user)
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage Jira-lite global_admin role assignments.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser("list", help="List global_admin users")
    list_parser.set_defaults(func=_cmd_list)

    grant_parser = subparsers.add_parser("grant", help="Grant global_admin to a user")
    grant_parser.add_argument("identifier", help="SOEID, email, or user_id")
    grant_parser.add_argument("--dry-run", action="store_true", help="Preview without saving changes")
    grant_parser.set_defaults(func=_cmd_grant)

    revoke_parser = subparsers.add_parser("revoke", help="Revoke global_admin from a user")
    revoke_parser.add_argument("identifier", help="SOEID, email, or user_id")
    revoke_parser.add_argument("--dry-run", action="store_true", help="Preview without saving changes")
    revoke_parser.set_defaults(func=_cmd_revoke)
    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
