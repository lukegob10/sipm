#!/usr/bin/env python3
from __future__ import annotations

import difflib
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    requirements_in = repo_root / "src" / "main" / "requirements.in"
    requirements_txt = repo_root / "src" / "main" / "requirements.txt"
    compile_command = "uv pip compile src/main/requirements.in -o src/main/requirements.txt --universal"

    if not requirements_in.exists():
        print(f"Missing source dependency file: {requirements_in}")
        return 2
    if not requirements_txt.exists():
        print(f"Missing lock file: {requirements_txt}")
        return 2

    uv_path = shutil.which("uv")
    if not uv_path:
        print("Missing `uv` in PATH. Install uv to verify dependency lock state.")
        return 2

    with tempfile.TemporaryDirectory(prefix="req-lock-check-") as tmpdir:
        generated = Path(tmpdir) / "requirements.generated.txt"
        shutil.copyfile(requirements_txt, generated)
        cmd = [
            uv_path,
            "pip",
            "compile",
            "src/main/requirements.in",
            "-o",
            str(generated),
            "--universal",
            "--custom-compile-command",
            compile_command,
            "--quiet",
        ]
        proc = subprocess.run(cmd, cwd=repo_root, text=True, capture_output=True)
        if proc.returncode != 0:
            print("Failed to compile requirements lock file via uv.")
            if proc.stdout:
                print(proc.stdout.strip())
            if proc.stderr:
                print(proc.stderr.strip())
            return proc.returncode

        expected = requirements_txt.read_text(encoding="utf-8").splitlines(keepends=True)
        actual = generated.read_text(encoding="utf-8").splitlines(keepends=True)

    if expected == actual:
        print("requirements.txt is up to date with requirements.in")
        return 0

    print("requirements.txt is out of date. Regenerate it with:")
    print(f"  {compile_command}")
    diff = difflib.unified_diff(
        expected,
        actual,
        fromfile="src/main/requirements.txt",
        tofile="generated",
        n=3,
    )
    sys.stdout.writelines(diff)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
