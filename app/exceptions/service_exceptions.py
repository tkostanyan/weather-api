"""Non-weather service related exception types.

Use this module for exceptions related to internal services/backends such as:
- Storage (S3 / local files)
- Cache (Redis / ElastiCache)
- Databases (MongoDB / DynamoDB)
- Application configuration
"""

from __future__ import annotations


class ServiceError(Exception):
    """Base exception for internal service failures."""


class ConfigurationError(ServiceError):
    """Raised when required configuration is missing or invalid."""


class StorageError(ServiceError):
    """Raised when storage operations fail."""


class CacheError(ServiceError):
    """Raised when cache operations fail."""


class DatabaseError(ServiceError):
    """Raised when database operations fail."""
