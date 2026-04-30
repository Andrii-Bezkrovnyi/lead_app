from __future__ import annotations

import redis.asyncio as redis

from shared.settings import settings


def create_redis_client() -> redis.Redis:
    return redis.from_url(
        settings.redis_url,
        decode_responses=True,
        health_check_interval=30
    )


async def get_redis(request) -> redis.Redis:
    return request.app.state.redis
