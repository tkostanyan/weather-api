"""AWS DynamoDB event logger implementation.

This module provides DynamoDB-based event logging for production deployment.
Uses aioboto3 for async DynamoDB operations.
"""

import json
import logging
import uuid
from datetime import datetime, timedelta
from typing import Any

from app.services.base import BaseEventLogger

logger = logging.getLogger(__name__)


class DynamoDBEventLogger(BaseEventLogger):
    """AWS DynamoDB event logger implementation for production.

    Example:
        event_logger = DynamoDBEventLogger(
            table_name="weather-events",
            region="us-east-1"
        )
        await event_logger.initialize()
        event_id = await event_logger.log("weather_request", city="London")
    """

    def __init__(
        self,
        table_name: str = "weather-events",
        region: str = "us-east-1",
        aws_access_key_id: str | None = None,
        aws_secret_access_key: str | None = None,
        endpoint_url: str | None = None,  # For LocalStack testing
    ):
        """Initialize DynamoDB event logger.

        Args:
            table_name: DynamoDB table name
            region: AWS region
            aws_access_key_id: AWS access key (optional)
            aws_secret_access_key: AWS secret key (optional)
            endpoint_url: Custom endpoint URL (for LocalStack)
        """
        self._table_name = table_name
        self._region = region
        self._aws_access_key_id = aws_access_key_id
        self._aws_secret_access_key = aws_secret_access_key
        self._endpoint_url = endpoint_url
        self._client = None
        self._table = None
        self._initialized = False

        logger.info(f"DynamoDBEventLogger initialized with table: {table_name}")

    async def _get_table(self):
        """Get or create the DynamoDB table resource."""
        if self._table is None:
            try:
                import aioboto3
            except ImportError:
                raise ImportError(
                    "aioboto3 is required for DynamoDB. Install it with: pip install aioboto3"
                )

            session = aioboto3.Session()

            resource_kwargs = {
                "region_name": self._region,
            }

            if self._aws_access_key_id:
                resource_kwargs["aws_access_key_id"] = self._aws_access_key_id
            if self._aws_secret_access_key:
                resource_kwargs["aws_secret_access_key"] = self._aws_secret_access_key
            if self._endpoint_url:
                resource_kwargs["endpoint_url"] = self._endpoint_url

            self._resource = await session.resource("dynamodb", **resource_kwargs).__aenter__()
            self._table = await self._resource.Table(self._table_name)

        return self._table

    async def close(self):
        """Close the DynamoDB resource."""
        if self._resource:
            await self._resource.__aexit__(None, None, None)
            self._resource = None
            self._table = None

    async def initialize(self) -> None:
        """Initialize DynamoDB table (assumes table exists in production)."""
        if self._initialized:
            return

        # In production, table should be created via CloudFormation/Terraform
        # This just validates connection
        table = await self._get_table()

        try:
            await table.load()
            logger.info(f"DynamoDB table '{self._table_name}' connected")
        except Exception as e:
            logger.warning(f"Could not load DynamoDB table: {e}")

        self._initialized = True

    async def log(
        self,
        event_type: str,
        city: str | None = None,
        file_path: str | None = None,
        details: str | None = None,
        client_ip: str | None = None,
    ) -> str:
        """Log an event to DynamoDB."""
        table = await self._get_table()

        event_id = str(uuid.uuid4())
        timestamp = datetime.utcnow().isoformat()

        item = {
            "event_id": event_id,
            "timestamp": timestamp,
            "event_type": event_type,
        }

        # Only add optional fields if they have values
        if city:
            item["city"] = city
        if file_path:
            item["file_path"] = file_path
        if details:
            item["details"] = details
        if client_ip:
            item["client_ip"] = client_ip

        await table.put_item(Item=item)

        logger.debug(f"Logged event to DynamoDB: type={event_type}, city={city}, id={event_id}")
        return event_id

    async def get_events(
        self,
        limit: int = 100,
        event_type: str | None = None,
        city: str | None = None,
    ) -> list[dict[str, Any]]:
        """Get logged events from DynamoDB.

        Note: This performs a scan which is expensive. In production,
        use GSIs for efficient querying by event_type or city.
        """
        table = await self._get_table()

        # Build filter expression
        filter_expression = None
        expression_values = {}

        from boto3.dynamodb.conditions import Attr

        if event_type:
            filter_expression = Attr("event_type").eq(event_type)
            expression_values[":event_type"] = event_type

        if city:
            city_filter = Attr("city").eq(city)
            if filter_expression:
                filter_expression = filter_expression & city_filter
            else:
                filter_expression = city_filter

        scan_kwargs = {"Limit": limit}
        if filter_expression:
            scan_kwargs["FilterExpression"] = filter_expression

        response = await table.scan(**scan_kwargs)

        events = response.get("Items", [])

        # Sort by timestamp descending
        events.sort(key=lambda x: x.get("timestamp", ""), reverse=True)

        return events[:limit]

    async def get_stats(self) -> dict[str, Any]:
        """Get event statistics from DynamoDB.

        Note: This performs a full table scan which is expensive.
        In production, use DynamoDB Streams + Lambda for real-time stats.
        """
        table = await self._get_table()

        # Scan all items (expensive - use sparingly)
        response = await table.scan()
        items = response.get("Items", [])

        # Calculate stats
        total = len(items)

        by_type = {}
        cities = set()
        hour_ago = (datetime.utcnow() - timedelta(hours=1)).isoformat()
        last_hour = 0

        for item in items:
            event_type = item.get("event_type", "unknown")
            by_type[event_type] = by_type.get(event_type, 0) + 1

            if item.get("city"):
                cities.add(item["city"])

            if item.get("timestamp", "") >= hour_ago:
                last_hour += 1

        return {
            "total_events": total,
            "events_by_type": by_type,
            "unique_cities": len(cities),
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
