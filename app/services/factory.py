"""Service Factory for initializing services based on environment.

This module provides a factory pattern for creating service instances
based on the ENVIRONMENT variable. It supports:

- local: MongoDB, Local File Storage, Redis
- prod: DynamoDB, S3, ElastiCache

Usage:
    from app.services.factory import ServiceFactory

    factory = ServiceFactory(settings)
    storage = factory.get_storage()
    cache = factory.get_cache()
    event_logger = factory.get_event_logger()
"""

import logging
from enum import StrEnum
from typing import Optional

from app.config import Settings
from app.services.base import BaseCache, BaseEventLogger, BaseStorage

logger = logging.getLogger(__name__)


class Environment(StrEnum):
    """Supported environments."""

    LOCAL = "local"
    PROD = "prod"
    TEST = "test"


class ServiceFactory:
    """Factory for creating service instances based on environment.

    The factory reads the ENVIRONMENT setting and initializes the
    appropriate implementations:

    LOCAL environment:
    - Storage: LocalFileStorage (writes to ./data folder)
    - Cache: RedisCache (connects to local Redis)
    - EventLogger: MongoDBEventLogger (connects to local MongoDB)

    PROD environment:
    - Storage: S3Storage (AWS S3)
    - Cache: ElastiCacheClient (AWS ElastiCache)
    - EventLogger: DynamoDBEventLogger (AWS DynamoDB)

    TEST environment:
    - Storage: LocalFileStorage (temp directory)
    - Cache: InMemoryCache
    - EventLogger: InMemoryEventLogger (simple dict-based)
    """

    _instance: Optional["ServiceFactory"] = None

    def __init__(self, settings: Settings):
        """Initialize the factory with settings.

        Args:
            settings: Application settings
        """
        self._settings = settings
        self._environment = Environment(settings.environment)

        # Cached service instances
        self._storage: BaseStorage | None = None
        self._cache: BaseCache | None = None
        self._event_logger: BaseEventLogger | None = None

        logger.info(f"ServiceFactory initialized for environment: {self._environment.value}")

    @property
    def environment(self) -> Environment:
        """Get the current environment."""
        return self._environment

    def get_storage(self) -> BaseStorage:
        """Get the storage service instance.

        Returns:
            BaseStorage implementation based on environment
        """
        if self._storage is not None:
            return self._storage

        if self._environment == Environment.PROD:
            self._storage = self._create_s3_storage()
        else:
            self._storage = self._create_local_storage()

        return self._storage

    def get_cache(self) -> BaseCache:
        """Get the cache service instance.

        Returns:
            BaseCache implementation based on environment
        """
        if self._cache is not None:
            return self._cache

        if self._environment == Environment.PROD:
            self._cache = self._create_elasticache()
        elif self._environment == Environment.TEST:
            self._cache = self._create_memory_cache()
        else:
            self._cache = self._create_redis_cache()

        return self._cache

    def get_event_logger(self) -> BaseEventLogger:
        """Get the event logger service instance.

        Returns:
            BaseEventLogger implementation based on environment
        """
        if self._event_logger is not None:
            return self._event_logger

        if self._environment == Environment.PROD:
            self._event_logger = self._create_dynamodb_logger()
        elif self._environment == Environment.TEST:
            self._event_logger = self._create_memory_logger()
        else:
            self._event_logger = self._create_mongodb_logger()

        return self._event_logger

    def _create_local_storage(self) -> BaseStorage:
        """Create local file storage."""
        from app.services.storage import LocalFileStorage

        data_dir = self._settings.data_dir
        data_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"Creating LocalFileStorage with data_dir: {data_dir}")
        return LocalFileStorage(data_dir=data_dir)

    def _create_s3_storage(self) -> BaseStorage:
        """Create S3 storage."""
        from app.services.storage import S3Storage

        logger.info(f"Creating S3Storage with bucket: {self._settings.s3_bucket_name}")
        return S3Storage(
            bucket_name=self._settings.s3_bucket_name,
            region=self._settings.aws_region,
            aws_access_key_id=self._settings.aws_access_key_id,
            aws_secret_access_key=self._settings.aws_secret_access_key,
            endpoint_url=self._settings.aws_endpoint_url,
        )

    def _create_memory_cache(self) -> BaseCache:
        """Create in-memory cache."""
        from app.services.cache import InMemoryCache

        logger.info(f"Creating InMemoryCache with ttl: {self._settings.cache_ttl_seconds}s")
        return InMemoryCache(ttl_seconds=self._settings.cache_ttl_seconds)

    def _create_redis_cache(self) -> BaseCache:
        """Create Redis cache."""
        from app.services.cache import RedisCache

        logger.info(
            f"Creating RedisCache with host: {self._settings.redis_host}:{self._settings.redis_port}"
        )
        return RedisCache(
            host=self._settings.redis_host,
            port=self._settings.redis_port,
            password=self._settings.redis_password,
            ttl_seconds=self._settings.cache_ttl_seconds,
        )

    def _create_elasticache(self) -> BaseCache:
        """Create ElastiCache client."""
        from app.services.cache import ElastiCacheClient

        logger.info(f"Creating ElastiCacheClient with host: {self._settings.elasticache_host}")
        return ElastiCacheClient(
            host=self._settings.elasticache_host,
            port=self._settings.elasticache_port,
            password=self._settings.elasticache_password,
            ttl_seconds=self._settings.cache_ttl_seconds,
            ssl=True,
        )

    def _create_mongodb_logger(self) -> BaseEventLogger:
        """Create MongoDB event logger."""
        from app.services.database import MongoDBEventLogger

        logger.info(
            f"Creating MongoDBEventLogger with connection: {self._settings.mongodb_connection_string}"
        )
        return MongoDBEventLogger(
            connection_string=self._settings.mongodb_connection_string,
            database_name=self._settings.mongodb_database_name,
        )

    def _create_dynamodb_logger(self) -> BaseEventLogger:
        """Create DynamoDB event logger."""
        from app.services.database import DynamoDBEventLogger

        logger.info(
            f"Creating DynamoDBEventLogger with table: {self._settings.dynamodb_table_name}"
        )
        return DynamoDBEventLogger(
            table_name=self._settings.dynamodb_table_name,
            region=self._settings.aws_region,
            aws_access_key_id=self._settings.aws_access_key_id,
            aws_secret_access_key=self._settings.aws_secret_access_key,
            endpoint_url=self._settings.aws_endpoint_url,
        )

    def _create_memory_logger(self) -> BaseEventLogger:
        """Create in-memory event logger (test environment)."""
        from app.services.database.memory_logger import InMemoryEventLogger

        logger.info("Creating InMemoryEventLogger (test environment)")
        return InMemoryEventLogger()

    async def initialize(self) -> None:
        """Initialize all services (e.g., create tables, indexes)."""
        event_logger = self.get_event_logger()
        await event_logger.initialize()
        logger.info("All services initialized")

    async def close(self) -> None:
        """Close all service connections."""
        if self._cache and hasattr(self._cache, "close"):
            await self._cache.close()

        if self._event_logger and hasattr(self._event_logger, "close"):
            await self._event_logger.close()

        if self._storage and hasattr(self._storage, "close"):
            await self._storage.close()

        logger.info("All service connections closed")

    def reset(self) -> None:
        """Reset all cached service instances."""
        self._storage = None
        self._cache = None
        self._event_logger = None


# Global factory instance
_factory: ServiceFactory | None = None


def get_service_factory(settings: Settings) -> ServiceFactory:
    """Get or create the global service factory.

    Args:
        settings: Application settings

    Returns:
        ServiceFactory instance
    """
    global _factory
    if _factory is None:
        _factory = ServiceFactory(settings)
    return _factory


def reset_service_factory() -> None:
    """Reset the global service factory (for testing)."""
    global _factory
    if _factory:
        _factory.reset()
    _factory = None
