"""Weather API routes.

This module defines the weather API endpoints with proper error handling.
Business logic is delegated to the WeatherService layer.
"""

import logging
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Request, status

from app.dependencies import WeatherServiceDep
from app.exceptions import APIKeyError, CityNotFoundError, RateLimitError, WeatherAPIError
from app.models.weather import (
    ErrorResponse,
    ForecastResponse,
    MultiCityWeatherResponse,
    WeatherSummary,
)
from app.rate_limiter import limiter

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/weather",
    tags=["Weather"],
    responses={
        404: {"model": ErrorResponse, "description": "City not found"},
        429: {"model": ErrorResponse, "description": "Rate limit exceeded"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)


def get_client_ip(request: Request) -> str:
    """Extract client IP from request."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


@router.get(
    "",
    response_model=WeatherSummary,
    summary="Get current weather",
    description="""
    Fetch current weather data for a city.

    The response includes temperature, humidity, wind speed, and other
    weather conditions. Data is cached for 5 minutes to improve performance.

    **Examples:**
    - `/weather?city=London`
    - `/weather?city=New York`
    - `/weather?city=London,UK` (with country code)
    """,
    responses={
        200: {
            "description": "Weather data retrieved successfully",
            "content": {
                "application/json": {
                    "example": {
                        "city": "London",
                        "country": "GB",
                        "temperature": 15.2,
                        "humidity": 72,
                        "weather_condition": "Clouds",
                        "cached": False,
                    }
                }
            },
        }
    },
)
@limiter.limit("60/minute")
async def get_weather(
    request: Request,
    city: Annotated[
        str,
        Query(
            min_length=1,
            max_length=100,
            description="City name (optionally with country code, e.g., 'London,UK')",
            examples=["London", "New York", "Paris,FR"],
        ),
    ],
    weather_service: WeatherServiceDep,
) -> WeatherSummary:
    """Get current weather for a city.

    This endpoint:
    1. Checks the cache for recent data (<5 min old)
    2. If not cached, fetches from OpenWeatherMap API
    3. Saves the response to storage (local files or S3)
    4. Logs the request to database (MongoDB or DynamoDB)
    5. Returns a formatted weather summary
    """
    client_ip = get_client_ip(request)

    try:
        summary, _ = await weather_service.get_weather(city, client_ip)
        return summary
    except CityNotFoundError:
        logger.warning(f"City not found: {city}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "CityNotFound",
                "message": f"City '{city}' not found",
                "detail": "Please check the city name and try again",
            },
        )
    except APIKeyError:
        logger.error("Invalid API key")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "ConfigurationError",
                "message": "Weather service is not properly configured",
                "detail": "Please contact the administrator",
            },
        )
    except RateLimitError:
        logger.warning("API rate limit exceeded")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error": "RateLimitExceeded",
                "message": "Service temporarily unavailable",
                "detail": "Please try again later",
            },
        )
    except WeatherAPIError as e:
        logger.error(f"Weather API error: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "error": "ExternalAPIError",
                "message": "Failed to fetch weather data",
                "detail": str(e),
            },
        )


@router.get(
    "/forecast",
    response_model=ForecastResponse,
    summary="Get weather forecast",
    description="""
    Fetch weather forecast for a city.

    Returns forecast data in 3-hour intervals for the specified number of days.
    Maximum 5 days available on free tier.
    """,
)
@limiter.limit("30/minute")
async def get_forecast(
    request: Request,
    city: Annotated[
        str,
        Query(
            min_length=1,
            max_length=100,
            description="City name",
            examples=["London", "New York"],
        ),
    ],
    weather_service: WeatherServiceDep,
    days: Annotated[
        int,
        Query(
            ge=1,
            le=5,
            description="Number of days to forecast (1-5)",
        ),
    ] = 3,
) -> ForecastResponse:
    """Get weather forecast for a city."""
    client_ip = get_client_ip(request)

    try:
        forecast = await weather_service.get_forecast(city, days, client_ip)
        return forecast
    except CityNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "CityNotFound", "message": f"City '{city}' not found"},
        )
    except WeatherAPIError as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"error": "ExternalAPIError", "message": str(e)},
        )


@router.get(
    "/multi",
    response_model=MultiCityWeatherResponse,
    summary="Get weather for multiple cities",
    description="""
    Fetch weather data for multiple cities in a single request.

    Cities should be provided as a comma-separated list.
    Maximum 10 cities per request.

    **Example:** `/weather/multi?cities=London,Paris,Berlin`
    """,
)
@limiter.limit("10/minute")
async def get_multi_city_weather(
    request: Request,
    cities: Annotated[
        str,
        Query(
            description="Comma-separated list of cities (max 10)",
            examples=["London,Paris,Berlin"],
        ),
    ],
    weather_service: WeatherServiceDep,
) -> MultiCityWeatherResponse:
    """Get weather for multiple cities concurrently."""
    client_ip = get_client_ip(request)

    # Parse and validate cities
    city_list = [c.strip() for c in cities.split(",") if c.strip()]

    if not city_list:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "InvalidInput", "message": "No valid cities provided"},
        )

    if len(city_list) > 10:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "TooManyCities", "message": "Maximum 10 cities allowed"},
        )

    return await weather_service.get_multi_city_weather(city_list, client_ip)
