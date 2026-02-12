"""Application configuration using Pydantic Settings.

This module provides centralized configuration management with support for
environment variables and .env files. Configuration supports both local
development and cloud deployment (AWS).

Environment Types:
- local: MongoDB, Local File Storage, Redis
- prod: DynamoDB, S3, ElastiCache
- test: In-memory implementations
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables.

    The ENVIRONMENT variable controls which service implementations are used:
    - local: Uses MongoDB, local file storage, Redis
    - prod: Uses DynamoDB, S3, ElastiCache
    - test: Uses in-memory implementations
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Environment Setting
    environment: Literal["local", "prod", "test"] = Field(
        default="local", description="Environment type: local, prod, or test"
    )

    # Weather API Configuration
    weather_api_key: str = Field(default="YOUR_API_KEY", description="OpenWeatherMap API key")
    weather_api_base_url: str = Field(
        default="https://api.openweathermap.org/data/2.5", description="Base URL for weather API"
    )

    # Cache Configuration
    cache_ttl_seconds: int = Field(
        default=300, ge=0, le=3600, description="Cache TTL in seconds (5 minutes default)"
    )

    # Redis (Local)
    redis_host: str = Field(default="localhost", description="Redis host")
    redis_port: int = Field(default=6379, description="Redis port")
    redis_password: str | None = Field(default=None, description="Redis password")

    # ElastiCache (Production)
    elasticache_host: str | None = Field(default=None, description="ElastiCache endpoint")
    elasticache_port: int = Field(default=6379, description="ElastiCache port")
    elasticache_password: str | None = Field(default=None, description="ElastiCache auth token")

    # Local File Storage
    data_dir: Path = Field(default=Path("./data"), description="Directory for local file storage")

    # S3 (Production)
    s3_bucket_name: str | None = Field(default=None, description="S3 bucket name")

    # Database Configuration
    # MongoDB (Local)
    mongodb_connection_string: str = Field(
        default="mongodb://localhost:27017", description="MongoDB connection string"
    )
    mongodb_database_name: str = Field(default="weather_api", description="MongoDB database name")

    # DynamoDB (Production)
    dynamodb_table_name: str = Field(default="weather-events", description="DynamoDB table name")

    # AWS Configuration (Production)
    aws_region: str = Field(default="us-east-1", description="AWS region")
    aws_access_key_id: str | None = Field(default=None, description="AWS access key")
    aws_secret_access_key: str | None = Field(default=None, description="AWS secret key")
    aws_endpoint_url: str | None = Field(
        default=None, description="AWS endpoint URL (for LocalStack testing)"
    )

    # Application Settings
    rate_limit_per_minute: int = Field(
        default=100, ge=1, le=1000, description="Maximum requests per minute per client IP"
    )
    debug: bool = Field(default=False, description="Enable debug mode")
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO", description="Logging level"
    )

    @field_validator("data_dir", mode="before")
    @classmethod
    def parse_path(cls, v: str | Path) -> Path:
        """Convert string paths to Path objects."""
        return Path(v) if isinstance(v, str) else v

    @property
    def is_api_key_configured(self) -> bool:
        """Check if a real API key is configured."""
        return (
            self.weather_api_key
            and self.weather_api_key != "your_api_key_here"
            and len(self.weather_api_key) > 10
        )

    @property
    def is_local(self) -> bool:
        """Check if running in local environment."""
        return self.environment == "local"

    @property
    def is_prod(self) -> bool:
        """Check if running in production environment."""
        return self.environment == "prod"

    def ensure_directories(self) -> None:
        """Ensure required directories exist (for local environment)."""
        if self.is_local:
            self.data_dir.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    """Get cached application settings.

    Uses LRU cache to avoid reloading settings on every request.

    Returns:
        Settings: Application settings instance
    """
    settings = Settings()
    settings.ensure_directories()
    return settings
