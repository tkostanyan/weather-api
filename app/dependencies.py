"""FastAPI dependency injection for services.

This module provides dependency injection functions for services,
allowing clean injection of storage, cache, and event logger
into route handlers based on the current environment.
"""

from typing import Annotated

from fastapi import Depends

from app.config import Settings, get_settings
from app.services.base import BaseCache, BaseEventLogger, BaseStorage
from app.services.factory import ServiceFactory, get_service_factory
from app.services.weather_service import WeatherService


def get_factory(settings: Annotated[Settings, Depends(get_settings)]) -> ServiceFactory:
    """Get the service factory instance."""
    return get_service_factory(settings)


def get_storage(factory: Annotated[ServiceFactory, Depends(get_factory)]) -> BaseStorage:
    """Dependency to get the storage service.

    Usage:
        @router.get("/weather")
        async def get_weather(
            storage: Annotated[BaseStorage, Depends(get_storage)]
        ):
            await storage.save(data, key)
    """
    return factory.get_storage()


def get_cache(factory: Annotated[ServiceFactory, Depends(get_factory)]) -> BaseCache:
    """Dependency to get the cache service.

    Usage:
        @router.get("/weather")
        async def get_weather(
            cache: Annotated[BaseCache, Depends(get_cache)]
        ):
            data = await cache.get(key)
    """
    return factory.get_cache()


def get_event_logger(factory: Annotated[ServiceFactory, Depends(get_factory)]) -> BaseEventLogger:
    """Dependency to get the event logger service.

    Usage:
        @router.get("/weather")
        async def get_weather(
            event_logger: Annotated[BaseEventLogger, Depends(get_event_logger)]
        ):
            await event_logger.log(...)
    """
    return factory.get_event_logger()


StorageDep = Annotated[BaseStorage, Depends(get_storage)]
CacheDep = Annotated[BaseCache, Depends(get_cache)]
EventLoggerDep = Annotated[BaseEventLogger, Depends(get_event_logger)]
SettingsDep = Annotated[Settings, Depends(get_settings)]


def get_weather_service(
    settings: SettingsDep,
    cache: CacheDep,
    storage: StorageDep,
    event_logger: EventLoggerDep,
) -> WeatherService:
    """Dependency to get the weather service.

    Usage:
        @router.get("/weather")
        async def get_weather(
            weather_service: Annotated[WeatherService, Depends(get_weather_service)]
        ):
            return await weather_service.get_weather(city, client_ip)
    """
    return WeatherService(settings, cache, storage, event_logger)


WeatherServiceDep = Annotated[WeatherService, Depends(get_weather_service)]
