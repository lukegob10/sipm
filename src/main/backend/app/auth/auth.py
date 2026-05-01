import hashlib
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict

import bcrypt
import jwt
from fastapi import Response, status

from ..paths import COOKIE_PATH
from ..security import security_http_exception

DEFAULT_DEV_SECRET = "dev-secret-change-me-at-least-32-bytes"


def _deployment_env() -> str:
    aliases = {
        "production": "prod",
        "prod": "prod",
        "uat": "uat",
        "development": "dev",
        "dev": "dev",
        "test": "test",
        "local": "dev",
    }
    raw = (os.getenv("ENV") or "dev").strip().lower()
    return aliases.get(raw, raw or "dev")


def _int_env(name: str) -> int | None:
    raw = str(os.getenv(name, "")).strip()
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError as exc:
        raise RuntimeError(f"{name} must be an integer.") from exc


def _int_env_with_default(name: str, default: int) -> int:
    value = _int_env(name)
    return default if value is None else value


def _bool_env(name: str, default: bool) -> bool:
    raw = str(os.getenv(name, "")).strip().lower()
    if not raw:
        return default
    if raw in {"1", "true", "yes", "on"}:
        return True
    if raw in {"0", "false", "no", "off"}:
        return False
    raise RuntimeError(f"{name} must be a boolean value.")


DEPLOYMENT_ENV = _deployment_env()
IS_NON_DEV = DEPLOYMENT_ENV not in {"dev", "test"}

SECRET_KEY = os.getenv("SIPM_SECRET_KEY", DEFAULT_DEV_SECRET)
ALGORITHM = "HS256"
_access_minutes = _int_env("SIPM_ACCESS_MINUTES")
ACCESS_TOKEN_EXPIRE_MINUTES = 60 if _access_minutes is None else _access_minutes
_refresh_minutes = _int_env("SIPM_REFRESH_MINUTES")
_refresh_days = _int_env("SIPM_REFRESH_DAYS")
if _refresh_minutes is not None:
    REFRESH_TOKEN_EXPIRE_MINUTES = _refresh_minutes
elif _refresh_days is not None:
    REFRESH_TOKEN_EXPIRE_MINUTES = _refresh_days * 24 * 60
else:
    REFRESH_TOKEN_EXPIRE_MINUTES = 60
RESET_TOKEN_EXPIRE_MINUTES = _int_env_with_default("SIPM_RESET_MINUTES", 30)
ONE_TIME_RESET_TOKEN_EXPIRE_MINUTES = _int_env_with_default("SIPM_ONE_TIME_RESET_MINUTES", 30)
ACCESS_TOKEN_COOKIE_MAX_AGE_SECONDS = max(ACCESS_TOKEN_EXPIRE_MINUTES, 0) * 60
REFRESH_TOKEN_COOKIE_MAX_AGE_SECONDS = max(REFRESH_TOKEN_EXPIRE_MINUTES, 0) * 60

SECURE_COOKIES = _bool_env("SIPM_SECURE_COOKIES", IS_NON_DEV)
COOKIE_SAMESITE = os.getenv("SIPM_COOKIE_SAMESITE", "strict" if IS_NON_DEV else "lax").lower()
ACTIVE_SPACE_COOKIE = "active_space_id"
_VALID_COOKIE_SAMESITE = {"lax", "strict", "none"}

BCRYPT_ROUNDS = _int_env_with_default("SIPM_BCRYPT_ROUNDS", 12)


# Keep local/dev/test environments usable without extra auth bootstrapping.
ALLOW_SELF_REGISTER = _bool_env("SIPM_ALLOW_SELF_REGISTER", not IS_NON_DEV)


def allow_self_register() -> bool:
    return ALLOW_SELF_REGISTER


def validate_auth_configuration() -> None:
    duration_settings = [
        ("SIPM_ACCESS_MINUTES", ACCESS_TOKEN_EXPIRE_MINUTES),
        ("SIPM_RESET_MINUTES", RESET_TOKEN_EXPIRE_MINUTES),
        ("SIPM_ONE_TIME_RESET_MINUTES", ONE_TIME_RESET_TOKEN_EXPIRE_MINUTES),
    ]
    if _refresh_minutes is not None:
        duration_settings.append(("SIPM_REFRESH_MINUTES", _refresh_minutes))
    elif _refresh_days is not None:
        duration_settings.append(("SIPM_REFRESH_DAYS", _refresh_days))
    else:
        duration_settings.append(("SIPM_REFRESH_MINUTES", REFRESH_TOKEN_EXPIRE_MINUTES))
    for setting_name, setting_value in duration_settings:
        if setting_value < 0:
            raise RuntimeError(f"{setting_name} must be greater than or equal to 0.")
    if IS_NON_DEV and SECRET_KEY == DEFAULT_DEV_SECRET:
        raise RuntimeError("SIPM_SECRET_KEY must be set in non-dev environments.")
    if IS_NON_DEV and not SECURE_COOKIES:
        raise RuntimeError("SIPM_SECURE_COOKIES must be true in non-dev environments.")
    if COOKIE_SAMESITE not in _VALID_COOKIE_SAMESITE:
        raise RuntimeError("SIPM_COOKIE_SAMESITE must be one of: lax, strict, none.")
    if COOKIE_SAMESITE == "none" and not SECURE_COOKIES:
        raise RuntimeError("SIPM_COOKIE_SAMESITE=none requires SIPM_SECURE_COOKIES=true.")
    try:
        bcrypt.gensalt(rounds=BCRYPT_ROUNDS)
    except ValueError as exc:
        raise RuntimeError("SIPM_BCRYPT_ROUNDS must be a valid bcrypt rounds value.") from exc


