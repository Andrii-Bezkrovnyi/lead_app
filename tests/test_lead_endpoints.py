from dataclasses import dataclass
from uuid import UUID

import pytest
from fastapi import FastAPI, Request
from httpx import AsyncClient, ASGITransport

from core.services.leads_service import LeadService
from landings.api.leads import get_lead_service, router
from landings.dependencies.auth import get_current_affiliate


@dataclass
class AffiliateStub:
    id: UUID
    name: str = "Alpha"


class FakeRedis:
    def __init__(self) -> None:
        self.streams = []
        self.data = {}

    async def xadd(self, stream, data):
        self.streams.append((stream, data))
        return "1-0"

    async def incr(self, key):
        self.data[key] = int(self.data.get(key, 0)) + 1
        return self.data[key]

    async def expire(self, key, seconds):
        return True


@pytest.mark.asyncio
async def test_create_lead_enqueues_to_stream():
    # Create FastAPI app and set up dependencies
    app = FastAPI()

    app.state.redis = FakeRedis()
    app.include_router(router)
    app.dependency_overrides[get_current_affiliate] = lambda: AffiliateStub(
        id=UUID("11111111-1111-1111-1111-111111111111")
    )

    async def _service_override(request: Request):
        return LeadService(request.app.state.redis)

    app.dependency_overrides[get_lead_service] = _service_override

    # Use AsyncClient
    async with AsyncClient(transport=ASGITransport(app=app),
                           base_url="http://test") as ac:
        response = await ac.post(
            "/lead",
            json={
                "name": "Олексій",
                "phone": "+380982342123",
                "country": "UA",
                "offer_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
                "affiliate_id": "11111111-1111-1111-1111-111111111111",
            },
        )

    assert response.status_code == 200
    assert response.json()["status"] == "accepted"
    assert len(app.state.redis.streams) > 0
