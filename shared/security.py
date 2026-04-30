from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
from typing import Any
from uuid import UUID, uuid4

from fastapi import HTTPException, status
from jose import JWTError, jwt

from shared.settings import settings


def _now() -> datetime:
    return datetime.now(timezone.utc)


def create_jwt(
    affiliate_id: UUID | str,
    token_type: str,
    ttl_seconds: int,
    *,
    extra_claims: dict[str, Any] | None = None,
) -> str:
    now = _now()
    payload: dict[str, Any] = {
        "id": str(affiliate_id),
        "type": token_type,
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        "iat": int(now.timestamp()),
        "nbf": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=ttl_seconds)).timestamp()),
        "jti": uuid4().hex,
    }
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_jwt(token: str) -> dict[str, Any]:
    try:
        return jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
            issuer=settings.jwt_issuer,
            audience=settings.jwt_audience,
            options={
                "require_exp": True,
                "require_iat": True,
                "verify_iss": True,
                "verify_aud": True,
            },
        )
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        ) from exc


def fingerprint_token(token: str) -> str:
    return sha256(token.encode("utf-8")).hexdigest()