def _password_bytes_for_bcrypt(password: str) -> bytes:
    """
    bcrypt only uses the first 72 bytes of the password.

    To avoid silent truncation, pre-hash with SHA-256 when the UTF-8 byte length exceeds 72.
    """
    raw = password.encode("utf-8")
    if len(raw) > 72:
        return hashlib.sha256(raw).digest()
    return raw


def hash_password(password: str) -> str:
    password_bytes = _password_bytes_for_bcrypt(password)
    hashed = bcrypt.hashpw(password_bytes, bcrypt.gensalt(rounds=BCRYPT_ROUNDS))
    return hashed.decode("utf-8")


def hash_bootstrap_password() -> str:
    # Never provision users with a known shared default password.
    return hash_password(secrets.token_urlsafe(48))


def verify_password(plain_password: str, hashed_password: str) -> bool:
    password_bytes = _password_bytes_for_bcrypt(plain_password)
    try:
        return bcrypt.checkpw(password_bytes, hashed_password.encode("utf-8"))
    except ValueError:
        return False


def generate_one_time_reset_token() -> str:
    return secrets.token_urlsafe(48)


def hash_one_time_reset_token(token: str) -> str:
    return hashlib.sha256(str(token or "").encode("utf-8")).hexdigest()


def _expiry(delta: timedelta) -> datetime:
    return datetime.now(timezone.utc) + delta


def create_token(user_id: str, role: str, token_type: str) -> str:
    if token_type == "access":
        expires = _expiry(timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    elif token_type == "refresh":
        expires = _expiry(timedelta(minutes=REFRESH_TOKEN_EXPIRE_MINUTES))
    elif token_type == "reset":
        expires = _expiry(timedelta(minutes=RESET_TOKEN_EXPIRE_MINUTES))
    else:
        raise ValueError(f"Unsupported token type: {token_type}")
    to_encode: Dict[str, Any] = {
        "sub": user_id,
        "role": role,
        "type": token_type,
        "exp": expires,
        "iat": int(datetime.now(timezone.utc).timestamp()),
    }
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str, expected_type: str) -> Dict[str, Any]:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError as exc:
        raise security_http_exception(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="TOKEN_EXPIRED",
            message="Token expired",
        ) from exc
    except jwt.InvalidTokenError as exc:
        raise security_http_exception(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="TOKEN_INVALID",
            message="Invalid token",
        ) from exc
    if payload.get("type") != expected_type:
        raise security_http_exception(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="TOKEN_TYPE_INVALID",
            message="Invalid token type",
        )
    return payload


def _delete_legacy_root_cookie(response: Response, key: str) -> None:
    if COOKIE_PATH != "/":
        response.delete_cookie(key, path="/")


def set_auth_cookies(response: Response, access_token: str, refresh_token: str) -> None:
    _delete_legacy_root_cookie(response, "access_token")
    _delete_legacy_root_cookie(response, "refresh_token")
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=SECURE_COOKIES,
        samesite=COOKIE_SAMESITE,
        path=COOKIE_PATH,
        max_age=ACCESS_TOKEN_COOKIE_MAX_AGE_SECONDS,
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=SECURE_COOKIES,
        samesite=COOKIE_SAMESITE,
        path=COOKIE_PATH,
        max_age=REFRESH_TOKEN_COOKIE_MAX_AGE_SECONDS,
    )


def clear_auth_cookies(response: Response) -> None:
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("refresh_token", path="/")
    response.delete_cookie(ACTIVE_SPACE_COOKIE, path="/")
    response.delete_cookie("access_token", path=COOKIE_PATH)
    response.delete_cookie("refresh_token", path=COOKIE_PATH)
    response.delete_cookie(ACTIVE_SPACE_COOKIE, path=COOKIE_PATH)


def set_active_space_cookie(response: Response, space_id: str) -> None:
    _delete_legacy_root_cookie(response, ACTIVE_SPACE_COOKIE)
    response.set_cookie(
        key=ACTIVE_SPACE_COOKIE,
        value=space_id,
        httponly=True,
        secure=SECURE_COOKIES,
        samesite=COOKIE_SAMESITE,
        path=COOKIE_PATH,
        max_age=REFRESH_TOKEN_COOKIE_MAX_AGE_SECONDS,
    )
