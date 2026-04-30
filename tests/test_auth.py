from __future__ import annotations

from uuid import UUID

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from core.models.affiliate import Affiliate
from core.models.base import Base
from core.services.auth_service import AuthService
from shared.security import decode_jwt


class MemoryRedis:
    def __init__(self) -> None:
        self.data = {}

    async def set(self, key, value, ex=None, nx=False):
        if nx and key in self.data:
            return False
        self.data[key] = value
        return True

    async def get(self, key):
        return self.data.get(key)

    async def delete(self, key):
        self.data.pop(key, None)
        return 1


@pytest.mark.asyncio
async def test_refresh_rotation_invalidates_old_token():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    Session = async_sessionmaker(engine, expire_on_commit=False)
    redis = MemoryRedis()

    async with Session() as session:
        affiliate_id = UUID("11111111-1111-1111-1111-111111111111")
        session.add(Affiliate(id=affiliate_id, name="Alpha"))
        await session.commit()

        service = AuthService(session, redis)
        pair = await service.issue_token_pair(affiliate_id)
        assert decode_jwt(pair.refresh_token)["type"] == "refresh"

        rotated = await service.rotate_refresh_token(pair.refresh_token)
        assert rotated.refresh_token != pair.refresh_token

        with pytest.raises(Exception):
            await service.rotate_refresh_token(pair.refresh_token)

    await engine.dispose()
