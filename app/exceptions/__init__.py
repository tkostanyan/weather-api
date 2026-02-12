"""Application exception types.

Exceptions are grouped into two modules:
- `weather_service_exceptions.py`: errors talking to external weather provider
- `service_exceptions.py`: errors from internal backing services

Import from `app.exceptions` for a stable public surface.
"""

from app.exceptions.service_exceptions import (
    CacheError,
    ConfigurationError,
    DatabaseError,
    ServiceError,
    StorageError,
)
from app.exceptions.weather_service_exceptions import (
    APIKeyError,
    CityNotFoundError,
    RateLimitError,
    WeatherAPIError,
)

__all__ = [
    # weather
    "WeatherAPIError",
    "CityNotFoundError",
    "APIKeyError",
    "RateLimitError",
    # internal
    "ServiceError",
    "ConfigurationError",
    "StorageError",
    "CacheError",
    "DatabaseError",
]
