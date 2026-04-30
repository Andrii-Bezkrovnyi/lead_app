from __future__ import annotations

from datetime import date, datetime, timezone
from uuid import UUID

import pytest

from core.models.affiliate import Affiliate
from core.models.lead import Lead
from core.models.offer import Offer
from core.services.leads_service import LeadService
from shared.schemas import LeadIn


class FakeRedis:
    def __init__(self) -> None:
        self.data = {}
        self.streams = {}

    async def xadd(self, stream, fields):
        self.streams.setdefault(stream, []).append(fields)
        return "1-0"

    async def set(self, key, value, ex=None, nx=False):
        if nx and key in self.data:
            return False
        self.data[key] = value
        return True

    async def delete(self, key):
        self.data.pop(key, None)
        return 1

    async def incr(self, key):
        self.data[key] = int(self.data.get(key, 0)) + 1
        return self.data[key]

    async def expire(self, key, seconds):
        return True


@pytest.mark.asyncio
async def test_dedup_key_and_enqueue():
    redis = FakeRedis()
    service = LeadService(redis)
    lead = LeadIn(
        name="Alex",
        phone="+380982342123",
        country="UA",
        offer_id=UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
        affiliate_id=UUID("11111111-1111-1111-1111-111111111111"),
    )

    msg_id = await service.enqueue(lead)
    assert msg_id == "1-0"
    assert "stream:leads" in redis.streams


@pytest.mark.asyncio
async def test_aggregate_returns_grouped_leads(session):
    redis = FakeRedis()
    service = LeadService(redis)

    affiliate_id = UUID("11111111-1111-1111-1111-111111111111")
    offer_a = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")

    # Сохраняем данные
    session.add(Affiliate(id=affiliate_id, name="Alpha"))
    session.add(Offer(id=offer_a, name="Offer A"))
    await session.commit()

    session.add(Lead(
        name="Alex",
        phone="+380982342123",
        country="UA",
        offer_id=offer_a,
        affiliate_id=affiliate_id,
        created_at=datetime(2026, 4, 20, 10, 0, tzinfo=timezone.utc),
    ))
    await session.commit()

    # Aggregate leads by date
    date_summary = await service.aggregate(
        session,
        affiliate_id=affiliate_id,
        date_from=date(2026, 4, 20),
        date_to=date(2026, 4, 21),
        group="date",
    )

    assert date_summary["total_count"] == 1
    assert date_summary["items"][0]["leads"][0].name == "Alex"
