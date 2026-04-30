from __future__ import annotations

import asyncio

from core.main import lifespan, app
from core.services.worker_service import LeadWorker


async def main() -> None:
    async with lifespan(app):
        worker = LeadWorker(app.state.redis, app.state.database.sessionmaker)
        stop_event = asyncio.Event()
        try:
            await worker.run_forever(stop_event=stop_event)
        except asyncio.CancelledError:
            stop_event.set()
            raise


if __name__ == "__main__":
    asyncio.run(main())
