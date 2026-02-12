"""Weather data models using Pydantic.

These models represent weather data from OpenWeatherMap API and provide
clean, typed interfaces for the application.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class WeatherCondition(BaseModel):
    """Weather condition details."""

    id: int = Field(..., description="Weather condition ID")
    main: str = Field(..., description="Group of weather parameters (Rain, Snow, etc.)")
    description: str = Field(..., description="Weather condition description")
    icon: str = Field(..., description="Weather icon ID")


class MainWeatherData(BaseModel):
    """Main weather measurements."""

    temp: float = Field(..., description="Temperature in Kelvin (converted to Celsius)")
    feels_like: float = Field(..., description="Feels like temperature")
    temp_min: float = Field(..., description="Minimum temperature")
    temp_max: float = Field(..., description="Maximum temperature")
    pressure: int = Field(..., description="Atmospheric pressure in hPa")
    humidity: int = Field(..., description="Humidity percentage")
    sea_level: int | None = Field(None, description="Sea level pressure")
    grnd_level: int | None = Field(None, description="Ground level pressure")


class WindData(BaseModel):
    """Wind measurements."""

    speed: float = Field(..., description="Wind speed in m/s")
    deg: int = Field(..., description="Wind direction in degrees")
    gust: float | None = Field(None, description="Wind gust speed")


class CloudData(BaseModel):
    """Cloud coverage data."""

    all: int = Field(..., description="Cloudiness percentage")


class SysData(BaseModel):
    """System/country data."""

    type: int | None = Field(None, description="Internal parameter")
    id: int | None = Field(None, description="Internal parameter")
    country: str = Field(..., description="Country code")
    sunrise: int = Field(..., description="Sunrise time (Unix timestamp)")
    sunset: int = Field(..., description="Sunset time (Unix timestamp)")


class Coordinates(BaseModel):
    """Geographic coordinates."""

    lon: float = Field(..., description="Longitude")
    lat: float = Field(..., description="Latitude")


class WeatherResponse(BaseModel):
    """Complete weather response from OpenWeatherMap API."""

    coord: Coordinates = Field(..., description="Geographic coordinates")
    weather: list[WeatherCondition] = Field(..., description="Weather conditions")
    base: str = Field(..., description="Internal parameter")
    main: MainWeatherData = Field(..., description="Main weather data")
    visibility: int = Field(..., description="Visibility in meters")
    wind: WindData = Field(..., description="Wind data")
    clouds: CloudData = Field(..., description="Cloud data")
    dt: int = Field(..., description="Data calculation time (Unix timestamp)")
    sys: SysData = Field(..., description="System data")
    timezone: int = Field(..., description="Timezone offset in seconds")
    id: int = Field(..., description="City ID")
    name: str = Field(..., description="City name")
    cod: int = Field(..., description="Response code")


class WeatherSummary(BaseModel):
    """Simplified weather response for API consumers.

    This provides a cleaner, more user-friendly response format.
    """

    city: str = Field(..., description="City name")
    country: str = Field(..., description="Country code")
    coordinates: Coordinates = Field(..., description="Geographic coordinates")
    temperature: float = Field(..., description="Current temperature in Celsius")
    feels_like: float = Field(..., description="Feels like temperature in Celsius")
    temp_min: float = Field(..., description="Minimum temperature in Celsius")
    temp_max: float = Field(..., description="Maximum temperature in Celsius")
    humidity: int = Field(..., description="Humidity percentage")
    pressure: int = Field(..., description="Atmospheric pressure in hPa")
    wind_speed: float = Field(..., description="Wind speed in m/s")
    wind_direction: int = Field(..., description="Wind direction in degrees")
    cloudiness: int = Field(..., description="Cloudiness percentage")
    visibility: int = Field(..., description="Visibility in meters")
    weather_condition: str = Field(..., description="Main weather condition")
    weather_description: str = Field(..., description="Detailed weather description")
    weather_icon: str = Field(..., description="Weather icon URL")
    sunrise: datetime = Field(..., description="Sunrise time")
    sunset: datetime = Field(..., description="Sunset time")
    timestamp: datetime = Field(..., description="Data timestamp")
    cached: bool = Field(default=False, description="Whether data was served from cache")

    @classmethod
    def from_api_response(cls, response: WeatherResponse, cached: bool = False) -> "WeatherSummary":
        """Create a WeatherSummary from raw API response.

        Args:
            response: Raw weather API response
            cached: Whether this data came from cache

        Returns:
            WeatherSummary: Formatted weather summary
        """

        # Convert Kelvin to Celsius
        def kelvin_to_celsius(k: float) -> float:
            return round(k - 273.15, 1)

        weather_condition = response.weather[0] if response.weather else None

        return cls(
            city=response.name,
            country=response.sys.country,
            coordinates=response.coord,
            temperature=kelvin_to_celsius(response.main.temp),
            feels_like=kelvin_to_celsius(response.main.feels_like),
            temp_min=kelvin_to_celsius(response.main.temp_min),
            temp_max=kelvin_to_celsius(response.main.temp_max),
            humidity=response.main.humidity,
            pressure=response.main.pressure,
            wind_speed=response.wind.speed,
            wind_direction=response.wind.deg,
            cloudiness=response.clouds.all,
            visibility=response.visibility,
            weather_condition=weather_condition.main if weather_condition else "Unknown",
            weather_description=weather_condition.description if weather_condition else "Unknown",
            weather_icon=f"https://openweathermap.org/img/wn/{weather_condition.icon}@2x.png"
            if weather_condition
            else "",
            sunrise=datetime.fromtimestamp(response.sys.sunrise),
            sunset=datetime.fromtimestamp(response.sys.sunset),
            timestamp=datetime.fromtimestamp(response.dt),
            cached=cached,
        )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "city": "London",
                "country": "GB",
                "coordinates": {"lon": -0.1257, "lat": 51.5085},
                "temperature": 15.2,
                "feels_like": 14.8,
                "temp_min": 13.5,
                "temp_max": 16.8,
                "humidity": 72,
                "pressure": 1015,
                "wind_speed": 3.6,
                "wind_direction": 220,
                "cloudiness": 40,
                "visibility": 10000,
                "weather_condition": "Clouds",
                "weather_description": "scattered clouds",
                "weather_icon": "https://openweathermap.org/img/wn/03d@2x.png",
                "sunrise": "2024-01-15T07:45:00",
                "sunset": "2024-01-15T16:30:00",
                "timestamp": "2024-01-15T12:00:00",
                "cached": False,
            }
        }
    )


class ForecastItem(BaseModel):
    """Single forecast item for a specific time."""

    timestamp: datetime = Field(..., description="Forecast timestamp")
    temperature: float = Field(..., description="Temperature in Celsius")
    feels_like: float = Field(..., description="Feels like temperature in Celsius")
    temp_min: float = Field(..., description="Minimum temperature in Celsius")
    temp_max: float = Field(..., description="Maximum temperature in Celsius")
    humidity: int = Field(..., description="Humidity percentage")
    pressure: int = Field(..., description="Atmospheric pressure in hPa")
    weather_condition: str = Field(..., description="Main weather condition")
    weather_description: str = Field(..., description="Detailed weather description")
    weather_icon: str = Field(..., description="Weather icon URL")
    wind_speed: float = Field(..., description="Wind speed in m/s")
    cloudiness: int = Field(..., description="Cloudiness percentage")
    precipitation_probability: float = Field(default=0, description="Probability of precipitation")


class ForecastResponse(BaseModel):
    """Multi-day weather forecast response."""

    city: str = Field(..., description="City name")
    country: str = Field(..., description="Country code")
    coordinates: Coordinates = Field(..., description="Geographic coordinates")
    forecasts: list[ForecastItem] = Field(..., description="List of forecast items")
    cached: bool = Field(default=False, description="Whether data was served from cache")


class MultiCityWeatherResponse(BaseModel):
    """Response for multiple cities weather request."""

    results: list[WeatherSummary] = Field(..., description="Weather data for each city")
    errors: dict[str, str] = Field(
        default_factory=dict, description="Errors for cities that failed"
    )
    total_cities: int = Field(..., description="Total cities requested")
    successful: int = Field(..., description="Number of successful responses")


class ErrorResponse(BaseModel):
    """Standard error response."""

    error: str = Field(..., description="Error type")
    message: str = Field(..., description="Human-readable error message")
    detail: str | None = Field(None, description="Additional error details")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "error": "CityNotFound",
                "message": "City 'InvalidCity' not found",
                "detail": "Please check the city name and try again",
            }
        }
    )
