"""In-memory event logger for tests.

This logger implements the BaseEventLogger interface without any external
dependencies. It's used when ENVIRONMENT=test.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import Any

from app.services.base import BaseEventLogger


class InMemoryEventLogger(BaseEventLogger):
    """Simple in-memory event logger."""

    def __init__(self):
        self._events: list[dict[str, Any]] = []

    async def initialize(self) -> None:
        return

    async def log(
        self,
        event_type: str,
        city: str | None = None,
        file_path: str | None = None,
        details: str | None = None,
        client_ip: str | None = None,
    ) -> str:
        event_id = str(uuid.uuid4())
        self._events.append(
            {
                "id": event_id,
                "timestamp": datetime.utcnow().isoformat(),
                "event_type": event_type,
                "city": city,
                "file_path": file_path,
                "details": details,
                "client_ip": client_ip,
            }
        )
        return event_id

    async def get_events(
        self,
        limit: int = 100,
        event_type: str | None = None,
        city: str | None = None,
    ) -> list[dict[str, Any]]:
        events = self._events
        if event_type:
            events = [e for e in events if e.get("event_type") == event_type]
        if city:
            events = [e for e in events if e.get("city") == city]
        return list(reversed(events))[:limit]

    async def get_stats(self) -> dict[str, Any]:
        total = len(self._events)
        by_type: dict[str, int] = {}
        cities = set()

        hour_ago = (datetime.utcnow() - timedelta(hours=1)).isoformat()
        last_hour = 0

        for e in self._events:
            et = e.get("event_type", "unknown")
            by_type[et] = by_type.get(et, 0) + 1
            if e.get("city"):
                cities.add(e["city"])
            if e.get("timestamp", "") >= hour_ago:
                last_hour += 1

        return {
            "total_events": total,
            "events_by_type": by_type,
            "unique_cities": len(cities),
            "events_last_hour": last_hour,
        }
