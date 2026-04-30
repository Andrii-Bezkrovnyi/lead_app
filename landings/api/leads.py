from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status

from core.services.leads_service import LeadService
from landings.dependencies.auth import get_current_affiliate
from shared.rate_limit import rate_limiter
from shared.schemas import LeadAccepted, LeadIn
from shared.settings import settings

router = APIRouter(tags=["landings"])


async def get_lead_service(request: Request) -> LeadService:
    return LeadService(request.app.state.redis)


@router.post(
    "/lead",
    response_model=LeadAccepted,
    summary="Accept lead from a landing page",
    description="Validates the JWT, checks affiliate_id consistency, and enqueues the lead into Redis Streams.",
)
async def create_lead(
    lead: LeadIn,
    affiliate=Depends(get_current_affiliate),
    _rate_limit: None = Depends(rate_limiter(
        "landings-lead",
        settings.rate_limit_requests,
        settings.rate_limit_window_seconds
    )),
    service: LeadService = Depends(get_lead_service),
) -> LeadAccepted:
    if str(lead.affiliate_id) != str(affiliate.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="affiliate_id does not match token id")

    message_id = await service.enqueue(lead)
    return LeadAccepted(stream=settings.leads_stream_name, message_id=message_id)
