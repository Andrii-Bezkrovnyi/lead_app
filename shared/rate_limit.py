from __future__ import annotations

import time
from typing import Callable

from fastapi import HTTPException, Request, status

from shared.deps import client_ip


def rate_limiter(namespace: str, limit: int, window_seconds: int) -> Callable:
    async def dependency(request: Request) -> None:
        redis_client = request.app.state.redis
        ip = client_ip(request)
        window = int(time.time() // window_seconds)
        key = f"rate:{namespace}:{ip}:{window}"

        current = await redis_client.incr(key)
        if current == 1:
            await redis_client.expire(key, window_seconds + 1)

        if current > limit:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded"
            )

    return dependency
