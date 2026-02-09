import ast
from pathlib import Path


ROUTES_DIR = Path(__file__).resolve().parents[1] / "backend" / "app" / "routes"

# These endpoints are intentionally global/read-only and do not need active-space context.
ALLOWED_NO_SPACE_DEP = {
    ("genai.py", "genai_intent"),
    ("genai.py", "genai_project_create"),
    ("phases.py", "list_phases"),
    ("spaces.py", "list_spaces"),
    ("workbench.py", "workbench_template"),
    ("workbench.py", "workbench_validate"),
}

SKIP_FILES = {"__init__.py", "auth.py", "sync.py"}
HTTP_DECORATORS = {"get", "post", "put", "patch", "delete", "options", "head"}


def _iter_route_functions():
    for path in sorted(ROUTES_DIR.glob("*.py")):
        if path.name in SKIP_FILES:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in tree.body:
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            is_route = False
            for dec in node.decorator_list:
                if (
                    isinstance(dec, ast.Call)
                    and isinstance(dec.func, ast.Attribute)
                    and isinstance(dec.func.value, ast.Name)
                    and dec.func.value.id == "router"
                    and dec.func.attr in HTTP_DECORATORS
                ):
                    is_route = True
                    break
            if is_route:
                yield path, node


def _depends_target(default_expr):
    if not (
        isinstance(default_expr, ast.Call)
        and isinstance(default_expr.func, ast.Name)
        and default_expr.func.id == "Depends"
        and default_expr.args
    ):
        return None
    return ast.unparse(default_expr.args[0])


def _is_space_enforced(dep_targets):
    for target in dep_targets:
        if target in {"current_space_dep", "current_space", "require_global_admin"}:
            return True
        if target.startswith("require_space_role("):
            return True
    return False


def test_protected_routes_require_space_or_global_admin_dependency():
    missing = []
    for path, fn in _iter_route_functions():
        key = (path.name, fn.name)
        if key in ALLOWED_NO_SPACE_DEP:
            continue
        args = fn.args.args or []
        defaults = fn.args.defaults or []
        dep_targets = []
        for default_expr in defaults:
            target = _depends_target(default_expr)
            if target:
                dep_targets.append(target)
        if not _is_space_enforced(dep_targets):
            missing.append(
                f"{path.name}:{fn.lineno}:{fn.name} deps={dep_targets}"
            )

    assert not missing, (
        "Routes missing space/global-admin enforcement dependency. "
        "Add `Depends(current_space_dep)`, `Depends(require_space_role(...))`, "
        "or `Depends(require_global_admin)`.\n"
        + "\n".join(sorted(missing))
    )
