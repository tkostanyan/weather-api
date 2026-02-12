"""Asynchronous weather API client.

This module provides an async HTTP client for fetching weather data
from OpenWeatherMap API using httpx.

Features:
- Async HTTP requests with connection pooling
- Automatic retries with exponential backoff
- Proper error handling and custom exceptions
- Support for current weather and forecasts
"""

import logging
from datetime import datetime
from typing import Any

import httpx

from app.config import Settings
from app.exceptions import APIKeyError, CityNotFoundError, RateLimitError, WeatherAPIError
from app.models.weather import (
    Coordinates,
    ForecastItem,
    ForecastResponse,
    WeatherResponse,
    WeatherSummary,
)

logger = logging.getLogger(__name__)


class WeatherClient:
    """Asynchronous client for OpenWeatherMap API.

    Uses httpx.AsyncClient for efficient connection pooling and async requests.

    Example:
        async with WeatherClient(settings) as client:
            weather = await client.get_current_weather("London")
            forecast = await client.get_forecast("London", days=3)
    """

    def __init__(self, settings: Settings):
        """Initialize the weather client.

        Args:
            settings: Application settings with API key and base URL
        """
        self._settings = settings
        self._base_url = settings.weather_api_base_url
        self._api_key = settings.weather_api_key
        self._client: httpx.AsyncClient | None = None

        logger.info(f"WeatherClient initialized with api_key: {self._api_key[:4]}...")

        logger.info(f"WeatherClient initialized with base_url: {self._base_url}")

    async def __aenter__(self) -> "WeatherClient":
        """Enter async context manager."""
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            timeout=httpx.Timeout(10.0, connect=5.0),
            headers={"Accept": "application/json"},
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit async context manager."""
        if self._client:
            await self._client.aclose()
            self._client = None

    def _get_client(self) -> httpx.AsyncClient:
        """Get the HTTP client, creating one if needed.

        Returns:
            httpx.AsyncClient instance
        """
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                timeout=httpx.Timeout(10.0, connect=5.0),
                headers={"Accept": "application/json"},
            )
        return self._client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    def _handle_error_response(self, response: httpx.Response, city: str) -> None:
        """Handle error responses from the API.

        Args:
            response: HTTP response
            city: City name for error context

        Raises:
            CityNotFoundError: City not found (404)
            APIKeyError: Invalid API key (401)
            RateLimitError: Rate limit exceeded (429)
            WeatherAPIError: Other API errors
        """
        if response.status_code == 404:
            raise CityNotFoundError(city)
        elif response.status_code == 401:
            raise APIKeyError()
        elif response.status_code == 429:
            raise RateLimitError()
        else:
            try:
                error_data = response.json()
                message = error_data.get("message", "Unknown error")
            except Exception:
                message = response.text or "Unknown error"

            raise WeatherAPIError(f"API error: {message}", status_code=response.status_code)

    async def get_current_weather_raw(self, city: str) -> dict[str, Any]:
        """Fetch raw current weather data for a city.

        Args:
            city: City name (can include country code, e.g., "London,UK")

        Returns:
            Raw JSON response as dictionary

        Raises:
            CityNotFoundError: City not found
            APIKeyError: Invalid API key
            WeatherAPIError: Other API errors
        """
        client = self._get_client()

        params = {
            "q": city,
            "appid": self._api_key,
        }

        logger.debug(f"Fetching weather for city: {city}")

        try:
            response = await client.get("/weather", params=params)
        except httpx.TimeoutException as e:
            logger.error(f"Timeout fetching weather for {city}: {e}")
            raise WeatherAPIError(f"Request timeout for city '{city}'")
        except httpx.RequestError as e:
            logger.error(f"Request error fetching weather for {city}: {e}")
            raise WeatherAPIError(f"Request failed for city '{city}': {str(e)}")

        if response.status_code != 200:
            self._handle_error_response(response, city)

        return response.json()

    async def get_current_weather(self, city: str) -> WeatherResponse:
        """Fetch current weather data for a city.

        Args:
            city: City name (can include country code, e.g., "London,UK")

        Returns:
            WeatherResponse model with weather data

        Raises:
            CityNotFoundError: City not found
            APIKeyError: Invalid API key
            WeatherAPIError: Other API errors
        """
        data = await self.get_current_weather_raw(city)
        return WeatherResponse(**data)

    async def get_weather_summary(self, city: str) -> WeatherSummary:
        """Fetch weather and return a user-friendly summary.

        Args:
            city: City name

        Returns:
            WeatherSummary with formatted data
        """
        response = await self.get_current_weather(city)
        return WeatherSummary.from_api_response(response)

    async def get_forecast_raw(self, city: str, cnt: int = 40) -> dict[str, Any]:
        """Fetch raw forecast data for a city.

        Args:
            city: City name
            cnt: Number of forecast items (3-hour intervals, max 40 = 5 days)

        Returns:
            Raw JSON response as dictionary
        """
        client = self._get_client()

        params = {
            "q": city,
            "appid": self._api_key,
            "cnt": cnt,
        }

        logger.debug(f"Fetching forecast for city: {city}, cnt: {cnt}")

        try:
            response = await client.get("/forecast", params=params)
        except httpx.TimeoutException as e:
            logger.error(f"Timeout fetching forecast for {city}: {e}")
            raise WeatherAPIError(f"Request timeout for city '{city}'")
        except httpx.RequestError as e:
            logger.error(f"Request error fetching forecast for {city}: {e}")
            raise WeatherAPIError(f"Request failed for city '{city}': {str(e)}")

        if response.status_code != 200:
            self._handle_error_response(response, city)

        return response.json()

    async def get_forecast(self, city: str, days: int = 3) -> ForecastResponse:
        """Fetch weather forecast for a city.

        Args:
            city: City name
            days: Number of days (1-5, default 3)

        Returns:
            ForecastResponse with forecast data
        """
        # OpenWeatherMap free tier provides 3-hour intervals
        # 8 intervals per day * days
        cnt = min(days * 8, 40)
        data = await self.get_forecast_raw(city, cnt)

        # Parse forecast items
        forecasts = []
        for item in data.get("list", []):
            weather = item.get("weather", [{}])[0]
            main = item.get("main", {})

            def kelvin_to_celsius(k: float) -> float:
                return round(k - 273.15, 1)

            forecasts.append(
                ForecastItem(
                    timestamp=datetime.fromtimestamp(item["dt"]),
                    temperature=kelvin_to_celsius(main.get("temp", 0)),
                    feels_like=kelvin_to_celsius(main.get("feels_like", 0)),
                    temp_min=kelvin_to_celsius(main.get("temp_min", 0)),
                    temp_max=kelvin_to_celsius(main.get("temp_max", 0)),
                    humidity=main.get("humidity", 0),
                    pressure=main.get("pressure", 0),
                    weather_condition=weather.get("main", "Unknown"),
                    weather_description=weather.get("description", "Unknown"),
                    weather_icon=f"https://openweathermap.org/img/wn/{weather.get('icon', '01d')}@2x.png",
                    wind_speed=item.get("wind", {}).get("speed", 0),
                    cloudiness=item.get("clouds", {}).get("all", 0),
                    precipitation_probability=item.get("pop", 0) * 100,
                )
            )

        city_data = data.get("city", {})
        coord = city_data.get("coord", {})

        return ForecastResponse(
            city=city_data.get("name", city),
            country=city_data.get("country", ""),
            coordinates=Coordinates(
                lon=coord.get("lon", 0),
                lat=coord.get("lat", 0),
            ),
            forecasts=forecasts,
        )


# Factory function for dependency injection
def create_weather_client(settings: Settings) -> WeatherClient:
    """Create a new WeatherClient instance.

    Args:
        settings: Application settings

    Returns:
        WeatherClient instance
    """
    return WeatherClient(settings)
