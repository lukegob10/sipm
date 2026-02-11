#!/usr/bin/env python3
"""Grant, revoke, or list Jira-lite global_admin users via API requests."""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from typing import Any, Dict, Optional, Tuple
from urllib.parse import quote

try:
    import requests
except Exception as exc:  # pragma: no cover - CLI import guard
    sys.stderr.write(f"Failed to import requests: {exc}\n")
    raise SystemExit(1)


UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-"
    r"[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{12}$"
)


def _normalize_identifier(identifier: str) -> str:
    return str(identifier or "").strip().lower()


def _coerce_soeid(identifier: str) -> str:
    ident = _normalize_identifier(identifier)
    if "@" in ident:
        return ident.split("@", 1)[0]
    return ident


def _looks_like_user_id(identifier: str) -> bool:
    ident = _normalize_identifier(identifier)
    if not ident:
        return False
    if UUID_RE.match(ident):
        return True
    # Support non-UUID user IDs if they contain obvious separators.
    return "/" in ident or ":" in ident


def _extract_error_text(resp: requests.Response) -> str:
    try:
        payload = resp.json()
    except Exception:
        payload = None
    if isinstance(payload, dict):
        detail = payload.get("detail")
        if isinstance(detail, str) and detail.strip():
            return detail.strip()
        if "message" in payload and isinstance(payload.get("message"), str):
            return payload["message"]
        return json.dumps(payload)
    return (resp.text or "").strip() or "<empty response body>"


def _print_user(prefix: str, payload: Dict[str, Any]) -> None:
    print(
        f"{prefix} user_id={payload.get('user_id')} "
        f"soeid={payload.get('soeid')} "
        f"email={payload.get('email')} "
        f"role={payload.get('role')} "
        f"active={payload.get('is_active')}"
    )


def _base_headers() -> Dict[str, str]:
    return {"Content-Type": "application/json"}


def _ensure_auth(session: requests.Session, args: argparse.Namespace) -> int:
    access_token = (args.access_token or os.getenv("SIPM_ACCESS_TOKEN") or "").strip()
    if access_token:
        session.cookies.set("access_token", access_token)
        return 0

    soeid = (args.auth_soeid or os.getenv("SIPM_ADMIN_SOEID") or "").strip()
    password = (args.auth_password or os.getenv("SIPM_ADMIN_PASSWORD") or "").strip()
    if not soeid or not password:
        sys.stderr.write(
            "Authentication required. Provide --auth-soeid/--auth-password "
            "or set SIPM_ADMIN_SOEID/SIPM_ADMIN_PASSWORD "
            "(or --access-token / SIPM_ACCESS_TOKEN).\n"
        )
        return 2

    login_url = args.base_url.rstrip("/") + "/api/auth/login"
    resp = session.post(
        login_url,
        json={"soeid": soeid, "password": password},
        headers=_base_headers(),
        timeout=args.timeout_seconds,
    )
    if resp.status_code >= 400:
        sys.stderr.write(f"Login failed ({resp.status_code}): {_extract_error_text(resp)}\n")
        return 1
    return 0


def _request_json(
    session: requests.Session,
    *,
    method: str,
    url: str,
    timeout_seconds: int,
) -> Tuple[int, Optional[Any], Optional[str]]:
    try:
        resp = session.request(
            method=method,
            url=url,
            headers=_base_headers(),
            timeout=timeout_seconds,
        )
    except requests.RequestException as exc:
        return 0, None, f"Request failed: {exc}"

    if resp.status_code >= 400:
        return resp.status_code, None, _extract_error_text(resp)
    try:
        return resp.status_code, resp.json(), None
    except Exception:
        text = (resp.text or "").strip()
        return resp.status_code, text if text else None, None


def _resolve_user_endpoint(identifier: str) -> Tuple[str, str]:
    ident = _normalize_identifier(identifier)
    if "@" in ident:
        return "by-soeid", _coerce_soeid(ident)
    if _looks_like_user_id(ident):
        return "by-user-id", ident
    # Default to SOEID-like identifier.
    return "by-soeid", ident


