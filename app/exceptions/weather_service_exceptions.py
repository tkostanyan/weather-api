"""Weather service related exception types.

These exceptions are raised when interacting with the external weather provider
(e.g., OpenWeatherMap).
"""

from __future__ import annotations


class WeatherAPIError(Exception):
    """Base exception for weather API errors."""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class CityNotFoundError(WeatherAPIError):
    """Raised when a city is not found."""

    def __init__(self, city: str):
        super().__init__(f"City '{city}' not found", status_code=404)
        self.city = city


class APIKeyError(WeatherAPIError):
    """Raised when the API key is invalid or missing."""

    def __init__(self):
        super().__init__("Invalid or missing API key", status_code=401)


class RateLimitError(WeatherAPIError):
    """Raised when API rate limit is exceeded."""

    def __init__(self):
        super().__init__("API rate limit exceeded", status_code=429)
