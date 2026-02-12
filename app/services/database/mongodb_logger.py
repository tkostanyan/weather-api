"""MongoDB event logger implementation.

This module provides MongoDB-based event logging for local development.
Uses motor for async MongoDB operations.
"""

import json
import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from app.services.base import BaseEventLogger

logger = logging.getLogger(__name__)


class MongoDBEventLogger(BaseEventLogger):
    """MongoDB event logger implementation for local development.

    Example:
        event_logger = MongoDBEventLogger(
            connection_string="mongodb://localhost:27017",
            database_name="weather_api"
        )
        await event_logger.initialize()
        event_id = await event_logger.log("weather_request", city="London")
    """

    def __init__(
        self,
        connection_string: str = "mongodb://localhost:27017",
        database_name: str = "weather_api",
        collection_name: str = "events",
    ):
        """Initialize MongoDB event logger.

        Args:
            connection_string: MongoDB connection string
            database_name: Database name
            collection_name: Collection name for events
        """
        self._connection_string = connection_string
        self._database_name = database_name
        self._collection_name = collection_name
        self._client = None
        self._db = None
        self._collection = None
        self._initialized = False

        logger.info(f"MongoDBEventLogger initialized with database: {database_name}")

    async def _get_collection(self):
        """Get or create the MongoDB collection."""
        if self._collection is None:
            try:
                from motor.motor_asyncio import AsyncIOMotorClient
            except ImportError:
                raise ImportError(
                    "motor is required for MongoDB. Install it with: pip install motor"
                )

            self._client = AsyncIOMotorClient(self._connection_string)
            self._db = self._client[self._database_name]
            self._collection = self._db[self._collection_name]

        return self._collection

    async def close(self):
        """Close the MongoDB connection."""
        if self._client:
            self._client.close()
            self._client = None
            self._db = None
            self._collection = None

    async def initialize(self) -> None:
        """Initialize indexes for the events collection."""
        if self._initialized:
            return

        collection = await self._get_collection()

        # Create indexes for common queries
        await collection.create_index("timestamp")
        await collection.create_index("event_type")
        await collection.create_index("city")
        await collection.create_index([("timestamp", -1)])

        self._initialized = True
        logger.info("MongoDBEventLogger indexes created")

    async def log(
        self,
        event_type: str,
        city: str | None = None,
        file_path: str | None = None,
        details: str | None = None,
        client_ip: str | None = None,
    ) -> str:
        """Log an event to MongoDB."""
        collection = await self._get_collection()

        document = {
            "timestamp": datetime.now(UTC),
            "event_type": event_type,
            "city": city,
            "file_path": file_path,
            "details": details,
            "client_ip": client_ip,
        }

        result = await collection.insert_one(document)
        event_id = str(result.inserted_id)

        logger.debug(f"Logged event to MongoDB: type={event_type}, city={city}, id={event_id}")
        return event_id

    async def get_events(
        self,
        limit: int = 100,
        event_type: str | None = None,
        city: str | None = None,
    ) -> list[dict[str, Any]]:
        """Get logged events from MongoDB."""
        collection = await self._get_collection()

        query = {}
        if event_type:
            query["event_type"] = event_type
        if city:
            query["city"] = city

        cursor = collection.find(query).sort("timestamp", -1).limit(limit)

        events = []
        async for doc in cursor:
            doc["id"] = str(doc.pop("_id"))
            events.append(doc)

        return events

    async def get_stats(self) -> dict[str, Any]:
        """Get event statistics from MongoDB."""
        collection = await self._get_collection()

        # Total events
        total = await collection.count_documents({})

        # Events by type
        pipeline = [{"$group": {"_id": "$event_type", "count": {"$sum": 1}}}]
        by_type = {}
        async for doc in collection.aggregate(pipeline):
            by_type[doc["_id"]] = doc["count"]

        # Unique cities
        unique_cities = len(await collection.distinct("city"))

        # Events in last hour
        hour_ago = datetime.now(UTC) - timedelta(hours=1)
        last_hour = await collection.count_documents({"timestamp": {"$gte": hour_ago}})

        return {
            "total_events": total,
            "events_by_type": by_type,
            "unique_cities": unique_cities,
            "events_last_hour": last_hour,
        }

    async def log_weather_request(
        self,
        city: str,
        cached: bool = False,
        file_path: str | None = None,
        client_ip: str | None = None,
        response_time_ms: float | None = None,
    ) -> str:
        """Convenience method to log a weather request."""
        event_type = "weather_cached" if cached else "weather_fetched"
        details = json.dumps(
            {
                "cached": cached,
                "response_time_ms": response_time_ms,
            }
        )

        return await self.log(
            event_type=event_type,
            city=city,
            file_path=file_path,
            details=details,
            client_ip=client_ip,
        )

    async def log_error(
        self,
        error_type: str,
        message: str,
        city: str | None = None,
        client_ip: str | None = None,
    ) -> str:
        """Log an error event."""
        details = json.dumps(
            {
                "error_type": error_type,
                "message": message,
            }
        )

        return await self.log(
            event_type="error",
            city=city,
            details=details,
            client_ip=client_ip,
        )
