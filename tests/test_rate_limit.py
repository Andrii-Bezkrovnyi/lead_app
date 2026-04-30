from __future__ import annotations

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from shared.rate_limit import rate_limiter


class FakeRedis:
    def __init__(self) -> None:
        self.values = {}

    async def incr(self, key):
        self.values[key] = self.values.get(key, 0) + 1
        return self.values[key]

    async def expire(self, key, seconds):
        return True


def test_rate_limiter_blocks_after_limit():
    app = FastAPI()
    app.state.redis = FakeRedis()

    @app.get("/limited")
    async def limited(_: None = Depends(rate_limiter("test", 2, 60))):
        return {"ok": True}

    client = TestClient(app)
    assert client.get("/limited").status_code == 200
    assert client.get("/limited").status_code == 200
    assert client.get("/limited").status_code == 429
