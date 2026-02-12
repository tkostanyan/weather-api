"""Integration tests for the Weather API."""

import os
from unittest.mock import AsyncMock, MagicMock

from fastapi import status
from fastapi.testclient import TestClient

# Set test environment
os.environ["ENVIRONMENT"] = "test"


class TestHealthEndpoints:
    """Tests for health check endpoints."""

    def test_root_endpoint(self, client: TestClient):
        """Test the root endpoint returns API info."""
        response = client.get("/")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "service" in data
        assert data["service"] == "Weather API"
        assert "version" in data
        assert "environment" in data

    def test_health_endpoint(self, client: TestClient):
        """Test the health check endpoint."""
        response = client.get("/health")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "healthy"
        assert "version" in data
        assert "components" in data


class TestWeatherEndpoint:
    """Tests for the /weather endpoint."""

    def test_get_weather_success(self, client: TestClient, mock_weather_response: dict):
        """Test successful weather retrieval."""
        from app.dependencies import get_weather_service
        from app.main import app
        from app.models.weather import WeatherResponse, WeatherSummary

        response_model = WeatherResponse(**mock_weather_response)
        summary = WeatherSummary.from_api_response(response_model)

        mock_service = MagicMock()
        mock_service.get_weather = AsyncMock(return_value=(summary, 100.0))

        # Override the dependency
        app.dependency_overrides[get_weather_service] = lambda: mock_service

        try:
            response = client.get("/weather?city=London")

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["city"] == "London"
            assert data["country"] == "GB"
            assert "temperature" in data
            assert "humidity" in data
        finally:
            # Clean up override
            app.dependency_overrides.clear()

    def test_get_weather_cached(self, client: TestClient, mock_weather_response: dict):
        """Test that second request returns cached data."""
        from app.dependencies import get_weather_service
        from app.main import app
        from app.models.weather import WeatherResponse, WeatherSummary

        response_model = WeatherResponse(**mock_weather_response)
        summary1 = WeatherSummary.from_api_response(response_model)
        summary1.cached = False

        summary2 = WeatherSummary.from_api_response(response_model)
        summary2.cached = True

        mock_service = MagicMock()
        # First call not cached, second call cached
        mock_service.get_weather = AsyncMock(side_effect=[(summary1, 100.0), (summary2, 5.0)])

        app.dependency_overrides[get_weather_service] = lambda: mock_service

        try:
            # First request
            response1 = client.get("/weather?city=London")
            assert response1.status_code == status.HTTP_200_OK
            assert response1.json()["cached"] is False

            # Second request should be cached
            response2 = client.get("/weather?city=London")
            assert response2.status_code == status.HTTP_200_OK
            assert response2.json()["cached"] is True
        finally:
            app.dependency_overrides.clear()

    def test_get_weather_city_not_found(self, client: TestClient):
        """Test 404 response for unknown city."""
        from app.dependencies import get_weather_service
        from app.exceptions import CityNotFoundError
        from app.main import app

        mock_service = MagicMock()
        mock_service.get_weather = AsyncMock(side_effect=CityNotFoundError("InvalidCity"))

        app.dependency_overrides[get_weather_service] = lambda: mock_service

        try:
            response = client.get("/weather?city=InvalidCity")

            assert response.status_code == status.HTTP_404_NOT_FOUND
            data = response.json()
            assert "detail" in data
            assert data["detail"]["error"] == "CityNotFound"
        finally:
            app.dependency_overrides.clear()

    def test_get_weather_missing_city(self, client: TestClient):
        """Test 422 response when city parameter is missing."""
        response = client.get("/weather")

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    def test_get_weather_empty_city(self, client: TestClient):
        """Test validation for empty city parameter."""
        response = client.get("/weather?city=")

        # FastAPI will return 422 for validation error
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    def test_get_weather_api_key_error(self, client: TestClient):
        """Test 500 response for API key error."""
        from app.dependencies import get_weather_service
        from app.exceptions import APIKeyError
        from app.main import app

        mock_service = MagicMock()
        mock_service.get_weather = AsyncMock(side_effect=APIKeyError())

        app.dependency_overrides[get_weather_service] = lambda: mock_service

        try:
            response = client.get("/weather?city=London")

            assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
            data = response.json()
            assert data["detail"]["error"] == "ConfigurationError"
        finally:
            app.dependency_overrides.clear()

    def test_get_weather_rate_limit_error(self, client: TestClient):
        """Test 429 response for rate limit error."""
        from app.dependencies import get_weather_service
        from app.exceptions import RateLimitError
        from app.main import app

        mock_service = MagicMock()
        mock_service.get_weather = AsyncMock(side_effect=RateLimitError())

        app.dependency_overrides[get_weather_service] = lambda: mock_service

        try:
            response = client.get("/weather?city=London")

            assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS
        finally:
            app.dependency_overrides.clear()


