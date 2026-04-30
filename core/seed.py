from __future__ import annotations

import asyncio
from uuid import UUID

from sqlalchemy import select

from core.models.affiliate import Affiliate
from core.models.offer import Offer
from shared.db import Database
from shared.settings import settings

DEFAULT_AFFILIATES = [
    (UUID("11111111-1111-1111-1111-111111111111"), "Alpha Agency"),
    (UUID("22222222-2222-2222-2222-222222222222"), "Beta Media"),
]
DEFAULT_OFFERS = [
    (UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"), "Offer A"),
    (UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"), "Offer B"),
]


async def seed() -> None:
    database = Database(settings.database_url)
    try:
        async with database.sessionmaker() as session:
            existing_affiliates = set((await session.execute(select(Affiliate.id))).scalars().all())
            existing_offers = set((await session.execute(select(Offer.id))).scalars().all())

            for affiliate_id, name in DEFAULT_AFFILIATES:
                if affiliate_id not in existing_affiliates:
                    session.add(Affiliate(id=affiliate_id, name=name))

            for offer_id, name in DEFAULT_OFFERS:
                if offer_id not in existing_offers:
                    session.add(Offer(id=offer_id, name=name))

            await session.commit()
    finally:
        await database.dispose()


if __name__ == "__main__":
    asyncio.run(seed())
