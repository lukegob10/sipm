#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path


LANGUAGE_BY_SUFFIX = {
    ".css": "css",
    ".html": "html",
    ".js": "javascript",
    ".md": "markdown",
    ".py": "python",
    ".sql": "sql",
}

SCRIPT_EXTENSIONS = {
    ".bash",
    ".fish",
    ".js",
    ".pl",
    ".ps1",
    ".py",
    ".rb",
    ".sh",
    ".ts",
    ".zsh",
}

SURFACE_ORDER = (
    "ci-cd",
    "config",
    "data-db",
    "docs",
    "backend",
    "frontend",
    "scripts",
    "tests",
    "other",
)

SAMPLE_LIMIT = 5
MAX_SCAN_BYTES = 1_000_000


@dataclass
class ScriptRecord:
    rel_path: str
    path_refs: set[str] = field(default_factory=set)
    name_refs: set[str] = field(default_factory=set)

    @property
    def basename(self) -> str:
        return Path(self.rel_path).name

    @property
    def status(self) -> str:
        if not self.path_refs and not self.name_refs:
            return "likely-stale"
        if len(self.path_refs) >= 1:
            return "referenced"
        if len(self.name_refs) >= 2:
            return "referenced"
        return "needs-review"

    def sample_refs(self) -> list[str]:
        return sorted(self.path_refs | self.name_refs)[:SAMPLE_LIMIT]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Repo-local inventory and stale-script helpers for codebase review."
    )
    parser.add_argument(
        "command",
        choices=("inventory", "stale-scripts"),
        help="Which review helper to run.",
    )
    parser.add_argument(
        "--root",
        default=".",
        help="Repository root. Defaults to the current directory.",
    )
    return parser.parse_args()