class TestForecastEndpoint:
    """Tests for the /weather/forecast endpoint."""

    def test_get_forecast_success(self, client: TestClient, mock_forecast_response: dict):
        """Test successful forecast retrieval."""
        from app.dependencies import get_weather_service
        from app.main import app
        from app.models.weather import Coordinates, ForecastResponse

        forecast = ForecastResponse(
            city="London",
            country="GB",
            coordinates=Coordinates(lon=-0.1257, lat=51.5085),
            forecasts=[],
            cached=False,
        )

        mock_service = MagicMock()
        mock_service.get_forecast = AsyncMock(return_value=forecast)

        app.dependency_overrides[get_weather_service] = lambda: mock_service

        try:
            response = client.get("/weather/forecast?city=London&days=3")

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["city"] == "London"
            assert "forecasts" in data
        finally:
            app.dependency_overrides.clear()

    def test_get_forecast_invalid_days(self, client: TestClient):
        """Test validation for invalid days parameter."""
        response = client.get("/weather/forecast?city=London&days=10")

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


class TestMultiCityEndpoint:
    """Tests for the /weather/multi endpoint."""

    def test_get_multi_city_success(self, client: TestClient, mock_weather_response: dict):
        """Test successful multi-city weather retrieval."""
        from app.dependencies import get_weather_service
        from app.main import app
        from app.models.weather import (
            MultiCityWeatherResponse,
            WeatherResponse,
            WeatherSummary,
        )

        response_model = WeatherResponse(**mock_weather_response)
        summary = WeatherSummary.from_api_response(response_model)

        multi_response = MultiCityWeatherResponse(
            results=[summary, summary],
            errors={},
            total_cities=2,
            successful=2,
        )

        mock_service = MagicMock()
        mock_service.get_multi_city_weather = AsyncMock(return_value=multi_response)

        app.dependency_overrides[get_weather_service] = lambda: mock_service

        try:
            response = client.get("/weather/multi?cities=London,Paris")

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["total_cities"] == 2
            assert data["successful"] >= 1
            assert "results" in data
        finally:
            app.dependency_overrides.clear()

    def test_get_multi_city_empty(self, client: TestClient):
        """Test error for empty cities parameter."""
        response = client.get("/weather/multi?cities=")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        data = response.json()
        assert data["detail"]["error"] == "InvalidInput"

    def test_get_multi_city_too_many(self, client: TestClient):
        """Test error for too many cities."""
        cities = ",".join([f"City{i}" for i in range(15)])
        response = client.get(f"/weather/multi?cities={cities}")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        data = response.json()
        assert data["detail"]["error"] == "TooManyCities"


class TestAPIDocumentation:
    """Tests for API documentation endpoints."""

    def test_openapi_schema(self, client: TestClient):
        """Test that OpenAPI schema is accessible."""
        response = client.get("/openapi.json")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "openapi" in data
        assert "paths" in data
        assert "/weather" in data["paths"]

    def test_docs_endpoint(self, client: TestClient):
        """Test that Swagger docs are accessible."""
        response = client.get("/docs")

        assert response.status_code == status.HTTP_200_OK
        assert "text/html" in response.headers["content-type"]

    def test_redoc_endpoint(self, client: TestClient):
        """Test that ReDoc is accessible."""
        response = client.get("/redoc")

        assert response.status_code == status.HTTP_200_OK
        assert "text/html" in response.headers["content-type"]
