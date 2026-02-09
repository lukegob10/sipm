import os
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Any, Dict

import bcrypt
import jwt
from fastapi import HTTPException, Response, status

SECRET_KEY = os.getenv("SIPM_SECRET_KEY", "dev-secret-change-me")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("SIPM_ACCESS_MINUTES", "60"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("SIPM_REFRESH_DAYS", "7"))
RESET_TOKEN_EXPIRE_MINUTES = int(os.getenv("SIPM_RESET_MINUTES", "30"))
SECURE_COOKIES = os.getenv("SIPM_SECURE_COOKIES", "false").lower() == "true"
COOKIE_SAMESITE = os.getenv("SIPM_COOKIE_SAMESITE", "lax").lower()
ACTIVE_SPACE_COOKIE = "active_space_id"

BCRYPT_ROUNDS = int(os.getenv("SIPM_BCRYPT_ROUNDS", "12"))


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


def verify_password(plain_password: str, hashed_password: str) -> bool:
    password_bytes = _password_bytes_for_bcrypt(plain_password)
    try:
        return bcrypt.checkpw(password_bytes, hashed_password.encode("utf-8"))
    except ValueError:
        return False


def _expiry(delta: timedelta) -> datetime:
    return datetime.now(timezone.utc) + delta


def create_token(user_id: str, role: str, token_type: str) -> str:
    if token_type == "access":
        expires = _expiry(timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    elif token_type == "refresh":
        expires = _expiry(timedelta(minutes=REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60))
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
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    if payload.get("type") != expected_type:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")
    return payload


def set_auth_cookies(response: Response, access_token: str, refresh_token: str) -> None:
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=SECURE_COOKIES,
        samesite=COOKIE_SAMESITE,
        path="/",
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=SECURE_COOKIES,
        samesite=COOKIE_SAMESITE,
        path="/",
    )


def clear_auth_cookies(response: Response) -> None:
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("refresh_token", path="/")
    response.delete_cookie(ACTIVE_SPACE_COOKIE, path="/")


def set_active_space_cookie(response: Response, space_id: str) -> None:
    response.set_cookie(
        key=ACTIVE_SPACE_COOKIE,
        value=space_id,
        httponly=True,
        secure=SECURE_COOKIES,
        samesite=COOKIE_SAMESITE,
        path="/",
    )


def set_reset_cookie(response: Response, reset_token: str) -> None:
    response.set_cookie(
        key="reset_token",
        value=reset_token,
        httponly=True,
        secure=SECURE_COOKIES,
        samesite=COOKIE_SAMESITE,
        path="/",
    )


def clear_reset_cookie(response: Response) -> None:
    response.delete_cookie("reset_token", path="/")
