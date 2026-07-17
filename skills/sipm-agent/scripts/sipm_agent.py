#!/usr/bin/env python3
"""Small stdlib-only client for SIPM's approval-gated Agent API."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any
from uuid import uuid4


def env(name: str, default: str | None = None) -> str | None:
    value = os.environ.get(name)
    return value if value not in (None, "") else default


def json_out(value: Any) -> None:
    print(json.dumps(value, indent=2, sort_keys=True))


class SipmClient:
    def __init__(
        self,
        base_url: str,
        token: str,
        *,
        default_space_id: str | None = None,
        proxy: str | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.default_space_id = default_space_id
        handlers: list[urllib.request.BaseHandler] = []
        if proxy:
            handlers.append(
                urllib.request.ProxyHandler({"http": proxy, "https": proxy})
            )
        self.opener = urllib.request.build_opener(*handlers)

    def request(
        self,
        method: str,
        path: str,
        *,
        space_id: str | None = None,
        query: dict[str, Any] | None = None,
        body: dict[str, Any] | None = None,
    ) -> Any:
        url = f"{self.base_url}/api{path}"
        clean_query = {
            key: value
            for key, value in (query or {}).items()
            if value not in (None, "")
        }
        if clean_query:
            url = f"{url}?{urllib.parse.urlencode(clean_query)}"
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/json",
        }
        effective_space = space_id or self.default_space_id
        if effective_space:
            headers["X-Space-Id"] = effective_space
        data = None
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(
            url, data=data, headers=headers, method=method.upper()
        )
        try:
            with self.opener.open(request, timeout=30) as response:
                raw = response.read().decode("utf-8")
                return json.loads(raw) if raw else None
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            try:
                error = json.loads(raw)
            except json.JSONDecodeError:
                error = {"message": raw}
            raise SystemExit(json.dumps({"status": exc.code, "error": error}, indent=2))

    def all_pages(
        self,
        path: str,
        *,
        space_id: str | None = None,
        query: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        params = dict(query or {})
        records: list[dict[str, Any]] = []
        template: dict[str, Any] = {}
        while True:
            page = self.request("GET", path, space_id=space_id, query=params)
            template = dict(page)
            records.extend(page.get("records", []))
            cursor = page.get("next_cursor")
            if not page.get("has_more") or not cursor:
                break
            params["cursor"] = cursor
        template["records"] = records
        template["next_cursor"] = None
        template["has_more"] = False
        return template

    def resolve_space_id(self, space: str | None) -> str:
        if not space:
            if self.default_space_id:
                return self.default_space_id
            raise SystemExit("Provide --space, --space-id, or SIPM_SPACE_ID.")
        target = space.strip().lower()
        page = self.all_pages("/agent/spaces", query={"limit": 200})
        matches = [
            row
            for row in page["records"]
            if target
            in {
                str(row.get("space_id", "")).lower(),
                str(row.get("slug", "")).lower(),
                str(row.get("name", "")).lower(),
            }
        ]
        if len(matches) != 1:
            raise SystemExit(
                f"Expected one accessible space match, found {len(matches)} for: {space}"
            )
        return str(matches[0]["space_id"])

    def get_detail(
        self, entity_type: str, entity_id: str, *, space_id: str
    ) -> dict[str, Any]:
        plural = {
            "program": "programs",
            "project": "projects",
            "solution": "solutions",
            "task": "tasks",
        }[entity_type]
        return self.request("GET", f"/agent/{plural}/{entity_id}", space_id=space_id)

    def find_work(
        self,
        entity_type: str,
        *,
        space_id: str,
        entity_id: str | None = None,
        exact_name: str | None = None,
        parent_id: str | None = None,
    ) -> dict[str, Any]:
        if entity_id:
            return self.get_detail(entity_type, entity_id, space_id=space_id)
        page = self.request(
            "GET",
            "/agent/work-items",
            space_id=space_id,
            query={
                "entity_type": entity_type,
                "exact_name": exact_name,
                "parent_id": parent_id,
                "limit": 2,
            },
        )
        records = page.get("records", [])
        if len(records) != 1 or page.get("has_more"):
            raise SystemExit(
                f"Expected one {entity_type} match, found {len(records)} or more."
            )
        return self.get_detail(entity_type, records[0]["entity_id"], space_id=space_id)


def load_json(path: str) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def client_from_args(args: argparse.Namespace, *, human: bool = False) -> SipmClient:
    base_url = args.base_url or env("SIPM_BASE_URL")
    token = (
        (args.human_token or env("SIPM_HUMAN_TOKEN"))
        if human
        else (args.token or env("SIPM_AGENT_TOKEN") or env("SIPM_TOKEN"))
    )
    if not base_url:
        raise SystemExit("Provide --base-url or SIPM_BASE_URL.")
    if not token:
        variable = "SIPM_HUMAN_TOKEN" if human else "SIPM_AGENT_TOKEN"
        raise SystemExit(f"Provide the appropriate token flag or {variable}.")
    return SipmClient(
        base_url,
        token,
        default_space_id=args.space_id or env("SIPM_SPACE_ID"),
        proxy=args.proxy or env("SIPM_PROXY"),
    )


def space_for(client: SipmClient, args: argparse.Namespace) -> str:
    return client.resolve_space_id(getattr(args, "space", None))


def add_space(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--space", help="Accessible space name, slug, or ID")


def main() -> int:
    parser = argparse.ArgumentParser(description="SIPM Agent API helper")
    parser.add_argument(
        "--base-url", help="SIPM app root, e.g. http://sipm/project-manager"
    )
    parser.add_argument(
        "--token", help="Service-account token; prefer SIPM_AGENT_TOKEN"
    )
    parser.add_argument(
        "--human-token",
        help="Human access-session token for delegated review; prefer SIPM_HUMAN_TOKEN",
    )
    parser.add_argument(
        "--space-id", help="Default exact space ID; prefer SIPM_SPACE_ID"
    )
    parser.add_argument("--proxy", help="Optional HTTP(S) proxy; prefer SIPM_PROXY")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("manifest", help="Show server capabilities and safety boundaries")
    spaces = sub.add_parser(
        "list-spaces", help="List accessible spaces with cursor traversal"
    )
    spaces.add_argument("--all", action="store_true")
    spaces.add_argument("--limit", type=int, default=50)
    spaces.add_argument("--cursor")

    sub.add_parser(
        "reference-data", help="Show authoritative fields, enums, filters, and limits"
    )

    search = sub.add_parser(
        "search-work", help="Search one typed work collection server-side"
    )
    add_space(search)
    search.add_argument(
        "--entity-type",
        choices=["program", "project", "solution", "task"],
        required=True,
    )
    search.add_argument("--entity-id")
    search.add_argument("--parent-id")
    search.add_argument("--exact-name")
    search.add_argument("--query")
    search.add_argument("--status")
    search.add_argument("--principal-soeid")
    search.add_argument("--lifecycle", choices=["active", "archived"], default="active")
    search.add_argument("--updated-since")
    search.add_argument("--limit", type=int, default=50)
    search.add_argument("--cursor")
    search.add_argument("--all", action="store_true")

    detail = sub.add_parser("get-work", help="Fetch one complete work item directly")
    add_space(detail)
    detail.add_argument(
        "--entity-type",
        choices=["program", "project", "solution", "task"],
        required=True,
    )
    detail.add_argument("--id", required=True)

    people = sub.add_parser(
        "list-people", help="Resolve assignable people, roles, and capacity"
    )
    add_space(people)
    people.add_argument("--query")
    people.add_argument("--soeid")
    people.add_argument("--role")
    people.add_argument("--limit", type=int, default=50)
    people.add_argument("--cursor")
    people.add_argument("--all", action="store_true")
    teams = sub.add_parser("list-teams", help="List teams and default capacity")
    add_space(teams)
    teams.add_argument("--query")
    teams.add_argument("--limit", type=int, default=50)
    teams.add_argument("--cursor")
    teams.add_argument("--all", action="store_true")
    members = sub.add_parser(
        "list-team-members", help="List one team's roles and capacity"
    )
    add_space(members)
    members.add_argument("--team-id", required=True)
    members.add_argument("--limit", type=int, default=50)
    members.add_argument("--cursor")
    members.add_argument("--all", action="store_true")

    graph = sub.add_parser("work-graph", help="Fetch bounded contextual project graphs")
    add_space(graph)
    graph.add_argument("--project-id")
    graph.add_argument("--solution-id")
    graph.add_argument("--task-id")
    graph.add_argument("--status")
    graph.add_argument("--owner-user-soeid")
    graph.add_argument("--assignee-user-soeid")
    graph.add_argument("--updated-since")
    graph.add_argument("--projection", choices=["summary", "full"], default="summary")
    graph.add_argument("--limit", type=int, default=50)
    graph.add_argument("--cursor")
    graph.add_argument("--all", action="store_true")

    for name, help_text in (
        ("validate-patch", "Validate a patch without persistence"),
        ("submit-change-request", "Submit a validated patch for approval"),
    ):
        command = sub.add_parser(name, help=help_text)
        add_space(command)
        command.add_argument("--patch-file", required=True)

    update = sub.add_parser(
        "propose-update", help="Build and validate/submit one optimistic update"
    )
    add_space(update)
    update.add_argument(
        "--entity-type",
        choices=["program", "project", "solution", "task"],
        required=True,
    )
    update.add_argument("--id", required=True)
    update.add_argument("--fields-json", required=True, help="JSON object of fields")
    update.add_argument("--reason", required=True)
    update.add_argument("--idempotency-key")
    update.add_argument("--validate-only", action="store_true")

    archive = sub.add_parser(
        "propose-archive", help="Validate or submit one soft-archive proposal"
    )
    add_space(archive)
    archive.add_argument(
        "--entity-type",
        choices=["program", "project", "solution", "task"],
        required=True,
    )
    archive.add_argument("--id", required=True)
    archive.add_argument("--reason", required=True)
    archive.add_argument("--idempotency-key")
    archive.add_argument("--validate-only", action="store_true")

    requests = sub.add_parser(
        "list-change-requests", help="List owned service-account requests"
    )
    add_space(requests)
    requests.add_argument("--status", default="pending")
    requests.add_argument("--limit", type=int, default=100)
    requests.add_argument("--cursor")
    requests.add_argument("--all", action="store_true")
    get_request = sub.add_parser("get-change-request", help="Get one owned request")
    add_space(get_request)
    get_request.add_argument("--request-id", required=True)
    replace_request = sub.add_parser(
        "replace-change-request",
        help="Replace one owned pending request while keeping its ID",
    )
    add_space(replace_request)
    replace_request.add_argument("--request-id", required=True)
    replace_request.add_argument("--patch-file", required=True)
    cancel = sub.add_parser(
        "cancel-change-request", help="Cancel one owned pending request"
    )
    add_space(cancel)
    cancel.add_argument("--request-id", required=True)
    poll = sub.add_parser(
        "poll-change-request", help="Poll until a request reaches a terminal state"
    )
    add_space(poll)
    poll.add_argument("--request-id", required=True)
    poll.add_argument("--interval", type=float, default=2.0)
    poll.add_argument("--timeout", type=float, default=120.0)

    audit = sub.add_parser(
        "audit-feed", help="Traverse scoped audit events for verification"
    )
    add_space(audit)
    audit.add_argument("--entity-type")
    audit.add_argument("--entity-id")
    audit.add_argument("--request-id")
    audit.add_argument("--since")
    audit.add_argument("--limit", type=int, default=100)
    audit.add_argument("--cursor")
    audit.add_argument("--all", action="store_true")

    review = sub.add_parser(
        "review-request", help="Fetch an immutable diff using a human session token"
    )
    add_space(review)
    review.add_argument("--request-id", required=True)
    for action in ("delegated-approve", "delegated-reject"):
        command = sub.add_parser(
            action,
            help=f"{action.split('-')[1].title()} an explicitly reviewed request",
        )
        add_space(command)
        command.add_argument("--request-id", required=True)
        command.add_argument("--observed-updated-at", required=True)
        command.add_argument("--review-note")

    args = parser.parse_args()
    human_command = args.command in {
        "review-request",
        "delegated-approve",
        "delegated-reject",
    }
    client = client_from_args(args, human=human_command)

    if args.command == "manifest":
        json_out(client.request("GET", "/agent/manifest"))
        return 0
    if args.command == "list-spaces":
        query = {"limit": args.limit, "cursor": args.cursor}
        json_out(
            client.all_pages("/agent/spaces", query=query)
            if args.all
            else client.request("GET", "/agent/spaces", query=query)
        )
        return 0
    if args.command == "reference-data":
        json_out(client.request("GET", "/agent/reference-data"))
        return 0

    space_id = space_for(client, args)
    if args.command == "search-work":
        query = {
            "entity_type": args.entity_type,
            "entity_id": args.entity_id,
            "parent_id": args.parent_id,
            "exact_name": args.exact_name,
            "q": args.query,
            "status": args.status,
            "principal_soeid": args.principal_soeid,
            "lifecycle": args.lifecycle,
            "updated_since": args.updated_since,
            "limit": args.limit,
            "cursor": args.cursor,
        }
        json_out(
            client.all_pages("/agent/work-items", space_id=space_id, query=query)
            if args.all
            else client.request(
                "GET", "/agent/work-items", space_id=space_id, query=query
            )
        )
        return 0
    if args.command == "get-work":
        json_out(client.get_detail(args.entity_type, args.id, space_id=space_id))
        return 0
    if args.command == "list-people":
        query = {
            "q": args.query,
            "soeid": args.soeid,
            "role": args.role,
            "limit": args.limit,
            "cursor": args.cursor,
        }
        json_out(
            client.all_pages("/agent/people", space_id=space_id, query=query)
            if args.all
            else client.request("GET", "/agent/people", space_id=space_id, query=query)
        )
        return 0
    if args.command == "list-teams":
        query = {"q": args.query, "limit": args.limit, "cursor": args.cursor}
        json_out(
            client.all_pages("/agent/teams", space_id=space_id, query=query)
            if args.all
            else client.request("GET", "/agent/teams", space_id=space_id, query=query)
        )
        return 0
    if args.command == "list-team-members":
        path = f"/agent/teams/{args.team_id}/members"
        query = {"limit": args.limit, "cursor": args.cursor}
        json_out(
            client.all_pages(path, space_id=space_id, query=query)
            if args.all
            else client.request("GET", path, space_id=space_id, query=query)
        )
        return 0
    if args.command == "work-graph":
        query = {
            "project_id": args.project_id,
            "solution_id": args.solution_id,
            "task_id": args.task_id,
            "status": args.status,
            "owner_user_soeid": args.owner_user_soeid,
            "assignee_user_soeid": args.assignee_user_soeid,
            "updated_since": args.updated_since,
            "projection": args.projection,
            "limit": args.limit,
            "cursor": args.cursor,
        }
        json_out(
            client.all_pages("/agent/work-graph", space_id=space_id, query=query)
            if args.all
            else client.request(
                "GET", "/agent/work-graph", space_id=space_id, query=query
            )
        )
        return 0
    if args.command in {"validate-patch", "submit-change-request"}:
        path = (
            "/agent/patches/validate"
            if args.command == "validate-patch"
            else "/agent/change-requests"
        )
        json_out(
            client.request(
                "POST", path, space_id=space_id, body=load_json(args.patch_file)
            )
        )
        return 0
    if args.command in {"propose-update", "propose-archive"}:
        detail_value = client.get_detail(args.entity_type, args.id, space_id=space_id)
        operation = {
            "client_operation_id": args.command,
            "op": "update" if args.command == "propose-update" else "archive",
            "entity": args.entity_type,
            "id": args.id,
            "if_updated_at": detail_value["updated_at"],
            "fields": json.loads(args.fields_json)
            if args.command == "propose-update"
            else {},
        }
        patch = {
            "dry_run": False,
            "reason": args.reason,
            "idempotency_key": args.idempotency_key or str(uuid4()),
            "operations": [operation],
        }
        path = (
            "/agent/patches/validate"
            if args.validate_only
            else "/agent/change-requests"
        )
        json_out(client.request("POST", path, space_id=space_id, body=patch))
        return 0
    if args.command == "list-change-requests":
        query = {"status": args.status, "limit": args.limit, "cursor": args.cursor}
        json_out(
            client.all_pages("/agent/change-requests", space_id=space_id, query=query)
            if args.all
            else client.request(
                "GET", "/agent/change-requests", space_id=space_id, query=query
            )
        )
        return 0
    if args.command == "get-change-request":
        json_out(
            client.request(
                "GET", f"/agent/change-requests/{args.request_id}", space_id=space_id
            )
        )
        return 0
    if args.command == "replace-change-request":
        current = client.request(
            "GET", f"/agent/change-requests/{args.request_id}", space_id=space_id
        )
        patch = load_json(args.patch_file)
        json_out(
            client.request(
                "PUT",
                f"/agent/change-requests/{args.request_id}",
                space_id=space_id,
                body={
                    "if_request_updated_at": current["updated_at"],
                    "reason": patch.get("reason"),
                    "operations": patch.get("operations"),
                },
            )
        )
        return 0
    if args.command == "cancel-change-request":
        json_out(
            client.request(
                "POST",
                f"/agent/change-requests/{args.request_id}/cancel",
                space_id=space_id,
                body={},
            )
        )
        return 0
    if args.command == "poll-change-request":
        deadline = time.monotonic() + args.timeout
        while True:
            value = client.request(
                "GET", f"/agent/change-requests/{args.request_id}", space_id=space_id
            )
            if value.get("status") not in {"pending"} or time.monotonic() >= deadline:
                json_out(value)
                return 0 if value.get("status") != "pending" else 1
            time.sleep(max(0.2, min(args.interval, 30.0)))
    if args.command == "audit-feed":
        query = {
            "entity_type": args.entity_type,
            "entity_id": args.entity_id,
            "request_id": args.request_id,
            "since": args.since,
            "limit": args.limit,
            "cursor": args.cursor,
        }
        json_out(
            client.all_pages("/agent/audit-feed", space_id=space_id, query=query)
            if args.all
            else client.request(
                "GET", "/agent/audit-feed", space_id=space_id, query=query
            )
        )
        return 0
    if args.command == "review-request":
        json_out(
            client.request(
                "GET",
                f"/agent/change-requests/{args.request_id}/delegated-review",
                space_id=space_id,
            )
        )
        return 0
    if args.command in {"delegated-approve", "delegated-reject"}:
        action = args.command.removeprefix("delegated-")
        body = {
            "confirm_change_request_id": args.request_id,
            "if_request_updated_at": args.observed_updated_at,
            "review_note": args.review_note,
        }
        json_out(
            client.request(
                "POST",
                f"/agent/change-requests/{args.request_id}/delegated-{action}",
                space_id=space_id,
                body=body,
            )
        )
        return 0
    parser.error("Unknown command")
    return 2


if __name__ == "__main__":
    sys.exit(main())
