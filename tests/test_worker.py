from __future__ import annotations

from uuid import UUID

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from core.models.affiliate import Affiliate
from core.models.base import Base
from core.models.offer import Offer
from core.services.worker_service import LeadWorker


class FakeRedis:
    def __init__(self) -> None:
        self.data = {}
        self.acked = []
        self.deleted = []
        self.streams = {}

    async def set(self, key, value, ex=None, nx=False):
        if nx and key in self.data:
            return False
        self.data[key] = value
        return True

    async def delete(self, key):
        self.deleted.append(key)
        self.data.pop(key, None)
        return 1

    async def incr(self, key):
        self.data[key] = int(self.data.get(key, 0)) + 1
        return self.data[key]

    async def xack(self, stream, group, msg_id):
        self.acked.append((stream, group, msg_id))
        return 1

    async def xadd(self, stream, fields):
        self.streams.setdefault(stream, []).append(fields)
        return "2-0"


@pytest.mark.asyncio
async def test_worker_processes_message_and_acks():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    Session = async_sessionmaker(engine, expire_on_commit=False)
    redis = FakeRedis()

    async with Session() as session:
        affiliate_id = UUID("11111111-1111-1111-1111-111111111111")
        offer_id = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
        session.add(Affiliate(id=affiliate_id, name="Alpha"))
        session.add(Offer(id=offer_id, name="Offer A"))
        await session.commit()

    worker = LeadWorker(redis, Session)
    await worker._handle_message(
        "1-0",
        {
            "name": "Alex",
            "phone": "+380000000000",
            "country": "UA",
            "offer_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
            "affiliate_id": "11111111-1111-1111-1111-111111111111",
        },
    )

    assert redis.acked
    await engine.dispose()
