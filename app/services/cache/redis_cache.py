"""Redis cache implementation.

This module provides Redis-based caching for local development.
Uses aioredis for async Redis operations.
"""

import json
import logging
from typing import Any, TypeVar

from app.services.base import BaseCache

logger = logging.getLogger(__name__)

T = TypeVar("T")


class RedisCache(BaseCache[T]):
    """Redis cache implementation for local development.

    Example:
        cache = RedisCache(
            host="localhost",
            port=6379,
            ttl_seconds=300
        )
        await cache.set("london", weather_data)
        data = await cache.get("london")
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 6379,
        password: str | None = None,
        db: int = 0,
        ttl_seconds: int = 300,
        key_prefix: str = "weather:",
    ):
        """Initialize Redis cache.

        Args:
            host: Redis host
            port: Redis port
            password: Redis password (optional)
            db: Redis database number
            ttl_seconds: Default TTL in seconds
            key_prefix: Prefix for all keys
        """
        self._host = host
        self._port = port
        self._password = password
        self._db = db
        self._ttl_seconds = ttl_seconds
        self._key_prefix = key_prefix
        self._redis = None

        logger.info(f"RedisCache initialized with host: {host}:{port}, ttl: {ttl_seconds}s")

    async def _get_redis(self):
        """Get or create the Redis connection."""
        if self._redis is None:
            try:
                import redis.asyncio as aioredis
            except ImportError:
                raise ImportError(
                    "redis is required for Redis cache. Install it with: pip install redis"
                )

            self._redis = aioredis.Redis(
                host=self._host,
                port=self._port,
                password=self._password,
                db=self._db,
                decode_responses=True,
            )

        return self._redis

    async def close(self):
        """Close the Redis connection."""
        if self._redis:
            await self._redis.close()
            self._redis = None

    def _make_key(self, key: str) -> str:
        """Add prefix to key."""
        return f"{self._key_prefix}{key}"

    async def get(self, key: str) -> T | None:
        """Get a value from Redis cache."""
        redis = await self._get_redis()
        prefixed_key = self._make_key(key)

        value = await redis.get(prefixed_key)

        if value is None:
            logger.debug(f"Redis cache MISS for key: {key}")
            return None

        logger.debug(f"Redis cache HIT for key: {key}")

        try:
            data = json.loads(value)
            # Reconstruct the object if it has a model class
            return data
        except json.JSONDecodeError:
            return value

    async def set(self, key: str, value: T, ttl_seconds: int | None = None) -> None:
        """Set a value in Redis cache."""
        redis = await self._get_redis()
        prefixed_key = self._make_key(key)
        ttl = ttl_seconds or self._ttl_seconds

        # Serialize value
        if hasattr(value, "model_dump"):
            # Pydantic model
            serialized = json.dumps(value.model_dump(mode="json"), default=str)
        elif isinstance(value, dict):
            serialized = json.dumps(value, default=str)
        else:
            serialized = json.dumps(value, default=str)

        await redis.set(prefixed_key, serialized, ex=ttl)
        logger.debug(f"Redis cache SET for key: {key}, ttl: {ttl}s")

    async def delete(self, key: str) -> bool:
        """Delete a key from Redis cache."""
        redis = await self._get_redis()
        prefixed_key = self._make_key(key)

        result = await redis.delete(prefixed_key)

        if result:
            logger.debug(f"Redis cache DELETE for key: {key}")
            return True
        return False

    async def clear(self) -> int:
        """Clear all keys with the prefix."""
        redis = await self._get_redis()

        # Find all keys with prefix
        pattern = f"{self._key_prefix}*"
        keys = []

        async for key in redis.scan_iter(match=pattern):
            keys.append(key)

        if keys:
            count = await redis.delete(*keys)
            logger.info(f"Redis cache CLEARED: {count} keys removed")
            return count

        return 0

    async def stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        redis = await self._get_redis()

        # Count keys with prefix
        pattern = f"{self._key_prefix}*"
        count = 0
        async for _ in redis.scan_iter(match=pattern):
            count += 1

        # Get Redis info
        info = await redis.info("stats")

        return {
            "total_entries": count,
            "ttl_seconds": self._ttl_seconds,
            "hits": info.get("keyspace_hits", 0),
            "misses": info.get("keyspace_misses", 0),
        }
