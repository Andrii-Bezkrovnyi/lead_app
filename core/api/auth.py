from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from core.services.auth_service import AuthService
from shared.db import get_db
from shared.rate_limit import rate_limiter
from shared.schemas import AuthTokenRequest, LogoutRequest, RefreshRequest, TokenPairResponse
from shared.settings import settings

router = APIRouter(prefix="/auth", tags=["auth"])


async def get_auth_service(request: Request, db: Annotated[AsyncSession, Depends(get_db)]) -> AuthService:
    return AuthService(db=db, redis_client=request.app.state.redis)


@router.post(
    "/token",
    response_model=TokenPairResponse,
    summary="Issue JWT pair",
    description="Generates a short-lived access token and a refresh token for an existing affiliate.",
)
async def issue_token(
    body: AuthTokenRequest,
    _rate_limit: None = Depends(
        rate_limiter(
            "core-auth-token",
            settings.rate_limit_requests,
            settings.rate_limit_window_seconds
        )
    ),
    service: AuthService = Depends(get_auth_service),
) -> TokenPairResponse:
    pair = await service.issue_token_pair(body.affiliate_id)
    return TokenPairResponse(
        access_token=pair.access_token,
        refresh_token=pair.refresh_token,
        token_type="bearer",
        access_expires_in=pair.access_expires_in,
        refresh_expires_in=pair.refresh_expires_in,
    )


@router.post(
    "/refresh",
    response_model=TokenPairResponse,
    summary="Rotate refresh token",
    description="Consumes an active refresh token, revokes it, and returns a new token pair.",
)
async def refresh_token(body: RefreshRequest, service: AuthService = Depends(get_auth_service)) -> TokenPairResponse:
    pair = await service.rotate_refresh_token(body.refresh_token)
    return TokenPairResponse(
        access_token=pair.access_token,
        refresh_token=pair.refresh_token,
        token_type="bearer",
        access_expires_in=pair.access_expires_in,
        refresh_expires_in=pair.refresh_expires_in,
    )


@router.post(
    "/logout",
    summary="Revoke refresh token",
    description="Invalidates a refresh token so it can no longer be rotated.",
)
async def logout(body: LogoutRequest, service: AuthService = Depends(get_auth_service)) -> dict[str, str]:
    await service.revoke_refresh_token(body.refresh_token)
    return {"status": "revoked"}
