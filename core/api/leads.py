from __future__ import annotations

from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from core.services.leads_service import LeadService
from shared.db import get_db
from shared.deps import get_current_affiliate
from shared.rate_limit import rate_limiter
from shared.schemas import LeadsSummaryResponse
from shared.settings import settings

router = APIRouter(tags=["leads"])


async def get_lead_service(request: Request) -> LeadService:
    return LeadService(request.app.state.redis)


@router.get(
    "/leads",
    response_model=LeadsSummaryResponse,
    summary="Affiliate leads analytics",
    description="Returns an affiliate summary for a period grouped by day or by offer.",
)
async def list_leads(
    date_from: Annotated[date, Query(description="Start date in YYYY-MM-DD")],
    date_to: Annotated[date, Query(description="End date in YYYY-MM-DD")],
    group: Annotated[Literal["date", "offer"], Query(description="Group by day or offer")],
    db: Annotated[AsyncSession, Depends(get_db)],
    affiliate=Depends(get_current_affiliate),
    _rate_limit: None = Depends(rate_limiter(
        "core-leads",
        settings.rate_limit_requests,
        settings.rate_limit_window_seconds)
    ),
    service: LeadService = Depends(get_lead_service),
) -> LeadsSummaryResponse:
    summary = await service.aggregate(db, affiliate.id, date_from, date_to, group)
    return LeadsSummaryResponse.model_validate(summary)


@router.get("/health", summary="Core health check")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "core"}
