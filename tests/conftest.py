"""Pytest configuration and fixtures."""

import asyncio
import os
import tempfile
from collections.abc import AsyncGenerator, Generator
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from httpx import AsyncClient

# Set test environment before importing app modules
os.environ["ENVIRONMENT"] = "test"
os.environ["WEATHER_API_KEY"] = "test_api_key_12345"
os.environ["CACHE_TTL_SECONDS"] = "300"
os.environ["DEBUG"] = "true"

from app.config import Settings
from app.models.weather import (
    WeatherResponse,
    WeatherSummary,
)
from app.services.cache import InMemoryCache
from app.services.factory import reset_service_factory
from app.services.storage import LocalFileStorage


@pytest.fixture(scope="session")
def event_loop():
    """Create an event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for test data."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def test_settings(temp_dir: Path) -> Settings:
    """Create test settings with temporary directories."""
    return Settings(
        environment="test",
        weather_api_key="test_api_key_12345",
        weather_api_base_url="https://api.openweathermap.org/data/2.5",
        cache_ttl_seconds=300,
        data_dir=temp_dir / "data",
        redis_host="localhost",
        redis_port=6379,
        mongodb_connection_string="mongodb://localhost:27017",
        mongodb_database_name="weather_api_test",
        rate_limit_per_minute=100,
        debug=True,
        log_level="DEBUG",
    )


@pytest.fixture
def mock_weather_response() -> dict:
    """Create a mock OpenWeatherMap API response."""
    return {
        "coord": {"lon": -0.1257, "lat": 51.5085},
        "weather": [{"id": 801, "main": "Clouds", "description": "few clouds", "icon": "02d"}],
        "base": "stations",
        "main": {
            "temp": 288.15,  # 15°C in Kelvin
            "feels_like": 287.65,
            "temp_min": 286.15,
            "temp_max": 290.15,
            "pressure": 1015,
            "humidity": 72,
        },
        "visibility": 10000,
        "wind": {"speed": 3.6, "deg": 220},
        "clouds": {"all": 20},
        "dt": 1705320000,
        "sys": {
            "type": 2,
            "id": 2075535,
            "country": "GB",
            "sunrise": 1705303500,
            "sunset": 1705333200,
        },
        "timezone": 0,
        "id": 2643743,
        "name": "London",
        "cod": 200,
    }


@pytest.fixture
def mock_forecast_response() -> dict:
    """Create a mock OpenWeatherMap forecast API response."""
    return {
        "cod": "200",
        "message": 0,
        "cnt": 8,
        "list": [
            {
                "dt": 1705320000,
                "main": {
                    "temp": 288.15,
                    "feels_like": 287.65,
                    "temp_min": 286.15,
                    "temp_max": 290.15,
                    "pressure": 1015,
                    "humidity": 72,
                },
                "weather": [
                    {"id": 801, "main": "Clouds", "description": "few clouds", "icon": "02d"}
                ],
                "clouds": {"all": 20},
                "wind": {"speed": 3.6, "deg": 220},
                "pop": 0.1,
                "sys": {"pod": "d"},
                "dt_txt": "2024-01-15 12:00:00",
            }
        ]
        * 8,
        "city": {
            "id": 2643743,
            "name": "London",
            "coord": {"lat": 51.5085, "lon": -0.1257},
            "country": "GB",
            "population": 1000000,
            "timezone": 0,
            "sunrise": 1705303500,
            "sunset": 1705333200,
        },
    }


@pytest.fixture
def weather_response_model(mock_weather_response: dict) -> WeatherResponse:
    """Create a WeatherResponse model from mock data."""
    return WeatherResponse(**mock_weather_response)


@pytest.fixture
def weather_summary_model(weather_response_model: WeatherResponse) -> WeatherSummary:
    """Create a WeatherSummary from mock data."""
    return WeatherSummary.from_api_response(weather_response_model)


@pytest_asyncio.fixture
async def cache(test_settings: Settings) -> AsyncGenerator[InMemoryCache, None]:
    """Create a test cache instance."""
    cache = InMemoryCache(ttl_seconds=test_settings.cache_ttl_seconds)
    yield cache
    await cache.clear()


@pytest_asyncio.fixture
async def storage(test_settings: Settings) -> AsyncGenerator[LocalFileStorage, None]:
    """Create a test storage instance."""
    test_settings.data_dir.mkdir(parents=True, exist_ok=True)
    storage = LocalFileStorage(data_dir=test_settings.data_dir)
    yield storage


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    """Create a test client for the FastAPI app."""
    reset_service_factory()

    from app.main import app

    with TestClient(app) as client:
        yield client

    reset_service_factory()


@pytest_asyncio.fixture
async def async_client() -> AsyncGenerator[AsyncClient, None]:
    """Create an async test client for the FastAPI app."""
    reset_service_factory()

    from app.main import app

    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client

    reset_service_factory()


def create_mock_httpx_response(
    status_code: int = 200,
    json_data: dict = None,
) -> MagicMock:
    """Create a mock httpx response."""
    response = MagicMock()
    response.status_code = status_code
    response.json.return_value = json_data or {}
    response.text = ""
    return response
