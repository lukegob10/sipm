#!/usr/bin/env python3
"""Request a temp password via /api/auth/admin-reset."""
from __future__ import annotations

import argparse
import json
import sys
import urllib.request
import urllib.error


def _post_json(url: str, payload: dict) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req) as resp:
        body = resp.read().decode("utf-8")
        if not body:
            return {}
        return json.loads(body)


def main() -> int:
    parser = argparse.ArgumentParser(description="Request a temp password via admin-reset.")
    parser.add_argument("identifier", help="SOEID or email")
    parser.add_argument(
        "--base-url",
        default="http://127.0.0.1:8000",
        help="Base URL for the Jira-lite app (default: http://127.0.0.1:8000)",
    )
    args = parser.parse_args()

    url = args.base_url.rstrip("/") + "/api/auth/admin-reset"
    try:
        result = _post_json(url, {"identifier": args.identifier})
    except urllib.error.HTTPError as exc:
        err_body = exc.read().decode("utf-8")
        sys.stderr.write(f"HTTP {exc.code}: {err_body}\n")
        return 1
    except urllib.error.URLError as exc:
        sys.stderr.write(f"Request failed: {exc}\n")
        return 1

    status = result.get("status", "")
    temp_password = result.get("temp_password")
    print(f"status: {status}")
    print(f"temp_password: {temp_password}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