def _grant_or_revoke(
    session: requests.Session,
    args: argparse.Namespace,
    *,
    grant: bool,
) -> int:
    endpoint_kind, normalized = _resolve_user_endpoint(args.identifier)
    method = "POST" if grant else "DELETE"
    action = "grant" if grant else "revoke"

    if endpoint_kind == "by-user-id":
        path = f"/api/users/{quote(normalized, safe='')}/global-admin"
    else:
        path = f"/api/users/by-soeid/{quote(normalized, safe='')}/global-admin"
    url = args.base_url.rstrip("/") + path

    if args.dry_run:
        print(f"DRY RUN: would {action} global_admin via {method} {url}")
        return 0

    status_code, payload, error = _request_json(
        session,
        method=method,
        url=url,
        timeout_seconds=args.timeout_seconds,
    )
    if error:
        # If SOEID lookup fails and identifier may be user_id, try user_id endpoint once.
        if endpoint_kind == "by-soeid" and status_code == 404 and _looks_like_user_id(normalized):
            retry_path = f"/api/users/{quote(normalized, safe='')}/global-admin"
            retry_url = args.base_url.rstrip("/") + retry_path
            status_code, payload, error = _request_json(
                session,
                method=method,
                url=retry_url,
                timeout_seconds=args.timeout_seconds,
            )
        if error:
            sys.stderr.write(f"{action.capitalize()} failed ({status_code}): {error}\n")
            return 1

    if isinstance(payload, dict):
        _print_user("Target:", payload)
        return 0

    print(payload)
    return 0


def _cmd_list(session: requests.Session, args: argparse.Namespace) -> int:
    active_only = "true" if args.active_only else "false"
    url = args.base_url.rstrip("/") + f"/api/users/global-admins?active_only={active_only}"
    status_code, payload, error = _request_json(
        session,
        method="GET",
        url=url,
        timeout_seconds=args.timeout_seconds,
    )
    if error:
        sys.stderr.write(f"List failed ({status_code}): {error}\n")
        return 1
    if not isinstance(payload, list):
        print(payload)
        return 0
    if not payload:
        print("No global_admin users found.")
        return 0
    print("global_admin users:")
    for user in payload:
        if isinstance(user, dict):
            _print_user("-", user)
    return 0


def _cmd_grant(session: requests.Session, args: argparse.Namespace) -> int:
    return _grant_or_revoke(session, args, grant=True)


def _cmd_revoke(session: requests.Session, args: argparse.Namespace) -> int:
    return _grant_or_revoke(session, args, grant=False)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage Jira-lite global_admin role assignments via API.")
    parser.add_argument(
        "--base-url",
        default=os.getenv("SIPM_BASE_URL", "http://127.0.0.1:8000"),
        help="Base URL for Jira-lite app (default: %(default)s)",
    )
    parser.add_argument(
        "--auth-soeid",
        default=os.getenv("SIPM_ADMIN_SOEID", ""),
        help="SOEID used to login before admin actions (fallback env: SIPM_ADMIN_SOEID)",
    )
    parser.add_argument(
        "--auth-password",
        default=os.getenv("SIPM_ADMIN_PASSWORD", ""),
        help="Password used to login before admin actions (fallback env: SIPM_ADMIN_PASSWORD)",
    )
    parser.add_argument(
        "--access-token",
        default=os.getenv("SIPM_ACCESS_TOKEN", ""),
        help="Existing access_token cookie value; skips login (fallback env: SIPM_ACCESS_TOKEN)",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=20,
        help="HTTP timeout in seconds (default: %(default)s)",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser("list", help="List global_admin users")
    list_parser.add_argument(
        "--active-only",
        action="store_true",
        help="Only list active global_admin users (default lists active + inactive)",
    )
    list_parser.set_defaults(func=_cmd_list)

    grant_parser = subparsers.add_parser("grant", help="Grant global_admin to a user")
    grant_parser.add_argument("identifier", help="SOEID, email, or user_id")
    grant_parser.add_argument("--dry-run", action="store_true", help="Preview request without sending it")
    grant_parser.set_defaults(func=_cmd_grant)

    revoke_parser = subparsers.add_parser("revoke", help="Revoke global_admin from a user")
    revoke_parser.add_argument("identifier", help="SOEID, email, or user_id")
    revoke_parser.add_argument("--dry-run", action="store_true", help="Preview request without sending it")
    revoke_parser.set_defaults(func=_cmd_revoke)
    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    try:
        session = requests.Session()
        needs_auth = not (args.command in {"grant", "revoke"} and bool(getattr(args, "dry_run", False)))
        if needs_auth:
            auth_code = _ensure_auth(session, args)
            if auth_code:
                return auth_code
        return int(args.func(session, args))
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
