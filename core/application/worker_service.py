from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

# Импортируем специфичное исключение Redis для обработки существующих групп
from redis.exceptions import ResponseError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from core.application.leads_service import LeadService
from core.models.lead import Lead
from shared.schemas import LeadIn
from shared.settings import settings

# Настройка логгера
logger = logging.getLogger(__name__)


class LeadWorker:
    def __init__(self, redis_client: Any,
                 sessionmaker: async_sessionmaker[AsyncSession]) -> None:
        self.redis = redis_client
        self.sessionmaker = sessionmaker
        self.lead_service = LeadService(redis_client)

    async def ensure_group(self) -> None:
        """
        Проверяет наличие группы потребителей в Redis Stream и создает её, если она отсутствует.
        Игнорирует ошибку BUSYGROUP, если группа уже была создана ранее.
        """
        try:
            await self.redis.xgroup_create(
                settings.leads_stream_name,
                settings.leads_consumer_group,
                id="0",  # Начинаем чтение с начала стрима
                mkstream=True,
            )
            logger.info(
                f"Consumer group '{settings.leads_consumer_group}' created successfully.")
        except ResponseError as exc:
            # Если группа уже существует, Redis вернет ошибку с текстом BUSYGROUP
            if "BUSYGROUP" in str(exc):
                logger.info(
                    f"Consumer group '{settings.leads_consumer_group}' already exists. Skipping.")
            else:
                logger.error(f"Unexpected Redis error during group creation: {exc}")
                raise
        except Exception as exc:
            logger.error(f"Critical error in ensure_group: {exc}")
            raise

    async def run_forever(self, stop_event: asyncio.Event | None = None) -> None:
        """Основной цикл обработки сообщений из стрима."""
        await self.ensure_group()
        stop_event = stop_event or asyncio.Event()

        logger.info("Worker started. Waiting for messages...")

        while not stop_event.is_set():
            # 1. Сначала пытаемся обработать "зависшие" сообщения
            await self._reclaim_pending_messages()

            # 2. Читаем новые сообщения (">")
            try:
                messages = await self.redis.xreadgroup(
                    settings.leads_consumer_group,
                    settings.leads_consumer_name,
                    streams={settings.leads_stream_name: ">"},
                    count=10,
                    block=2000,  # Ждем 2 секунды, если сообщений нет
                )

                if not messages:
                    continue

                for _, entries in messages:
                    for message_id, payload in entries:
                        try:
                            await self._handle_message(message_id, payload)
                        except Exception:
                            logger.exception(
                                "Lead processing failed",
                                extra={"message_id": message_id}
                            )
            except Exception as e:
                logger.error(f"Error during xreadgroup: {e}")
                await asyncio.sleep(1)  # Защита от "быстрого" цикла при ошибках связи

    async def _reclaim_pending_messages(self) -> None:
        """Подхватывает сообщения, которые были считаны, но не подтверждены (ACK) другими воркерами."""
        if not hasattr(self.redis, "xautoclaim"):
            return

        start_id = "0-0"
        while True:
            response = await self.redis.xautoclaim(
                settings.leads_stream_name,
                settings.leads_consumer_group,
                settings.leads_consumer_name,
                min_idle_time=settings.leads_claim_idle_ms,
                start_id=start_id,
                count=10,
            )

            if not response:
                break

            next_start = response[0]
            messages = response[1] if len(response) > 1 else []

            if not messages:
                break

            for message_id, payload in messages:
                try:
                    logger.info(f"Reclaiming pending message: {message_id}")
                    await self._handle_message(message_id, payload)
                except Exception:
                    logger.exception(
                        "Reclaimed lead processing failed",
                        extra={"message_id": message_id}
                    )

            if next_start == start_id or next_start == "0-0":
                break
            start_id = next_start

    @staticmethod
    def _attempts_key(message_id: str) -> str:
        return f"attempts:{message_id}"

    async def _move_to_dlq(self, message_id: str, payload: dict[str, str], error: str,
                           attempts: int) -> None:
        """Перемещает проблемное сообщение в Dead Letter Queue (DLQ)."""
        await self.redis.xadd(
            settings.leads_dlq_stream_name,
            {
                "original_message_id": message_id,
                "payload": json.dumps(payload),
                "error": error,
                "attempts": str(attempts),
            },
        )
        # Подтверждаем в основном стриме, чтобы оно больше не висело в Pending
        await self.redis.xack(settings.leads_stream_name, settings.leads_consumer_group,
                              message_id)
        logger.warning(f"Message {message_id} moved to DLQ: {error}")

    async def _handle_message(self, message_id: str, payload: dict[str, Any]) -> None:
        """Логика обработки одной заявки (Lead)."""
        try:
            # Декодируем байты в строки, если Redis возвращает bytes
            decoded_payload = {
                k.decode() if isinstance(k, bytes) else k:
                    v.decode() if isinstance(v, bytes) else v
                for k, v in payload.items()
            }

            lead_data = LeadIn(**decoded_payload)
        except Exception as exc:
            await self._move_to_dlq(message_id, payload,
                                    f"Invalid payload format: {exc}", attempts=0)
            return

        # Дедупликация
        if not await self.redis.set(self.lead_service.dedup_key(lead_data), "1", ex=600,
                                    nx=True):
            await self.redis.xack(settings.leads_stream_name,
                                  settings.leads_consumer_group, message_id)
            logger.info(
                f"Duplicate lead detected: {lead_data.phone}. Acking without save.")
            return

        attempts_key = self._attempts_key(message_id)
        try:
            async with self.sessionmaker() as db:
                db.add(
                    Lead(
                        name=lead_data.name.strip(),
                        phone=lead_data.phone.strip().replace(" ", ""),
                        country=lead_data.country.strip().upper(),
                        offer_id=lead_data.offer_id,
                        affiliate_id=lead_data.affiliate_id,
                    )
                )
                await db.commit()

            await self.redis.delete(attempts_key)
            await self.redis.xack(settings.leads_stream_name,
                                  settings.leads_consumer_group, message_id)

        except Exception as exc:
            await self.redis.delete(self.lead_service.dedup_key(lead_data))

            attempts = await self.redis.incr(attempts_key)
            await self.redis.expire(attempts_key, settings.retry_key_ttl_seconds)

            if attempts >= settings.leads_max_retries:
                await self._move_to_dlq(
                    message_id,
                    payload,
                    str(exc),
                    attempts=attempts
                )
                await self.redis.delete(attempts_key)
            else:
                logger.error(
                    f"Retry {attempts}/{settings.leads_max_retries} for message {message_id}: {exc}"
                )
                raise
