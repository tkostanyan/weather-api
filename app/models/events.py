"""Event logging models.

These models represent event log entries stored in SQLite (local DynamoDB equivalent).
"""


class EventType:
    """Event type constants."""

    WEATHER_REQUEST = "weather_request"
    WEATHER_CACHED = "weather_cached"
    WEATHER_FETCHED = "weather_fetched"
    FILE_SAVED = "file_saved"
    ERROR = "error"
    FORECAST_REQUEST = "forecast_request"
    MULTI_CITY_REQUEST = "multi_city_request"
