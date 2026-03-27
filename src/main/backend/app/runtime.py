import os


_PROFILE_ALIASES = {
    "production": "prod",
    "prod": "prod",
    "uat": "uat",
    "dev": "dev",
    "development": "dev",
    "local": "dev",
    "test": "dev",
}
_VALID_TA_ENVS = {"dev", "uat", "prod"}


def get_ta_connection_env() -> str:
    """
    Resolve TAConnection env name.

    Use ENV with alias normalization for TAConnection(env=...).
    """
    profile = (os.getenv("ENV") or "").strip().lower()
    normalized = _PROFILE_ALIASES.get(profile, profile)
    if normalized in _VALID_TA_ENVS:
        return normalized

    if normalized:
        raise RuntimeError(
            "ENV must resolve to dev/local/test, uat, or prod for TAConnection(env=...)."
        )
    raise RuntimeError(
        "ENV is required for TAConnection(env=...). Set ENV to dev/local/test, uat, or prod."
    )
