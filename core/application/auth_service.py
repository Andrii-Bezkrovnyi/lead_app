from __future__ import annotations

import json
from dataclasses import dataclass
from uuid import UUID, uuid4

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.models.affiliate import Affiliate
from shared.security import create_jwt, decode_jwt, fingerprint_token
from shared.settings import settings


@dataclass(slots=True)
class TokenPair:
    access_token: str
    refresh_token: str
    access_expires_in: int
    refresh_expires_in: int


class AuthService:
    def __init__(self, db: AsyncSession, redis_client) -> None:
        self.db = db
        self.redis = redis_client

    @staticmethod
    def _refresh_key(jti: str) -> str:
        return f"auth:refresh:{jti}"

    async def issue_token_pair(self, affiliate_id: UUID, session_id: str | None = None) -> TokenPair:
        affiliate = await self.db.get(Affiliate, affiliate_id)
        if affiliate is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Affiliate not found")

        session_id = session_id or uuid4().hex
        access_token = create_jwt(
            affiliate.id,
            "access",
            settings.access_token_ttl_seconds,
            extra_claims={"sid": session_id},
        )
        refresh_token = create_jwt(
            affiliate.id,
            "refresh",
            settings.refresh_token_ttl_seconds,
            extra_claims={"sid": session_id},
        )
        refresh_payload = decode_jwt(refresh_token)

        await self.redis.set(
            self._refresh_key(str(refresh_payload["jti"])),
            json.dumps(
                {
                    "affiliate_id": str(affiliate.id),
                    "session_id": session_id,
                    "refresh_hash": fingerprint_token(refresh_token),
                }
            ),
            ex=settings.refresh_token_ttl_seconds,
        )

        return TokenPair(
            access_token=access_token,
            refresh_token=refresh_token,
            access_expires_in=settings.access_token_ttl_seconds,
            refresh_expires_in=settings.refresh_token_ttl_seconds,
        )

    async def rotate_refresh_token(self, refresh_token: str) -> TokenPair:
        payload = decode_jwt(refresh_token)
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token required")

        affiliate_id = payload.get("id")
        jti = payload.get("jti")
        session_id = payload.get("sid")
        if not affiliate_id or not jti or not session_id:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token payload")

        key = self._refresh_key(str(jti))
        stored_raw = await self.redis.get(key)
        if stored_raw is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token revoked or expired")

        stored = json.loads(stored_raw)
        if stored.get("affiliate_id") != str(affiliate_id):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token mismatch")
        if stored.get("session_id") != str(session_id):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token mismatch")
        if stored.get("refresh_hash") != fingerprint_token(refresh_token):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token mismatch")

        await self.redis.delete(key)
        return await self.issue_token_pair(UUID(str(affiliate_id)), session_id=str(session_id))

    async def revoke_refresh_token(self, refresh_token: str) -> None:
        payload = decode_jwt(refresh_token)
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token required")
        jti = payload.get("jti")
        if jti:
            await self.redis.delete(self._refresh_key(str(jti)))

    async def authenticate_access_token(self, access_token: str) -> Affiliate:
        payload = decode_jwt(access_token)
        if payload.get("type") != "access":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Access token required")

        affiliate_id = payload.get("id")
        if not affiliate_id:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid access token payload")

        try:
            affiliate_uuid = UUID(str(affiliate_id))
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid access token payload"
            ) from exc

        affiliate = await self.db.get(Affiliate, affiliate_uuid)
        if affiliate is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Affiliate not found")
        return affiliate
