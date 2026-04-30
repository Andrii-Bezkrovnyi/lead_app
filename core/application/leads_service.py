from __future__ import annotations

import hashlib
from datetime import date, datetime, timedelta, timezone
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.models.lead import Lead
from shared.schemas import LeadIn, LeadSummaryLead
from shared.settings import settings


class LeadService:
    def __init__(self, redis_client) -> None:
        self.redis = redis_client

    @staticmethod
    def _normalize_phone(phone: str) -> str:
        return phone.strip().replace(" ", "")

    @staticmethod
    def dedup_key(lead: LeadIn) -> str:
        raw = "|".join(
            [
                lead.name.strip().lower(),
                LeadService._normalize_phone(lead.phone),
                str(lead.offer_id),
                str(lead.affiliate_id),
            ]
        ).encode("utf-8")
        return f"dedup:{hashlib.sha256(raw).hexdigest()}"

    async def enqueue(self, lead: LeadIn) -> str:
        return await self.redis.xadd(
            settings.leads_stream_name,
            {
                "name": lead.name.strip(),
                "phone": self._normalize_phone(lead.phone),
                "country": lead.country.strip().upper(),
                "offer_id": str(lead.offer_id),
                "affiliate_id": str(lead.affiliate_id),
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
        )

    async def acquire_dedup_lock(self, lead: LeadIn) -> bool:
        return bool(await self.redis.set(self.dedup_key(lead), "1", ex=600, nx=True))

    async def release_dedup_lock(self, lead: LeadIn) -> None:
        await self.redis.delete(self.dedup_key(lead))

    async def process_stream_message(self, db: AsyncSession, payload: dict[str, str]) -> bool:
        lead = LeadIn(
            name=payload["name"],
            phone=payload["phone"],
            country=payload["country"],
            offer_id=UUID(payload["offer_id"]),
            affiliate_id=UUID(payload["affiliate_id"]),
        )

        if not await self.acquire_dedup_lock(lead):
            return False

        try:
            db.add(
                Lead(
                    name=lead.name.strip(),
                    phone=self._normalize_phone(lead.phone),
                    country=lead.country.strip().upper(),
                    offer_id=lead.offer_id,
                    affiliate_id=lead.affiliate_id,
                )
            )
            await db.commit()
            return True
        except Exception:
            await db.rollback()
            await self.release_dedup_lock(lead)
            raise

    async def aggregate(
        self,
        db: AsyncSession,
        affiliate_id: UUID,
        date_from: date,
        date_to: date,
        group: str,
    ) -> dict:
        if date_from > date_to:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="date_from must be before or equal to date_to"
            )
        if group not in {"date", "offer"}:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="group must be date or offer"
            )

        start = datetime.combine(date_from, datetime.min.time(), tzinfo=timezone.utc)
        end = datetime.combine(date_to + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc)

        stmt = (
            select(Lead)
            .where(
                Lead.affiliate_id == affiliate_id,
                Lead.created_at >= start,
                Lead.created_at < end,
            )
            .order_by(Lead.created_at.asc(), Lead.id.asc())
        )
        leads = (await db.execute(stmt)).scalars().all()

        grouped: dict[str, list[Lead]] = {}
        for lead in leads:
            created_at = lead.created_at
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=timezone.utc)
            group_key = created_at.astimezone(
                timezone.utc
            ).date().isoformat() if group == "date" else str(lead.offer_id)
            grouped.setdefault(group_key, []).append(lead)

        items: list[dict] = []
        if group == "date":
            current_day = date_from
            while current_day <= date_to:
                group_key = current_day.isoformat()
                group_leads = grouped.get(group_key, [])
                items.append(
                    {
                        "group_key": group_key,
                        "count": len(group_leads),
                        "leads": [
                            LeadSummaryLead(
                                id=lead.id,
                                name=lead.name,
                                phone=lead.phone,
                                country=lead.country,
                                offer_id=lead.offer_id,
                                affiliate_id=lead.affiliate_id,
                                created_at=lead.created_at,
                            )
                            for lead in group_leads
                        ],
                    }
                )
                current_day += timedelta(days=1)
        else:
            items = [
                {
                    "group_key": group_key,
                    "count": len(group_leads),
                    "leads": [
                        LeadSummaryLead(
                            id=lead.id,
                            name=lead.name,
                            phone=lead.phone,
                            country=lead.country,
                            offer_id=lead.offer_id,
                            affiliate_id=lead.affiliate_id,
                            created_at=lead.created_at,
                        )
                        for lead in group_leads
                    ],
                }
                for group_key, group_leads in sorted(grouped.items(), key=lambda item: item[0])
            ]

        return {
            "affiliate_id": affiliate_id,
            "group": group,
            "date_from": date_from,
            "date_to": date_to,
            "total_count": len(leads),
            "items": items,
        }
