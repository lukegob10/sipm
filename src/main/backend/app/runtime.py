import os


TA_ORACLE_RUNTIME_USER = "TA_ECS_DS1_RW"
_PROFILE_ALIASES = {
    "production": "prod",
    "prod": "prod",
    "uat": "uat",
    "dev": "dev",
    "development": "dev",
}


def is_ta_oracle_mode() -> bool:
    """Return True when DB runtime should use TAConnection + Oracle."""
    return (os.getenv("USER") or "").strip() == TA_ORACLE_RUNTIME_USER


def get_ta_connection_env() -> str:
    """
    Resolve TAConnection env name.

    Use SIPM_DB_PROFILE with the same alias normalization used by DB URLs.
    """
    profile = (os.getenv("SIPM_DB_PROFILE") or "").strip().lower()
    normalized = _PROFILE_ALIASES.get(profile, profile)
    if normalized:
        return normalized

    raise RuntimeError(
        "TA Oracle mode enabled (USER=TA_ECS_DS1_RW), but SIPM_DB_PROFILE is not "
        "set for TAConnection(env=...)."
    )
