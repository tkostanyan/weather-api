"""Cache services package.

Provides abstract cache interface and implementations for:
- In-memory cache (testing/single instance)
- Redis (local development)
- ElastiCache (AWS production)
"""

from app.services.cache.elasticache_client import ElastiCacheClient
from app.services.cache.memory_cache import InMemoryCache
from app.services.cache.redis_cache import RedisCache

__all__ = ["InMemoryCache", "RedisCache", "ElastiCacheClient"]
