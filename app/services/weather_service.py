"""Weather service layer for business logic.

This module contains the business logic for weather operations,
separated from the route handlers. It orchestrates interactions between
the weather API client, cache, storage, and event logging.
"""

import asyncio
import logging
import time

from app.config import Settings
from app.exceptions import (
    APIKeyError,
    CityNotFoundError,
    RateLimitError,
    WeatherAPIError,
)
from app.models.events import EventType
from app.models.weather import (
    ForecastResponse,
    MultiCityWeatherResponse,
    WeatherSummary,
)
from app.services.base import BaseCache, BaseEventLogger, BaseStorage
from app.services.weather_client import create_weather_client

logger = logging.getLogger(__name__)


class WeatherService:
    """Service for weather-related business logic.

    This service encapsulates the business logic for fetching, caching,
    storing, and logging weather data. It acts as an orchestration layer
    between the route handlers and various backend services.
    """

    def __init__(
        self,
        settings: Settings,
        cache: BaseCache,
        storage: BaseStorage,
        event_logger: BaseEventLogger,
    ):
        """Initialize the weather service.

        Args:
            settings: Application settings
            cache: Cache service instance
            storage: Storage service instance
            event_logger: Event logger service instance
        """
        self.settings = settings
        self.cache = cache
        self.storage = storage
        self.event_logger = event_logger

    async def get_weather(
        self,
        city: str,
        client_ip: str,
    ) -> tuple[WeatherSummary, float]:
        """Get current weather for a city with caching and logging.

        This method:
        1. Checks the cache for recent data (<5 min old)
        2. If not cached, fetches from OpenWeatherMap API
        3. Saves the response to storage (local files or S3)
        4. Logs the request to database (MongoDB or DynamoDB)
        5. Returns a formatted weather summary

        Args:
            city: City name (optionally with country code)
            client_ip: Client IP address for logging

        Returns:
            Tuple of (WeatherSummary, response_time_ms)

        Raises:
            CityNotFoundError: City not found
            APIKeyError: Invalid API key
            RateLimitError: API rate limit exceeded
            WeatherAPIError: Other API errors
        """
        start_time = time.time()

        # Normalize city name for cache key
        cache_key = city.lower().strip()

        # Check cache first
        cached_data = await self.cache.get(cache_key)
        if cached_data is not None:
            logger.info(f"Cache hit for city: {city}")

            # Log cache hit
            response_time_ms = (time.time() - start_time) * 1000
            await self.event_logger.log_weather_request(
                city=city,
                cached=True,
                client_ip=client_ip,
                response_time_ms=response_time_ms,
            )

            # Reconstruct WeatherSummary if cached as dict (from Redis)
            if isinstance(cached_data, dict):
                cached_data = WeatherSummary(**cached_data)

            # Mark as cached and return
            cached_data.cached = True
            return cached_data, response_time_ms

        # Fetch from API
        logger.info(f"Cache miss for city: {city}, fetching from API")

        weather_client = create_weather_client(self.settings)

        try:
            async with weather_client:
                summary = await weather_client.get_weather_summary(city)
        except CityNotFoundError as e:
            logger.warning(f"City not found: {city}")
            await self.event_logger.log_error(
                error_type="CityNotFound",
                message=str(e),
                city=city,
                client_ip=client_ip,
            )
            raise
        except APIKeyError:
            logger.error("Invalid API key")
            await self.event_logger.log_error(
                error_type="APIKeyError",
                message="Invalid or missing API key",
                city=city,
                client_ip=client_ip,
            )
            raise
        except RateLimitError:
            logger.warning("API rate limit exceeded")
            await self.event_logger.log_error(
                error_type="RateLimitError",
                message="External API rate limit exceeded",
                city=city,
                client_ip=client_ip,
            )
            raise
        except WeatherAPIError as e:
            logger.error(f"Weather API error: {e}")
            await self.event_logger.log_error(
                error_type="WeatherAPIError",
                message=str(e),
                city=city,
                client_ip=client_ip,
            )
            raise

        # Save to storage
        try:
            file_path = await self.storage.save_weather(
                summary.model_dump(mode="json"),
                city=summary.city,
                timestamp=summary.timestamp,
            )
            logger.info(f"Saved weather data to: {file_path}")
        except Exception as e:
            logger.error(f"Failed to save weather data: {e}")
            file_path = None

        # Cache the result
        await self.cache.set(cache_key, summary)

        # Log the request
        response_time_ms = (time.time() - start_time) * 1000
        await self.event_logger.log_weather_request(
            city=city,
            cached=False,
            file_path=file_path,
            client_ip=client_ip,
            response_time_ms=response_time_ms,
        )

        return summary, response_time_ms

    async def get_forecast(
        self,
        city: str,
        days: int,
        client_ip: str,
    ) -> ForecastResponse:
        """Get weather forecast for a city.

        Args:
            city: City name
            days: Number of days to forecast (1-5)
            client_ip: Client IP address for logging

        Returns:
            ForecastResponse with forecast data

        Raises:
            CityNotFoundError: City not found
            WeatherAPIError: API errors
        """
        # Check cache
        cache_key = f"forecast:{city.lower()}:{days}"
        cached = await self.cache.get(cache_key)
        if cached is not None:
            logger.info(f"Cache hit for forecast: {city}")
            # Reconstruct ForecastResponse if cached as dict
            if isinstance(cached, dict):
                cached = ForecastResponse(**cached)
            cached.cached = True
            return cached

        weather_client = create_weather_client(self.settings)

        try:
            async with weather_client:
                forecast = await weather_client.get_forecast(city, days)
        except (CityNotFoundError, WeatherAPIError):
            raise

        # Cache and log
        await self.cache.set(cache_key, forecast)
        await self.event_logger.log(
            event_type=EventType.FORECAST_REQUEST,
            city=city,
            details=f'{{"days": {days}}}',
            client_ip=client_ip,
        )

        return forecast

    async def get_multi_city_weather(
        self,
        cities: list[str],
        client_ip: str,
    ) -> MultiCityWeatherResponse:
        """Get weather for multiple cities concurrently.

        Args:
            cities: List of city names
            client_ip: Client IP address for logging

        Returns:
            MultiCityWeatherResponse with results and errors
        """

        async def fetch_city(
            city: str,
        ) -> tuple[str, WeatherSummary | None, str | None]:
            """Fetch weather for a single city, returning (city, result, error)."""
            cache_key = city.lower().strip()

            # Check cache
            cached = await self.cache.get(cache_key)
            if cached is not None:
                # Reconstruct if cached as dict
                if isinstance(cached, dict):
                    cached = WeatherSummary(**cached)
                cached.cached = True
                return (city, cached, None)

            # Fetch from API
            weather_client = create_weather_client(self.settings)
            try:
                async with weather_client:
                    summary = await weather_client.get_weather_summary(city)

                # Cache and save
                await self.cache.set(cache_key, summary)
                await self.storage.save_weather(
                    summary.model_dump(mode="json"),
                    city=summary.city,
                )

                return (city, summary, None)
            except CityNotFoundError:
                return (city, None, f"City '{city}' not found")
            except WeatherAPIError as e:
                return (city, None, str(e))

        # Fetch all cities concurrently
        results = await asyncio.gather(*[fetch_city(city) for city in cities])

        # Separate successes and errors
        weather_results = []
        errors = {}

        for city, result, error in results:
            if result:
                weather_results.append(result)
            elif error:
                errors[city] = error

        # Log the request
        await self.event_logger.log(
            event_type=EventType.MULTI_CITY_REQUEST,
            details=f'{{"cities": {len(cities)}, "successful": {len(weather_results)}}}',
            client_ip=client_ip,
        )

        return MultiCityWeatherResponse(
            results=weather_results,
            errors=errors,
            total_cities=len(cities),
            successful=len(weather_results),
        )
