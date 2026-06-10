#!/usr/bin/env python3
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


def env(name: str, default: str | None = None) -> str | None:
    value = os.environ.get(name)
    return value if value not in (None, "") else default


def normalize_base_url(value: str) -> str:
    return value.rstrip("/")


def json_out(value: Any) -> None:
    print(json.dumps(value, indent=2, sort_keys=True))


class SipmClient:
    def __init__(
        self,
        *,
        base_url: str,
        token: str,
        default_space_id: str | None = None,
        proxy: str | None = None,
    ) -> None:
        self.base_url = normalize_base_url(base_url)
        self.token = token
        self.default_space_id = default_space_id
        handlers: list[urllib.request.BaseHandler] = []
        if proxy:
            handlers.append(urllib.request.ProxyHandler({"http": proxy, "https": proxy}))
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
        if query:
            clean_query = {k: v for k, v in query.items() if v not in (None, "")}
            if clean_query:
                url = f"{url}?{urllib.parse.urlencode(clean_query)}"
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/json",
        }
        effective_space_id = space_id or self.default_space_id
        if effective_space_id:
            headers["X-Space-Id"] = effective_space_id
        data = None
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(url, data=data, headers=headers, method=method.upper())
        try:
            with self.opener.open(req, timeout=30) as response:
                raw = response.read().decode("utf-8")
                return json.loads(raw) if raw else None
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            try:
                detail = json.loads(raw)
            except json.JSONDecodeError:
                detail = raw
            raise SystemExit(json.dumps({"status": exc.code, "error": detail}, indent=2))

    def list_spaces(self) -> list[dict[str, Any]]:
        value = self.request("GET", "/spaces")
        return value if isinstance(value, list) else value.get("value", [])

    def resolve_space_id(self, space: str | None) -> str:
        if not space:
            if self.default_space_id:
                return self.default_space_id
            raise SystemExit("Provide --space, --space-id, or SIPM_SPACE_ID.")
        spaces = self.list_spaces()
        target = space.strip().lower()
        for row in spaces:
            if target in {
                str(row.get("space_id", "")).lower(),
                str(row.get("slug", "")).lower(),
                str(row.get("name", "")).lower(),
            }:
                return str(row["space_id"])
        raise SystemExit(f"Space not found: {space}")

    def work_graph(self, *, space_id: str, **filters: Any) -> dict[str, Any]:
        return self.request("GET", "/agent/work-graph", space_id=space_id, query=filters)

    def find_project(
        self,
        *,
        space_id: str,
        project_name: str | None = None,
        project_id: str | None = None,
    ) -> dict[str, Any]:
        graph = self.work_graph(space_id=space_id, project_id=project_id, limit=200)
        records = graph.get("records", [])
        if project_id:
            matches = [row for row in records if row.get("project_id") == project_id]
        else:
            target = str(project_name or "").strip().lower()
            matches = [row for row in records if str(row.get("project_name", "")).lower() == target]
        if len(matches) != 1:
            raise SystemExit(f"Expected one project match, found {len(matches)}.")
        return matches[0]

    def find_solution(
        self,
        *,
        space_id: str,
        solution_name: str | None = None,
        solution_id: str | None = None,
        project_name: str | None = None,
        project_id: str | None = None,
    ) -> dict[str, Any]:
        query: dict[str, Any] = {"limit": 200}
        if project_id:
            query["project_id"] = project_id
        if solution_id:
            query["solution_id"] = solution_id
        graph = self.work_graph(space_id=space_id, **query)
        projects = graph.get("records", [])
        if project_name:
            target_project = project_name.strip().lower()
            projects = [
                row for row in projects if str(row.get("project_name", "")).lower() == target_project
            ]
        solutions: list[dict[str, Any]] = []
        for project in projects:
            for solution in project.get("solutions", []):
                item = dict(solution)
                item["project_name"] = project.get("project_name")
                solutions.append(item)
        if solution_id:
            matches = [row for row in solutions if row.get("solution_id") == solution_id]
        else:
            target = str(solution_name or "").strip().lower()
            matches = [row for row in solutions if str(row.get("solution_name", "")).lower() == target]
        if len(matches) != 1:
            raise SystemExit(f"Expected one solution match, found {len(matches)}.")
        return matches[0]

    def validate_patch(self, *, space_id: str, patch: dict[str, Any]) -> dict[str, Any]:
        return self.request("POST", "/agent/patches/validate", space_id=space_id, body=patch)

    def submit_change_request(self, *, space_id: str, patch: dict[str, Any]) -> dict[str, Any]:
        return self.request("POST", "/agent/change-requests", space_id=space_id, body=patch)


def load_patch(path: str) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def configured_client(args: argparse.Namespace) -> SipmClient:
    base_url = args.base_url or env("SIPM_BASE_URL")
    token = args.token or env("SIPM_AGENT_TOKEN") or env("SIPM_TOKEN")
    if not base_url:
        raise SystemExit("Provide --base-url or SIPM_BASE_URL.")
    if not token:
        raise SystemExit("Provide --token or SIPM_AGENT_TOKEN.")
    return SipmClient(
        base_url=base_url,
        token=token,
        default_space_id=args.space_id or env("SIPM_SPACE_ID"),
        proxy=args.proxy or env("SIPM_PROXY"),
    )


