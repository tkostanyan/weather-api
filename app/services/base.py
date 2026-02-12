"""Abstract base classes for services.

This module defines the abstract interfaces for Storage, Database (Event Logging),
and Cache services. Concrete implementations for local and production environments
inherit from these base classes.

Design Pattern: Abstract Factory + Strategy
- Allows easy swapping between local dev and production AWS services
- Environment variable (ENVIRONMENT) controls which implementations are used
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Generic, TypeVar

T = TypeVar("T")


class BaseStorage(ABC):
    """Abstract base class for storage services (S3 / Local File).

    Implementations:
    - LocalFileStorage: Saves to local filesystem
    - S3Storage: Saves to AWS S3 bucket
    """

    @abstractmethod
    async def save(self, data: dict[str, Any], key: str) -> str:
        """Save data to storage.

        Args:
            data: Dictionary to save as JSON
            key: Storage key/filename

        Returns:
            Full path/URL where data was saved
        """
        pass

    @abstractmethod
    async def load(self, key: str) -> dict[str, Any] | None:
        """Load data from storage.

        Args:
            key: Storage key/filename

        Returns:
            Loaded dictionary or None if not found
        """
        pass

    @abstractmethod
    async def delete(self, key: str) -> bool:
        """Delete data from storage.

        Args:
            key: Storage key/filename

        Returns:
            True if deleted, False if not found
        """
        pass

    @abstractmethod
    async def list_keys(self, prefix: str = "") -> list[str]:
        """List all keys in storage.

        Args:
            prefix: Optional key prefix filter

        Returns:
            List of keys
        """
        pass

    def generate_weather_key(self, city: str, timestamp: datetime | None = None) -> str:
        """Generate a storage key for weather data.

        Args:
            city: City name
            timestamp: Optional timestamp (defaults to now)

        Returns:
            Storage key in format: {city}_{timestamp}.json
        """
        ts = timestamp or datetime.utcnow()
        safe_city = "".join(c if c.isalnum() else "_" for c in city.lower())
        timestamp_str = ts.strftime("%Y%m%d_%H%M%S")
        return f"weather/{safe_city}_{timestamp_str}.json"

    async def save_weather(
        self, data: dict[str, Any], city: str, timestamp: datetime | None = None
    ) -> str:
        """Convenience method to save weather data with auto-generated key.

        Args:
            data: Weather data dictionary
            city: City name
            timestamp: Optional timestamp for key generation

        Returns:
            Full path/URL where data was saved
        """
        key = self.generate_weather_key(city, timestamp)
        return await self.save(data, key)


class BaseEventLogger(ABC):
    """Abstract base class for event logging services (DynamoDB / MongoDB / SQLite).

    Implementations:
    - SQLiteEventLogger: Local development with SQLite
    - MongoDBEventLogger: Local development with MongoDB
    - DynamoDBEventLogger: Production with AWS DynamoDB
    """

    @abstractmethod
    async def initialize(self) -> None:
        """Initialize the database/table structure."""
        pass

    @abstractmethod
    async def log(
        self,
        event_type: str,
        city: str | None = None,
        file_path: str | None = None,
        details: str | None = None,
        client_ip: str | None = None,
    ) -> str:
        """Log an event.

        Args:
            event_type: Type of event
            city: City name (optional)
            file_path: File path/URL (optional)
            details: Additional details as JSON string (optional)
            client_ip: Client IP address (optional)

        Returns:
            Event ID
        """
        pass

    @abstractmethod
    async def get_events(
        self,
        limit: int = 100,
        event_type: str | None = None,
        city: str | None = None,
    ) -> list[dict[str, Any]]:
        """Get logged events with optional filters.

        Args:
            limit: Maximum number of events
            event_type: Filter by event type
            city: Filter by city

        Returns:
            List of event dictionaries
        """
        pass

    @abstractmethod
    async def get_stats(self) -> dict[str, Any]:
        """Get event statistics.

        Returns:
            Dictionary with statistics
        """
        pass

    async def log_weather_request(
        self,
        city: str,
        cached: bool = False,
        file_path: str | None = None,
        client_ip: str | None = None,
        response_time_ms: float | None = None,
    ) -> str:
        """Convenience method to log a weather request.

        Args:
            city: Requested city
            cached: Whether response was from cache
            file_path: Path where data was saved
            client_ip: Client IP address
            response_time_ms: Response time in milliseconds

        Returns:
            Event ID
        """
        import json

        event_type = "weather_cached" if cached else "weather_fetched"
        details = json.dumps(
            {
                "cached": cached,
                "response_time_ms": response_time_ms,
            }
        )

        return await self.log(
            event_type=event_type,
            city=city,
            file_path=file_path,
            details=details,
            client_ip=client_ip,
        )

    async def log_error(
        self,
        error_type: str,
        message: str,
        city: str | None = None,
        client_ip: str | None = None,
    ) -> str:
        """Log an error event.

        Args:
            error_type: Type of error
            message: Error message
            city: City (if applicable)
            client_ip: Client IP address

        Returns:
            Event ID
        """
        import json

        details = json.dumps(
            {
                "error_type": error_type,
                "message": message,
            }
        )

        return await self.log(
            event_type="error",
            city=city,
            details=details,
            client_ip=client_ip,
        )


class BaseCache(ABC, Generic[T]):
    """Abstract base class for cache services (Redis / ElastiCache / In-Memory).

    Implementations:
    - InMemoryCache: Simple in-memory cache for single instance
    - RedisCache: Local development with Redis
    - ElastiCacheClient: Production with AWS ElastiCache
    """

    @abstractmethod
    async def get(self, key: str) -> T | None:
        """Get a value from cache.

        Args:
            key: Cache key

        Returns:
            Cached value or None if not found/expired
        """
        pass

    @abstractmethod
    async def set(self, key: str, value: T, ttl_seconds: int | None = None) -> None:
        """Set a value in cache.

        Args:
            key: Cache key
            value: Value to cache
            ttl_seconds: Optional TTL override
        """
        pass

    @abstractmethod
    async def delete(self, key: str) -> bool:
        """Delete a key from cache.

        Args:
            key: Cache key

        Returns:
            True if deleted, False if not found
        """
        pass

    @abstractmethod
    async def clear(self) -> int:
        """Clear all entries from cache.

        Returns:
            Number of entries cleared
        """
        pass

    @abstractmethod
    async def stats(self) -> dict[str, Any]:
        """Get cache statistics.

        Returns:
            Dictionary with cache stats
        """
        pass
