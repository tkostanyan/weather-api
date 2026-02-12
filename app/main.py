"""FastAPI Weather API Application.

A robust weather API service that fetches data from OpenWeatherMap,
with configurable backends for caching, storage, and event logging.

This application supports:
- LOCAL environment: MongoDB, Local File Storage, Redis
- PROD environment: DynamoDB, S3, ElastiCache

Architecture:
- Abstract base classes define service interfaces
- Factory pattern creates appropriate implementations based on ENVIRONMENT
- Easy to swap between local development and production AWS
"""

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app import __version__
from app.config import get_settings
from app.rate_limiter import limiter
from app.routers import weather
from app.services.factory import get_service_factory, reset_service_factory

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan handler for startup/shutdown events."""
    # Startup
    logger.info("Starting Weather API service...")

    settings = get_settings()
    settings.ensure_directories()

    # Initialize services using factory
    factory = get_service_factory(settings)
    await factory.initialize()

    logger.info(f"Weather API v{__version__} started successfully")
    logger.info(f"Environment: {settings.environment}")
    logger.info(f"API Key configured: {settings.is_api_key_configured}")
    logger.info(f"Cache TTL: {settings.cache_ttl_seconds} seconds")

    if settings.is_local:
        logger.info("Using LOCAL services: MongoDB, LocalFileStorage, Redis")
        logger.info(f"Data directory: {settings.data_dir}")
    else:
        logger.info("Using PROD services: DynamoDB, S3, ElastiCache")

    yield

    # Shutdown
    logger.info("Shutting down Weather API service...")
    await factory.close()
    reset_service_factory()


# Create FastAPI application
app = FastAPI(
    title="Weather API",
    description="""
    ## Weather API Service

    A robust weather API that fetches data from OpenWeatherMap with:

    - **Caching**: 5-minute TTL cache (Redis/ElastiCache)
    - **Storage**: Persistent storage (Local Files/S3)
    - **Logging**: Event tracking (MongoDB/DynamoDB)
    - **Rate Limiting**: Configurable per-client rate limits

    ### Environments

    - **LOCAL**: Uses MongoDB, Local File Storage, Redis
    - **PROD**: Uses DynamoDB, S3, ElastiCache

    ### Features

    - Get current weather for any city
    - Get multi-day weather forecast
    - Fetch weather for multiple cities at once
    - Automatic data persistence
    - Comprehensive error handling

    ### Authentication

    This API uses OpenWeatherMap as the data source. You need to configure
    a valid API key in the environment variables.

    ### Rate Limits

    - 100 requests per minute per client IP (configurable)
    """,
    version=__version__,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_tags=[
        {
            "name": "Weather",
            "description": "Weather data operations - current weather, forecasts, and multi-city queries",
        },
        {
            "name": "Health",
            "description": "Health check and service status endpoints",
        },
    ],
)

# Add rate limiter to app state
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS middleware for cross-origin requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle uncaught exceptions globally."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "InternalServerError",
            "message": "An unexpected error occurred",
            "detail": str(exc) if get_settings().debug else None,
        },
    )


# Health check endpoints
@app.get(
    "/",
    tags=["Health"],
    summary="Root endpoint",
    description="Returns basic API information and links to documentation.",
)
async def root():
    """Root endpoint with API information."""
    settings = get_settings()
    return {
        "service": "Weather API",
        "version": __version__,
        "environment": settings.environment,
        "docs": "/docs",
        "redoc": "/redoc",
        "health": "/health",
    }


@app.get(
    "/health",
    tags=["Health"],
    summary="Health check",
    description="Returns the health status of the service and its components.",
)
async def health_check():
    """Health check endpoint for monitoring."""
    settings = get_settings()

    components = {
        "environment": settings.environment,
        "api_key_configured": settings.is_api_key_configured,
        "cache_ttl_seconds": settings.cache_ttl_seconds,
    }

    if settings.is_local:
        components["storage"] = "LocalFileStorage"
        components["database"] = "MongoDB"
        components["cache"] = "Redis"
        components["data_directory"] = str(settings.data_dir)
    else:
        components["storage"] = "S3"
        components["database"] = "DynamoDB"
        components["cache"] = "ElastiCache"
        components["s3_bucket"] = settings.s3_bucket_name
        components["dynamodb_table"] = settings.dynamodb_table_name

    return {
        "status": "healthy",
        "version": __version__,
        "components": components,
    }


# Include routers
app.include_router(weather.router)

# (Rate limiting is enforced via `@limiter.limit(...)` decorators on endpoints.)


if __name__ == "__main__":
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
        log_level=settings.log_level.lower(),
    )
