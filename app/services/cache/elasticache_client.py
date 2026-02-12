"""AWS ElastiCache (Redis) implementation.

This module provides ElastiCache-based caching for production deployment.
Uses the same interface as Redis but with AWS-specific configuration.
"""

import json
import logging
from typing import Any, TypeVar

from app.services.base import BaseCache

logger = logging.getLogger(__name__)

T = TypeVar("T")


class ElastiCacheClient(BaseCache[T]):
    """AWS ElastiCache (Redis mode) client for production.

    This is essentially the same as RedisCache but configured for AWS ElastiCache.
    In production, use the ElastiCache endpoint URL.

    Example:
        cache = ElastiCacheClient(
            host="my-cluster.xxxxx.cache.amazonaws.com",
            port=6379,
            ttl_seconds=300,
            ssl=True
        )
        await cache.set("london", weather_data)
    """

    def __init__(
        self,
        host: str,
        port: int = 6379,
        password: str | None = None,
        ttl_seconds: int = 300,
        key_prefix: str = "weather:",
        ssl: bool = True,  # ElastiCache typically uses SSL
    ):
        """Initialize ElastiCache client.

        Args:
            host: ElastiCache endpoint
            port: Port (usually 6379)
            password: Auth token (if enabled)
            ttl_seconds: Default TTL in seconds
            key_prefix: Prefix for all keys
            ssl: Use SSL connection (recommended for production)
        """
        self._host = host
        self._port = port
        self._password = password
        self._ttl_seconds = ttl_seconds
        self._key_prefix = key_prefix
        self._ssl = ssl
        self._redis = None

        logger.info(f"ElastiCacheClient initialized with host: {host}:{port}, ssl: {ssl}")

    async def _get_redis(self):
        """Get or create the Redis connection."""
        if self._redis is None:
            try:
                import redis.asyncio as aioredis
            except ImportError:
                raise ImportError(
                    "redis is required for ElastiCache. Install it with: pip install redis"
                )

            self._redis = aioredis.Redis(
                host=self._host,
                port=self._port,
                password=self._password,
                ssl=self._ssl,
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
        """Get a value from ElastiCache."""
        redis = await self._get_redis()
        prefixed_key = self._make_key(key)

        value = await redis.get(prefixed_key)

        if value is None:
            logger.debug(f"ElastiCache MISS for key: {key}")
            return None

        logger.debug(f"ElastiCache HIT for key: {key}")

        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value

    async def set(self, key: str, value: T, ttl_seconds: int | None = None) -> None:
        """Set a value in ElastiCache."""
        redis = await self._get_redis()
        prefixed_key = self._make_key(key)
        ttl = ttl_seconds or self._ttl_seconds

        # Serialize value
        if hasattr(value, "model_dump"):
            serialized = json.dumps(value.model_dump(mode="json"), default=str)
        elif isinstance(value, dict):
            serialized = json.dumps(value, default=str)
        else:
            serialized = json.dumps(value, default=str)

        await redis.set(prefixed_key, serialized, ex=ttl)
        logger.debug(f"ElastiCache SET for key: {key}, ttl: {ttl}s")

    async def delete(self, key: str) -> bool:
        """Delete a key from ElastiCache."""
        redis = await self._get_redis()
        prefixed_key = self._make_key(key)

        result = await redis.delete(prefixed_key)

        if result:
            logger.debug(f"ElastiCache DELETE for key: {key}")
            return True
        return False

    async def clear(self) -> int:
        """Clear all keys with the prefix.

        Warning: Use carefully in production!
        """
        redis = await self._get_redis()

        pattern = f"{self._key_prefix}*"
        keys = []

        async for key in redis.scan_iter(match=pattern):
            keys.append(key)

        if keys:
            count = await redis.delete(*keys)
            logger.info(f"ElastiCache CLEARED: {count} keys removed")
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

        info = await redis.info("stats")

        return {
            "total_entries": count,
            "ttl_seconds": self._ttl_seconds,
            "hits": info.get("keyspace_hits", 0),
            "misses": info.get("keyspace_misses", 0),
            "connected_clients": info.get("connected_clients", 0),
        }
