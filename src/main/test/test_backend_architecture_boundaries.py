from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
SERVICES_DIR = REPO_ROOT / "src" / "main" / "backend" / "app" / "services"


def test_backend_services_do_not_import_route_modules():
    violations = []
    forbidden_patterns = (
        "backend.app.routes",
        "from ..routes",
        "from ...routes",
        "import ..routes",
        "import ...routes",
    )
    for path in sorted(SERVICES_DIR.glob("*.py")):
        text = path.read_text(encoding="utf-8")
        for pattern in forbidden_patterns:
            if pattern in text:
                violations.append(f"{path.relative_to(REPO_ROOT)} imports route layer via {pattern!r}")

    assert not violations, "Service layer must not depend on route modules:\n" + "\n".join(violations)
