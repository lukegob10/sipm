"""
Automatically hydrate process environment variables from the repository `.env`
for local Python processes launched from `src/main`.
"""

try:
    from backend.app.environment import load_repo_env

    load_repo_env()
except Exception:
    # Avoid breaking unrelated Python entrypoints if the package isn't importable
    # in the current execution context.
    pass