def list_active_repo_files(root: Path) -> list[Path]:
    result = subprocess.run(
        [
            "git",
            "-C",
            str(root),
            "ls-files",
            "-z",
            "--cached",
            "--others",
            "--exclude-standard",
        ],
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        stderr = result.stderr.decode("utf-8", errors="ignore").strip()
        raise RuntimeError(f"git ls-files failed for {root}: {stderr or 'unknown error'}")

    rel_paths: list[Path] = []
    for raw in result.stdout.split(b"\0"):
        if not raw:
            continue
        rel = Path(raw.decode("utf-8", errors="ignore"))
        if (root / rel).is_file():
            rel_paths.append(rel)
    return sorted(rel_paths, key=lambda path: path.as_posix())


def classify_surface(rel_path: Path) -> str:
    rel = rel_path.as_posix()
    if rel.startswith(".github/"):
        return "ci-cd"
    if rel.startswith("scripts/"):
        return "scripts"
    if rel.startswith("docs/sql/"):
        return "data-db"
    if rel.startswith("docs/"):
        return "docs"
    if rel.startswith("src/main/backend/"):
        return "backend"
    if rel.startswith("src/main/ui/"):
        return "frontend"
    if rel.startswith("src/main/test/"):
        return "tests"
    if rel in {"src/main/requirements.in", "src/main/requirements.txt"}:
        return "config"
    if rel.startswith("src/main/") and rel_path.suffix.lower() in {".txt", ".in", ".toml", ".yaml", ".yml"}:
        return "config"
    return "other"


def classify_language(rel_path: Path) -> str | None:
    return LANGUAGE_BY_SUFFIX.get(rel_path.suffix.lower())


def build_inventory(root: Path) -> tuple[Counter[str], dict[str, list[str]]]:
    language_counts: Counter[str] = Counter()
    surfaces: dict[str, list[str]] = defaultdict(list)
    for rel_path in list_active_repo_files(root):
        language = classify_language(rel_path)
        if language:
            language_counts[language] += 1
        surfaces[classify_surface(rel_path)].append(rel_path.as_posix())
    return language_counts, surfaces


def render_inventory(root: Path) -> str:
    language_counts, surfaces = build_inventory(root)
    lines = [
        f"Repo active surface inventory for {root.resolve()}",
        "Source set: git-tracked files plus untracked non-ignored files.",
        "Ignored local noise: htmlcov, .venv, .pytest_cache, __pycache__, .git, and other git-ignored paths.",
    ]
    if language_counts:
        rendered_languages = ", ".join(
            f"{language}={language_counts[language]}"
            for language in sorted(language_counts)
        )
        lines.append(f"Languages: {rendered_languages}")
    else:
        lines.append("Languages: none")
    lines.append("")
    lines.append("Surfaces:")
    for surface in SURFACE_ORDER:
        paths = surfaces.get(surface, [])
        if not paths:
            lines.append(f"- {surface}: not present")
            continue
        sample = ", ".join(paths[:SAMPLE_LIMIT])
        lines.append(f"- {surface}: {len(paths)} paths")
        lines.append(f"  sample: {sample}")
    return "\n".join(lines)


def has_shebang(path: Path) -> bool:
    try:
        with path.open("rb") as handle:
            return handle.readline(256).startswith(b"#!")
    except OSError:
        return False


def is_probably_text(path: Path) -> bool:
    try:
        with path.open("rb") as handle:
            chunk = handle.read(4096)
    except OSError:
        return False
    return b"\0" not in chunk


def read_text(path: Path) -> str | None:
    try:
        if path.stat().st_size > MAX_SCAN_BYTES:
            return None
        return path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return None


def collect_script_candidates(root: Path, files: list[Path]) -> list[ScriptRecord]:
    candidates: list[ScriptRecord] = []
    for rel_path in files:
        if not rel_path.parts or rel_path.parts[0] != "scripts":
            continue
        abs_path = root / rel_path
        if not abs_path.is_file() or not is_probably_text(abs_path):
            continue
        if rel_path.suffix.lower() in SCRIPT_EXTENSIONS or has_shebang(abs_path) or os.access(abs_path, os.X_OK):
            candidates.append(ScriptRecord(rel_path=rel_path.as_posix()))
    return sorted(candidates, key=lambda record: record.rel_path)


def scan_script_references(root: Path, files: list[Path], candidates: list[ScriptRecord]) -> None:
    candidate_paths = {record.rel_path for record in candidates}
    patterns = []
    for record in candidates:
        basename_pattern = re.compile(
            rf"(?<![A-Za-z0-9_./\\\\-]){re.escape(record.basename)}(?![A-Za-z0-9_./\\\\-])"
        )
        patterns.append(
            (
                record,
                record.rel_path,
                record.rel_path.replace("/", "\\"),
                basename_pattern,
            )
        )

    for rel_path in files:
        rel_text = rel_path.as_posix()
        if rel_text in candidate_paths:
            continue
        content = read_text(root / rel_path)
        if not content:
            continue
        for record, posix_path, windows_path, basename_pattern in patterns:
            if posix_path in content or windows_path in content:
                record.path_refs.add(rel_text)
                continue
            if basename_pattern.search(content):
                record.name_refs.add(rel_text)


def render_stale_scripts(root: Path) -> str:
    files = list_active_repo_files(root)
    candidates = collect_script_candidates(root, files)
    scan_script_references(root, files, candidates)

    lines = [
        f"Repo-local stale script scan for {root.resolve()}",
        "Candidate set: files under scripts/ that are tracked or untracked and not git-ignored.",
        "Noise excluded automatically through git ls-files --exclude-standard.",
        "",
    ]
    if not candidates:
        lines.append("No script candidates found.")
        return "\n".join(lines)

    grouped: dict[str, list[ScriptRecord]] = defaultdict(list)
    for record in candidates:
        grouped[record.status].append(record)

    for status in ("likely-stale", "needs-review", "referenced"):
        lines.append(status.upper())
        records = grouped.get(status, [])
        if not records:
            lines.append("- none")
            continue
        for record in records:
            lines.append(
                f"- {record.rel_path} | path_refs={len(record.path_refs)} | name_refs={len(record.name_refs)}"
            )
            refs = record.sample_refs()
            if refs:
                lines.append(f"  refs: {', '.join(refs)}")
        lines.append("")
    return "\n".join(lines).rstrip()


def main() -> int:
    args = parse_args()
    root = Path(args.root).resolve()
    try:
        if args.command == "inventory":
            print(render_inventory(root))
            return 0
        if args.command == "stale-scripts":
            print(render_stale_scripts(root))
            return 0
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
