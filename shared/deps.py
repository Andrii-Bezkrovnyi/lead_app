from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from core.models.affiliate import Affiliate
from shared.db import get_db
from shared.security import decode_jwt

bearer_scheme = HTTPBearer(auto_error=True)


async def get_current_affiliate(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(bearer_scheme)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Affiliate:
    payload = decode_jwt(credentials.credentials)
    if payload.get("type") != "access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Access token required")

    affiliate_id = payload.get("id")
    if not affiliate_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token payload missing id")

    try:
        affiliate_uuid = UUID(str(affiliate_id))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid affiliate id") from exc

    affiliate = await db.get(Affiliate, affiliate_uuid)
    if affiliate is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Affiliate not found")

    return affiliate


def client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"