def add_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--base-url", help="SIPM app root, for example http://sipm/project-manager")
    parser.add_argument("--token", help="Service-account API token. Prefer SIPM_AGENT_TOKEN.")
    parser.add_argument("--space-id", help="Explicit SIPM space_id. Prefer resolving with --space.")
    parser.add_argument("--proxy", help="Optional HTTP(S) proxy URL. Prefer SIPM_PROXY.")


def main() -> int:
    parser = argparse.ArgumentParser(description="SIPM approval-gated agent API helper")
    add_common(parser)
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list-spaces", help="List spaces accessible to the token")

    graph = sub.add_parser("work-graph", help="Read scoped project/solution/task context")
    graph.add_argument("--space", help="Space name, slug, or ID")
    graph.add_argument("--project-id")
    graph.add_argument("--solution-id")
    graph.add_argument("--project-name", help="Client-side filter by exact project name")
    graph.add_argument("--status")
    graph.add_argument("--owner-user-soeid")
    graph.add_argument("--assignee-user-soeid")
    graph.add_argument("--updated-since")
    graph.add_argument("--limit", type=int, default=50)

    resolve = sub.add_parser("resolve-solution", help="Resolve a solution and print IDs/timestamps")
    resolve.add_argument("--space", help="Space name, slug, or ID")
    resolve.add_argument("--project-name")
    resolve.add_argument("--project-id")
    resolve.add_argument("--solution-name")
    resolve.add_argument("--solution-id")

    validate = sub.add_parser("validate-patch", help="Validate a raw agent patch JSON file")
    validate.add_argument("--space", help="Space name, slug, or ID")
    validate.add_argument("--patch-file", required=True)

    submit = sub.add_parser("submit-change-request", help="Submit a raw patch JSON file for approval")
    submit.add_argument("--space", help="Space name, slug, or ID")
    submit.add_argument("--patch-file", required=True)

    propose = sub.add_parser("propose-solution-update", help="Submit a pending solution update proposal")
    propose.add_argument("--space", help="Space name, slug, or ID")
    propose.add_argument("--project-name")
    propose.add_argument("--project-id")
    propose.add_argument("--solution-name")
    propose.add_argument("--solution-id")
    propose.add_argument("--description")
    propose.add_argument("--due-date")
    propose.add_argument("--status")
    propose.add_argument("--priority", type=int)
    propose.add_argument("--owner")
    propose.add_argument("--owner-user-soeid")
    propose.add_argument("--assignee")
    propose.add_argument("--assignee-user-soeid")
    propose.add_argument("--reason", required=True)
    propose.add_argument("--idempotency-key")
    propose.add_argument("--validate-only", action="store_true")

    args = parser.parse_args()
    client = configured_client(args)

    if args.command == "list-spaces":
        json_out(client.list_spaces())
        return 0

    space_id = client.resolve_space_id(getattr(args, "space", None))

    if args.command == "work-graph":
        payload = client.work_graph(
            space_id=space_id,
            project_id=args.project_id,
            solution_id=args.solution_id,
            status=args.status,
            owner_user_soeid=args.owner_user_soeid,
            assignee_user_soeid=args.assignee_user_soeid,
            updated_since=args.updated_since,
            limit=args.limit,
        )
        if args.project_name:
            target = args.project_name.strip().lower()
            payload["records"] = [
                row for row in payload.get("records", [])
                if str(row.get("project_name", "")).lower() == target
            ]
        json_out(payload)
        return 0

    if args.command == "resolve-solution":
        json_out(
            client.find_solution(
                space_id=space_id,
                solution_name=args.solution_name,
                solution_id=args.solution_id,
                project_name=args.project_name,
                project_id=args.project_id,
            )
        )
        return 0

    if args.command in {"validate-patch", "submit-change-request"}:
        patch = load_patch(args.patch_file)
        if args.command == "validate-patch":
            json_out(client.validate_patch(space_id=space_id, patch=patch))
        else:
            json_out(client.submit_change_request(space_id=space_id, patch=patch))
        return 0

    if args.command == "propose-solution-update":
        solution = client.find_solution(
            space_id=space_id,
            solution_name=args.solution_name,
            solution_id=args.solution_id,
            project_name=args.project_name,
            project_id=args.project_id,
        )
        fields = {
            "description": args.description,
            "due_date": args.due_date,
            "status": args.status,
            "priority": args.priority,
            "owner": args.owner,
            "owner_user_soeid": args.owner_user_soeid,
            "assignee": args.assignee,
            "assignee_user_soeid": args.assignee_user_soeid,
        }
        fields = {key: value for key, value in fields.items() if value is not None}
        if not fields:
            raise SystemExit("Provide at least one mutable solution field.")
        patch = {
            "dry_run": False,
            "reason": args.reason,
            "idempotency_key": args.idempotency_key or f"solution-{solution['solution_id']}-{int(time.time())}",
            "operations": [
                {
                    "client_operation_id": "update-solution",
                    "op": "update",
                    "entity": "solution",
                    "id": solution["solution_id"],
                    "if_updated_at": solution["updated_at"],
                    "fields": fields,
                }
            ],
        }
        if args.validate_only:
            json_out(client.validate_patch(space_id=space_id, patch=patch))
        else:
            json_out(client.submit_change_request(space_id=space_id, patch=patch))
        return 0

    parser.error("Unknown command")
    return 2


if __name__ == "__main__":
    sys.exit(main())
