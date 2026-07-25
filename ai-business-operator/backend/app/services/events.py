"""Redis pub/sub event bus with signed messages.

Agents publish here; the orchestrator subscribes. Signatures are the trust boundary
between worker processes — an unsigned event is dropped, loudly.
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncGenerator
from datetime import UTC, datetime

import redis.asyncio as redis

from app.config import get_settings
from app.schemas import Event, EventType
from app.security import sign_payload, verify_signature

log = logging.getLogger(__name__)

CHANNEL = "aibo:events"


class EventBus:
    def __init__(self, client: redis.Redis) -> None:
        self._client = client

    @classmethod
    def from_env(cls) -> EventBus:
        settings = get_settings()
        return cls(redis.from_url(settings.redis_url, decode_responses=True))

    async def publish(
        self,
        event: EventType,
        *,
        project_id: int,
        agent: str,
        task_id: int | None = None,
        result: dict | None = None,
    ) -> Event:
        message = Event(
            event=event,
            project_id=project_id,
            task_id=task_id,
            agent=agent,
            result=result or {},
            timestamp=datetime.now(UTC),
        )
        message.signature = sign_payload(message.signable())
        await self._client.publish(CHANNEL, message.model_dump_json())
        log.info(
            "event.published",
            extra={"event_type": event.value, "project_id": project_id, "agent": agent},
        )
        return message

    async def subscribe(self) -> AsyncGenerator[Event, None]:
        """Yield verified events. Mis-signed messages are dropped and logged."""
        pubsub = self._client.pubsub()
        await pubsub.subscribe(CHANNEL)
        try:
            async for raw in pubsub.listen():
                if raw.get("type") != "message":
                    continue
                try:
                    event = Event.model_validate(json.loads(raw["data"]))
                except (ValueError, TypeError):
                    log.warning("event.malformed", extra={"raw": str(raw.get("data"))[:200]})
                    continue

                if not verify_signature(event.signable(), event.signature):
                    log.error(
                        "event.signature_invalid",
                        extra={"event_type": event.event.value, "agent": event.agent},
                    )
                    continue

                yield event
        finally:
            await pubsub.unsubscribe(CHANNEL)
            await pubsub.aclose()

    async def aclose(self) -> None:
        await self._client.aclose()
