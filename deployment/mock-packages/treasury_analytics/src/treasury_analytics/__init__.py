"""Local-only shim for the corporate treasury_analytics package.

This package exists so home-lab deployments can rehearse the same import and
connection boundary used in corporate environments. Production-style builds
should install the real treasury_analytics distribution instead.
"""

from __future__ import annotations

import os

import oracledb


_ENV_ALIASES = {
    "development": "dev",
    "local": "dev",
    "test": "dev",
    "production": "prod",
}


def _normalized_env(env: str) -> str:
    raw = str(env or "").strip().lower()
    return _ENV_ALIASES.get(raw, raw)


def _env_value(profile: str, name: str) -> str:
    profile_key = profile.upper()
    value = os.getenv(f"TA_{profile_key}_{name}") or os.getenv(f"TA_{name}")
    if value:
        return value
    raise RuntimeError(f"Missing TA_{profile_key}_{name} or TA_{name} for treasury_analytics local mock.")


class TAConnection:
    """Small compatibility surface for SIPM's TAConnection usage."""

    def __init__(self, env: str):
        self.env = _normalized_env(env)

    def connect(self):
        return oracledb.connect(
            user=_env_value(self.env, "USER"),
            password=_env_value(self.env, "PASSWORD"),
            dsn=_env_value(self.env, "DSN"),
        )
