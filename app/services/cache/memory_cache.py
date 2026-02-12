"""In-memory cache implementation.

This module provides a simple in-memory TTL cache.
Useful for testing or single-instance deployments.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any, Generic, TypeVar

from app.services.base import BaseCache

logger = logging.getLogger(__name__)

T = TypeVar("T")


class CacheEntry(Generic[T]):
    """A single cache entry with timestamp."""

    def __init__(self, value: T, created_at: datetime | None = None):
        self.value = value
        self.created_at = created_at or datetime.utcnow()

    def is_expired(self, ttl_seconds: int) -> bool:
        """Check if this entry has expired."""
        expiry_time = self.created_at + timedelta(seconds=ttl_seconds)
        return datetime.utcnow() > expiry_time

    def age_seconds(self) -> float:
        """Get the age of this entry in seconds."""
        return (datetime.utcnow() - self.created_at).total_seconds()


class InMemoryCache(BaseCache[T]):
    """Simple in-memory TTL cache.

    For single-instance deployment or testing only.
    Data is lost on restart.

    Example:
        cache = InMemoryCache(ttl_seconds=300)
        await cache.set("london", weather_data)
        data = await cache.get("london")
    """

    def __init__(self, ttl_seconds: int = 300):
        """Initialize in-memory cache.

        Args:
            ttl_seconds: Default TTL in seconds
        """
        self._cache: dict[str, CacheEntry[T]] = {}
        self._ttl_seconds = ttl_seconds
        self._lock = asyncio.Lock()

        logger.info(f"InMemoryCache initialized with ttl: {ttl_seconds}s")

    @property
    def ttl_seconds(self) -> int:
        """Get the TTL in seconds."""
        return self._ttl_seconds

    async def get(self, key: str) -> T | None:
        """Get a value from cache if it exists and hasn't expired."""
        async with self._lock:
            entry = self._cache.get(key)

            if entry is None:
                logger.debug(f"InMemoryCache MISS for key: {key}")
                return None

            if entry.is_expired(self._ttl_seconds):
                logger.debug(f"InMemoryCache EXPIRED for key: {key}")
                del self._cache[key]
                return None

            logger.debug(f"InMemoryCache HIT for key: {key} (age: {entry.age_seconds():.1f}s)")
            return entry.value

    async def set(self, key: str, value: T, ttl_seconds: int | None = None) -> None:
        """Set a value in cache.

        Note: ttl_seconds parameter is ignored for in-memory cache,
        which uses the global TTL. This maintains API compatibility.
        """
        async with self._lock:
            self._cache[key] = CacheEntry(value)
            logger.debug(f"InMemoryCache SET for key: {key}")

    async def delete(self, key: str) -> bool:
        """Delete a key from cache."""
        async with self._lock:
            if key in self._cache:
                del self._cache[key]
                logger.debug(f"InMemoryCache DELETE for key: {key}")
                return True
            return False

    async def clear(self) -> int:
        """Clear all entries from cache."""
        async with self._lock:
            count = len(self._cache)
            self._cache.clear()
            logger.info(f"InMemoryCache CLEARED: {count} entries removed")
            return count

    async def stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        async with self._lock:
            total = len(self._cache)
            expired = sum(
                1 for entry in self._cache.values() if entry.is_expired(self._ttl_seconds)
            )

            return {
                "total_entries": total,
                "valid_entries": total - expired,
                "expired_entries": expired,
                "ttl_seconds": self._ttl_seconds,
            }

    async def cleanup_expired(self) -> int:
        """Remove all expired entries."""
        async with self._lock:
            expired_keys = [
                key for key, entry in self._cache.items() if entry.is_expired(self._ttl_seconds)
            ]

            for key in expired_keys:
                del self._cache[key]

            if expired_keys:
                logger.info(f"InMemoryCache cleanup: {len(expired_keys)} expired entries removed")

            return len(expired_keys)

    def __len__(self) -> int:
        """Return the number of entries in cache."""
        return len(self._cache)
