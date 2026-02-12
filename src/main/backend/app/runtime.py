import os


_PROFILE_ALIASES = {
    "production": "prod",
    "prod": "prod",
    "uat": "uat",
    "dev": "dev",
    "development": "dev",
}


def get_ta_connection_env() -> str:
    """
    Resolve TAConnection env name.

    Use ENV with alias normalization for TAConnection(env=...).
    """
    profile = (os.getenv("ENV") or "").strip().lower()
    normalized = _PROFILE_ALIASES.get(profile, profile)
    if normalized:
        return normalized

    raise RuntimeError(
        "ENV is required for TAConnection(env=...). Set ENV to dev, uat, or prod."
    )
