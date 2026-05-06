from __future__ import annotations

import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Mapping

from fastapi import Request, status
from sqlalchemy.orm import Session

from ..models import User
from ..security import security_http_exception
from .auth import _bool_env, _deployment_env, hash_bootstrap_password


DEFAULT_SOEID_HEADER = "SM_USER"
DEFAULT_NAME_HEADER = "name"

_HEADER_NAME_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")
_HEADER_TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9._@-]{1,255}$")


@dataclass(frozen=True)
class ProxyAuthConfig:
    enabled: bool
    soeid_header: str
    name_header: str
    dev_mock_enabled: bool
    dev_mock_soeid: str
    dev_mock_name: str


@dataclass(frozen=True)
class ProxyIdentity:
    soeid: str
    display_name: str
    email: str


def _env_text(name: str) -> str:
    return str(os.getenv(name, "")).strip()


def _default_email_for_soeid(soeid: str) -> str:
    domain = str(os.getenv("DOMAIN_NAME", "citi.com")).strip() or "citi.com"
    return f"{soeid}@{domain}"


def load_proxy_auth_config() -> ProxyAuthConfig:
    return ProxyAuthConfig(
        enabled=_bool_env("SIPM_PROXY_AUTH_ENABLED", False),
        soeid_header=_env_text("SIPM_PROXY_AUTH_SOEID_HEADER") or DEFAULT_SOEID_HEADER,
        name_header=_env_text("SIPM_PROXY_AUTH_NAME_HEADER") or DEFAULT_NAME_HEADER,
        dev_mock_enabled=_bool_env("SIPM_PROXY_AUTH_DEV_MOCK_ENABLED", False),
        dev_mock_soeid=_env_text("SIPM_PROXY_AUTH_DEV_MOCK_SOEID"),
        dev_mock_name=_env_text("SIPM_PROXY_AUTH_DEV_MOCK_NAME"),
    )


def proxy_auth_enabled() -> bool:
    return load_proxy_auth_config().enabled


def _validate_header_name(env_name: str, header_name: str, *, required: bool) -> None:
    raw = str(header_name or "").strip()
    if not raw:
        if required:
            raise RuntimeError(f"{env_name} must be set when SIPM_PROXY_AUTH_ENABLED=true.")
        return
    if not _HEADER_NAME_PATTERN.fullmatch(raw):
        raise RuntimeError(f"{env_name} must be a valid HTTP header name.")


def _normalize_identity_token(value: str | None) -> str:
    return str(value or "").strip().lower()


def _validate_soeid_value(value: str, *, env_name: str) -> None:
    if not value:
        raise RuntimeError(f"{env_name} must not be empty.")
    if not _HEADER_TOKEN_PATTERN.fullmatch(value):
        raise RuntimeError(f"{env_name} must be a simple token without spaces.")


def validate_proxy_auth_configuration() -> None:
    config = load_proxy_auth_config()
    if not config.enabled:
        if config.dev_mock_enabled:
            raise RuntimeError("SIPM_PROXY_AUTH_DEV_MOCK_ENABLED requires SIPM_PROXY_AUTH_ENABLED=true.")
        return

    _validate_header_name("SIPM_PROXY_AUTH_SOEID_HEADER", config.soeid_header, required=True)
    _validate_header_name("SIPM_PROXY_AUTH_NAME_HEADER", config.name_header, required=True)

    if config.dev_mock_enabled:
        if _deployment_env() not in {"dev", "test"}:
            raise RuntimeError("SIPM_PROXY_AUTH_DEV_MOCK_ENABLED is only allowed in dev/test environments.")
        dev_soeid = _normalize_identity_token(config.dev_mock_soeid)
        _validate_soeid_value(dev_soeid, env_name="SIPM_PROXY_AUTH_DEV_MOCK_SOEID")


def _mapping_get_case_insensitive(headers: Mapping[str, str], header_name: str) -> str:
    if not header_name:
        return ""
    direct = headers.get(header_name)
    if direct is not None:
        return str(direct).strip()
    target = header_name.lower()
    for key, value in headers.items():
        if str(key).lower() == target:
            return str(value).strip()
    return ""


def proxy_identity_from_headers(headers: Mapping[str, str]) -> ProxyIdentity | None:
    config = load_proxy_auth_config()
    if not config.enabled:
        return None

    soeid = _normalize_identity_token(_mapping_get_case_insensitive(headers, config.soeid_header))
    if not soeid:
        return None
    if not _HEADER_TOKEN_PATTERN.fullmatch(soeid):
        return None

    display_name = _mapping_get_case_insensitive(headers, config.name_header) or soeid.upper()
    email = _default_email_for_soeid(soeid)
    return ProxyIdentity(
        soeid=soeid,
        display_name=display_name,
        email=email,
    )


def proxy_identity_from_request(request: Request) -> ProxyIdentity | None:
    return proxy_identity_from_headers(request.headers)


def provision_proxy_user(session: Session, identity: ProxyIdentity) -> User:
    user = session.query(User).filter(User.soeid == identity.soeid).first()
    now = datetime.now(timezone.utc)

    if user:
        if not user.is_active:
            raise security_http_exception(
                status_code=status.HTTP_403_FORBIDDEN,
                code="USER_INACTIVE",
                message="User inactive",
            )
        changed = False
        if user.display_name != identity.display_name:
            user.display_name = identity.display_name
            changed = True
        if user.email != identity.email:
            user.email = identity.email
            changed = True
        if user.external_id != identity.soeid:
            user.external_id = identity.soeid
            changed = True
        if user.last_login_at != now:
            user.last_login_at = now
            changed = True
        if changed:
            session.add(user)
            session.commit()
            session.refresh(user)
        return user

    user = User(
        soeid=identity.soeid,
        email=identity.email,
        display_name=identity.display_name,
        password_hash=hash_bootstrap_password(),
        role="user",
        is_active=True,
        external_id=identity.soeid,
        last_login_at=now,
        password_changed_at=now,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def portal_auth_disabled_exception():
    return security_http_exception(
        status_code=status.HTTP_410_GONE,
        code="PORTAL_AUTH_REQUIRED",
        message="Authentication is managed by the company portal.",
    )


def maybe_inject_dev_proxy_headers(scope: dict) -> None:
    config = load_proxy_auth_config()
    if not config.enabled or not config.dev_mock_enabled:
        return

    target_headers = {
        name.lower()
        for name in [
            config.soeid_header,
            config.name_header,
        ]
        if name
    }
    if not target_headers:
        return

    headers = [
        (key, value)
        for key, value in list(scope.get("headers") or [])
        if key.decode("latin1").lower() not in target_headers
    ]

    dev_soeid = _normalize_identity_token(config.dev_mock_soeid)
    headers.append((config.soeid_header.lower().encode("latin1"), dev_soeid.encode("utf-8")))

    display_name = str(config.dev_mock_name or dev_soeid.upper()).strip()
    if config.name_header and display_name:
        headers.append((config.name_header.lower().encode("latin1"), display_name.encode("utf-8")))

    scope["headers"] = headers


__all__ = [
    "ProxyAuthConfig",
    "ProxyIdentity",
    "load_proxy_auth_config",
    "maybe_inject_dev_proxy_headers",
    "portal_auth_disabled_exception",
    "provision_proxy_user",
    "proxy_auth_enabled",
    "proxy_identity_from_headers",
    "proxy_identity_from_request",
    "validate_proxy_auth_configuration",
]
